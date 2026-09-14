
#2023-07-28
# edit 2025-08-02

import json
import time
from urllib.parse import urlparse
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle
from resources.lib.control import getSetting, quote
from resources.lib.utils import isBlockedHoster
from resources.lib import log_utils

SITE_IDENTIFIER = 'moflix'
SITE_DOMAIN = 'moflix-stream.xyz'
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100) # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain

        # self.search_link = self.base_link + '/secure/search/%s?type=&limit=8&provider='
        self.search_link = self.base_link + '/api/v1/search/%s?query=%s&limit=8'
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        try:
            t = set([cleantitle.get(i) for i in set(titles) if i])
            links = []
            for title in titles:
                title = quote(title)
                oRequest = cRequestHandler(self.search_link % (title, title))
                oRequest.addHeaderEntry('Referer', self.base_link + '/')
                jSearch = json.loads(oRequest.request())  # .values()
                # if not 'success' in jSearch['status']: continue
                if not jSearch: continue
                aResults = jSearch['results']
                for i in aResults:
                    if 'imdb_id' in i and i['imdb_id'] == imdb:
                        links.append({'id': i['id'], 'name': i['name']})
                        break
                    elif season == 0:
                        if 'is_series' in i and i['is_series']: continue
                        if 'year' in i and year != i['year']: continue
                        if cleantitle.get(i['name']) in t:
                            links.append({'id': i['id'], 'name': i['name']})
                    else:
                        if 'is_series' in i and not i['is_series']: continue
                        if cleantitle.get(i['name']) in t:
                            id = i['id']
                            url = self.base_link + '/api/v1/titles/%s?load=images,genres,productionCountries,keywords,videos,primaryVideo,seasons,compactCredits' % id
                            oRequest = cRequestHandler(url)
                            oRequest.addHeaderEntry('Referer', url)
                            jSearch = json.loads(oRequest.request())
                            links.append({'id': jSearch['title']['id'], 'name': i['name']})

                if len(links) > 0: break
                #
            if len(links) == 0: return self.sources
            for link in links:
                id = link['id']
                if season == 0:
                    # url = self.base_link + '/secure/titles/%s?titleId=%s' % (id, id)
                    url = self.base_link + '/api/v1/titles/%s?load=images,genres,productionCountries,keywords,videos,primaryVideo,seasons,compactCredits' % id
                else:
                    # url = self.base_link + '/secure/titles/%s?titleId=%sseasonNumber=%s&episodeNumber=%s' % (id, id, season, episode)
                    url = self.base_link + '/api/v1/titles/%s/seasons/%s/episodes/%s?load=videos,compactCredits,primaryVideo' % (id, season, episode)
                oRequest = cRequestHandler(url)
                oRequest.addHeaderEntry('Referer', url)
                jSearch = json.loads(oRequest.request())
                # if not 'success' in jSearch['status']: continue
                if not jSearch: continue
                if season == 0:
                    jVideos = jSearch['title']['videos']
                else:
                    jVideos = jSearch['episode']['videos']
                # import pydevd
                # pydevd.settrace('10.128.5.144', port=12345, stdoutToServer=True, stderrToServer=True)
                for j in jVideos:
                    quality = j['quality'] if j['quality'] else 'SD'
                    quality = '1080p' if '1080' in quality else '720p'
                    sUrl = j['src']

                    # 2026-08-21.3: moflix-stream.link is currently resolved by
                    # ResolveURL's Byse resolver and repeatedly spends ~30s on a
                    # captcha attempt before failing.  It never contributed a
                    # usable source in the reference logs, so skip ONLY this
                    # exact hostname during scraping.  All other Moflix hosters
                    # keep the proven full-resolve path unchanged.
                    sHost = (urlparse(str(sUrl)).hostname or '').lower()
                    if sHost == 'moflix-stream.link':
                        log_utils.log('[MOFLIX-FAST] slow failing host skipped: %s' % sHost, log_utils.LOGINFO)
                        continue

                    _host_started = time.time()
                    isBlocked, sHoster, url, prioHoster = isBlockedHoster(sUrl)
                    try:
                        log_utils.log('[MOFLIX-HOST-TIMING] %s | %.2fs | blocked=%s | resolver=%s' %
                                      (sHost or sUrl, time.time() - _host_started, str(isBlocked), str(sHoster)),
                                      log_utils.LOGINFO)
                    except Exception:
                        pass
                    if 'poophq' in sHoster or 'doods.to' in sHoster: sHoster = 'Veev'
                    elif 'moflix-stream.click' in sHoster: sHoster = 'FileLions'
                    elif 'moflix-stream.day' in sHoster: sHoster = 'VidGuard'
                    if isBlocked: continue
                    if url:
                        self.sources.append({'source': sHoster, 'quality': quality, 'language': j['language'], 'url': url, 'info': '', 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})

            return self.sources
        except:
            return self.sources

    def resolve(self, url):
        try:
            return url
        except:
            return