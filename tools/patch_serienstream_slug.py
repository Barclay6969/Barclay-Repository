import hashlib
import pathlib
import re
import zipfile
import xml.etree.ElementTree as ET

root = pathlib.Path('.')
xdir = root / 'zips' / 'plugin.video.xship'
old_zip = xdir / 'plugin.video.xship-2026.07.07.zip'
new_version = '2026.07.08'
new_zip = xdir / f'plugin.video.xship-{new_version}.zip'

if new_zip.exists():
    print(f'{new_zip.name} already exists; nothing to do')
    raise SystemExit(0)
if not old_zip.exists():
    raise SystemExit(f'Missing source package: {old_zip}')

patched = False
addon_xml_bytes = None

resolver_replacement = r'''    def _get_http_session(self):
        try:
            session = getattr(self, '_http_session', None)
            if session is not None:
                return session

            import requests
            requests.packages.urllib3.disable_warnings()
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            })
            self._http_session = session
            return session
        except:
            return None

    def _extract_bridge_target(self, html, base_url):
        if not html:
            return None
        try:
            text = html_unescape(str(html)).replace('\\/', '/')
            text = text.replace('\\u002F', '/').replace('\\u003A', ':')

            candidates = []
            patterns = [
                r'<iframe[^>]+src=["\']([^"\']+)',
                r'(?:window\.)?location(?:\.href)?\s*=\s*["\']([^"\']+)',
                r'["\'](?:url|src|href)["\']\s*:\s*["\']([^"\']+)',
                r'(?:url|src|href)\s*=\s*["\']([^"\']+)',
                r'postMessage\(\s*["\'](https?://[^"\']+)',
            ]
            for pattern in patterns:
                candidates.extend(re.findall(pattern, text, re.IGNORECASE | re.DOTALL))

            # Last resort for bridge pages that embed the hoster URL directly in JS.
            candidates.extend(re.findall(r'https?://[^\s"\'<>]+', text, re.IGNORECASE))

            seen = set()
            for candidate in candidates:
                candidate = html_unescape(candidate).replace('\\/', '/').strip()
                if not candidate or candidate in seen:
                    continue
                seen.add(candidate)

                target = urljoin(base_url, candidate)
                if not target or not target.startswith(('http://', 'https://')):
                    continue
                if self._is_serienstream_url(target):
                    # Internal bridge hops are allowed and will be followed by
                    # _resolve_with_session().
                    return target

                lower = target.lower().split('?', 1)[0]
                if lower.endswith(('.js', '.css', '.png', '.jpg', '.jpeg', '.svg', '.ico', '.woff', '.woff2')):
                    continue

                if log_utils:
                    logger.info('SerienStream - Bridge target: %s' % target[:100])
                return target
        except Exception as e:
            if log_utils:
                logger.info('SerienStream - Bridge parse error: %s' % str(e))
        return None

    def _resolve_with_session(self, url, referer):
        session = self._get_http_session()
        if session is None:
            return None

        try:
            # Seed the same HTTP session with the episode page first. SerienStream's
            # /r?t= bridge can depend on cookies/session state from that page.
            if referer and referer != url:
                try:
                    session.get(
                        referer,
                        headers={'Referer': self.base_link},
                        allow_redirects=True,
                        verify=False,
                        timeout=8
                    )
                except:
                    pass

            current = url
            current_referer = referer
            for _hop in range(4):
                response = session.get(
                    current,
                    headers={'Referer': current_referer},
                    allow_redirects=True,
                    verify=False,
                    timeout=10
                )
                final_url = response.url or current

                if log_utils:
                    logger.info('SerienStream - Session resolve hop %d: %s' % (_hop + 1, final_url[:100]))

                if final_url and not self._is_serienstream_url(final_url):
                    return final_url

                bridge_target = self._extract_bridge_target(response.text, final_url)
                if bridge_target:
                    if not self._is_serienstream_url(bridge_target):
                        return bridge_target
                    if bridge_target != current:
                        current_referer = final_url
                        current = bridge_target
                        continue

                if not self._is_frame_bridge(response.text):
                    location = response.headers.get('Location')
                    target = self._external_redirect_target(final_url, location)
                    if target:
                        return target
                break
        except Exception as e:
            if log_utils:
                logger.info('SerienStream - Session resolve error: %s' % str(e))
        return None

    def resolve(self, url):
        try:
            if log_utils:
                logger.info('SerienStream - Resolving: %s' % url[:80])

            referer = getattr(self, 'episode_referer', self.base_link)
            internal_redirect = self._is_internal_redirect_url(url)

            # 2026.07.08: use one persistent requests.Session, seed it with the
            # episode page, then follow redirects/bridge hops. This mirrors the
            # working Lastship approach and preserves cookies plus Referer.
            resolved = self._resolve_with_session(url, referer)
            if resolved:
                if log_utils:
                    logger.info('SerienStream - Resolved via persistent session: %s' % resolved[:100])
                return resolved

            # Keep cRequestHandler as a compatibility fallback, but parse a frame
            # bridge instead of discarding it immediately.
            try:
                oRequest = cRequestHandler(url, caching=False, ignoreErrors=True)
                oRequest.addHeaderEntry('User-Agent', 'Mozilla/5.0')
                oRequest.addHeaderEntry('Referer', referer)
                response_html = oRequest.request()
                final_url = oRequest.getRealUrl()

                if final_url and final_url != url and not self._is_serienstream_url(final_url):
                    if log_utils:
                        logger.info('SerienStream - Resolved via cRequestHandler: %s' % final_url[:100])
                    return final_url

                bridge_target = self._extract_bridge_target(response_html, final_url or url)
                if bridge_target and not self._is_serienstream_url(bridge_target):
                    return bridge_target
            except:
                pass

            if internal_redirect:
                if log_utils:
                    logger.info('SerienStream - Internal redirect unresolved after session+bridge handling')
                return None

            if log_utils:
                logger.info('SerienStream - Could not resolve, returning original URL')
            return url

        except Exception as e:
            if log_utils:
                logger.info('SerienStream - Resolve error: %s' % str(e))
            return None if self._is_internal_redirect_url(url) else url

'''

