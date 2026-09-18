# -*- coding: utf-8 -*-
import re
try:
    from json import loads
except Exception:
    from simplejson import loads

from scrapers.modules.tools import cParser
from scrapers.modules import cleantitle
from resources.lib.control import getSetting, quote_plus
from resources.lib.requestHandler import cRequestHandler
from resources.lib.domain_manager import resolve_domain

SITE_IDENTIFIER = 'kkiste'
SITE_DOMAIN = 'kkiste.eu'
SITE_NAME = 'KKiste'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)
        self.language = ['de', 'en']
        self.domain = resolve_domain(SITE_IDENTIFIER, SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.browse_link = self.base_link + '/data/browse/?lang=%s&keyword=%s&year=%s&type=%s&page=1'
        self.watch_links = [self.base_link + '/data/watch/?_id=%s', self.base_link + '/data/watch?_id=%s']
        self.hoster_priority = {
            'streamtape': 5, 'voe': 10, 'doodstream': 5, 'mixdrop': 9,
            'streamwish': 8, 'filemoon': 5, 'vidoza': 7, 'upstream': 5,
            'streamruby': 10, 'vidguard': 6
        }
        self.min_priority = 6
        self.max_per_hoster = 5

    def _headers(self, referer=None):
        return {
            'User-Agent': UA,
            'Accept': 'application/json, text/plain, */*',
            'Referer': referer or self.base_link + '/',
            'Origin': self.base_link,
            'X-Requested-With': 'XMLHttpRequest'
        }

    def _json(self, url, referer=None):
        try:
            request = cRequestHandler(url, caching=True)
            for key, value in self._headers(referer).items():
                request.addHeaderEntry(key, value)
            payload = request.request()
            return loads(payload) if payload else None
        except Exception:
            return None

    def _watch(self, media_id, referer=None):
        for template in self.watch_links:
            data = self._json(template % media_id, referer)
            if data and isinstance(data.get('streams'), list):
                return data
        return None

    def _language_queries(self):
        setting = getSetting('hosts.language') or '0'
        if setting == '1':
            return ['2']
        if setting == '2':
            return ['3']
        return ['2', '3']

    @staticmethod
    def _language(data, title=''):
        value = str(data.get('lang', '')).strip()
        if value == '2':
            return 'de', 'Deutsch'
        if value == '3':
            return 'en', 'Englisch'
        if value == '4':
            if re.search(r'\bSeason\b', str(title), re.I):
                return 'en', 'Mehrsprachig'
            return 'de', 'Mehrsprachig'
        if re.search(r'\bSeason\b', str(title), re.I):
            return 'en', 'Englisch'
        return 'de', 'Deutsch'

    @staticmethod
    def _matches(item, clean_titles, year, season):
        title = str(item.get('title', ''))
        if not title:
            return False
        if int(season or 0) == 0:
            if re.search(r'\b(Staffel|Season)\s+\d+', title, re.I):
                return False
            clean = cleantitle.get(re.sub(r'\s*\(\d{4}\)\s*$', '', title).strip())
            if clean not in clean_titles:
                return False
            try:
                item_year = int(item.get('year', 0))
                if item_year and year and abs(item_year - int(year)) > 1:
                    return False
            except Exception:
                pass
            return True
        match = re.search(r'Staffel\s+(\d+)|Season\s+(\d+)', title, re.I)
        if not match:
            return False
        found = int(match.group(1) or match.group(2))
        if found != int(season):
            return False
        base = re.sub(r'\s*[-:]\s*(Staffel|Season)\s*\d+.*', '', title, flags=re.I).strip()
        return cleantitle.get(base) in clean_titles

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        sources = []
        try:
            clean_titles = set(cleantitle.get(x) for x in set(titles or []) if x)
            media_type = 'tvseries' if int(season or 0) > 0 else 'movies'
            found_ids = set()
            hoster_count = {}

            for lang in self._language_queries():
                for title in titles or []:
                    if not title:
                        continue
                    search_url = self.browse_link % (lang, quote_plus(title), '' if season else year, media_type)
                    data = self._json(search_url, self.base_link + '/browse?keyword=%s' % quote_plus(title))
                    if not data or not isinstance(data.get('movies'), list):
                        continue
                    for movie in data['movies']:
                        media_id = str(movie.get('_id') or '')
                        if not media_id or media_id in found_ids or not self._matches(movie, clean_titles, year, season):
                            continue
                        found_ids.add(media_id)
                        watch = self._watch(media_id, self.base_link + '/browse?keyword=%s' % quote_plus(title))
                        if not watch:
                            continue
                        language, lang_label = self._language(watch, movie.get('title', ''))
                        for stream in watch.get('streams') or []:
                            if int(season or 0) > 0 and str(stream.get('e', '')) != str(episode):
                                continue
                            url = str(stream.get('stream') or '').strip()
                            if not url or 'youtube' in url.lower() or 'vod' in url.lower():
                                continue
                            if url.startswith('//'):
                                url = 'https:' + url
                            elif url.startswith('/'):
                                url = 'https:/' + url
                            ok, names = cParser.parse(url, '//([^/]+)/')
                            if not ok:
                                continue
                            host = names[0]
                            short = host.rsplit('.', 1)[0] if '.' in host else host
                            rank = 0
                            for key, value in self.hoster_priority.items():
                                if key in short.lower():
                                    rank = value
                                    break
                            if rank < self.min_priority:
                                continue
                            count_key = '%s:%s' % (language, short.lower())
                            if hoster_count.get(count_key, 0) >= self.max_per_hoster:
                                continue
                            hoster_count[count_key] = hoster_count.get(count_key, 0) + 1
                            release = str(stream.get('release') or '').upper()
                            quality = 'CAM' if ('CAM' in release or 'TS' in release) else 'SD' if 'SD' in release else 'HD'
                            sources.append({
                                'source': short,
                                'quality': quality,
                                'language': language,
                                'url': url,
                                'direct': False,
                                'debridonly': False,
                                'priority': int(self.priority),
                                'prioHoster': max(1, 20 - rank),
                                'info': lang_label
                            })
            return sorted(sources, key=lambda x: x.get('prioHoster', 100))
        except Exception:
            return sources

    def resolve(self, url):
        return url
