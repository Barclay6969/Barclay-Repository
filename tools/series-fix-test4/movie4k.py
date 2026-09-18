# -*- coding: UTF-8 -*-

import json
import re
from difflib import SequenceMatcher

from resources.lib.control import getSetting, quote_plus, setSetting
from resources.lib.requestHandler import cRequestHandler
from resources.lib.utils import isBlockedHosterFast as isBlockedHoster
from scrapers.modules import cleantitle
from resources.lib.domain_manager import resolve_domain

SITE_IDENTIFIER = 'movie4k'
SITE_DOMAIN = 'movie4k.sx'
SITE_NAME = SITE_IDENTIFIER.upper()
LEGACY_DOMAINS = ('movie4k-to.cfd', 'www.movie4k-to.cfd', 'movie4k.to', 'www.movie4k.to')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'


class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)
        self.language = ['de', 'en']
        self.domain = resolve_domain(SITE_IDENTIFIER, SITE_DOMAIN)
        if self.domain in LEGACY_DOMAINS:
            self.domain = SITE_DOMAIN
            setSetting('provider.' + SITE_IDENTIFIER + '.domain', self.domain)
        self.base_link = 'https://' + self.domain
        self.browse_link = self.base_link + '/data/browse/?lang=%s&keyword=%s&year=%s&type=%s&page=1'
        self.watch_links = [
            self.base_link + '/data/watch/?_id=%s',
            self.base_link + '/data/watch?_id=%s'
        ]
        self.checkHoster = False if getSetting('provider.movie4k.checkHoster') == 'false' else True
        self.sources = []

    def _request_json(self, url, referer=None):
        try:
            request = cRequestHandler(url, caching=True)
            request.addHeaderEntry('User-Agent', UA)
            request.addHeaderEntry('Accept', 'application/json, text/plain, */*')
            request.addHeaderEntry('Referer', referer or (self.base_link + '/'))
            request.addHeaderEntry('Origin', self.base_link)
            request.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
            payload = request.request()
            if not payload or payload in ('SEITE NICHT ERREICHBAR', 'URL FEHLER', 'TIMEOUT', 'CLOUDFLARE-SCHUTZ AKTIV'):
                return None
            if '"success":false' in payload:
                return None
            return json.loads(payload)
        except Exception:
            return None

    def _watch(self, media_id):
        for template in self.watch_links:
            data = self._request_json(template % media_id)
            if isinstance(data, dict) and isinstance(data.get('streams'), list):
                return data
        return None

    def _language_queries(self):
        setting = getSetting('hosts.language') or '0'
        if setting == '1':
            return [('2', 'de', 'Deutsch'), ('4', 'de', 'Mehrsprachig')]
        if setting == '2':
            return [('3', 'en', 'Englisch'), ('4', 'en', 'Mehrsprachig')]
        return [
            ('2', 'de', 'Deutsch'),
            ('4', 'de', 'Mehrsprachig'),
            ('3', 'en', 'Englisch')
        ]

    @staticmethod
    def _clean_stream_url(url):
        url = str(url or '').strip()
        if url.startswith('https:///'):
            return 'https://' + url[9:]
        if url.startswith('http:///'):
            return 'http://' + url[8:]
        if url.startswith('//'):
            return 'https:' + url
        return url

    @staticmethod
    def _quality(item):
        text = ' '.join(str(item.get(key) or '') for key in ['release', 'quality', 'res', 'stream']).lower()
        if '2160' in text or '4k' in text:
            return '4K'
        if '1440' in text or '2k' in text:
            return '1440p'
        if '1080' in text:
            return '1080p'
        if '720' in text:
            return '720p'
        if '480' in text:
            return '480p'
        if '360' in text:
            return '360p'
        return 'HD'

    @staticmethod
    def _title_match(candidate, clean_titles):
        current = cleantitle.get(candidate or '')
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

    @staticmethod
    def _base_and_season(title):
        match = re.search(r'^(.*?)\s*[-:]?\s*(?:Staffel|Season)\s*0*(\d+)\b', str(title or ''), re.I)
        if not match:
            return '', 0
        return match.group(1).strip(), int(match.group(2))

    def _candidate_matches(self, item, clean_titles, year, season):
        title = str(item.get('title') or '').strip()
        if not title:
            return False

        if int(season or 0) > 0:
            base, found_season = self._base_and_season(title)
            return bool(
                found_season == int(season) and
                self._title_match(base, clean_titles)
            )

        if re.search(r'\b(?:Staffel|Season)\s*\d+', title, re.I):
            return False
        base = re.sub(r'\s*\(\d{4}\)\s*$', '', title).strip()
        if not self._title_match(base, clean_titles):
            return False
        try:
            item_year = int(item.get('year') or 0)
            if item_year and year and abs(item_year - int(year)) > 1:
                return False
        except Exception:
            pass
        return True

    @staticmethod
    def _language_from_watch(watch, title, fallback_code, fallback_label):
        if re.search(r'\bStaffel\b', title or '', re.I):
            return 'de', 'Deutsch'
        if re.search(r'\bSeason\b', title or '', re.I):
            return 'en', 'Englisch'
        value = str(watch.get('lang') or '').strip()
        if value == '2':
            return 'de', 'Deutsch'
        if value == '3':
            return 'en', 'Englisch'
        if value == '4':
            return fallback_code, 'Mehrsprachig'
        return fallback_code, fallback_label

    def run(self, titles, year, season=0, episode=0, imdb=''):
        self.sources = []
        season_num = int(season or 0)
        episode_num = int(episode or 0)
        clean_titles = set(cleantitle.get(x) for x in titles or [] if x)
        media_type = 'tvseries' if season_num else 'movies'
        year_param = '' if season_num else str(year or '')

        candidates = []
        seen_ids = set()

        for lang, fallback_code, fallback_label in self._language_queries():
            matched_for_lang = 0
            for raw_title in titles or []:
                try:
                    data = self._request_json(
                        self.browse_link % (lang, quote_plus(raw_title), year_param, media_type),
                        self.base_link + '/browse?keyword=' + quote_plus(raw_title)
                    )
                    movies = data.get('movies', []) if isinstance(data, dict) else []
                except Exception:
                    movies = []

                for item in movies:
                    media_id = str(item.get('_id') or '')
                    if not media_id or media_id in seen_ids:
                        continue
                    if not self._candidate_matches(item, clean_titles, year, season_num):
                        continue
                    seen_ids.add(media_id)
                    candidates.append((item, fallback_code, fallback_label))
                    matched_for_lang += 1
                    if matched_for_lang >= 2:
                        break

                if matched_for_lang >= 2:
                    break

        seen_streams = set()
        raw_sources = []

        for item, fallback_code, fallback_label in candidates:
            media_id = item.get('_id')
            watch = self._watch(media_id)
            if not watch:
                continue

            language, language_label = self._language_from_watch(
                watch, item.get('title', ''), fallback_code, fallback_label
            )

            for stream in watch.get('streams') or []:
                if not isinstance(stream, dict):
                    continue
                if stream.get('deleted') is True or str(stream.get('deleted') or '') == '1':
                    continue
                if season_num:
                    try:
                        if int(stream.get('e') or 0) != episode_num:
                            continue
                    except Exception:
                        continue

                stream_url = self._clean_stream_url(stream.get('stream'))
                if not stream_url or stream_url in seen_streams:
                    continue
                seen_streams.add(stream_url)
                raw_sources.append((stream, stream_url, language, language_label))

        # Prefer newest entries but keep a strict ceiling so MediaInfo never has
        # to chew through dozens of stale mirrors.
        raw_sources.sort(key=lambda x: str(x[0].get('added') or ''), reverse=True)

        per_host = {}
        for stream, stream_url, language, language_label in raw_sources:
            try:
                blocked, hoster, clean_url, prio_hoster = isBlockedHoster(
                    stream_url,
                    isResolve=self.checkHoster
                )
            except Exception:
                continue
            if blocked or not clean_url:
                continue

            host_key = (str(hoster or '').lower(), language)
            if per_host.get(host_key, 0) >= 2:
                continue
            per_host[host_key] = per_host.get(host_key, 0) + 1

            self.sources.append({
                'source': hoster,
                'quality': self._quality(stream),
                'language': language,
                'url': clean_url,
                'direct': True if self.checkHoster else False,
                'priority': int(self.priority),
                'prioHoster': prio_hoster,
                'info': language_label
            })
            if len(self.sources) >= 12:
                break

        return self.sources

    def resolve(self, url):
        return url
