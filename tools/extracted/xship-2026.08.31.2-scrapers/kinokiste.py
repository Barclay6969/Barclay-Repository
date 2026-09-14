# kinokiste
# 2023-01-27 (fix: keyword-API statt limit=0)
# edit 2026-05-22

import json
import re
from resources.lib.requestHandler import cRequestHandler
from resources.lib.utils import isBlockedHosterFast as isBlockedHoster
from scrapers.modules import cleantitle
from scrapers.modules.tools import cParser
from resources.lib.control import getSetting, quote_plus

from resources.lib.domain_manager import resolve_domain

SITE_IDENTIFIER = 'kinokiste'
SITE_DOMAIN = 'kinokiste.club'
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)  # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = resolve_domain(SITE_IDENTIFIER, SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        # FIX: keyword-Parameter nutzen statt limit=0 (limit=0 lädt ALLE Einträge -> Loop/Timeout)
        self.search_movie  = self.base_link + '/data/browse/?lang=2&type=movies&order_by=new&keyword=%s&page=1'
        self.search_series = self.base_link + '/data/browse/?lang=2&type=tvseries&order_by=new&keyword=%s&page=1'
        self.watch_link    = self.base_link + '/data/watch/?_id=%s'
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        try:
            t = set([cleantitle.get(i) for i in set(titles) if i])
            years = (year, year+1, year-1)
            found_id = None
            found_quality = 'HD'

            for sSearchText in titles:
                try:
                    search_url = self.search_series if season > 0 else self.search_movie
                    oRequest = cRequestHandler(search_url % quote_plus(sSearchText))
                    oRequest.cacheTime = 60 * 60 * 6
                    raw = oRequest.request()
                    if not raw: continue
                    data = json.loads(raw)
                    movies = data.get('movies', [])
                    if not movies: continue

                    for movie in movies:
                        sTitle = movie.get('title', '')
                        sId    = movie.get('_id')
                        if not sId: continue

                        if season > 0:
                            if 'Staffel' not in sTitle and 'Season' not in sTitle: continue
                            sNameClean = re.split(r'\s*[-–]\s*\d+\s*(?:Staffel|Season)', sTitle)[0].strip()
                            if cleantitle.get(sNameClean) not in t: continue
                            m = re.search(r'(\d+)\s*(?:Staffel|Season)', sTitle)
                            if not m or int(m.group(1)) != season: continue
                        else:
                            if cleantitle.get(sTitle) not in t: continue
                            item_year = movie.get('year')
                            if item_year and int(str(item_year)) not in years: continue

                        found_id = sId
                        found_quality = movie.get('quality', 'HD')
                        break

                    if found_id: break
                except Exception:
                    continue

            if not found_id: return self.sources
            oRequest2 = cRequestHandler(self.watch_link % found_id)
            raw2 = oRequest2.request()
            if not raw2: return self.sources
            jStreams = json.loads(raw2).get('streams', [])
            jStreams = sorted(jStreams, key=lambda k: k.get('added', ''), reverse=True)

            max = 0
            max_search = 0
            for stream in jStreams:
                try:
                    max_search +=1
                    if max_search == 10: break
                    if season > 0 and str(stream.get('e', '')) != str(episode): continue
                    sUrl = stream.get('stream', '')
                    if not sUrl or not sUrl.startswith('http'): continue
                    release = stream.get('release', '')
                    quality = '1080p' if '1080' in release else 'CAM' if 'CAM' in release.upper() else found_quality or 'HD'
                    isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl)
                    if isBlocked: continue
                    if url:
                        max += 1
                        self.sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': url, 'direct': True, 'prioHoster': prioHoster})
                    if max == 3: break

                except Exception:
                    continue

        except Exception:
            pass
        return self.sources

    def resolve(self, url):
        return url
