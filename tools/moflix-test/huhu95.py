# -*- coding: utf-8 -*-
import json
from resources.lib.control import getSetting
from resources.lib.requestHandler import cRequestHandler

SITE_IDENTIFIER = 'huhu'
SITE_DOMAIN = 'www.huhu.to'
SITE_NAME = 'HUHU'


class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain + '/web-vod/'
        self.links_link = self.base_link + 'api/links?id=%s'
        self.get_link = self.base_link + 'api/get?link='
        self.sources = []

    def _json(self, url, headers=None, caching=True):
        try:
            request = cRequestHandler(url, caching=caching)
            for key, value in (headers or {}).items():
                request.addHeaderEntry(key, value)
            payload = request.request()
            return json.loads(payload) if payload else None
        except Exception:
            return None

    def _headers(self):
        return {
            'Referer': self.base_link,
            'Origin': 'https://' + self.domain,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def _media_id(self, imdb, season, episode):
        if not imdb:
            return None
        try:
            api_key = getSetting('api.tmdb')
            if not api_key:
                return None
            url = 'https://api.themoviedb.org/3/find/%s?api_key=%s&external_source=imdb_id' % (imdb, api_key)
            data = self._json(url)
            if not data:
                return None
            if int(season or 0) > 0:
                result = (data.get('tv_results') or [])[0]
                return 'series.%s.%s.%s' % (result.get('id'), int(season), int(episode))
            result = (data.get('movie_results') or [])[0]
            return 'movie.%s' % result.get('id')
        except Exception:
            return None

    @staticmethod
    def _quality(name):
        text = str(name or '').lower()
        for value in ('2160', '1440', '1080', '720', '480', '360'):
            if value in text:
                return '4K' if value == '2160' else value + 'p'
        return 'HD'

    @staticmethod
    def _hoster(name):
        text = str(name or '').split('(')[0].strip()
        mapping = {
            'Server P2': 'Streamtape',
            'Server W2': 'Doodstream',
            'Server O': 'Vidoza',
            'Server E': 'Mixdrop',
            'Server M2': 'Supervideo',
            'Server G2': 'Luluvideo'
        }
        for key, value in mapping.items():
            if key in text:
                return value
        return text or 'Huhu'

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        self.sources = []
        media_id = self._media_id(imdb, season, episode)
        if not media_id:
            return self.sources

        links = self._json(self.links_link % media_id, self._headers())
        if not isinstance(links, list):
            return self.sources

        for item in links:
            try:
                if not isinstance(item, dict):
                    continue
                raw = str(item.get('url') or '').strip()
                if not raw:
                    continue
                name = str(item.get('name') or '')
                language = str(item.get('language') or 'de').split('(')[0].strip().lower()
                if language in ('german', 'deutsch', 'deu', 'ger'):
                    language = 'de'
                elif language in ('english', 'englisch', 'eng'):
                    language = 'en'
                elif language not in ('de', 'en'):
                    language = 'de'

                self.sources.append({
                    'source': self._hoster(name),
                    'quality': self._quality(name),
                    'language': language,
                    'url': self.get_link + raw,
                    'direct': False,
                    'debridonly': False,
                    'info': name,
                    'priority': int(self.priority),
                    'prioHoster': 100
                })
            except Exception:
                continue
        return self.sources

    def resolve(self, url):
        try:
            request = cRequestHandler(url, caching=False, ignoreErrors=True)
            for key, value in self._headers().items():
                request.addHeaderEntry(key, value)
            request.request()
            return request.getRealUrl() or url
        except Exception:
            return None
