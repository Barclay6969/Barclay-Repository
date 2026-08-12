import hashlib
import pathlib
import re
import zipfile
import xml.etree.ElementTree as ET

root = pathlib.Path('.')
xdir = root / 'zips' / 'plugin.video.xship'
old_zip = xdir / 'plugin.video.xship-2026.07.07.zip'
new_version = '2026.07.13'
new_zip = xdir / f'plugin.video.xship-{new_version}.zip'

if new_zip.exists():
    print(f'{new_zip.name} already exists; nothing to do')
    raise SystemExit(0)
if not old_zip.exists():
    raise SystemExit(f'Missing source package: {old_zip}')

patched = False
addon_xml_bytes = None

# Exact Lastship principle ported to xShip's scraper interface:
# - serienstream.to is the single base domain
# - NO login attempt/requirement
# - one requests.Session for search, episode page and data-play-url redirect
# - episode URL is the Referer for the redirect request
# - allow requests to follow redirects and use response.url as hoster URL
# - no custom frame-bridge/token/domain rewriting logic

request_page_replacement = r'''    def _get_http_session(self):
        session = getattr(self, '_http_session', None)
        if session is not None:
            return session
        try:
            import requests
            requests.packages.urllib3.disable_warnings()
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            self._http_session = session
            return session
        except Exception as e:
            if log_utils:
                logger.info('SerienStream - Session init error: %s' % str(e))
            return None

    def _request_page(self, full_url):
        session = self._get_http_session()
        if session is None:
            return ''
        try:
            response = session.get(full_url, timeout=12, allow_redirects=True, verify=False)
            response.raise_for_status()
            return response.text or ''
        except Exception as e:
            if log_utils:
                logger.info('SerienStream - Session page error: %s | %s' % (str(e), full_url))
            return ''

'''

resolver_replacement = r'''    def resolve(self, url):
        try:
            if log_utils:
                logger.info('SerienStream - Lastship resolve: %s' % url[:100])

            session = self._get_http_session()
            if session is None:
                return None

            referer = getattr(self, 'episode_referer', None) or self.base_link
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
                logger.info('SerienStream - Lastship final URL: %s' % final_url[:120])

            # Lastship normalises VOE domains to voe.sx.
            try:
                parsed = urlparse(final_url)
                host = (parsed.netloc or '').lower()
                if 'voe' in host and host != 'voe.sx':
                    final_url = final_url.replace(parsed.netloc, 'voe.sx', 1)
            except:
                pass

            # Never hand an internal homepage to Kodi as a video URL.
            try:
                parsed = urlparse(final_url)
                host = (parsed.hostname or '').lower()
                path = parsed.path or '/'
                if host in ('serienstream.to', 'serienstream.cx', '186.2.175.5') and path in ('', '/'):
                    if log_utils:
                        logger.info('SerienStream - Lastship resolve ended on internal homepage')
                    return None
            except:
                pass

            return final_url

        except Exception as e:
            if log_utils:
                logger.info('SerienStream - Lastship resolve error: %s' % str(e))
            return None

'''

with zipfile.ZipFile(old_zip, 'r') as zin, zipfile.ZipFile(new_zip, 'w', zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        lower = item.filename.lower()

        if lower.endswith('/serienstream.py') or lower == 'serienstream.py':
            text = data.decode('utf-8').replace('\r\n', '\n')

            # Single Lastship base domain. Do not mix tokens across domains.
            text = re.sub(r"SITE_DOMAIN\s*=\s*['\"][^'\"]+['\"]", "SITE_DOMAIN = 'serienstream.to'", text, count=1)
            text = re.sub(r"LEGACY_DOMAINS\s*=\s*set\([^\n]+\)", "LEGACY_DOMAINS = set(['serienstream.cx'])", text, count=1)

            # Remove xShip's mandatory/login attempt. Lastship does not login.
            login_pattern = r'''            login, password = self\._getLogin\(\)\n[\s\S]*?            aLinks = \[\]\n'''
            login_repl = "            if log_utils:\n                logger.info('SerienStream - Lastship flow: no login required')\n\n            aLinks = []\n"
            text, login_count = re.subn(login_pattern, login_repl, text, count=1)
            if login_count != 1:
                raise SystemExit(f'Could not remove login gate in {item.filename}')

            # Search pages must use the SAME requests.Session as episode + redirect.
            imdb_req_pattern = r'''                    oRequest = cRequestHandler\(imdb_search_url\)\n                    oRequest\.addHeaderEntry\('User-Agent', 'Mozilla/5\.0'\)\n                    sHtmlContent = oRequest\.request\(\)'''
            text, imdb_count = re.subn(imdb_req_pattern, "                    sHtmlContent = self._request_page(imdb_search_url)", text, count=1)
            if imdb_count != 1:
                raise SystemExit(f'Could not patch IMDB search request in {item.filename}')

            title_req_pattern = r'''                        oRequest = cRequestHandler\(search_url\)\n                        oRequest\.addHeaderEntry\('User-Agent', 'Mozilla/5\.0'\)\n                        sHtmlContent = oRequest\.request\(\)'''
            text, title_count = re.subn(title_req_pattern, "                        sHtmlContent = self._request_page(search_url)", text, count=1)
            if title_count != 1:
                raise SystemExit(f'Could not patch title search request in {item.filename}')

            # Episode/season pages all flow through _request_page already. Replace it
            # with the persistent Lastship-style session implementation.
            request_pattern = r'''    def _request_page\(self, full_url\):[\s\S]*?(?=    @staticmethod\n    def _parse_stream_link_buttons)'''
            text, request_count = re.subn(request_pattern, lambda _m: request_page_replacement, text, count=1)
            if request_count != 1:
                raise SystemExit(f'Could not replace _request_page in {item.filename}')

            # Remove ALL xShip bridge/redirect resolver experiments. Keep helper
            # methods above them untouched; replace only resolver implementation.
            resolver_pattern = r'''    def _resolve_http_redirect\(self, url, referer\):[\s\S]*?(?=    @staticmethod\n    def _getLogin\(\):)'''
            text, resolver_count = re.subn(resolver_pattern, lambda _m: resolver_replacement, text, count=1)
            if resolver_count != 1:
                raise SystemExit(f'Could not replace resolver in {item.filename}')

            # Ensure session exists on the source instance before first request.
            init_anchor = "        self.credentials_checked = False\n"
            if init_anchor not in text:
                raise SystemExit(f'Could not find __init__ anchor in {item.filename}')
            text = text.replace(init_anchor, init_anchor + "        self._http_session = None\n", 1)

            # Compile the generated scraper before packaging it.
            compile(text, item.filename, 'exec')
            data = text.encode('utf-8')
            patched = True
            print(f'Applied exact Lastship session flow to {item.filename}')

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
