# -*- coding: UTF-8 -*-
import ast
import re
from resources.lib.control import getSetting, urlparse
from resources.lib.requestHandler import cRequestHandler
from resources.lib.domain_manager import resolve_domain
from scrapers.modules import dom_parser, cleantitle, source_utils
from resources.lib import log_utils, hoster_compat

SITE_IDENTIFIER = 'kinoger'
SITE_DOMAIN = 'kinoger.fun'
SITE_NAME = 'KINOGER'
DOOD_DOMAINS = ('dood.sbs','dood.re','dood.cx','dood.la','dood.so','dood.pm','dood.to','dood.watch')
SPECIAL_HOSTS = ('kinoger.embed4me.vip','kinoger.seekplays.pro','kinoger.pw','kinoger.be','kinoger.ru','veev.pro')
BLOCKED_HOSTS = ('youtube.com','www.youtube.com','m.youtube.com','youtu.be','youtube-nocookie.com','www.youtube-nocookie.com')


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
            log_utils.log('[KINOGER-FUN-TEST] kein Seitentreffer: %s' % (titles[0] if titles else ''), log_utils.LOGINFO)
            return self.sources
        try:
            req = cRequestHandler(page)
            req.cacheTime = 60 * 60 * 12
            html = req.request()
            qualities = re.findall(r'title=["\']Stream\.([^"\']+)["\']', html, re.I)
            sidx = int(season) - 1 if season else 0
            eidx = int(episode) - 1 if episode else 0
            seen = set()

            def add_source(raw_url, quality_index=0):
                try:
                    url = str(raw_url or '').strip().replace('&amp;', '&')
                    if not url:
                        return
                    if url.startswith('//'):
                        url = 'https:' + url
                    elif url.startswith('/'):
                        # Current KinoGer pages expose internal /vod/ links in addition
                        # to external hosters. ResolveURL cannot use these as hosters.
                        if url.startswith('/vod/'):
                            return
                        url = self.base_link + url

                    raw_lower = str(url or '').lower()
                    if ('youtube.com' in raw_lower or 'youtu.be' in raw_lower or
                            'youtube-nocookie.com' in raw_lower or 'plugin.video.youtube' in raw_lower):
                        log_utils.log('[KINOGER-FUN-TEST] YouTube-URL blockiert: %s' % str(url)[:120], log_utils.LOGINFO)
                        return

                    host = _host(url)
                    if not host:
                        return
                    if host in BLOCKED_HOSTS or host.endswith('.youtube.com') or host.endswith('.youtube-nocookie.com'):
                        log_utils.log('[KINOGER-FUN-TEST] YouTube-Host blockiert: %s' % host, log_utils.LOGINFO)
                        return

                    quality_label = qualities[quality_index] if quality_index < len(qualities) else ''
                    quality = self._quality(quality_label)
                    # Keep KinoGer-native host names visible. This also makes it obvious
                    # in Kodi when KinoGer serves FSST / kinoger.ru / kinoger.be again.
                    if 'fsst' in host or 'incvideo' in host:
                        display = 'FSST'
                    elif host == 'kinoger.ru':
                        display = 'KinoGer.ru'
                    elif host == 'kinoger.be':
                        display = 'KinoGer.be'
                    else:
                        display = host
                        if hoster_compat.is_supported_host(host):
                            display = hoster_compat.display_name(host)
                        else:
                            valid, known = source_utils.is_host_valid(url, hostDict)
                            if valid and known:
                                display = known

                    if 'youtube' in str(display or '').lower():
                        log_utils.log('[KINOGER-FUN-TEST] YouTube-Anzeigename blockiert: %s' % display, log_utils.LOGINFO)
                        return

                    if host == 'kinoger.be' and '$$' not in url:
                        url += '$$https://kinoger.fun/'

                    url = _rewrite_dood(url)
                    dedupe = str(url).split('$$', 1)[0]
                    if dedupe in seen:
                        return
                    seen.add(dedupe)

                    self.sources.append({
                        'source': display or host,
                        'quality': quality,
                        'language': 'de',
                        'url': url,
                        'direct': False,
                        'priority': int(self.priority),
                        'prioHoster': 100
                    })
                except Exception:
                    return

            # Current layout: Hoster buttons expose data-link URLs. For series, use
            # only the requested episode block when KinoGer supplies serie-S_E IDs.
            data_html = html
            if season and episode:
                episode_pattern = (
                    r'<li[^>]+id=["\']serie-%d_%d["\'][^>]*>.*?'
                    r'<ul[^>]*>(.*?)</ul>\s*</li>'
                ) % (int(season), int(episode))
                match = re.search(episode_pattern, html, re.S | re.I)
                if match:
                    data_html = match.group(1)

            # Pair every data-link with its nearby visible label. KinoGer also
            # places non-playable buttons such as Premium Hoster / Trailer beside
            # the real mirrors. Those must never enter xShip's playable source list.
            data_links = []
            skipped_labels = []
            for match in re.finditer(
                    r'data-link\s*=\s*["\']([^"\']+)["\']',
                    data_html, re.I):
                data_url = match.group(1)
                # Keep the context deliberately local so words elsewhere on the page
                # cannot accidentally suppress a valid hoster.
                start = max(0, data_html.rfind('<', 0, match.start()))
                end = data_html.find('</', match.end())
                if end < 0 or end - match.end() > 320:
                    end = min(len(data_html), match.end() + 220)
                else:
                    end = min(len(data_html), data_html.find('>', end) + 1)
                context = data_html[start:end]
                label = re.sub(r'<[^>]+>', ' ', context)
                label = re.sub(r'\s+', ' ', label).strip()
                low_label = label.lower()
                if (re.search(r'\bpremium(?:\s+hoster)?\b', low_label) or
                        re.search(r'\btrailer\b', low_label) or
                        re.search(r'\byoutube\b', low_label)):
                    skipped_labels.append(label[:100] or 'unbekannt')
                    log_utils.log(
                        '[KINOGER-FUN-TEST] Nicht-Video data-link blockiert: %s | %s' %
                        (label[:100] or 'unbekannt', str(data_url)[:100]),
                        log_utils.LOGINFO
                    )
                    continue
                data_links.append(data_url)

            raw_hosts = []
            for raw in data_links:
                try:
                    value = str(raw or '').strip().replace('&amp;', '&')
                    raw_hosts.append(_host(value) or value[:60])
                except Exception:
                    pass
            log_utils.log('[KINOGER-FUN-TEST] data-link hosts: %s' % ', '.join(raw_hosts), log_utils.LOGINFO)
            if skipped_labels:
                log_utils.log('[KINOGER-FUN-TEST] blockierte Labels: %s' % ' | '.join(skipped_labels), log_utils.LOGINFO)
            for idx, data_url in enumerate(data_links):
                add_source(data_url, idx)

            # Keep the old KinoGer JavaScript-array path as a fallback. It may also
            # coexist with data-link on some titles, therefore sources are deduped.
            legacy_links = re.findall(r'\.show.+?,(\[\[.+?\]\])', html)
            for idx, block in enumerate(legacy_links):
                try:
                    table = ast.literal_eval(block)
                    url = str(table[sidx][eidx]).strip()
                    add_source(url, idx)
                except Exception:
                    continue

            # Final safety net: KinoGer must never expose YouTube/trailer entries as playable sources.
            self.sources = [item for item in self.sources if not (
                'youtube' in str(item.get('source') or '').lower() or
                'youtube.com' in str(item.get('url') or '').lower() or
                'youtu.be' in str(item.get('url') or '').lower() or
                'youtube-nocookie.com' in str(item.get('url') or '').lower() or
                'plugin.video.youtube' in str(item.get('url') or '').lower()
            )]

            log_utils.log(
                '[KINOGER-FUN-TEST] %s | page=%s | data-link=%d | legacy=%d | sources=%d' % (
                    titles[0] if titles else '', page, len(data_links), len(legacy_links), len(self.sources)
                ),
                log_utils.LOGINFO
            )
            if not self.sources:
                log_utils.log('Kinoger: kein Provider - %s' % (titles[0] if titles else ''), log_utils.LOGINFO)
        except Exception as exc:
            log_utils.log('[KINOGER-FUN-TEST] Fehler: %s' % str(exc), log_utils.LOGINFO)
        return self.sources

    def resolve(self, url):
        return url