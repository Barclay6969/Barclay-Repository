import hashlib
import pathlib
import re
import zipfile
import xml.etree.ElementTree as ET

root = pathlib.Path('.')
xdir = root / 'zips' / 'plugin.video.xship'
old_zip = xdir / 'plugin.video.xship-2026.07.09.zip'
new_version = '2026.07.10'
new_zip = xdir / f'plugin.video.xship-{new_version}.zip'

if new_zip.exists():
    print(f'{new_zip.name} already exists; nothing to do')
    raise SystemExit(0)
if not old_zip.exists():
    raise SystemExit(f'Missing source package: {old_zip}')

patched = False
addon_xml_bytes = None

# 0.10: keep .cx for search/discovery, but refresh the episode page on
# serienstream.to before parsing hoster buttons. /r?t= tokens are encrypted and
# must be used on the host that generated them; copying a .cx token to .to/IP
# only redirects to the homepage.
episode_refresh = r'''            sHtmlContent = self._request_page(full_url)

            # 2026.07.10: SerienStream redirect tokens are host-specific. Search
            # and title matching can stay on .cx, but obtain fresh data-play-url
            # values from the same episode path on serienstream.to (the domain
            # used by the working Lastship implementation). If that page is not
            # usable, keep the original .cx page as a safe fallback.
            try:
                parsed_episode = urlparse(full_url)
                alt_full_url = 'https://serienstream.to' + (parsed_episode.path or '/')
                if parsed_episode.query:
                    alt_full_url += '?' + parsed_episode.query

                session = self._get_http_session()
                if session is not None:
                    alt_response = session.get(
                        alt_full_url,
                        headers={'Referer': 'https://serienstream.to'},
                        allow_redirects=True,
                        verify=False,
                        timeout=10
                    )
                    alt_html = alt_response.text or ''
                    if alt_response.status_code == 200 and self._has_stream_links(alt_html):
                        sHtmlContent = alt_html
                        full_url = alt_full_url
                        if log_utils:
                            logger.info('SerienStream - Using fresh .to episode tokens: %s' % full_url)
                    elif log_utils:
                        logger.info('SerienStream - .to episode refresh unavailable; keeping .cx tokens')
            except Exception as e:
                if log_utils:
                    logger.info('SerienStream - .to episode refresh error: %s' % str(e))
'''

with zipfile.ZipFile(old_zip, 'r') as zin, zipfile.ZipFile(new_zip, 'w', zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        lower = item.filename.lower()

        if lower.endswith('/serienstream.py') or lower == 'serienstream.py':
            text = data.decode('utf-8').replace('\r\n', '\n')
            needle = "            sHtmlContent = self._request_page(full_url)\n"
            if needle not in text:
                raise SystemExit(f'Expected episode request line not found in {item.filename}')
            if 'Using fresh .to episode tokens' in text:
                raise SystemExit(f'0.10 episode refresh already present in {item.filename}')

            text = text.replace(needle, episode_refresh, 1)
            data = text.encode('utf-8')
            patched = True
            print(f'Patched fresh serienstream.to episode-token refresh in {item.filename}')

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
