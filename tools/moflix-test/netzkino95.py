# -*- coding: UTF-8 -*-
import json
import re
import urllib.parse
from resources.lib.requestHandler import cRequestHandler
from resources.lib.control import getSetting
from scrapers.modules import cleantitle

SITE_IDENTIFIER = 'netzkino'
SITE_DOMAIN = 'netzkino.de'
SITE_NAME = 'NETZKINO'
GRAPHQL = 'https://data.netzkino.de/netzkino/graphql'
SEARCH_HASH = 'e7f141530416887b1faa663dbdd468534c6639e47886e8156686afd9a0f81d76'


class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)
        self.language = ['de']
        self.sources = []

    def _request(self, url):
        try:
            req = cRequestHandler(url, caching=True)
            return req.request()
        except Exception:
            return ''

    def _search_url(self, text):
        extensions = {'persistedQuery': {'version': 1, 'sha256Hash': SEARCH_HASH}}
        variables = {'text': text}
        return '%s?extensions=%s&variables=%s&operationName=Search' % (
            GRAPHQL,
            urllib.parse.quote(json.dumps(extensions)),
            urllib.parse.quote(json.dumps(variables))
        )

    def _details(self, content_id):
        html = self._request('https://www.netzkino.de/details/%s' % content_id)
        if not html:
            return None
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
            queries = data.get('props', {}).get('__dehydratedState', {}).get('queries', [])
            for query in queries:
                if (query.get('queryKey') or [''])[0] != 'MovieDetails':
                    continue
                movie = query.get('state', {}).get('data', {}).get('data', {}).get('movie') or {}
                pmd = movie.get('videoSource', {}).get('pmdUrl')
                if pmd:
                    return {'title': movie.get('title'), 'year': movie.get('productionYear'), 'pmd': pmd}
        except Exception:
            pass
        return None

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        self.sources = []
        if season or not titles:
            return self.sources
        query = min([str(x) for x in titles if x], key=len).lower()
        try:
            raw = self._request(self._search_url(query))
            data = json.loads(raw) if raw else {}
            nodes = data.get('data', {}).get('search', {}).get('nodes', [])
            wanted = set(cleantitle.get(x) for x in titles if x)
            for node in nodes if isinstance(nodes, list) else []:
                content_id = node.get('id')
                if not content_id:
                    continue
                detail = self._details(content_id)
                if not detail:
                    continue
                if cleantitle.get(detail.get('title') or '') not in wanted:
                    continue
                try:
                    if detail.get('year') and year and int(detail['year']) != int(year):
                        continue
                except Exception:
                    pass
                stream = str(detail.get('pmd') or '')
                if not stream:
                    continue
                if not stream.startswith('http'):
                    stream = 'https://pmd.netzkino-seite.netzkino.de/' + stream.lstrip('/')
                self.sources.append({'source': 'Netzkino', 'quality': 'HD', 'language': 'de',
                                     'url': stream, 'direct': True, 'priority': int(self.priority),
                                     'prioHoster': 1})
        except Exception:
            pass
        return self.sources

    def resolve(self, url):
        return url
