
# burningseries

# edit 2026-06-21

import json
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules.tools import cParser
from resources.lib.control import getSetting, addonName, setSetting, dialog
from scrapers.modules import cleantitle, dom_parser
from resources.lib.utils import isBlockedHoster


SITE_IDENTIFIER = 'burningseries'
SITE_DOMAIN = 'burningseries.ac'
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100) # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain

        self.search_link = self.base_link + '/andere-serien'
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        if season == 0: return self.sources
        self._checkApi()
        t = [cleantitle.get(i) for i in set(titles) if i]
        oRequest = cRequestHandler(self.search_link, caching=True)
        oRequest.cacheTime = 60 * 60 * 48  # 48 Stunden
        sHtmlContent = oRequest.request()
        links = dom_parser.parse_dom(sHtmlContent, "div", attrs={"class": "genre"})
        links = dom_parser.parse_dom(links, "a")
        links = [(i.attrs["href"], i.attrs["title"]) for i in links]
        aLinks = []
        for sUrl, sName in links:
            if len(sName.split('|')) >= 1:
                aName=sName.split('|')
                for sName in aName:
                    if cleantitle.get(sName) in set(t) and sUrl not in aLinks:
                        aLinks.append(sUrl)
                        break
            else:
                if cleantitle.get(sName) in set(t) and sUrl not in aLinks:
                    aLinks.append(sUrl)
                    break

            if len(aLinks) > 0: break

        if len(aLinks) == 0: return self.sources

        for link in aLinks: # sollte immer mur ein Link sein
            sUrl = self.base_link + '/' + link +'/'+str(season)
            sHtmlContent = cRequestHandler(sUrl).request()
            table = dom_parser.parse_dom(sHtmlContent, "table", attrs={"class": "episodes"})
            a = dom_parser.parse_dom(table, "a")
            epUrl = [(i.attrs['href']) for i in a if i.content == str(episode)][0]
            aHoster = [(i.attrs['href']) for i in a if epUrl in i.attrs['href'] and 'hoster' in i.content]
            for link in aHoster:
                hoster = link.rsplit('/', 1)[1]
                sUrl = self.base_link + '/' + link
                quality = 'HD'
                isBlocked, hoster, url, prioHoster = isBlockedHoster(hoster, isResolve=False)
                if isBlocked: continue
                self.sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': sUrl, 'direct': False, 'priority': int(self.priority), 'prioHoster': prioHoster})


        return self.sources

    def resolve(self, url):
        # Hier alles einbauen was zur auflösung notwendig ist
        from resources.lib.tools import logger
        from resources.lib.captcha.captcha_helper import solve_recaptcha, extract_recaptcha_sitekey
        Request = cRequestHandler(url, caching=False)
        Request.addHeaderEntry('Referer', self.base_link)
        Request.addHeaderEntry('Upgrade-Insecure-Requests', '1')
        htmlContent = Request.request()
        sitekey = extract_recaptcha_sitekey(htmlContent)
        if not sitekey:
            logger.error('BurningSeries: getHosterUrl: No sitekey found in HTML content.')
            return None

        sUrl = Request.getRealUrl()
        google_captcha_token = solve_recaptcha(sitekey, sUrl)
        if not google_captcha_token:
            logger.error('BurningSeries: getHosterUrl: Failed to solve captcha.')
            return None

        lIDMatch, lID = cParser.parseSingleResult(htmlContent, r'data-lid="([^"]+)"')
        securityTokenMatch, securityToken = cParser.parseSingleResult(htmlContent, r'security_token" content="([^"]+)"')

        if not lIDMatch:
            logger.error('BurningSeries: getHosterUrl: No lID found in HTML content.')
            # return None?
            return

        if not securityTokenMatch:
            logger.error('BurningSeries: getHosterUrl: No securityToken found in HTML content.')
            # return None?
            return

        responseHeader = Request.getResponseHeader()
        if hasattr(responseHeader, 'get_all'):
            setCookieHeaders = responseHeader.get_all('Set-Cookie')
        elif hasattr(responseHeader, 'getheaders'):
            setCookieHeaders = responseHeader.getheaders('Set-Cookie')
        else:
            setCookieHeaders = []

        cookie_string_parts = []

        for header in setCookieHeaders:
            name_value = header.split(";", 1)[0].strip()
            if "=" in name_value:
                cookie_string_parts.append(name_value)

        headers = {
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'accept-language': 'de-DE,de;q=0.9',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': self.base_link,
            'priority': 'u=1, i',
            'referer': url,
            'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest'
        }

        cookies = {}
        for part in cookie_string_parts:
            if "=" in part:
                name, value = part.split("=", 1)
                cookies[name.strip()] = value.strip()

        data = {
            'token': securityToken,
            'LID': lID,
            'ticket': google_captcha_token
        }

        embedRequest = cRequestHandler(f'{self.base_link}/ajax/embed.php', caching=False, method='POST', data=data)
        for k, v in headers.items():
            embedRequest.addHeaderEntry(k, v)
        # Manually set cookies as header if needed
        if cookies:
            cookie_header = '; '.join([f"{k}={v}" for k, v in cookies.items()])
            embedRequest.addHeaderEntry('Cookie', cookie_header)
        response_text = embedRequest.request()

        parsedJson = json.loads(response_text)
        if not parsedJson or 'link' not in parsedJson:
            logger.error('BurningSeries: getHosterUrl: No result from resolve request.')
            # return None?
            return
        return parsedJson['link']

    @staticmethod
    def _checkApi():
        provider=getSetting('captcha.provider')
        if getSetting(provider+'.pass')=='':
            dialog.ok(addonName + '  ' + SITE_NAME,
                      "%s benötigt einen Captcha-Dienst (%s).\nIn den Captcha-Einstellungen einen API Key eintragen.\nBis dahin wird %s als Provider deaktiviert." % (
                          SITE_NAME, provider.upper(), SITE_NAME))
            setSetting('provider.' + SITE_IDENTIFIER, 'false')
            exit()
