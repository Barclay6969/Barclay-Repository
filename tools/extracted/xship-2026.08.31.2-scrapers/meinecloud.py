
# movie4k
# 2022-11-11
# edit 2026-05-23

# Wichtige Info: dieser Scraper ersetzt u.a. Movie4k, Streamcloud, Fhdfilme, Filmpro
# Alle diese Seiten nutzen die gleiche DataBase

from resources.lib.utils import isBlockedHosterFast as isBlockedHoster
import re
from scrapers.modules.tools import cParser  # re - alternative
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle
from scrapers.modules.meinecloud_shared import get_movie_links
from resources.lib.control import getSetting

SITE_IDENTIFIER = 'meinecloud'
SITE_DOMAIN = 'meinecloud.click'
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100) # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.sources = []


    def run(self, titles, year, season=0, episode=0, imdb=''):
        try:
            if season == 0:
                ## https://meinecloud.click/movie/tt1477834
                aResult = get_movie_links(imdb)
                for sUrl in aResult:
                    if sUrl.startswith('/'): sUrl = 'https:' + sUrl
                    isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl)
                    if isBlocked: continue
                    if url:
                        self.sources.append({'source': hoster, 'quality': '1080p', 'language': 'de', 'url': url, 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})
                return self.sources

            else:
                # https://meinecloud.click/serial/7772588
                sImdb = str(imdb[2:])
                oRequest = cRequestHandler('https://meinecloud.click/serial/%s' % sImdb, caching=True)
                sHtmlContent = oRequest.request()
                pattern = r'data-link="([^"]+)"\s+data-label="S%s\sE%s' %(season,episode)
                isMatch, aResult = cParser.parse(sHtmlContent, pattern)
                i=0
                for sUrl in dict.fromkeys(aResult):
                    # if 'railer' in sName or 'youtube'in sUrl or 'vod'in sUrl: continue
                    # if sUrl.startswith('/'): sUrl = re.sub('//', 'https://', sUrl)
                    if sUrl.startswith('/'): sUrl = 'https:' + sUrl
                    isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl)
                    if isBlocked: continue
                    if url:
                        i += 1  # z.B. Serie "For All Mankind" S2 E1 werden 2 Streams gefunden, der 2.Stream ist NOK
                        self.sources.append({'source': hoster+'(%s)' %i, 'quality': '1080p', 'language': 'de', 'url': url, 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})
                        if i==1: break
            return self.sources
        except:
            return self.sources

    def resolve(self, url):
        try:
            return url
        except:
            return
