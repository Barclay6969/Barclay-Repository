# -*- coding: UTF-8 -*-

import concurrent.futures
import json
import re
from difflib import SequenceMatcher

from resources.lib.requestHandler import cRequestHandler
from resources.lib.utils import isBlockedHosterFast as isBlockedHoster
from resources.lib.control import getSetting, quote_plus
from scrapers.modules import cleantitle
from scrapers.modules.meinecloud_shared import get_movie_links
from resources.lib.domain_manager import resolve_domain

SITE_IDENTIFIER = 'kinoking'
SITE_DOMAIN = 'kinoking.cc'
SITE_NAME = SITE_IDENTIFIER.upper()


class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)
        self.language = ['de']
        self.domain = resolve_domain(SITE_IDENTIFIER, SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/index.php?search=%s'
        self.sources = []

    @staticmethod
    def _attrs(tag):
        attrs = {}
        for key, quote, value in re.findall(r'([\w:-]+)\s*=\s*([\'\"])(.*?)\2', tag or '', re.I | re.S):
            attrs[key.lower()] = value
        return attrs

    @staticmethod
    def _title_match(candidate, clean_titles):
        candidate = re.sub(r'\s*\(\d{4}\)\s*$', '', str(candidate or '')).strip()
        current = cleantitle.get(candidate)
        if not current:
            return False
        if current in clean_titles:
            return True
        for wanted in clean_titles:
            if not wanted or min(len(current), len(wanted)) < 5:
                continue
            if SequenceMatcher(None, current, wanted).ratio() >= 0.92:
                return True
        return False

    def _search_results(self, html, want_series):
        results = []

        # KinoKing V2 (09/2026): cards expose id/type/title in data attributes.
        for card in re.findall(r'<[^>]+\bfav-data-source\b[^>]*>', html or '', re.I | re.S):
            attrs = self._attrs(card)
            media_id = attrs.get('data-id', '')
            media_type = attrs.get('data-type', '').lower()
            title = attrs.get('data-title', '')
            if not media_id or not title:
                continue
            if want_series:
                if media_type and media_type != 'series':
                    continue
            else:
                if media_type and media_type != 'movie':
                    continue
            results.append((media_id, title))

        if results:
            return results

        # Compatibility with older markup.
        if want_series:
            for m in re.finditer(r'onclick=["\']playContent\([\'\"]?(\d+)', html or '', re.I):
                chunk = html[m.end():m.end() + 500]
                title_m = re.search(r'(?:alt|title)=["\']([^"\']+)', chunk, re.I)
                if title_m:
                    results.append((m.group(1), title_m.group(1)))
        else:
            for m in re.finditer(r'onclick=["\']playMovie\((\d+)\)', html or '', re.I):
                chunk = html[m.end():m.end() + 500]
                title_m = re.search(r'(?:alt|title)=["\']([^"\']+)', chunk, re.I)
                if title_m:
                    results.append((m.group(1), title_m.group(1)))
        return results

    def _series_candidates(self, titles):
        clean_titles = set(cleantitle.get(i) for i in titles or [] if i)
        result = []
        seen = set()

        for raw_title in titles or []:
            try:
                req = cRequestHandler(self.search_link % quote_plus(raw_title), caching=True)
                req.cacheTime = 60 * 60
                html = req.request()
                for media_id, title in self._search_results(html, True):
                    if media_id in seen:
                        continue
                    if not self._title_match(title, clean_titles):
                        continue
                    seen.add(media_id)
                    result.append(media_id)
                    if len(result) >= 2:
                        return result
            except Exception:
                continue
        return result

    def _series_links(self, media_id, season, episode):
        page_url = self.base_link + '/series.php?id=%s&season=%s' % (media_id, int(season))
        try:
            html = cRequestHandler(page_url, caching=False).request() or ''
        except Exception:
            return []

        episode_id = ''
        direct_links = []

        # Current KinoKing embeds exact episode metadata as JSON.
        match = re.search(
            r'const\s+allEpisodesData\s*=\s*(\[.*?\])\s*;\s*let\s+watchedEpisodes',
            html,
            re.I | re.S
        )
        if match:
            try:
                episodes = json.loads(match.group(1))
                for item in episodes:
                    if int(item.get('season_number') or 0) != int(season):
                        continue
                    if int(item.get('episode_number') or 0) != int(episode):
                        continue
                    episode_id = str(item.get('id') or '')
                    raw = str(item.get('video_links') or item.get('custom_video_url') or '')
                    direct_links.extend(re.findall(r'https?://[^\s,|]+', raw))
                    break
            except Exception:
                pass

        # Fallback: episode rows are ordered on the selected season page.
        if not episode_id:
            ids = re.findall(r'playEpisode\([\'\"]?(\d+)[\'\"]?\)', html, re.I)
            idx = int(episode) - 1
            if 0 <= idx < len(ids):
                episode_id = ids[idx]

        if episode_id:
            try:
                api = self.base_link + '/api/episode-navigation.php?episode_id=%s' % episode_id
                payload = cRequestHandler(api, caching=False).request()
                data = json.loads(payload) if payload else {}
                current = data.get('current') or {}
                if current:
                    if int(current.get('season') or season) != int(season):
                        return []
                    if int(current.get('episode') or episode) != int(episode):
                        return []
                direct_links.extend(data.get('links') or [])
            except Exception:
                pass

        unique = []
        seen = set()
        for value in direct_links:
            url = str(value or '').replace('\\/', '/').strip()
            if url.startswith('//'):
                url = 'https:' + url
            if url and url not in seen:
                seen.add(url)
                unique.append(url)
        return unique

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        self.sources = []
        season_num = int(season or 0)

        if season_num > 0:
            links = []
            for media_id in self._series_candidates(titles):
                links.extend(self._series_links(media_id, season_num, int(episode)))
        else:
            clean_titles = set(cleantitle.get(i) for i in titles or [] if i)
            pages = []
            for raw_title in titles or []:
                try:
                    req = cRequestHandler(self.search_link % quote_plus(raw_title), caching=True)
                    req.cacheTime = 60 * 60
                    html = req.request()
                    for media_id, title in self._search_results(html, False):
                        if self._title_match(title, clean_titles):
                            url = self.base_link + '/movie.php?id=%s' % media_id
                            if url not in pages:
                                pages.append(url)
                    if pages:
                        break
                except Exception:
                    continue

            self.list = []
            if pages:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [executor.submit(self.chk_year, i, year) for i in pages]
                    concurrent.futures.wait(futures)
            links = list(self.list)

        seen = set()
        for link in links:
            if not link or link in seen:
                continue
            seen.add(link)

            resolve_links = [link]
            if 'meinecloud.click/movie/' in link:
                try:
                    mc_imdb = link.rstrip('/').rsplit('/', 1)[-1] or imdb
                    resolve_links = get_movie_links(mc_imdb) or []
                except Exception:
                    resolve_links = []

            for resolve_link in resolve_links:
                if resolve_link.startswith('//'):
                    resolve_link = 'https:' + resolve_link
                elif resolve_link.startswith('/'):
                    resolve_link = self.base_link + resolve_link

                try:
                    is_blocked, hoster, clean_url, prio_hoster = isBlockedHoster(resolve_link)
                except Exception:
                    continue
                if is_blocked or not clean_url:
                    continue
                self.sources.append({
                    'source': hoster,
                    'quality': 'HD',
                    'language': 'de',
                    'url': clean_url,
                    'direct': True,
                    'priority': int(self.priority),
                    'prioHoster': prio_hoster
                })

        return self.sources

    def resolve(self, url):
        return url

    def chk_year(self, url, year):
        try:
            request = cRequestHandler(url)
            request.cacheTime = 60 * 60
            html = request.request()
            found_year = re.search(r'<title>.*?(\d{4})', html, re.I | re.S)
            if found_year and year and int(found_year.group(1)) != int(year):
                return

            iframe = re.search(r'<iframe.*?src=["\']([^"\']+)', html, re.I | re.S)
            if iframe:
                self.list.append(iframe.group(1))
        except Exception:
            pass
