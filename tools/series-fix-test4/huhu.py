# -*- coding: UTF-8 -*-

import json
from urllib.parse import urlparse

try:
    import requests
except Exception:
    requests = None

from resources.lib.control import getSetting
from resources.lib.requestHandler import cRequestHandler
from resources.lib.utils import isBlockedHosterFast as isBlockedHoster

SITE_IDENTIFIER = 'huhu'
SITE_DOMAIN = 'www.huhu.to'
SITE_NAME = 'HUHU'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'


class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)
        self.language = ['de', 'en']
        self.domain = SITE_DOMAIN
        self.base_link = 'https://' + self.domain
        self.source_link = self.base_link + '/mediaurl-source.json'
        self.sources = []
        self._seen = set()

    def _json(self, url, headers=None, caching=True):
        try:
            request = cRequestHandler(url, caching=caching)
            for key, value in (headers or {}).items():
                request.addHeaderEntry(key, value)
            payload = request.request()
            return json.loads(payload) if payload else None
        except Exception:
            return None

    def _tmdb_id(self, imdb, is_series):
        if not imdb:
            return None
        try:
            api_key = getSetting('api.tmdb')
            if not api_key:
                return None
            url = 'https://api.themoviedb.org/3/find/%s?api_key=%s&external_source=imdb_id' % (imdb, api_key)
            data = self._json(url)
            key = 'tv_results' if is_series else 'movie_results'
            items = data.get(key) if isinstance(data, dict) else []
            if not items:
                return None
            return items[0].get('id')
        except Exception:
            return None

    def _post_source(self, payload):
        headers = {
            'User-Agent': UA,
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json; charset=utf-8',
            'Origin': self.base_link,
            'Referer': self.base_link + '/'
        }

        if requests is not None:
            try:
                response = requests.post(
                    self.source_link,
                    data=json.dumps(payload),
                    headers=headers,
                    timeout=12
                )
                if response.status_code == 200:
                    data = response.json()
                    return data if isinstance(data, list) else []
            except Exception:
                pass

        # urllib fallback for Kodi installations where requests is unavailable.
        try:
            from urllib.request import Request, urlopen
            req = Request(
                self.source_link,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers,
                method='POST'
            )
            with urlopen(req, timeout=12) as response:
                data = json.loads(response.read().decode('utf-8', 'replace'))
                return data if isinstance(data, list) else []
        except Exception:
            return []

    @staticmethod
    def _quality(item):
        text = ' '.join([
            str(item.get('tag') or ''),
            str(item.get('name') or ''),
            str(item.get('url') or '')
        ]).lower()
        if '2160' in text or '4k' in text:
            return '4K'
        if '1440' in text:
            return '1440p'
        if '1080' in text:
            return '1080p'
        if '960' in text:
            return '960p'
        if '800' in text:
            return '800p'
        if '720' in text:
            return '720p'
        if '480' in text or '360' in text:
            return 'SD'
        return 'HD'

    @staticmethod
    def _language(item):
        values = item.get('languages') or []
        if isinstance(values, str):
            values = [values]
        value = str(values[0] if values else 'de').lower()
        if value.startswith('en'):
            return 'en'
        if value.startswith('de'):
            return 'de'
        return value or 'de'

    @staticmethod
    def _fallback_hoster(item):
        name = str(item.get('name') or '').strip()
        host = (urlparse(str(item.get('url') or '')).hostname or '').replace('www.', '')
        return host or name or SITE_NAME

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        self.sources = []
        self._seen = set()
        is_series = int(season or 0) > 0
        tmdb_id = self._tmdb_id(imdb, is_series)
        if not tmdb_id:
            return self.sources

        payload = {
            'language': 'de',
            'region': 'DE',
            'type': 'series' if is_series else 'movie',
            'ids': {'tmdb_id': int(tmdb_id)},
            'name': ''
        }
        if is_series:
            payload['episode'] = {
                'ids': {},
                'season': int(season),
                'episode': int(episode)
            }

        for item in self._post_source(payload):
            if not isinstance(item, dict) or item.get('type') != 'url':
                continue
            raw = str(item.get('url') or '').strip()
            if not raw.startswith(('http://', 'https://')) or raw in self._seen:
                continue
            self._seen.add(raw)

            try:
                blocked, hoster, clean_url, prio_hoster = isBlockedHoster(raw, isResolve=False)
            except Exception:
                blocked, hoster, clean_url, prio_hoster = False, self._fallback_hoster(item), raw, 100
            if blocked or not clean_url:
                continue

            self.sources.append({
                'source': hoster or self._fallback_hoster(item),
                'quality': self._quality(item),
                'language': self._language(item),
                'url': clean_url,
                'direct': False,
                'debridonly': False,
                'info': str(item.get('name') or ''),
                'priority': int(self.priority),
                'prioHoster': prio_hoster
            })

            if len(self.sources) >= 20:
                break

        return self.sources

    def resolve(self, url):
        return url
