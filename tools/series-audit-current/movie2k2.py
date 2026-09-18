# -*- coding: UTF-8 -*-
import re
import xbmc
from resources.lib.utils import isBlockedHoster
from resources.lib.control import getSetting
from resources.lib.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser
from scrapers.modules import cleantitle
from resources.lib.domain_manager import resolve_domain

try:
    from urllib import parse as urllib_parse
except ImportError:
    import urllib as urllib_parse

SITE_IDENTIFIER = 'movie2k2'
SITE_DOMAIN = 'movie2k.cx'
SITE_NAME = 'Movie2k2'


class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)
        self.language = ['de']
        self.domain = resolve_domain(SITE_IDENTIFIER, SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/search?q=%s'
        self.ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        sources = []
        if not titles:
            return sources
        logger.info('Load %s - Start run for: %s' % (SITE_NAME, titles[0]))
        links = self.search(titles, year, season, episode)
        if not links:
            logger.info('Load %s - No movie links found' % SITE_NAME)
            return sources

        for url in links:
            try:
                oRequest = cRequestHandler(url)
                oRequest.addHeaderEntry('User-Agent', self.ua)
                oRequest.addHeaderEntry('Referer', self.base_link)
                html = oRequest.request()
                if not html:
                    continue

                pattern = r"loadMirror\s*\(\s*'([^']+)'\s*\).*?>\s*(?:&nbsp;)*\s*([^<|\s|&]+)"
                isMatch, aResult = cParser().parse(html, pattern)
                if not isMatch:
                    continue

                logger.info('Load %s - Found %s potential mirrors' % (SITE_NAME, len(aResult)))
                for sStreamUrl, sHosterName in aResult:
                    if sStreamUrl.startswith('//'):
                        sStreamUrl = 'https:' + sStreamUrl
                    elif sStreamUrl.startswith('/'):
                        sStreamUrl = self.base_link + sStreamUrl

                    isBlocked, hoster, sFinalUrl, prioHoster = isBlockedHoster(sStreamUrl, isResolve=False)
                    if isBlocked:
                        continue

                    sources.append({
                        'source': hoster or sHosterName.replace('.com', '').replace('.to', '').strip(),
                        'quality': 'HD' if 'hd.gif' in html.lower() else 'SD',
                        'language': 'de',
                        'url': sFinalUrl or sStreamUrl,
                        'direct': False,
                        'prioHoster': prioHoster
                    })
            except Exception as e:
                logger.info('Load %s - Error in hoster parsing: %s' % (SITE_NAME, str(e)))
        return sources

    def search(self, titles, year, season, episode):
        results = []
        search_term = titles[0]
        target_tokens = [cleantitle.get(token) for token in re.split(r'\W+', search_term) if len(cleantitle.get(token)) > 2]

        def token_match(value):
            clean_value = cleantitle.get(value)
            return target_tokens and all(token in clean_value for token in target_tokens)

        try:
            query_url = self.search_link % urllib_parse.quote(search_term)
            oRequest = cRequestHandler(query_url)
            oRequest.addHeaderEntry('User-Agent', self.ua)
            html = oRequest.request()
            if not html:
                return []

            if 'loadMirror' in html:
                real_url = oRequest.getRealUrl()
                if not season or token_match(real_url):
                    return [real_url]

            pattern = r'href\s*=\s*["\']([^"\']*?/stream/[^"\']+)["\'][^>]*>.*?<strong>([^<]+)</strong>'
            isMatch, aResult = cParser().parse(html, pattern)
            if isMatch:
                target_clean = cleantitle.get(search_term)
                ranked = []
                for sPath, sName in aResult:
                    score = 0
                    clean_name = cleantitle.get(sName)
                    if target_clean == clean_name:
                        score = 100
                    elif target_clean in clean_name or clean_name in target_clean:
                        score = 70
                    elif token_match(sName):
                        score = 50
                    if season:
                        hay = '%s %s' % (sName, sPath)
                        if re.search(r'\b(?:s|staffel\s*|season\s*)0*%d\b' % int(season), hay, re.I):
                            score += 25
                    if score > 0:
                        full_url = sPath if sPath.startswith('http') else self.base_link + ('' if sPath.startswith('/') else '/') + sPath
                        ranked.append((score, full_url, sName))
                if ranked:
                    ranked.sort(key=lambda item: item[0], reverse=True)
                    results.append(ranked[0][1])

            if not results:
                short_term = search_term.split(' ')[0]
                if short_term != search_term:
                    query_url = self.search_link % urllib_parse.quote(short_term)
                    oRequest = cRequestHandler(query_url)
                    oRequest.addHeaderEntry('User-Agent', self.ua)
                    html = oRequest.request()
                    if 'loadMirror' in html:
                        real_url = oRequest.getRealUrl()
                        if token_match(real_url):
                            return [real_url]
                    isMatch, aResult = cParser().parse(html, pattern)
                    if isMatch:
                        for sPath, sName in aResult:
                            if token_match(sName):
                                full_url = sPath if sPath.startswith('http') else self.base_link + ('' if sPath.startswith('/') else '/') + sPath
                                results.append(full_url)
                                break
        except Exception as e:
            logger.info('Load %s - Search error: %s' % (SITE_NAME, str(e)))
        return results

    def resolve(self, url):
        return url
