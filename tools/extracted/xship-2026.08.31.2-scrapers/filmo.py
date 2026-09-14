# -*- coding: UTF-8 -*-

import json
import re
import requests
from html import unescape
from urllib.parse import quote_plus, urljoin

from resources.lib.control import getSetting
from resources.lib.requestHandler import cRequestHandler
from resources.lib.tools import logger
from resources.lib.utils import isBlockedHoster
from scrapers.modules import cleantitle

SITE_IDENTIFIER = 'filmo'
SITE_DOMAIN = 'filmo.to'
SITE_NAME = 'Filmo'

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

try:
    requests.packages.urllib3.disable_warnings()
except Exception:
    pass


class source:
    def _dbg(self, message):
        try:
            logger.info('[FILMO-DEBUG] %s' % message)
        except Exception:
            pass

    def __init__(self):
        self.priority = 1
        self.language = ['de', 'en']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_link = self.base_link + '/search?q=%s'
        self.suggest_link = self.base_link + '/search/suggest?q=%s'
        self.sources = []
        self._seen = set()
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': UA,
            'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
            'Connection': 'close'
        })

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        self._dbg('run start | titles=%s | year=%s | season=%s | imdb=%s' % (titles, year, season, imdb))
        try:
            _pf = self._session.get(
                self.base_link + '/',
                timeout=12,
                verify=False,
                allow_redirects=True
            )
            self._dbg('FILMO Session Preflight | status=%s | cookies=%s' % (
                _pf.status_code, len(self._session.cookies)
            ))
        except Exception as exc:
            self._dbg('FILMO Session Preflight Fehler: %s' % exc)
        if int(season or 0) > 0:
            self._dbg('Abbruch: Serieninhalt')
            return self.sources
        try:
            clean_titles = set([self._norm_title(title) for title in titles if title])
            clean_titles.discard('')
            candidates = self._candidates(titles)

            # Fast path: Wenn die Suchergebnisse bereits einen eindeutigen
            # Titel-Treffer enthalten, muessen nicht erst zahlreiche fremde
            # Filmseiten geladen werden. Falls kein exakter Treffer vorhanden
            # ist, bleibt das bisherige breite Fallback unveraendert erhalten.
            exact_candidates = [
                item for item in candidates
                if self._norm_title(item.get('title')) in clean_titles
            ]
            if exact_candidates:
                self._dbg('Exakte Kandidaten: %s/%s' % (len(exact_candidates), len(candidates)))
                candidates = exact_candidates

            self._dbg('Kandidaten gefunden: %s' % len(candidates))
            for candidate in candidates:
                self._dbg('Kandidat: %s | %s' % (candidate.get('title'), candidate.get('url')))
                page = self._get(candidate.get('url'), referer=self.base_link + '/')
                if not page:
                    self._dbg('Filmseite leer: %s' % candidate.get('url'))
                    continue
                self._dbg('Filmseite geladen: %s Bytes' % len(page))
                title = self._page_title(page) or candidate.get('title')
                if not self._matches(title, clean_titles, year, page):
                    self._dbg('Titel/Jahr Match fehlgeschlagen: %s' % title)
                    continue
                self._dbg('Titel/Jahr Match OK: %s' % title)
                before_sources = len(self.sources)
                self._add_chips(candidate.get('url'), page)
                self._dbg('Streams nach _add_chips: %s' % len(self.sources))

                # Ein validierter exakter Film-Treffer mit Streams ist das
                # Ziel. Weitere gleichnamige/fremde Kandidaten wuerden nur
                # zusaetzliche Requests verursachen.
                if len(self.sources) > before_sources:
                    break
                if len(self.sources) >= 20:
                    break
        except Exception as exc:
            logger.error('[Filmo] Fehler: %s' % exc)
            self._dbg('run Exception: %s' % exc)
        self._dbg('run Ende | Streams=%s' % len(self.sources))
        return self.sources

    def resolve(self, url):
        return url

    def _candidates(self, titles):
        self._dbg('_candidates start')
        result = []
        seen = set()
        for title in titles:
            if not title:
                continue
            suggested = self._suggest(title)
            searched = self._search(title)
            self._dbg('Titel "%s": suggest=%s search=%s' % (title, len(suggested), len(searched)))
            for item in suggested + searched:
                url = item.get('url') or ''
                if not url:
                    continue
                url = urljoin(self.base_link, url)
                if '/movies/' not in url or url in seen:
                    continue
                seen.add(url)
                result.append({'title': item.get('title') or '', 'url': url})
                if len(result) >= 30:
                    return result
        return result

    def _suggest(self, title):
        self._dbg('_suggest: %s' % title)
        try:
            headers = {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
            payload, status, _real_url = self._request(
                self.suggest_link % quote_plus(title),
                referer=self.base_link + '/',
                headers=headers,
                caching=True
            )
            self._dbg('_suggest Status=%s URL=%s payload=%s' % (status, _real_url, len(payload or '')))
            if status not in ('200', '301'):
                return []
            data = json.loads(payload or '{}')
            items = []
            for movie in data.get('movies') or []:
                if isinstance(movie, dict):
                    items.append({'title': movie.get('title') or '', 'url': movie.get('url') or ''})
            return items
        except Exception:
            return []

    def _search(self, title):
        self._dbg('_search: %s' % title)
        html = self._get(self.search_link % quote_plus(title), referer=self.base_link + '/')
        if not html:
            self._dbg('_search: leere Antwort')
            return []
        self._dbg('_search HTML=%s Bytes' % len(html))
        items = []
        seen = set()
        for match in re.finditer(r'(?is)<a\b[^>]+href=["\']([^"\']*/movies/[^"\']+)["\'][^>]*>(.*?)</a>', html):
            url = unescape(match.group(1)).strip()
            if url in seen:
                continue
            seen.add(url)
            body = match.group(2)
            title = (
                self._class_text(body, 'popular-spotlight-card__title')
                or self._class_text(body, 'movie-poster-grid-card__title')
                or self._attr_text(body, 'alt')
            )
            items.append({'title': title, 'url': url})
        return items

    def _add_chips(self, page_url, html):
        csrf = self._csrf_token(html)
        open_mint = self._open_mint_url(html) or (self.base_link + '/n')
        rows = self._provider_rows(html)
        self._dbg('_add_chips | csrf=%s | openMint=%s | rows=%s' % ('ja' if csrf else 'nein', open_mint, len(rows)))
        for row in rows:
            self._dbg('Provider-Row Sprache=%s Chips=%s' % (row.get('language'), len(row.get('chips') or [])))
            language = self._language(row.get('language'))
            if language not in ('de', 'en'):
                continue
            for chip in row.get('chips') or []:
                self._dbg('Mint start | hoster=%s | p=%s' % (chip.get('hoster'), str(chip.get('p'))[:60]))
                final_url = self._mint(open_mint, chip.get('p'), csrf, page_url)
                self._dbg('Mint Ergebnis: %s' % final_url)
                if not final_url or final_url in self._seen:
                    continue
                self._seen.add(final_url)

                is_blocked, hoster, clean_url, prio_hoster = isBlockedHoster(final_url, isResolve=False)
                self._dbg('Hostercheck | blocked=%s | hoster=%s | url=%s' % (is_blocked, hoster, clean_url))
                if is_blocked or not clean_url:
                    continue

                quality = self._quality(chip.get('metadata') or [])
                info = ' | '.join([value for value in chip.get('metadata') or [] if value and value != quality])
                if row.get('language'):
                    info = ('%s | %s' % (row.get('language'), info)).strip(' |')

                self.sources.append({
                    'source': hoster or chip.get('hoster') or SITE_NAME,
                    'quality': quality,
                    'language': language,
                    'url': clean_url,
                    'direct': False,
                    'debridonly': False,
                    'prioHoster': prio_hoster,
                    'info': info
                })

    def _provider_rows(self, html):
        rows = []
        pattern = re.compile(
            r'(?is)<div class=["\']provider-row["\'][^>]*>.*?'
            r'<span class=["\']provider-row__lang["\']>(.*?)</span>.*?'
            r'<div class=["\']provider-row__chips["\']>(.*?)(?=<div class=["\']provider-row["\']|</section>|<div class=["\']mt-2|\Z)'
        )
        for match in pattern.finditer(html or ''):
            row_html = match.group(2)
            chips = []
            for chip_match in re.finditer(r'(?is)<div\b[^>]*data-provider-chip\b[^>]*>.*?</div>', row_html):
                chip_html = chip_match.group(0)
                p_value = self._attr_text_raw(chip_html, 'data-p')
                if not p_value:
                    continue
                chips.append({
                    'p': p_value,
                    'hoster': self._attr_text(chip_html, 'aria-label') or self._class_text(chip_html, 'provider-chip__name'),
                    'metadata': self._metadata(chip_html),
                })
            if chips:
                rows.append({'language': self._clean(match.group(1)), 'chips': chips})
        return rows

    def _mint(self, open_mint, p_value, csrf, referer):
        if not p_value:
            self._dbg('_mint: p leer')
            return ''
        try:
            # WICHTIG: FILMO bindet den ausgegebenen Mint-Token an die HTTP-Session.
            # Deshalb müssen POST /n und GET /n/<token> zwingend über dieselbe
            # requests.Session laufen. Ein Wechsel zwischen cRequestHandler und
            # requests.Session führt reproduzierbar zu HTTP 404.
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': self.base_link,
                'Referer': referer or self.base_link + '/',
            }
            if csrf:
                headers['X-CSRF-TOKEN'] = csrf

            post_response = self._session.post(
                open_mint,
                json={'p': p_value},
                headers=headers,
                timeout=12,
                verify=False,
                allow_redirects=True
            )
            self._dbg('_mint Session POST | status=%s | real=%s | payload=%s | cookies=%s' % (
                post_response.status_code,
                post_response.url or open_mint,
                len(post_response.text or ''),
                len(self._session.cookies)
            ))

            if post_response.status_code not in (200, 201):
                return ''

            try:
                token = (post_response.json() or {}).get('x')
            except Exception:
                token = (json.loads(post_response.text or '{}') or {}).get('x')

            self._dbg('_mint Token vorhanden=%s' % bool(token))
            if not token:
                return ''

            mint_url = open_mint.rstrip('/') + '/' + quote_plus(token)
            redirect_headers = {
                'Referer': referer or self.base_link + '/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }

            response = self._session.get(
                mint_url,
                headers=redirect_headers,
                timeout=12,
                verify=False,
                allow_redirects=True
            )

            redirect_html = response.text or ''
            real_url = response.url or mint_url
            self._dbg('_mint Session GET | status=%s | real=%s | html=%s | redirects=%s | cookies=%s' % (
                response.status_code,
                real_url,
                len(redirect_html),
                len(response.history),
                len(self._session.cookies)
            ))

            # Idealfall: FILMO hat direkt zum externen Hoster weitergeleitet.
            if real_url and real_url != mint_url and '/n/' not in real_url:
                return real_url

            # Manche Varianten liefern das Ziel als Location ohne automatischen
            # Redirect oder als Link im HTML.
            location = response.headers.get('Location', '')
            if location:
                location = urljoin(self.base_link, location)
                if '/n/' not in location:
                    return location

            match = re.search(r'<a\b[^>]*href=["\']([^"\']+)["\']', redirect_html, re.I)
            if match:
                href = urljoin(self.base_link, unescape(match.group(1)).strip())
                if href and '/n/' not in href:
                    return href

            return ''
        except Exception as exc:
            logger.error('[Filmo] Mint Session Fehler: %s' % exc)
            self._dbg('_mint Session Exception: %s' % exc)
            return ''

    def _get(self, url, referer=None):
        if not url:
            return ''
        try:
            payload, status, _real_url = self._request(
                url,
                referer=referer or self.base_link + '/',
                headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'},
                caching=False
            )
            if status not in ('200', '301'):
                return ''
            return payload
        except Exception:
            return ''

    def _request(self, url, referer=None, headers=None, post=None, jspost=False, caching=False):
        # FILMO koppelt CSRF- und Mint-Token an die aktuelle Web-Session.
        # Deshalb laufen ALLE FILMO-Requests über dieselbe requests.Session.
        try:
            req_headers = dict(headers or {})
            if referer:
                req_headers['Referer'] = referer

            if post is not None:
                if jspost:
                    response = self._session.post(
                        url,
                        json=post,
                        headers=req_headers,
                        timeout=12,
                        verify=False,
                        allow_redirects=True
                    )
                else:
                    response = self._session.post(
                        url,
                        data=post,
                        headers=req_headers,
                        timeout=12,
                        verify=False,
                        allow_redirects=True
                    )
            else:
                response = self._session.get(
                    url,
                    headers=req_headers,
                    timeout=12,
                    verify=False,
                    allow_redirects=True
                )

            status = '301' if response.history else str(response.status_code)
            self._dbg('SessionRequest | method=%s | status=%s | real=%s | payload=%s | cookies=%s' % (
                'POST' if post is not None else 'GET',
                status,
                response.url or url,
                len(response.text or ''),
                len(self._session.cookies)
            ))
            return response.text or '', status, response.url or url
        except Exception as exc:
            logger.error('[Filmo] Session-Request Fehler: %s' % exc)
            self._dbg('SessionRequest Exception: %s' % exc)
            return '', '0', url

    @staticmethod
    def _norm_title(title):
        # cleantitle behandelt den normalen ASCII-Bindestrich, aber nicht
        # zuverlaessig alle typografischen Unicode-Striche. Das fuehrte z.B.
        # bei 'Obsession – Du sollst mich lieben' zu einem False-Negative.
        text = str(title or '')
        for dash in ('–', '—', '−', '‐', '‑', '﹘', '﹣', '－'):
            text = text.replace(dash, '-')
        return cleantitle.get(text) or ''

    def _matches(self, title, clean_titles, year, html):
        clean_title = self._norm_title(title)
        if clean_title not in clean_titles:
            return False
        page_year = self._year(html)
        try:
            if year and page_year and abs(int(page_year) - int(year)) > 1:
                return False
        except Exception:
            pass
        return True

    def _year(self, html):
        release = self._detail_value(html, 'Erscheinungsdatum')
        match = re.search(r'\b(19\d{2}|20\d{2})\b', release or '')
        if match:
            return match.group(1)
        match = re.search(r'<span[^>]*class=["\'][^"\']*ft-meta-label[^"\']*["\'][^>]*>\s*(19\d{2}|20\d{2})\s*</span>', html or '', re.I)
        return match.group(1) if match else ''

    def _detail_value(self, html, label):
        match = re.search(
            r'(?is)<h3[^>]*class=["\'][^"\']*section-headline[^"\']*["\'][^>]*>\s*%s\s*</h3>.*?'
            r'<dd[^>]*class=["\'][^"\']*entry-description[^"\']*["\'][^>]*>(.*?)</dd>' % re.escape(label),
            html or ''
        )
        return self._clean(match.group(1)) if match else ''

    def _page_title(self, html):
        match = re.search(r'<h1[^>]*>(.*?)</h1>', html or '', re.S | re.I)
        if match:
            return self._clean(match.group(1))
        match = re.search(r'<title[^>]*>(.*?)</title>', html or '', re.S | re.I)
        title = self._clean(match.group(1)) if match else ''
        return re.sub(r'\s+jetzt kostenlos streamen\s+.*$', '', title, flags=re.I)

    def _csrf_token(self, html):
        return self._meta_content(html, 'csrf-token')

    def _open_mint_url(self, html):
        match = re.search(r'"openMint"\s*:\s*"([^"]+)"', html or '')
        return self._json_url(match.group(1)) if match else ''

    def _metadata(self, chip_html):
        values = []
        for match in re.finditer(r'(?is)<span class=["\']provider-chip__metadata-tag["\']>(.*?)</span>', chip_html or ''):
            value = self._clean(match.group(1))
            if value:
                values.append(value)
        return values

    @staticmethod
    def _quality(values):
        text = ' '.join([str(value or '') for value in values]).lower()
        if '2160' in text or '4k' in text:
            return '4K'
        if '1440' in text:
            return '1440p'
        if '1080' in text:
            return '1080p'
        if '720' in text:
            return '720p'
        if '480' in text or 'sd' in text:
            return 'SD'
        return 'HD'

    @staticmethod
    def _language(value):
        text = str(value or '').strip().lower()
        if text in ('deutsch', 'german', 'de', 'ger'):
            return 'de'
        if text in ('english', 'englisch', 'en', 'eng'):
            return 'en'
        return 'unknown'

    def _class_text(self, html, class_name):
        match = re.search(r'(?is)<[^>]+class=["\'][^"\']*%s[^"\']*["\'][^>]*>(.*?)</[^>]+>' % re.escape(class_name), html or '')
        return self._clean(match.group(1)) if match else ''

    def _attr_text(self, html, attr):
        return self._clean(self._attr_text_raw(html, attr))

    @staticmethod
    def _attr_text_raw(html, attr):
        match = re.search(r'\b%s=["\']([^"\']+)["\']' % re.escape(attr), html or '', re.S | re.I)
        return unescape(match.group(1)).strip() if match else ''

    def _meta_content(self, html, name):
        match = re.search(r'<meta[^>]+name=["\']%s["\'][^>]+content=["\']([^"\']*)["\']' % re.escape(name), html or '', re.S | re.I)
        return self._clean(match.group(1)) if match else ''

    @staticmethod
    def _json_url(value):
        return value.replace('\\/', '/').replace('\\u0026', '&').replace('\\u003d', '=')

    @staticmethod
    def _clean(value):
        value = unescape(value or '')
        value = re.sub(r'<[^>]+>', ' ', value)
        value = re.sub(r'\s+', ' ', value)
        return value.strip()
