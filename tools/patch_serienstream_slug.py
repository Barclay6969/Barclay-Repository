import hashlib
import pathlib
import re
import zipfile
import xml.etree.ElementTree as ET

root = pathlib.Path('.')
xdir = root / 'zips' / 'plugin.video.xship'
old_zip = xdir / 'plugin.video.xship-2026.07.08.zip'
new_version = '2026.07.09'
new_zip = xdir / f'plugin.video.xship-{new_version}.zip'

if new_zip.exists():
    print(f'{new_zip.name} already exists; nothing to do')
    raise SystemExit(0)
if not old_zip.exists():
    raise SystemExit(f'Missing source package: {old_zip}')

patched = False
addon_xml_bytes = None

internal_helper = r'''    def _is_serienstream_url(self, url):
        try:
            parsed = urlparse(str(url).split('|', 1)[0])
            host = (parsed.netloc or '').split(':', 1)[0].lower()
            domains = set([
                SITE_DOMAIN,
                (self.domain or SITE_DOMAIN).lower(),
                'serienstream.to',
                '186.2.175.5'
            ])
            return host in domains or any(host.endswith('.' + domain) for domain in domains if domain != '186.2.175.5')
        except:
            return False

'''

resolver = r'''    def _resolve_with_session(self, url, referer):
        session = self._get_http_session()
        if session is None:
            return None

        try:
            # Seed the same HTTP session with the episode page first.
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

            # Try the original /r?t= token on every currently known SerienStream
            # entry host. A redirect to a bare SerienStream homepage is an internal
            # bridge/fallback, never a playable result.
            parsed_start = urlparse(url)
            request_path = parsed_start.path or '/'
            if parsed_start.query:
                request_path += '?' + parsed_start.query

            start_urls = [url]
            if request_path.startswith('/r?') or request_path.startswith('/r/') or request_path == '/r':
                for base in ('https://serienstream.to', 'http://186.2.175.5'):
                    candidate = base + request_path
                    if candidate not in start_urls:
                        start_urls.append(candidate)

            for start_url in start_urls:
                current = start_url
                current_referer = referer
                visited = set()

                for _hop in range(6):
                    if current in visited:
                        break
                    visited.add(current)

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

                    # Only an external host is a valid resolver result.
                    if final_url and not self._is_serienstream_url(final_url):
                        return final_url

                    bridge_target = self._extract_bridge_target(response.text, final_url)
                    if bridge_target:
                        if not self._is_serienstream_url(bridge_target):
                            return bridge_target

                        # Never hand a bare internal homepage to Kodi. Follow only
                        # meaningful internal bridge paths; otherwise try the same
                        # encrypted /r?t= token on the next known SerienStream host.
                        parsed_target = urlparse(bridge_target)
                        if parsed_target.path not in ('', '/'):
                            if bridge_target != current:
                                current_referer = final_url
                                current = bridge_target
                                continue
                        elif log_utils:
                            logger.info('SerienStream - Ignoring internal homepage bridge: %s' % bridge_target[:100])

                    # If allow_redirects collapsed the request to an internal root,
                    # stop this host and retry the original token on the next host.
                    parsed_final = urlparse(final_url)
                    if self._is_serienstream_url(final_url) and parsed_final.path in ('', '/'):
                        if log_utils:
                            logger.info('SerienStream - Internal homepage reached; trying alternate SerienStream host')
                        break

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

'''

with zipfile.ZipFile(old_zip, 'r') as zin, zipfile.ZipFile(new_zip, 'w', zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        lower = item.filename.lower()

        if lower.endswith('/serienstream.py') or lower == 'serienstream.py':
            text = data.decode('utf-8').replace('\r\n', '\n')

            pattern_internal = r'    def _is_serienstream_url\(self, url\):[\s\S]*?(?=    def _is_internal_redirect_url\(self, url\):)'
            text, count1 = re.subn(pattern_internal, lambda _m: internal_helper, text, count=1)

            pattern_resolver = r'    def _resolve_with_session\(self, url, referer\):[\s\S]*?(?=    def resolve\(self, url\):)'
            text, count2 = re.subn(pattern_resolver, lambda _m: resolver, text, count=1)

            if count1 != 1 or count2 != 1:
                raise SystemExit(f'Expected SerienStream 0.8 resolver blocks not found in {item.filename}: {count1}/{count2}')

            data = text.encode('utf-8')
            patched = True
            print(f'Patched internal-domain filtering and alternate /r token retries in {item.filename}')

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
