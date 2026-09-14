

# edit 2025-08-02

import re
import datetime
from resources.lib.control import  getSetting, urljoin, setSetting
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle, dom_parser
from resources.lib.utils import isBlockedHosterFast as isBlockedHoster

SITE_IDENTIFIER = 'aniworld'
SITE_DOMAIN = 'aniworld.to' # https://www.aniworld.info/
SITE_NAME = SITE_IDENTIFIER.upper()

date = datetime.date.today()
currentyear = int(date.strftime("%Y"))

class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100) # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain

        self.search_link = '/animes'
        self.login = getSetting('aniworld.user')
        self.password = getSetting('aniworld.pass')
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        # if self.login == '' or self.password == '':
        #     import xbmcgui, xbmcaddon
        #     AddonName = xbmcaddon.Addon().getAddonInfo('name')
        #     xbmcgui.Dialog().ok(AddonName,
        #                         "In den Einstellungen die Kontodaten (Login) für %s eintragen / überprüfen\nBis dahin wird %s von der Suche ausgeschlossen. Es erfolgt kein erneuter Hinweis!" % (
        #                         SITE_NAME, SITE_NAME))
        #     setSetting('provider.' + SITE_IDENTIFIER, 'false')
        #     return []

        sources = []
        if season == 0: return sources
        try:
            t = [cleantitle.get(i) for i in titles if i]
            url = urljoin(self.base_link, self.search_link)
            #url = urljoin('https://sus.to', self.search_link) # for test only
            #isTrue, sHtmlContent = getcontent.aniworld(url)
            #if not isTrue: sHtmlContent = cRequestHandler(url).request()
            oRequest = cRequestHandler(url)
            oRequest.cacheTime = 60*60*24
            sHtmlContent = oRequest.request()
            # if not self.base_link in str(dom_parser.parse_dom(sHtmlContent, "meta", attrs={"property": "og:url"})):
            #     url = urljoin(self.base_link, self.search_link)
            #     sHtmlContent = cRequestHandler(url).request()

            links = dom_parser.parse_dom(sHtmlContent, "div", attrs={"class": "genre"})
            links = dom_parser.parse_dom(links, "a")
            links = [(i.attrs["href"], i.content) for i in links]
            #links = [i for i in links if cleantitle.get(i[1]) in t or any([a in cleantitle.get(i[1]) for a in t])]
            url = ''
            aLinks = []
            for i in links:
                try:
                    if cleantitle.get(i[1]) in t:
                        #print (i[1])
                        url = i[0]
                        break
                except:
                    pass

            if url == '':
                for i in links:
                    for a in t:
                        try:
                            if any([a in cleantitle.get(i[1])]):
                                aLinks.append({'source': i[0]})
                                break
                        except:
                            pass

            if url == '':
                if len(aLinks) > 0:
                    for i in aLinks:
                        url = i['source']
                        self.run2(url, year, season=season, episode=episode, hostDict=hostDict, imdb=imdb)
                else:
                    return sources
            else:
                self.run2(url, year, season=season, episode=episode, hostDict=hostDict, imdb=imdb)
        except:
            return sources
        return self.sources

    def run2(self, url, year, season=0, episode=0, hostDict=None, imdb=None):
        try:
            url = url[:-1] if url.endswith('/') else url
            if "staffel" in url:
                url = re.findall("(.*?)staffel", url)[0]
            url += '/staffel-%d/episode-%d' % (int(season), int(episode))
            url = urljoin(self.base_link, url)
            sHtmlContent = cRequestHandler(url).request()
            # startDate = dom_parser.parse_dom(sHtmlContent, 'span', attrs={'itemprop': 'startDate'})
            # startDate = int(dom_parser.parse_dom(startDate[0].content, 'a')[0].content)
            # endDate = dom_parser.parse_dom(sHtmlContent, 'span', attrs={'itemprop': 'endDate'})
            # endDate = dom_parser.parse_dom(endDate[0].content, 'a')[0].content
            # endDate = currentyear if endDate == 'Heute' else int(endDate)
            a = dom_parser.parse_dom(sHtmlContent, 'a', attrs={'class': 'imdb-link'}, req='href')
            foundImdb = a[0].attrs["data-imdb"]

            if not foundImdb == imdb: return
            # if not startDate == year: return


            r = dom_parser.parse_dom(sHtmlContent, 'div', attrs={'class': 'hosterSiteVideo'})
            #r = dom_parser.parse_dom(r, 'li', attrs={'data-lang-key': re.compile('[1|2|3]')})
            #r = dom_parser.parse_dom(r, 'li', attrs={'data-lang-key': re.compile('[1]')}) #- only german
            r = dom_parser.parse_dom(r, 'li', attrs={'data-lang-key': re.compile('[1|3]')})  #- only german and subbed DE

            r = [(i.attrs['data-link-target'], dom_parser.parse_dom(i, 'h4'),
                  'Untertitel DE' if i.attrs['data-lang-key'] == '3' else '' if i.attrs['data-lang-key'] == '1' else 'Untertitel EN' if i.attrs['data-lang-key'] == '2' else '') for i
                 in r]
            r = [(i[0], re.sub(r'\s(.*)', '', i[1][0].content), 'HD' if 'hd' in i[1][0][1].lower() else 'SD', i[2]) for i in r]

            import requests
            requests.packages.urllib3.disable_warnings()
            s = requests.Session()
            for link, host, quality, info in r:
                redirect_url = urljoin(self.base_link, link)
                response = s.get(redirect_url, allow_redirects=True, verify=False, timeout=10)
                sUrl = response.url
                quality = 'HD'  # temp
                isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl, isResolve=True)
                if isBlocked: continue
                self.sources.append(
                    {'source': host, 'quality': quality, 'language': 'de', 'url': url, 'info': info, 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})
            return self.sources
        except:
            return self.sources

    def resolve(self, url):
        return url
        # try:
        #     URL_LOGIN = urljoin(self.base_link, '/login')
        #     Handler = cRequestHandler(URL_LOGIN, caching=False)
        #     Handler.addHeaderEntry('Upgrade-Insecure-Requests', '1')
        #     Handler.addHeaderEntry('Referer', self.base_link)
        #     Handler.addParameters('email', self.login)
        #     Handler.addParameters('password', self.password)
        #     Handler.request()
        #     Request = cRequestHandler(self.base_link + url, caching=False)
        #     Request.addHeaderEntry('Referer', self.base_link)
        #     Request.addHeaderEntry('Upgrade-Insecure-Requests', '1')
        #     Request.request()
        #     url = Request.getRealUrl()
        #
        #     if self.base_link in url:
        #         import xbmcgui, xbmcaddon
        #         AddonName = xbmcaddon.Addon().getAddonInfo('name')
        #         xbmcgui.Dialog().ok(AddonName, "- Geschützter Link - \nIn den Einstellungen die Kontodaten (Login) für Anicloud eintragen")
        #         return
        #     else:
        #         return url
        #
        # except:
        #     return

