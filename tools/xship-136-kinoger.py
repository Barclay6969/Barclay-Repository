# -*- coding: UTF-8 -*-
import ast
import re
from resources.lib.control import getSetting, urlparse
from resources.lib.requestHandler import cRequestHandler
from resources.lib.domain_manager import resolve_domain
from scrapers.modules import dom_parser, cleantitle, source_utils
from resources.lib import log_utils, hoster_compat

SITE_IDENTIFIER = 'kinoger'
SITE_DOMAIN = 'kinoger.com'
SITE_NAME = 'KINOGER'
DOOD_DOMAINS = ('dood.sbs','dood.re','dood.cx','dood.la','dood.so','dood.pm','dood.to','dood.watch')
SPECIAL_HOSTS = ('kinoger.embed4me.vip','kinoger.seekplays.pro','kinoger.pw','kinoger.be','kinoger.ru','veev.pro')


def _host(url):
    try:
        return (urlparse(str(url or '').split('|',1)[0].split('$$',1)[0]).hostname or '').lower()
    except Exception:
        return ''


def _rewrite_dood(url):
    value = str(url or '')
    for domain in DOOD_DOMAINS:
        if domain in value.lower():
            value = value.replace(domain, 'veev.to')
    return value


class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)
        self.language = ['de']
        self.domain = resolve_domain(SITE_IDENTIFIER, SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/index.php?do=search&subaction=search&search_start=1&full_search=0&result_from=1&titleonly=3&story=%s'
        self.sources = []

    @staticmethod
    def _quality(value):
        q = str(value or '')
        if '2160' in q or '4K' in q: return '4K'
        if '1440' in q or '2K' in q: return '1440p'
        if q == 'HD+': return '1080p'
        if q == 'HD': return '720p'
        if '480' in q: return '480p'
        if '360' in q: return '360p'
        return 'SD'

    def _find_page(self, titles, year, season):
        wanted = [cleantitle.get(x) for x in titles or [] if x]
        years = [str(year), str(int(year) + 1)] if not season else ['']
        for title in titles or []:
            try:
                req = cRequestHandler(self.search_link % title)
                req.removeBreakLines(False); req.removeNewLines(False)
                req.cacheTime = 60 * 60 * 12
                html = req.request()
                blocks = dom_parser.parse_dom(html, 'div', attrs={'class':'title'})
                anchors = dom_parser.parse_dom(blocks, 'a')
                for item in anchors:
                    try:
                        href = item.attrs['href']; text = item.content
                        parsed = re.findall(r'(.*?)\((\d+)', text)
                        if not parsed: continue
                        name, found_year = parsed[0]
                        clean = cleantitle.get(name)
                        if season:
                            if 'staffel' in clean and any(key in clean for key in wanted):
                                return href
                        elif any(key in clean for key in wanted) and found_year in years:
                            return href
                    except Exception:
                        continue
            except Exception:
                continue
        return ''

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        self.sources = []
        page = self._find_page(titles, year, season)
        if not page:
            return self.sources
        try:
            req = cRequestHandler(page)
            req.cacheTime = 60 * 60 * 12
            html = req.request()
            qualities = re.findall(r'title="Stream.(.+?)"', html)
            links = re.findall(r'.show.+?,(\[\[.+?\]\])', html)
            if not links:
                return self.sources
            sidx = int(season) - 1 if season else 0
            eidx = int(episode) - 1 if episode else 0
            for idx, block in enumerate(links):
                try:
                    table = ast.literal_eval(block)
                    url = str(table[sidx][eidx]).strip()
                    if not url:
                        continue
                    host = _host(url)
                    quality = self._quality(qualities[idx] if idx < len(qualities) else '')
                    display = host
                    if hoster_compat.is_supported_host(host):
                        display = hoster_compat.display_name(host)
                    else:
                        valid, known = source_utils.is_host_valid(url, hostDict)
                        if valid and known:
                            display = known
                    if host == 'kinoger.be' and '$$' not in url:
                        url += '$$https://kinoger.com/'
                    url = _rewrite_dood(url)
                    self.sources.append({'source': display or host, 'quality': quality, 'language':'de',
                                         'url': url, 'direct': False, 'priority': int(self.priority),
                                         'prioHoster': 100})
                except Exception:
                    continue
            if not self.sources:
                log_utils.log('Kinoger: kein Provider - %s' % (titles[0] if titles else ''), log_utils.LOGINFO)
        except Exception:
            pass
        return self.sources

    def resolve(self, url):
        return url
