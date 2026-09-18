# -*- coding: UTF-8 -*-

import json
import re

from resources.lib.control import getSetting, quote_plus
from resources.lib.domain_manager import resolve_domain
from resources.lib.requestHandler import cRequestHandler
from resources.lib.utils import isBlockedHosterFast as isBlockedHoster
from scrapers.modules import cleantitle

SITE_IDENTIFIER = 'movie2k'
SITE_DOMAIN = 'movie2k.ch'
SITE_NAME = SITE_IDENTIFIER.upper()
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)
        self.language = ['de', 'en']
        self.domain = resolve_domain(SITE_IDENTIFIER, SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/data/browse/?lang=%s&keyword=%s&year=%s&type=%s&page=1'
        self.watch_link = self.base_link + '/data/watch/?_id=%s'
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        try:
            streams = self._search(titles, year, season, episode)
            if not streams:
                return self.sources

            streams = sorted(streams, key=lambda item: item.get('added', ''), reverse=True)
            total = 0
            checked = 0

            for item in streams:
                if checked >= 50 or total >= 10:
                    break
                checked += 1

                stream_url = item.get('stream', '')
                if not stream_url:
                    continue

                quality = self._quality(item.get('release', ''))
                is_blocked, hoster, clean_url, prio_hoster = isBlockedHoster(stream_url, isResolve=False)
                if is_blocked or not clean_url:
                    continue

                language = item.get('_xship_language', 'de')
                language_label = item.get('_xship_language_label', '')
                self.sources.append({
                    'source': hoster,
                    'quality': quality,
                    'language': language,
                    'url': clean_url,
                    'info': language_label,
                    'direct': False,
                    'priority': int(self.priority),
                    'prioHoster': prio_hoster
                })
                total += 1
        except Exception:
            pass

        return self.sources

    def resolve(self, url):
        return url

    def _ajax_headers(self, referer=None):
        return {
            'User-Agent': UA,
            'Accept': 'application/json, text/plain, */*',
            'Referer': referer or (self.base_link + '/'),
            'Origin': self.base_link,
            'X-Requested-With': 'XMLHttpRequest'
        }

    def _request_json(self, url, referer=None):
        try:
            request = cRequestHandler(url)
            request.cacheTime = 60 * 60 * 6
            for key, value in self._ajax_headers(referer).items():
                request.addHeaderEntry(key, value)
            payload = request.request()
            if not payload or '"success":false' in payload:
                return None
            payload = re.sub(r'\\\s+\\', '\\\\', payload)
            return json.loads(payload)
        except Exception:
            return None

    def _language_queries(self):
        # Keep xVault's current behaviour.  The multi-language catalogue
        # contains both German and English mirrors and is especially useful
        # for series where the old lang=2-only query misses Season entries.
        setting = getSetting('hosts.language') or '0'
        if setting == '2':
            return ['3']
        return ['4']

    @staticmethod
    def _language_from_watch(data, title=''):
        title = str(title or '')
        # Serien zuerst anhand des Katalogtitels einordnen. Movie2k liefert
        # Season-Eintraege teilweise mit lang=4 (Multi); xShips zentraler
        # Sprachfilter akzeptiert aber nur de/en und wuerde sie sonst verwerfen.
        if re.search(r'\bStaffel\b', title, re.IGNORECASE):
            return 'de', 'Deutsch'
        if re.search(r'\bSeason\b', title, re.IGNORECASE):
            return 'en', 'Englisch'

        value = str(data.get('lang', '')).strip()
        if value == '2':
            return 'de', 'Deutsch'
        if value == '3':
            return 'en', 'Englisch'
        if value == '4':
            # Multi-Katalog ohne eindeutigen Serienmarker: fuer xShip als DE
            # weiterreichen statt komplett aus der Quellenliste zu verschwinden.
            return 'de', 'Mehrsprachig'
        return 'de', 'Deutsch'

    @staticmethod
    def _match_search_result(item, clean_titles, year, season):
        title = str(item.get('title', ''))
        if not title:
            return False

        if int(season or 0) > 0:
            match = re.search(r'Staffel\s+(\d+)|Season\s+(\d+)', title, re.IGNORECASE)
            if not match:
                return False
            found_season = match.group(1) or match.group(2)
            if str(found_season) != str(season):
                return False
            series_title = re.sub(
                r'\s*[-:]\s*(Staffel|Season)\s*\d+.*',
                '',
                title,
                flags=re.IGNORECASE
            ).strip()
            return cleantitle.get(series_title) in clean_titles

        if re.search(r'\b(Staffel|Season)\s+\d+', title, re.IGNORECASE):
            return False

        api_title = re.sub(r'\s*\(\d{4}\)\s*$', '', title).strip()
        if cleantitle.get(api_title) not in clean_titles:
            return False

        try:
            api_year = int(item.get('year', 0))
            req_year = int(year)
            if api_year and req_year and abs(api_year - req_year) > 1:
                return False
        except Exception:
            pass
        return True

    def _search_titles(self, titles):
        result = []
        seen = set()
        for value in titles or []:
            title = str(value or '').strip()
            if not title:
                continue
            candidates = [title]
            if ' - ' in title:
                candidates.append(title.split(' - ', 1)[0].strip())
            if ':' in title:
                candidates.append(title.split(':', 1)[0].strip())

            plain = title.replace("'", '').replace('’', '').replace('`', '')
            plain = __import__('re').sub(r'\s*[-:]\s*', ' ', plain)
            plain = __import__('re').sub(r'\s+', ' ', plain).strip()
            if plain:
                candidates.append(plain)

            for candidate in candidates:
                key = candidate.lower()
                if candidate and key not in seen:
                    seen.add(key)
                    result.append(candidate)
        return result[:8]

    def _search(self, titles, year, season, episode):
        results = []
        media_type = 'tvseries' if int(season or 0) > 0 else 'movies'
        year_param = '' if int(season or 0) > 0 else str(year)
        search_titles = self._search_titles(titles)
        clean_titles = set(cleantitle.get(title) for title in search_titles if title)
        seen_ids = set()

        for lang in self._language_queries():
            for title in search_titles:
                if not title:
                    continue
                try:
                    query = self.search_link % (
                        lang,
                        quote_plus(title),
                        year_param,
                        media_type
                    )
                    data = self._request_json(
                        query,
                        self.base_link + '/browse?keyword=%s' % quote_plus(title)
                    )
                    movies = data.get('movies', []) if data else []
                    if not movies:
                        continue

                    matches = [
                        item for item in movies
                        if self._match_search_result(item, clean_titles, year, season)
                    ]

                    for match in matches:
                        media_id = match.get('_id')
                        if not media_id or media_id in seen_ids:
                            continue
                        seen_ids.add(media_id)

                        watch = self._request_json(
                            self.watch_link % media_id,
                            self.base_link + '/browse?keyword=%s' % quote_plus(title)
                        )
                        if not watch:
                            continue

                        language, label = self._language_from_watch(watch, match.get('title', ''))
                        streams = watch.get('streams', []) or []
                        if int(season or 0) > 0:
                            streams = [
                                item for item in streams
                                if item.get('e', False) and str(item.get('e')) == str(episode)
                            ]

                        for stream in streams:
                            if not isinstance(stream, dict):
                                continue
                            stream['_xship_language'] = language
                            stream['_xship_language_label'] = label
                            results.append(stream)

                        if len(results) >= 60:
                            return results
                except Exception:
                    continue

        return results

    @staticmethod
    def _quality(release):
        release = str(release or '')
        if '2160' in release or '4K' in release:
            return '4K'
        if '1440' in release or '2K' in release:
            return '1440p'
        if '1080' in release:
            return '1080p'
        if '720' in release:
            return '720p'
        if '480' in release:
            return '480p'
        if '360' in release:
            return '360p'
        return 'HD'
