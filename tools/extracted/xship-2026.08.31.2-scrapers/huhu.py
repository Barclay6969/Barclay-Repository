

# edit 2025-08-02

import json
from scrapers.modules.tools import cParser
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle
from resources.lib.control import getSetting, quote
from resources.lib.utils import isBlockedHosterFast as isBlockedHoster

SITE_IDENTIFIER = 'huhu'
SITE_DOMAIN = 'www.huhu.to'
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100) # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'http://' + self.domain + '/web-vod/'
        #self.search_link = self.base_link
        self.search_link = self.base_link + 'api/list?id=%s.popular.search=%s'
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        try:
            if season == 0: mediatype = 'movie'
            else: mediatype = 'series'
            t = set([cleantitle.get(i) for i in set(titles) if i])
            links = []
            # import pydevd
            # pydevd.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)
            for sSearchText in titles:
                try:
                    sSearchText = quote(sSearchText)
                    oRequest = cRequestHandler(self.search_link %(mediatype, sSearchText ))
                    oRequest.addHeaderEntry('Referer', self.base_link)
                    oRequest.addHeaderEntry('Origin', 'https://' + self.domain)
                    oRequest.removeNewLines(False)
                    if season != 0: oRequest.cacheTime = 60 * 60 * 4  # 4 Stunden
                    jSearch = json.loads(oRequest.request())
                    if not jSearch: continue
                    aResults = jSearch['data']
                    if len(aResults) == 0: continue
                    #isTvshow = False
                    for i in aResults:
                        sId = i['id']  # ID des Films / Serie für die weitere URL
                        sName = i['name']  # Name des Films / Serie
                        if 'releaseDate' in i and len(str(i['releaseDate'].split('-')[0].strip())) != '':
                            sYear = str(i['releaseDate'].split('-')[0].strip())
                        else: continue

                        if cleantitle.get(sName) in t and int(sYear) == year:
                            if season == 0:
                                sUrl =  self.base_link + 'api/links?id=%s' % sId
                            else:
                                # https://huhu.to/web-vod/links?id=series.94997.1.1
                                sUrl = self.base_link + 'api/links?id=%s.%s.%s' %(sId, season, episode)
                            if not sUrl in links: links.append(sUrl)
                            break

                    if len(links) > 0: break
                except:
                    continue

            for hUrl in links:
                oRequest = cRequestHandler(hUrl)
                #if season != 0: oRequest.cacheTime = 60 * 60 * 4  # 4 Stunden
                oRequest.addHeaderEntry('Referer', self.base_link)
                oRequest.addHeaderEntry('Origin', 'https://' + self.domain)
                oRequest.removeNewLines(False)
                jSearch = json.loads(oRequest.request())
                if not jSearch: continue

                for i in jSearch:
                    if not 'language' in str(i): language = 'de'
                    else: language = i['language']
                    isMatch, quality = cParser.parseSingleResult(i['name'], "\(([^\)]+)")
                    if not isMatch: quality = '720p'
                    url = 'https://www.huhu.to/web-vod/api/get?link=%s' % i['url']
                    _USER_AGENT = cRequestHandler.RandomUA()
                    Request = cRequestHandler(url, caching=False)
                    Request.addHeaderEntry('User-Agent', _USER_AGENT)
                    Request.request()
                    sUrl =  Request.getRealUrl()
                    isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl)
                    if isBlocked:
                        continue
                    if url: self.sources.append({'source': hoster, 'quality': quality, 'language': language, 'url': url, 'info': i['name'] , 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})

            return self.sources
        except:
            return self.sources

    def resolve(self, url):
        try:
            return url
        except:
            return