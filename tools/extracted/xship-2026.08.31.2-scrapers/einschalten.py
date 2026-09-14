
# einschalten
# 2024-09-05
# edit 2025-08-02

import json
from resources.lib.requestHandler import cRequestHandler
from resources.lib.utils import isBlockedHosterFast as isBlockedHoster
from scrapers.modules.tools import cParser
from resources.lib.control import getSetting
from scrapers.modules import cleantitle
from resources.lib import log_utils

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

                # Kodi 21 / ResolveURL Dood fallback: use an instance-owned default
                # urllib opener for vide0.net before falling back to ResolveURL.
                url = self._resolve_dood_default_tls(streamUrl)
                if url:
                    self.sources.append({'source': 'DoodStream', 'quality': quality, 'language': 'de', 'url': url, 'direct': True, 'priority': int(self.priority), 'prioHoster': 100})
                    continue

                isBlocked, hoster, url, prioHoster = isBlockedHoster(streamUrl)
                if isBlocked: continue
                if url: self.sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': url, 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})

            return self.sources
        except:
            return self.sources

    def _resolve_dood_default_tls(self, stream_url):
        try:
            import random
            import re
            import string
            import time
            from urllib.parse import quote_plus, urljoin, urlparse
            from urllib.request import Request, build_opener, HTTPHandler, HTTPSHandler
            from urllib.error import HTTPError

            parsed = urlparse(stream_url)
            host = (parsed.hostname or '').lower()
            match_id = re.search(r'/(?:e|d)/([0-9A-Za-z]+)', parsed.path or '')
            if host not in ('vide0.net', 'vvide0.com') or not match_id:
                return None

            media_id = match_id.group(1)
            ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0.0.0 Safari/537.36'
            opener = build_opener(HTTPHandler(), HTTPSHandler())
            candidates = ['https://playmogo.com/e/' + media_id, stream_url]

            for page_url in candidates:
                try:
                    log_utils.log('[EINSCHALTEN-DOOD] Default-TLS page: %s' % page_url, log_utils.LOGINFO)
                    req = Request(page_url, headers={
                        'User-Agent': ua,
                        'Referer': self.base_link + '/',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    })
                    response = opener.open(req, timeout=8)
                    final_url = response.geturl()
                    html = response.read().decode('utf-8', 'replace')
                    status = getattr(response, 'status', 200)
                    log_utils.log('[EINSCHALTEN-DOOD] Page OK: status=%s final=%s bytes=%s' % (status, final_url, len(html)), log_utils.LOGINFO)

                    pattern = r"dsplayer\.hotkeys[^']+'([^']+).+?function\s*makePlay.+?return[^?]+([^\"]+)"
                    m = re.search(pattern, html, re.DOTALL)
                    if not m:
                        log_utils.log('[EINSCHALTEN-DOOD] pass_md5/token nicht gefunden', log_utils.LOGWARNING)
                        continue

                    pass_url = urljoin(final_url, m.group(1))
                    token = m.group(2)
                    req2 = Request(pass_url, headers={
                        'User-Agent': ua,
                        'Referer': final_url,
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': '*/*',
                    })
                    response2 = opener.open(req2, timeout=8)
                    base = response2.read().decode('utf-8', 'replace').strip()
                    status2 = getattr(response2, 'status', 200)
                    log_utils.log('[EINSCHALTEN-DOOD] pass_md5: status=%s bytes=%s' % (status2, len(base)), log_utils.LOGINFO)
                    if not base.startswith('http'):
                        continue

                    direct = base + ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10)) + token + str(int(time.time() * 1000))
                    headers = 'User-Agent=%s&Referer=%s' % (quote_plus(ua), quote_plus(final_url))
                    log_utils.log('[EINSCHALTEN-DOOD] Direct URL erzeugt: host=%s' % (urlparse(direct).hostname or ''), log_utils.LOGINFO)
                    return direct + '|' + headers
                except HTTPError as exc:
                    try:
                        cf = exc.headers.get('cf-mitigated', '')
                        server = exc.headers.get('server', '')
                    except Exception:
                        cf = ''
                        server = ''
                    log_utils.log('[EINSCHALTEN-DOOD] HTTPError %s | server=%s | cf=%s | %s' % (getattr(exc, 'code', '?'), server, cf, page_url), log_utils.LOGWARNING)
                except Exception as exc:
                    log_utils.log('[EINSCHALTEN-DOOD] Fehler %s: %s' % (type(exc).__name__, exc), log_utils.LOGWARNING)
            return None
        except Exception as exc:
            try:
                log_utils.log('[EINSCHALTEN-DOOD] Setup-Fehler %s: %s' % (type(exc).__name__, exc), log_utils.LOGWARNING)
            except Exception:
                pass
            return None

    def resolve(self, url):
        return  url

