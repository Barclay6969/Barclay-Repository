
# einschalten
# 2024-09-05
# edit 2025-08-02

import json
from resources.lib.requestHandler import cRequestHandler
from resources.lib.utils import isBlockedHosterFast as isBlockedHoster
from scrapers.modules.tools import cParser
from resources.lib.control import getSetting
from scrapers.modules import cleantitle

SITE_IDENTIFIER = 'einschalten'
SITE_DOMAIN = 'einschalten.in'
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100) # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain

        self.search_link = self.base_link + '/search?query=%s'
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        if season > 0: return  self.sources
        try:
            t = [cleantitle.get(i) for i in set(titles) if i]
            links = []
            for sSearchText in set(titles):
                URL_SEARCH = self.search_link % sSearchText
                oRequest = cRequestHandler(URL_SEARCH, caching=True)
                oRequest.cacheTime = 60 * 60 #* 48  # 48 Stunden
                sHtmlContent = oRequest.request()
                pattern = r'"id":(\d+).*?"title":"([^"]+).*?releaseDate":"(\d{4})'
                isMatch, aResult = cParser.parse(sHtmlContent, pattern)
                if not isMatch: continue
                for sId, sName, sYear in aResult:
                    if year == int(sYear):
                        if cleantitle.get(sName) in set(t) and sId not in links:
                            links.append(sId)
                            break

                if len(links) > 0: break

            if len(links) == 0: return self.sources
            for link in set(links):
                sUrl = self.base_link + '/api/movies/' + link + '/watch'
                sHtmlContent = cRequestHandler(sUrl).request()
                if not 'streamUrl' in sHtmlContent: continue
                jResult = json.loads(sHtmlContent)
                releaseName = jResult['releaseName']
                if '720p' in releaseName: quality = '720p'
                elif '1080p' in releaseName: quality = '1080p'
                else: quality = 'SD'
                streamUrl = jResult['streamUrl']
                isBlocked, hoster, url, prioHoster = isBlockedHoster(streamUrl)
                if isBlocked: continue
                if url: self.sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': url, 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})

            return self.sources
        except:
            return self.sources

    def resolve(self, url):
        return  url

