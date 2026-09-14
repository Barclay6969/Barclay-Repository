# kinoger
# edit 2026-06-21

import re, ast
from resources.lib.control import getSetting
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import dom_parser, cleantitle
# from scrapers.modules.tools import cParser, cUtil
from resources.lib import log_utils
from resources.lib.utils import isBlockedHosterFast as isBlockedHoster

SITE_IDENTIFIER = 'kinoger'
SITE_DOMAIN = 'kinoger.com'
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100) # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search = self.base_link + '/index.php?do=search&subaction=search&search_start=1&full_search=0&result_from=1&titleonly=3&story=%s'
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        url = ''
        try:
            t = [cleantitle.get(i) for i in titles  if i]
            years = [str(year), str(year + 1)] if season == 0 else ['']
            for title in titles:
                try:
                    sUrl = self.search % title
                    oRequest = cRequestHandler(sUrl)
                    oRequest.removeBreakLines(False)
                    oRequest.removeNewLines(False)
                    oRequest.cacheTime = 60 * 60 * 12
                    sHtmlContent = oRequest.request()

                    search_results = dom_parser.parse_dom(sHtmlContent, 'div', attrs={'class': 'title'})
                    search_results = dom_parser.parse_dom(search_results, 'a')
                    search_results = [(i.attrs['href'], i.content) for i in search_results]
                    search_results = [(i[0], re.findall(r'(.*?)\((\d+)', i[1])[0]) for i in search_results]

                    if season > 0:
                        for x in range(0, len(search_results)):
                            title = cleantitle.get(search_results[x][1][0])
                            if 'staffel' in title and any(k in title for k in t):
                                url = search_results[x][0]
                    else:
                        for x in range(0, len(search_results)):
                            title = cleantitle.get(search_results[x][1][0])
                            if any(k in title for k in t) and search_results[x][1][1] in years:
                                url = search_results[x][0]
                                break
                    if url != '': break
                except:
                    pass

            if url == '': return self.sources

            oRequest = cRequestHandler(url)
            oRequest.cacheTime = 60 * 60 * 12
            sHtmlContent = oRequest.request()
            quali = re.findall(r'title="Stream.(.+?)"', sHtmlContent)
            links = re.findall(r'.show.+?,(\[\[.+?\]\])', sHtmlContent)
            if len(links) == 0: return self.sources

            if season > 0 and episode > 0:
                season = season - 1
                episode = episode - 1

            for i in range(0, len(links)):
                try:
                    direct = True
                    pw = ast.literal_eval(links[i])
                    url = (pw[season][episode]).strip()
                    if 'kinoger.ru' in url: url = url.replace('kinoger.ru', 'voe.sx')
                    isBlocked, hoster, url, prioHoster = isBlockedHoster(url, isResolve=True)
                    if isBlocked: continue  # direct = False
                    quality = quali[i]
                    if quality == '': quality = 'SD'
                    if quality == 'HD': quality = '720p'
                    if quality == 'HD+': quality = '1080p'

                    self.sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': url, 'direct': direct, 'priority': int(self.priority), 'prioHoster': prioHoster})
                except:
                    continue

            if len(self.sources) == 0:
                log_utils.log('Kinoger: kein Provider - %s ' % titles[0], log_utils.LOGINFO)
            else:
                return self.sources
        except:
            return self.sources


    def resolve(self, url):
        try:
            return url
        except:
            return


    # def _quality(self, q): # Kinoger.be Quality
    #     hl = q.split('x')
    #     h = int(hl[0])
    #     l = int(hl[1])
    #     if h >= 1920: return '1080p'
    #     elif l >= 720 or h >= 1080: return '720p'
    #     else: return 'SD'