# kinoking
# 2026-02-15
# edit 2026-02-15

import json, re
import concurrent.futures
from resources.lib.requestHandler import cRequestHandler
from resources.lib.utils import isBlockedHosterFast as isBlockedHoster
from resources.lib.control import getSetting
from scrapers.modules import cleantitle

SITE_IDENTIFIER = 'kinoking'
SITE_DOMAIN = 'kinoking.cc'
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100) # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain

        self.search_link = self.base_link + '/index.php?search=%s'
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        t = [cleantitle.get(i) for i in set(titles) if i]
        links = []
        hoster = []
        for sSearchText in set(titles):
            try:
                URL_SEARCH = self.search_link % sSearchText
                oRequest = cRequestHandler(URL_SEARCH, caching=True)
                oRequest.cacheTime = 60 * 60
                sHtmlContent = oRequest.request()
                # Titel im alt-Attribut: onclick="playMovie(12324)"> ... alt="Inception"
                if season == 0:
                    pattern = r'onclick="playMovie\((\d+)\)"'
                else:
                    pattern = r"onclick=\"playContent\('(\d+)'\)\""
                results = []
                for m in re.finditer(pattern, sHtmlContent):
                    chunk = sHtmlContent[m.end():m.end() + 300]
                    alt_m = re.search(r'alt="([^"]+)"', chunk)
                    if alt_m:
                        results.append((m.group(1), alt_m.group(1)))
                for id, sName in results:
                    if cleantitle.get(sName) in t:
                        if season == 0:
                            url = self.base_link + '/movie.php?id=%s' % id
                        else:
                            url = self.base_link + '/series.php?id=%s' % id
                        if url not in links:
                            links.append(url)
                if len(links) > 0: break
            except:
                continue

        if len(links) == 0: return self.sources

        if season == 0:
            self.list = []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(self.chk_year, i, year) for i in links]
                concurrent.futures.wait(futures)
            if len(self.list) > 0: hoster = self.list
        else:
            try:
                sHtmlContent = cRequestHandler(links[0]).request()
                episodeId = re.search(r'playEpisode\((\d+)', sHtmlContent).group(1)
                api_url = self.base_link + '/api/episode-navigation.php?episode_id=%s' % episodeId
                req = cRequestHandler(api_url).request()
                jreq = json.loads(req)['links']
                hoster.append(jreq[episode - 1])
            except:
                pass

        for link in hoster:
            isBlocked, sDomain, sUrl, prioHoster = isBlockedHoster(link)
            if isBlocked: continue
            self.sources.append({'source': sDomain, 'quality': 'HD', 'language': 'de', 'url': sUrl, 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})

        return self.sources

    def resolve(self, url):
        return url

    def chk_year(self, url, year):
        try:
            oRequest = cRequestHandler(url)
            oRequest.cacheTime = 60 * 60
            sHtmlContent = oRequest.request()
            found_year = re.search(r'<title>.*?(\d{4})', sHtmlContent).group(1)
            if int(found_year) == year:
                found_hoster = re.search(r'<iframe.*?src="([^"]+)', sHtmlContent).group(1)
                self.list.append(found_hoster)
        except:
            pass