with zipfile.ZipFile(old_zip, 'r') as zin, zipfile.ZipFile(new_zip, 'w', zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        lower = item.filename.lower()

        if lower.endswith('/serienstream.py') or lower == 'serienstream.py':
            text = data.decode('utf-8').replace('\r\n', '\n')
            pattern = r'    def _resolve_http_redirect\(self, url, referer\):[\s\S]*?(?=    @staticmethod\n    def _getLogin\(\):)'
            text, count = re.subn(pattern, lambda _m: resolver_replacement, text, count=1)
            if count != 1:
                raise SystemExit(f'Expected SerienStream resolver block not found in {item.filename}')
            data = text.encode('utf-8')
            patched = True
            print(f'Patched persistent session/frame bridge resolver in {item.filename}')

        if lower.endswith('/addon.xml') or lower == 'addon.xml':
            try:
                addon = ET.fromstring(data)
            except Exception:
                addon = None
            if addon is not None and addon.attrib.get('id') == 'plugin.video.xship':
                addon.attrib['version'] = new_version
                data = ET.tostring(addon, encoding='utf-8', xml_declaration=True)
                addon_xml_bytes = data
                print(f'Updated addon.xml to {new_version}')

        zout.writestr(item, data)

if not patched:
    new_zip.unlink(missing_ok=True)
    raise SystemExit('serienstream.py not patched')
if addon_xml_bytes is None:
    new_zip.unlink(missing_ok=True)
    raise SystemExit('plugin.video.xship addon.xml not found')

repo_src = root / 'addons' / 'repository.barclay' / 'addon.xml'
repo_xml = repo_src.read_text(encoding='utf-8-sig').strip()
xship_xml = addon_xml_bytes.decode('utf-8-sig').strip()
repo_xml = re.sub(r'^<\?xml[^>]*\?>\s*', '', repo_xml)
xship_xml = re.sub(r'^<\?xml[^>]*\?>\s*', '', xship_xml)
feed = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n' + repo_xml + '\n\n' + xship_xml + '\n</addons>\n'
(root / 'zips' / 'addons.xml').write_text(feed, encoding='utf-8', newline='\n')
(root / 'zips' / 'addons.xml.md5').write_text(hashlib.md5(feed.encode('utf-8')).hexdigest() + '\n', encoding='ascii', newline='\n')

print(f'Created {new_zip}')
