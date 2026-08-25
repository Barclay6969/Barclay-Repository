
# megakino
# 2022-07-19
# edit 2026-06-19

from resources.lib.utils import isBlockedHosterFast as isBlockedHoster
import re
from scrapers.modules.tools import cParser  # re - alternative
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle, dom_parser
from resources.lib.control import getSetting, urljoin

SITE_IDENTIFIER = 'megakino'
SITE_DOMAIN = 'megakino15.com'
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100) # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        t = set([cleantitle.get(i) for i in set(titles) if i])
        links = []
        # Suche nach 'imdb'
        try:
            oRequest = cRequestHandler(self.base_link)
            oRequest.addParameters('do', 'search')
            oRequest.addParameters('subaction', 'search')
            oRequest.addParameters('story', imdb)
            sHtmlContent = oRequest.request()
            r = dom_parser.parse_dom(sHtmlContent, 'div', attrs={'id': 'dle-content'})[0].content
            if season != 0:
                pattern = r'<a\s+class="poster[^>]*href="([^"]+).*?alt="([^"]+)'
            else:
                pattern = r'<a\s+class="poster[^>]*href="([^"]+).*?alt="([^"]+)">.*?<li>.*?(\d{4}).*?</a>'
            isMatch, aResult = cParser.parse(r, pattern)

            if isMatch:
                if season == 0:
                    for sUrl, sName, sYear in aResult:  # sUrl, sName, sQuality, sYear
                        links.append({'url': sUrl, 'name': sName, 'quality': 'HD', 'year': sYear})
                elif season > 0:
                    for sUrl, sName in aResult:
                        if cleantitle.get(sName.split('-')[0].strip()) in t and str(season) in sName.split('-')[1]:
                            links.append({'url': sUrl, 'name': sName.split('- S')[0].strip(), 'quality': 'HD', 'year': ''})

                if len(links) == 0 and season == 0:
                    for sUrl, sName, sYear in aResult:
                        if not int(sYear) == year: continue
                        for a in t:
                            if any([a in cleantitle.get(sName)]):
                                links.append({'url': sUrl, 'name': sName, 'quality': 'HD', 'year': sYear})
        except:
            pass

        # wenn Suche 'imdb' nicht erfolgreich war - dann ab hier Suche nach Titel
        if len(links)==0:
                for sSearchText in titles:
                    try:
                        # url = self.search_link % (sSearchText)
                        oRequest = cRequestHandler(self.base_link)
                        oRequest.addParameters('do', 'search')
                        oRequest.addParameters('subaction', 'search')
                        # oRequest.addParameters('search_start', '0')
                        # oRequest.addParameters('full_search', '0')
                        # oRequest.addParameters('result_from', '1')
                        oRequest.addParameters('story', sSearchText)
                        oRequest.addParameters('titleonly', '3')
                        sHtmlContent = oRequest.request()
                        r = dom_parser.parse_dom(sHtmlContent, 'div', attrs={'id': 'dle-content'})[0].content
                        if season != 0:
                            pattern = '<a\s+class="poster[^>]*href="([^"]+).*?alt="([^"]+)'
                        else:
                            pattern = '<a\s+class="poster[^>]*href="([^"]+).*?alt="([^"]+)">.*?<li>.*?(\d{4}).*?</a>'
                        isMatch, aResult = cParser.parse(r, pattern)
                        if not isMatch: continue
                        if season == 0:
                            for sUrl, sName, sYear in aResult:  # sUrl, sName, sQuality, sYear
                                if not int(sYear) == year: continue
                                # if '1080' in sQuality: sQuality = '1080p'
                                if cleantitle.get(sName) in t:
                                    links.append({'url': sUrl, 'name': sName, 'quality': 'HD', 'year': sYear})

                        elif season > 0:
                            for sUrl, sName in aResult:
                                if cleantitle.get(sName.split('-')[0].strip()) in t and str(season) in sName.split('-')[1]:
                                    links.append({'url': sUrl, 'name': sName.split('- S')[0].strip(), 'quality': 'HD', 'year': ''})

                        if len(links) == 0 and season == 0:
                            for sUrl, sName, sYear in aResult:
                                if not int(sYear) == year: continue
                                # if '1080' in sQuality: sQuality = '1080p'
                                for a in t:
                                    if any([a in cleantitle.get(sName)]):
                                        links.append({'url': sUrl, 'name': sName, 'quality': 'HD', 'year': sYear})
                                        break
                        if len(links) > 0: break
                    except:
                        continue

        if len(links) == 0: return self.sources

        for link in links:
            sUrl = urljoin(self.base_link, link['url'])
            sHtmlContent = cRequestHandler(sUrl).request()
            challenge_pattern = r'fetch\s*\(\s*["\']([^"\']+)["\']'
            is_challenge, match_groups = cParser.parseSingleResult(sHtmlContent, challenge_pattern)
            if is_challenge:
                import requests
                from urllib.parse import urlparse
                parsed_url = urlparse(sUrl)
                base_url = "{}://{}".format(parsed_url.scheme, parsed_url.netloc)
                token_path = match_groups
                token_url = base_url + token_path if token_path.startswith('/') else base_url + '/' + token_path
                s = requests.Session()
                headers = {'User-Agent': cRequestHandler.RandomUA(), 'Referer': base_url + '/'}
                s.get(base_url, headers=headers, timeout=5)
                s.get(token_url, headers=headers, timeout=5)
                response = s.get(sUrl, headers=headers)
                sHtmlContent = response.text

            if season > 0:
                quality = link['quality']
                pattern = r'<select\s+name="pmovie__select-items"\s+class="[^"]+"\s+style="[^"]+"\s+id="ep%s">\s*(.*?)\s*</select>' % str(episode)
                isMatch, sHtmlContent = cParser.parseSingleResult(sHtmlContent, pattern)
                isMatch, aResult = cParser.parse(sHtmlContent, 'value="(http[^"]+)')
                if not isMatch: return self.sources
            else:
                pattern = r'poster__label">([^/|<]+)'
                isMatch, sQuality = cParser.parseSingleResult(sHtmlContent, pattern)
                if '1080' in sQuality: sQuality = '1080p'
                quality = sQuality if isMatch else link['quality']
                pattern=r'iframe.*?src="(http[^"]+)'
                isMatch, aResult = cParser.parse(sHtmlContent, pattern)
                if not isMatch: return self.sources
            for sUrl in aResult:
                if 'youtube' in sUrl.lower(): continue
                # if sUrl.startswith('/'): sUrl = re.sub('//', 'https://', sUrl)
                # if sUrl.startswith('/'): sUrl = 'https:/' + sUrl
                isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl)
                if isBlocked: continue
                if url:
                    self.sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': url, 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})

        return self.sources

    def resolve(self, url):
        try:
            return url
        except:
            return