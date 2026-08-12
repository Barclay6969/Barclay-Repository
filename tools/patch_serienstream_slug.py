import hashlib
import pathlib
import re
import zipfile
import xml.etree.ElementTree as ET

root = pathlib.Path('.')
xdir = root / 'zips' / 'plugin.video.xship'
# Rebase on 0.7 so none of the experimental 0.8-0.10 bridge/token logic survives.
old_zip = xdir / 'plugin.video.xship-2026.07.07.zip'
new_version = '2026.07.11'
new_zip = xdir / f'plugin.video.xship-{new_version}.zip'

if new_zip.exists():
    print(f'{new_zip.name} already exists; nothing to do')
    raise SystemExit(0)
if not old_zip.exists():
    raise SystemExit(f'Missing source package: {old_zip}')

patched = False
addon_xml_bytes = None

# Lastship's working principle:
# - one SerienStream base domain for discovery, episode page and /r?t= token
# - one persistent requests.Session
# - resolve data-play-url with the episode page as Referer
# - let requests follow redirects and return response.url
resolver_replacement = r'''    def _get_http_session(self):
        try:
            session = getattr(self, '_http_session', None)
            if session is not None:
                return session

            import requests
            requests.packages.urllib3.disable_warnings()
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            self._http_session = session
            return session
        except:
            return None

    def resolve(self, url):
        try:
            if log_utils:
                logger.info('SerienStream - Lastship-style resolving: %s' % url[:100])

            session = self._get_http_session()
            if session is None:
                return None

            referer = getattr(self, 'episode_referer', None) or getattr(self, 'base_link', 'https://serienstream.to')
            headers = {
                'Referer': referer,
                'Upgrade-Insecure-Requests': '1'
            }

            response = session.get(
                url,
                headers=headers,
                timeout=10,
                allow_redirects=True,
                verify=False
            )
            final_url = response.url or url

            if log_utils:
                logger.info('SerienStream - Lastship-style final URL: %s' % final_url[:120])

            # A fall-back to the SerienStream homepage is not a video URL.
            try:
                from urllib.parse import urlparse
                host = (urlparse(final_url).hostname or '').lower()
                path = urlparse(final_url).path or '/'
                if host in ('serienstream.to', 'serienstream.cx', '186.2.175.5') and path in ('', '/'):
                    if log_utils:
                        logger.info('SerienStream - Lastship-style resolve ended on internal homepage')
                    return None
            except:
                pass

            # Mirror Lastship's VOE normalization.
            try:
                if 'voe' in final_url.lower() and 'voe.sx' not in final_url.lower():
                    from urllib.parse import urlparse
                    parsed = urlparse(final_url)
                    if parsed.netloc:
                        final_url = final_url.replace(parsed.netloc, 'voe.sx', 1)
            except:
                pass

            return final_url

        except Exception as e:
            if log_utils:
                logger.info('SerienStream - Lastship-style resolve error: %s' % str(e))
            return None

'''

with zipfile.ZipFile(old_zip, 'r') as zin, zipfile.ZipFile(new_zip, 'w', zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        lower = item.filename.lower()

        if lower.endswith('/serienstream.py') or lower == 'serienstream.py':
            text = data.decode('utf-8').replace('\r\n', '\n')

            # Use the same base domain throughout, exactly like the supplied
            # Lastship scraper does. Do not mix .cx-generated tokens with .to.
            text = text.replace('serienstream.cx', 'serienstream.to')

            # Replace xShip's old HTTP/bridge resolver block with the minimal
            # Lastship-style resolver. 0.7 has this block directly before _getLogin.
            pattern = r'    def _resolve_http_redirect\(self, url, referer\):[\s\S]*?(?=    @staticmethod\n    def _getLogin\(\):)'
            text, count = re.subn(pattern, lambda _m: resolver_replacement, text, count=1)
            if count != 1:
                raise SystemExit(f'Expected SerienStream resolver block not found in {item.filename}')

            data = text.encode('utf-8')
            patched = True
            print(f'Applied Lastship-style single-domain/session resolver to {item.filename}')

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
