
# kkiste
# 2023-01-28
# edit 2026-06-09

from resources.lib.utils import isBlockedHosterFast as isBlockedHoster
import re
from scrapers.modules.tools import cParser  # re - alternative
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle
from resources.lib.control import getSetting, urljoin

from resources.lib.domain_manager import resolve_domain

SITE_IDENTIFIER = 'kkiste'
SITE_DOMAIN = 'kkiste-io.click' # kkiste.pro
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100) # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = resolve_domain(SITE_IDENTIFIER, SITE_DOMAIN)
        self.base_link = 'https://' + self.domain

        # self.search_link = urljoin(self.base_link, '/index.php?do=search')# /index.php?do=search&subaction=search&story=
        self.search_link = urljoin(self.base_link, '/index.php?do=search&subaction=search&titleonly=3&story=%s')
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        sources = []
        try:
            t = set([cleantitle.get(i) for i in set(titles) if i])
            years = (year, year+1, year-1, 0)
            links = []
            for sSearchText in titles:
                try:
                    oRequest = cRequestHandler(self.search_link % sSearchText)
                    sHtmlContent = oRequest.request()
                    pattern = r'class="short">.*?href="([^"]+)">([^<]+).*?Jahr:.*?([\d]+)<'
                    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
                    if not isMatch:
                        continue

                    for sUrl, sName, sYear in aResult:
                        if season == 0:
                            if cleantitle.get(sName) in t and int(sYear) in years:
                                  if sUrl not in links: links.append(sUrl)
                        else:
                            if cleantitle.get(sName.split('-')[0].strip()) in t and str(season) in sName.split('-')[1]:
                                if sUrl not in links: links.append(sUrl)

                    if len(links) > 0: break
                except:
                    continue

            if len(links) == 0: return sources
            for link in set(links):
                sHtmlContent = cRequestHandler(link).request()
                if season > 0:
                    pattern = r'\s%s<.*?</ul>' % episode
                    isMatch, sHtmlContent = cParser.parseSingleResult(sHtmlContent, pattern)
                    if not isMatch: return sources
                isMatch, aResult = cParser.parse(sHtmlContent, 'link="([^"]+)">')
                if not isMatch: return sources

                for sUrl in aResult:
                    if 'youtube'in sUrl or 'vod'in sUrl: continue
                    if sUrl.startswith('/'): sUrl = re.sub('//', 'https://', sUrl)
                    if sUrl.startswith('/'): sUrl = 'https:/' + sUrl
                    isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl)
                    if isBlocked: continue
                    if url: self.sources.append({'source': hoster, 'quality': 'HD', 'language': 'de', 'url': url, 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})

            return self.sources
        except:
            return self.sources


    def resolve(self, url):
        try:
            return url
        except:
            return
