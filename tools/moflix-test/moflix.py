# -*- coding: UTF-8 -*-

import json
import re
import time
from html import unescape as html_unescape
from urllib.parse import quote_plus, urljoin, urlparse

from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle
from resources.lib.control import getSetting, quote
from resources.lib.utils import isBlockedHoster
from resources.lib import log_utils

SITE_IDENTIFIER = 'moflix'
SITE_DOMAIN = 'moflix-stream.xyz'
SITE_NAME = SITE_IDENTIFIER.upper()
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'


class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain.strip('/')
        self.search_link = self.base_link + '/api/v1/search/%s?query=%s&limit=8'
        self.detail_link = self.base_link + '/api/v1/titles/%s?load=images,genres,productionCountries,keywords,videos,primaryVideo,seasons,compactCredits'
        self.episode_link = self.base_link + '/api/v1/titles/%s/seasons/%s/episodes/%s?load=videos,compactCredits,primaryVideo'
        self.episodes_link = self.base_link + '/api/v1/titles/%s/seasons/%s/episodes?perPage=100&query=&page=1'
        self.sources = []
        self._seen = set()

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        try:
            item = self._best_match(titles, year, season, imdb)
            if not item:
                log_utils.log('[MOFLIX-XVAULT] no matching title found', log_utils.LOGINFO)
                return self.sources

            if int(season or 0) > 0 and int(episode or 0) > 0:
                videos = self._episode_videos(item.get('id'), season, episode)
            else:
                detail = self._json(self.detail_link % item.get('id'), self.base_link + '/')
                title_data = detail.get('title') if isinstance(detail.get('title'), dict) else {}
                videos = title_data.get('videos') or []

            self._add_videos(videos)
        except Exception as exc:
            log_utils.log('[MOFLIX-XVAULT] error: %s' % exc, log_utils.LOGERROR)
        return self.sources

    def resolve(self, url):
        return url

    def _best_match(self, titles, year, season, imdb):
        candidates = []
        seen = set()
        for title in self._search_titles(titles):
            path_title = quote(title)
            query_title = quote_plus(title)
            data = self._json(self.search_link % (path_title, query_title), self.base_link + '/')
            results = data.get('results') if isinstance(data, dict) else []
            for item in results or []:
                if not isinstance(item, dict):
                    continue
                if str(item.get('model_type') or '').lower() == 'person':
                    continue
                item_id = item.get('id')
                if not item_id or item_id in seen:
                    continue
                seen.add(item_id)
                score = self._match_score(item, titles, year, season, imdb)
                if score > 0:
                    candidates.append((score, item))

        candidates.sort(key=lambda value: value[0], reverse=True)
        if candidates:
            best_score, best_item = candidates[0]
            log_utils.log('[MOFLIX-XVAULT] match score=%s id=%s name=%s' % (
                best_score, best_item.get('id'), best_item.get('name') or best_item.get('title') or ''
            ), log_utils.LOGINFO)
            return best_item
        return None

    def _match_score(self, item, titles, year, season, imdb):
        want_series = int(season or 0) > 0
        is_series = bool(item.get('is_series'))
        if want_series != is_series:
            return 0

        score = 0
        if imdb and str(item.get('imdb_id') or '').strip().lower() == str(imdb).strip().lower():
            score += 100

        clean_titles = set(cleantitle.get(title) for title in titles or [] if title)
        item_titles = set()
        for key in ['name', 'title', 'original_title']:
            value = item.get(key)
            if value:
                item_titles.add(cleantitle.get(value))
        for value in list(item_titles):
            stripped = re.sub(r'(unrated|extended|directorscut|germansub|uncut)$', '', value or '')
            if stripped:
                item_titles.add(stripped)

        if clean_titles.intersection(item_titles):
            score += 60
        elif self._loose_title_match(clean_titles, item_titles):
            score += 25
        elif not score:
            return 0

        item_year = self._year(item)
        try:
            if year and item_year:
                delta = abs(int(year) - int(item_year))
                if delta == 0:
                    score += 20
                elif delta == 1:
                    score += 8
                else:
                    score -= 35
        except Exception:
            pass
        return score

    def _episode_videos(self, title_id, season, episode):
        if not title_id:
            return []

        direct_url = self.episode_link % (title_id, int(season or 0), int(episode or 0))
        detail = self._json(direct_url, self.base_link + '/')
        episode_data = detail.get('episode') if isinstance(detail.get('episode'), dict) else {}
        videos = episode_data.get('videos') or []
        if videos:
            return videos

        log_utils.log('[MOFLIX-XVAULT] direct episode returned no videos; trying season listing fallback S%sE%s' % (
            season, episode
        ), log_utils.LOGINFO)

        listing = self._json(self.episodes_link % (title_id, int(season or 0)), self.base_link + '/')
        pagination = listing.get('pagination') if isinstance(listing.get('pagination'), dict) else {}
        for candidate in pagination.get('data') or []:
            try:
                if int(candidate.get('episode_number') or 0) != int(episode or 0):
                    continue
                candidate_videos = candidate.get('videos') or []
                if candidate_videos:
                    return candidate_videos
                candidate_number = candidate.get('episode_number') or episode
                retry = self._json(
                    self.episode_link % (title_id, int(season or 0), int(candidate_number)),
                    self.base_link + '/'
                )
                retry_episode = retry.get('episode') if isinstance(retry.get('episode'), dict) else {}
                return retry_episode.get('videos') or []
            except Exception:
                continue
        return []

    def _add_videos(self, videos):
        for video in videos or []:
            if not isinstance(video, dict):
                continue

            original_url = html_unescape(str(video.get('src') or '').strip())
            if not original_url or original_url in self._seen:
                continue
            if 'youtube.' in original_url.lower() or 'youtu.be/' in original_url.lower():
                continue
            self._seen.add(original_url)

            original_host = (urlparse(original_url).hostname or '').lower()
            if original_host == 'moflix-stream.link':
                log_utils.log('[MOFLIX-FAST] slow failing host skipped: %s' % original_host, log_utils.LOGINFO)
                continue

            if self._is_moflix_hls(original_url) and not self._direct_hls_usable(original_url):
                log_utils.log('[MOFLIX-XVAULT] unusable direct HLS skipped: %s' % original_host, log_utils.LOGINFO)
                continue

            quality = self._quality('%s %s' % (video.get('quality') or '', original_url))
            language = self._language(video.get('language'), video.get('quality'), video.get('name'), original_url)
            mirror_prio = self._mirror_priority(original_url)

            started = time.time()
            is_blocked, hoster, resolved_url, prio_hoster = isBlockedHoster(original_url)
            try:
                log_utils.log('[MOFLIX-HOST-TIMING] %s | %.2fs | blocked=%s | resolver=%s' % (
                    original_host or original_url,
                    time.time() - started,
                    str(is_blocked),
                    str(hoster)
                ), log_utils.LOGINFO)
            except Exception:
                pass

            if is_blocked or not resolved_url:
                continue

            hoster_text = str(hoster or '')
            if 'poophq' in hoster_text or 'doods.to' in hoster_text:
                hoster = 'Veev'
            elif 'moflix-stream.click' in hoster_text:
                hoster = 'FileLions'
            elif 'moflix-stream.day' in hoster_text:
                hoster = 'VidGuard'

            try:
                prio_hoster = min(int(prio_hoster), int(mirror_prio))
            except Exception:
                prio_hoster = mirror_prio

            self.sources.append({
                'source': hoster,
                'quality': quality,
                'language': language,
                'url': resolved_url,
                'info': self._info(video),
                'direct': True,
                'priority': int(self.priority),
                'prioHoster': prio_hoster
            })

    def _json(self, url, referer):
        try:
            request = cRequestHandler(url)
            request.addHeaderEntry('User-Agent', UA)
            request.addHeaderEntry('Accept', 'application/json, text/plain, */*')
            request.addHeaderEntry('Accept-Language', 'de-DE,de;q=0.9,en;q=0.8')
            request.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
            request.addHeaderEntry('Referer', referer or self.base_link + '/')
            payload = request.request()
            if not payload:
                return {}
            return json.loads(payload)
        except Exception as exc:
            log_utils.log('[MOFLIX-XVAULT] request failed: %s (%s)' % (url, exc), log_utils.LOGINFO)
            return {}

    def _request_text(self, url, referer=None):
        try:
            request = cRequestHandler(url)
            request.addHeaderEntry('User-Agent', UA)
            request.addHeaderEntry('Accept', '*/*')
            request.addHeaderEntry('Accept-Language', 'de-DE,de;q=0.9,en;q=0.8')
            request.addHeaderEntry('Referer', referer or self.base_link + '/')
            request.addHeaderEntry('Origin', self.base_link)
            payload = request.request()
            try:
                status = str(request.getStatus() or '')
            except Exception:
                status = '200' if payload else ''
            return payload or '', status
        except Exception:
            return '', ''

    def _direct_hls_usable(self, url):
        try:
            master, status = self._request_text(url, self.base_link + '/')
            if status not in ['', '200', '301', '302'] or '#EXTM3U' not in master:
                return False
            child = self._first_child_playlist(master)
            if not child:
                return True
            child_url = urljoin(url, child)
            payload, child_status = self._request_text(child_url, url)
            return bool(payload) and child_status in ['', '200', '301', '302']
        except Exception:
            return False

    @staticmethod
    def _first_child_playlist(master):
        for line in (master or '').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '.m3u' in line.lower():
                return line
        return ''

    def _search_titles(self, titles):
        seen = set()
        result = []
        for title in titles or []:
            title = html_unescape(str(title or '').strip())
            if not title:
                continue
            variants = [title]
            if ' - ' in title:
                variants.append(title.split(' - ', 1)[0].strip())
            if ':' in title:
                variants.append(title.split(':', 1)[0].strip())
            for variant in variants:
                key = variant.lower()
                if variant and key not in seen:
                    seen.add(key)
                    result.append(variant)
        return result[:8]

    @staticmethod
    def _loose_title_match(clean_titles, item_titles):
        for wanted in clean_titles:
            for current in item_titles:
                if not wanted or not current or min(len(wanted), len(current)) < 5:
                    continue
                if wanted in current or current in wanted:
                    return True
        return False

    @staticmethod
    def _year(item):
        for key in ['year', 'release_date', 'first_air_date']:
            value = item.get(key)
            match = re.search(r'\b(19\d{2}|20\d{2})\b', str(value or ''))
            if match:
                return match.group(1)
        return ''

    @staticmethod
    def _quality(value):
        text = str(value or '').lower()
        if '2160' in text or '4k' in text:
            return '4K'
        if '1440' in text:
            return '1440p'
        if '1080' in text:
            return '1080p'
        if '720' in text:
            return '720p'
        if '480' in text or '360' in text or 'sd' in text:
            return 'SD'
        return 'HD'

    @staticmethod
    def _language(explicit, *values):
        explicit = str(explicit or '').strip().lower()
        if explicit in ['de', 'deu', 'ger', 'german', 'deutsch']:
            return 'de'
        if explicit in ['en', 'eng', 'english', 'englisch']:
            return 'en'
        if explicit in ['multi', 'multilang', 'dual', 'dl']:
            return 'multi'
        text = ' '.join(str(value or '').lower() for value in values)
        tokens = set(re.findall(r'[a-z]+', text))
        if 'multi' in tokens or 'dual' in tokens or 'dl' in tokens or ('de' in tokens and 'en' in tokens):
            return 'multi'
        if any(token in tokens for token in ['de', 'deu', 'ger', 'german', 'deutsch']):
            return 'de'
        if any(token in tokens for token in ['en', 'eng', 'english', 'englisch']):
            return 'en'
        return explicit or 'unknown'

    @staticmethod
    def _info(video):
        values = []
        for key in ['name', 'quality', 'type', 'origin']:
            value = str(video.get(key) or '').strip()
            if value and value.lower() not in ['none', 'null']:
                values.append(value)
        return ' | '.join(values)

    @staticmethod
    def _is_moflix_hls(url):
        try:
            clean_url = str(url or '').split('|', 1)[0].split('?', 1)[0].lower()
            host = (urlparse(clean_url).hostname or '').lower()
            return clean_url.endswith(('.m3u8', '.m3u')) and (
                host.endswith('.moflix-stream.day') or
                host.endswith('.moflix-stream.xyz') or
                host in ['moflix-stream.day', 'moflix-stream.xyz']
            )
        except Exception:
            return False

    @staticmethod
    def _mirror_priority(url):
        host = (urlparse(str(url or '').split('|', 1)[0]).hostname or '').lower()
        if host == 'veev.to':
            return 25
        if host == 'moflix-stream.click':
            return 35
        if host in ['moflix.rpmplay.xyz', 'moflix.upns.xyz']:
            return 45
        if host == 'moflix-stream.link':
            return 55
        if host == 'gupload.xyz':
            return 70
        return 100
