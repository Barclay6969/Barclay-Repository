# movie2k
# 2022-11-04 (fix: URL-Limit vor isBlockedHoster, verhindert 3-Minuten-Lauf)
# edit 2026-05-22

import re
import json
from resources.lib.control import getSetting
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules.tools import cParser
from resources.lib.utils import isBlockedHosterFast as isBlockedHoster

from resources.lib.domain_manager import resolve_domain

SITE_IDENTIFIER = 'movie2k'
SITE_DOMAIN = 'movie2k.ch'
SITE_NAME = SITE_IDENTIFIER.upper()

# Hoster die bekannt tot/nutzlos sind - vor isBlockedHoster filtern
#_SKIP_HOSTERS = ('streamtape', 'doodstream', 'myvidplay', 'dood',
#                 'veev', 'strmup', 'savefiles', 'vidara', 'vidsonic')
_SKIP_HOSTERS = ()
class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100) # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = resolve_domain(SITE_IDENTIFIER, SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/data/browse/?lang=2&keyword=%s&year=%s&type=%s&page=1'
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        try:
            jSearch = self._search(titles, year, season, episode)
            if not jSearch: return self.sources

            jSearch = sorted(jSearch, key=lambda k: k.get('added', ''), reverse=True)

            # FIX: Erst filtern, dann erst isBlockedHoster aufrufen
            # Verhindert 70+ HEAD-Requests für tote Links
            candidates = []
            for item in jSearch:
                sUrl = item.get('stream', '')
                if not sUrl: continue
                # Bekannte tote Hoster sofort überspringen
                url_lower = sUrl.lower()
                if any(skip in url_lower for skip in _SKIP_HOSTERS): continue
                candidates.append(item)
                if len(candidates) >= 10: break  # Max 10 Kandidaten prüfen

            count = 0
            max_search = 0
            for item in candidates:
                try:
                    max_search += 1
                    if max_search == 10: break
                    sUrl = item.get('stream', '')
                    quality = '1080p' if '1080p' in item.get('release', '') else 'HD'
                    isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl)
                    if isBlocked: continue
                    if url:
                        self.sources.append({'source': hoster, 'quality': quality,
                                             'language': 'de', 'url': url, 'info': '',
                                             'direct': True, 'prioHoster': prioHoster})
                        count += 1
                        if count >= 3: break  # Max 3 funktionierende Quellen
                except Exception:
                    continue

        except Exception:
            pass
        return self.sources

    def _search(self, titles, year, season, episode):
        mtype = 'tvseries' if season > 0 else 'movies'
        year_param = '' if season > 0 else str(year)
        for title in titles:
            try:
                query = self.search_link % (title, year_param, mtype)
                oRequest = cRequestHandler(query)
                oRequest.cacheTime = 60 * 60 * 6
                raw = oRequest.request()
                if not raw or '"success":false' in raw: continue
                raw = re.sub(r'\\\s+\\', '\\\\', raw)
                data = json.loads(raw)
                jSearch = data.get('movies', [])
                if not jSearch: continue

                found_id = None
                if season > 0:
                    for i in jSearch:
                        isMatch, sSeason = cParser.parseSingleResult(
                            i.get('title', ''), r'Staffel.*?(\d+)')
                        if isMatch and sSeason == str(season):
                            found_id = i.get('_id')
                            break
                else:
                    for i in jSearch:
                        item_year = str(i.get('year', ''))
                        if item_year not in (str(year), str(year+1), str(year-1)): continue
                        found_id = i.get('_id')
                        break

                if not found_id: continue
                oRequest2 = cRequestHandler(self.base_link + '/data/watch/?_id=%s' % found_id)
                oRequest2.cacheTime = 60 * 60 * 6
                result = json.loads(oRequest2.request())
                streams = result.get('streams', [])
                if season > 0:
                    return [i for i in streams if str(i.get('e', '')) == str(episode)]
                return streams
            except Exception:
                continue
        return []

    def resolve(self, url):
        return url
