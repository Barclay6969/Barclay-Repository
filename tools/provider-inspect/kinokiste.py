# -*- coding: UTF-8 -*-
import json
import re
from resources.lib.control import getSetting, quote_plus, urlparse
from resources.lib.requestHandler import cRequestHandler
from resources.lib.domain_manager import resolve_domain
from scrapers.modules import cleantitle

SITE_IDENTIFIER = 'kinokiste'
SITE_DOMAIN = 'kinokiste.eu'
SITE_NAME = 'KINOKISTE'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'


class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)
        self.language = ['de', 'en']
        self.domain = resolve_domain(SITE_IDENTIFIER, SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/data/browse/?lang=%s&keyword=%s&year=%s&type=%s&page=1'
        self.imdb_link = self.base_link + '/data/browse/?lang=%s&order_by=new&page=1&imdb=%s'
        self.watch_links = [self.base_link + '/data/watch/?_id=%s', self.base_link + '/data/watch?_id=%s']
        self.sources = []

    def _json(self, url):
        try:
            req = cRequestHandler(url, caching=True)
            req.addHeaderEntry('User-Agent', UA)
            req.addHeaderEntry('Referer', self.base_link + '/')
            req.addHeaderEntry('Origin', self.base_link)
            req.addHeaderEntry('X-Requested-With', 'XMLHttpRequest')
            data = req.request()
            return json.loads(data) if data else None
        except Exception:
            return None

    def _watch(self, media_id):
        for template in self.watch_links:
            data = self._json(template % media_id)
            if data and isinstance(data.get('streams'), list):
                return data
        return None

    @staticmethod
    def _quality(value):
        text = str(value or '').upper()
        if '2160' in text or '4K' in text: return '4K'
        if '1080' in text: return '1080p'
        if '720' in text: return '720p'
        if 'CAM' in text: return 'CAM'
        if 'SD' in text: return 'SD'
        return 'HD'

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        self.sources = []
        clean_titles = set(cleantitle.get(x) for x in titles or [] if x)
        media_type = 'tvseries' if int(season or 0) > 0 else 'movies'
        movies = []
        seen = set()

        for lang in ('4', '2', '3'):
            if imdb:
                data = self._json(self.imdb_link % (lang, imdb))
                for movie in (data.get('movies') if data and isinstance(data.get('movies'), list) else []):
                    mid = str(movie.get('_id') or '')
                    if mid and mid not in seen:
                        seen.add(mid); movies.append(movie)
            for title in titles or []:
                data = self._json(self.search_link % (lang, quote_plus(title), '' if season else year, media_type))
                for movie in (data.get('movies') if data and isinstance(data.get('movies'), list) else []):
                    mid = str(movie.get('_id') or '')
                    if mid and mid not in seen:
                        seen.add(mid); movies.append(movie)
            if movies:
                break

        for movie in movies:
            title = str(movie.get('title') or '')
            mid = str(movie.get('_id') or '')
            if not title or not mid:
                continue
            if season:
                sm = re.search(r'(?:Staffel|Season)\s*(\d+)', title, re.I)
                if not sm or int(sm.group(1)) != int(season):
                    continue
                base = re.sub(r'\s*[-:]?\s*(?:Staffel|Season)\s*\d+.*', '', title, flags=re.I).strip()
                if cleantitle.get(base) not in clean_titles:
                    continue
            else:
                base = re.sub(r'\s*\(\d{4}\)\s*$', '', title).strip()
                if cleantitle.get(base) not in clean_titles:
                    continue
                try:
                    item_year = int(movie.get('year') or 0)
                    if item_year and year and abs(item_year - int(year)) > 1:
                        continue
                except Exception:
                    pass

            watch = self._watch(mid)
            if not watch:
                continue
            lang_value = str(watch.get('lang') or '')
            language = 'en' if lang_value == '3' or 'Season' in title else 'de'
            info = 'Mehrsprachig' if lang_value == '4' else ('Englisch' if language == 'en' else 'Deutsch')
            best = {}
            for stream in watch.get('streams') or []:
                if season and str(stream.get('e') or '') != str(episode):
                    continue
                url = str(stream.get('stream') or '').strip()
                if not url:
                    continue
                if url.startswith('//'):
                    url = 'https:' + url
                host = urlparse(url).hostname or ''
                if not host:
                    continue
                quality = self._quality(stream.get('release') or movie.get('quality'))
                key = host.lower()
                if key not in best or quality in ('4K','1080p'):
                    best[key] = (url, quality)
            for host, (url, quality) in best.items():
                self.sources.append({'source': host, 'quality': quality, 'language': language,
                                     'url': url, 'direct': False, 'priority': int(self.priority),
                                     'prioHoster': 100, 'info': info})
        return self.sources

    def resolve(self, url):
        return url
