
# edit 2026-09-18 - robust series search

import re

from resources.lib.utils import isBlockedHosterFast as isBlockedHoster
from scrapers.modules.tools import cParser
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle
from resources.lib.control import getSetting, quote

from resources.lib.domain_manager import resolve_domain

SITE_IDENTIFIER = 'hdfilme'
SITE_DOMAIN = 'hd-filme.lol'    # https://www.hdfilme.zip/ www.hdfilme.today    hdfilme.date www.hdfilme.today
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100) # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = resolve_domain(SITE_IDENTIFIER, SITE_DOMAIN)
        self.base_link = 'https://' + self.domain

        self.search_link = self.base_link + '/index.php?do=search&do=search&subaction=search&search_start=1&full_search=0&result_from=1&titleonly=3&story=%s'
        self.checkHoster = True
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb=''):
        sources = []
        try:
            t = set([cleantitle.get(i) for i in set(titles) if i])
            links = []
            search_titles = []
            for raw_title in titles:
                if not raw_title:
                    continue
                for candidate in [
                    raw_title,
                    '%s Staffel %s' % (raw_title, int(season)) if int(season or 0) > 0 else '',
                    '%s - Staffel %s' % (raw_title, int(season)) if int(season or 0) > 0 else '',
                    '%s Season %s' % (raw_title, int(season)) if int(season or 0) > 0 else ''
                ]:
                    if candidate and candidate not in search_titles:
                        search_titles.append(candidate)

            for sSearchText in search_titles:
                try:
                    oRequest = cRequestHandler(self.search_link % quote(sSearchText))
                    oRequest.cacheTime = 60 * 60 * 24 * 1
                    # oRequest = cRequestHandler(self.search_link, caching=True)
                    # oRequest.addParameters('story', sSearchText)
                    # oRequest.addParameters('do', 'search')
                    # oRequest.addParameters('subaction', 'search')
                    sHtmlContent = oRequest.request()
                    #pattern = 'class="col-md-li">.*?href="([^"]+).*?title="([^"]+).*?h2>.*?(\d+)'
                    pattern = r'box-product(.*?)<h3.*?href="([^"]+).*?<p.*?>(.*?)(\d{4})'
                    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
                    if not isMatch:
                        continue

                    for sDummy, sUrl, sName, sYear in aResult:
                        sName = sName.strip()
                        if season == 0:
                            if cleantitle.get(sName) in t and int(sYear) == year:
                                links.append(sUrl)

                        else:
                            match = re.search(r'^(.*?)\s*[-:]\s*(?:Staffel|Season)\s*0*(\d+)\b', sName, re.I)
                            if match and cleantitle.get(match.group(1).strip()) in t and int(match.group(2)) == int(season):
                                links.append(sUrl)
                                break
                    if len(links) > 0: break
                except:
                    continue

            if len(links) == 0: return sources

            for url in links: # showHosters
                oRequest = cRequestHandler(url)
                oRequest.cacheTime = 60 * 60 * 24 * 1
                sHtmlContent = oRequest.request()
                quality = '720p'
                if season > 0:
                    pattern = r'Episoden\s%s<.*?</ul>' % episode
                    isMatch, sHtmlContent = cParser.parseSingleResult(sHtmlContent, pattern)
                    if not isMatch: return sources

                isMatch, aResult = cParser.parse(sHtmlContent, 'link="([^"]+).*?>([^<]+)')

                if isMatch:
                    for sUrl, sName in aResult:
                        if 'youtube' in sUrl or 'dropload' in sUrl: continue
                        elif 'Player' in sName: continue
                        elif sUrl.startswith('/'): sUrl = 'https:' + sUrl
                        isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl)
                        if isBlocked: continue
                        if url: self.sources.append({'source': hoster, 'quality': 'HD', 'language': 'de', 'url': url, 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})

            return self.sources
        except:
            return sources

    def resolve(self, url):
        try:
            return url
        except:
            return
