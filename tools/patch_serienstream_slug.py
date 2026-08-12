import hashlib
import pathlib
import re
import zipfile
import xml.etree.ElementTree as ET

root = pathlib.Path('.')
xdir = root / 'zips' / 'plugin.video.xship'
old_zip = xdir / 'plugin.video.xship-2026.07.13.zip'
new_version = '2026.07.14'
new_zip = xdir / f'plugin.video.xship-{new_version}.zip'

if new_zip.exists():
    print(f'{new_zip.name} already exists; nothing to do')
    raise SystemExit(0)
if not old_zip.exists():
    raise SystemExit(f'Missing source package: {old_zip}')

addon_xml_bytes = None
patched_sources = False

with zipfile.ZipFile(old_zip, 'r') as zin, zipfile.ZipFile(new_zip, 'w', zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        lower = item.filename.lower()

        if lower.endswith('/resources/lib/sources.py'):
            text = data.decode('utf-8').replace('\r\n', '\n')

            # xVault-compatible VOE direct resolver dependencies.
            if 'import base64\n' not in text:
                text = text.replace('import sys\n', 'import sys\nimport base64\n', 1)
            if 'from html import unescape as html_unescape' not in text:
                text = text.replace('import re,json,random,time\n', 'import re,json,random,time\nfrom html import unescape as html_unescape\nfrom urllib.parse import urlencode, urljoin, urlparse\n', 1)

            # Never delete a valid scraper source only because MediaInfo cannot probe
            # a protected/redirect URL before the provider resolver has run.
            old = """            else:\n                log_utils.log('[BG-Probe] Keine MediaInfo: %s / %s' % (provider, source_name), log_utils.LOGWARNING)\n                return\n            source.update({'info': info})\n        except:\n            return\n        source.update({'_probe': probe})\n        self.sources_new.append(source)"""
            new = """            else:\n                log_utils.log('[BG-Probe] Keine MediaInfo, Quelle bleibt erhalten: %s / %s' % (provider, source_name), log_utils.LOGWARNING)\n                probe = {'width': resolution, 'height': resolution}\n                if prioHoster != 999:\n                    info = source.get('info', '') + '| Keine Auflösung'\n            source.update({'info': info})\n        except Exception as e:\n            log_utils.log('[BG-Probe] Fehler, Quelle bleibt erhalten: %s / %s / %s' % (source.get('provider'), source.get('source'), str(e)), log_utils.LOGWARNING)\n            probe = {'width': 0, 'height': 0}\n        source.update({'_probe': probe})\n        self.sources_new.append(source)"""
            if old not in text:
                raise SystemExit('BG-probe anchor not found')
            text = text.replace(old, new, 1)

            # xVault playback path: try VOE direct resolution before ResolveURL.
            old = """            if not direct == True:\n                try:\n                    hmf = resolver.HostedMediaFile(url=url, include_disabled=True, include_universal=False, include_popups=False)\n                    if not hmf.valid_url():\n                        hmf = resolver.HostedMediaFile(url=url, include_disabled=True, include_universal=False, include_popups=True)\n                    if hmf.valid_url():\n                        url = hmf.resolve()\n                        if url == False or url == None or url == '': url = None  # raise Exception()\n                except:\n                    url = None"""
            new = """            if not direct == True:\n                voe_url = self._resolveVoeDirect(url, item)\n                if voe_url:\n                    url = voe_url\n                else:\n                    try:\n                        hmf = resolver.HostedMediaFile(url=url, include_disabled=True, include_universal=False, include_popups=False)\n                        if not hmf.valid_url():\n                            hmf = resolver.HostedMediaFile(url=url, include_disabled=True, include_universal=False, include_popups=True)\n                        if hmf.valid_url():\n                            url = hmf.resolve()\n                            if url == False or url == None or url == '': url = None\n                    except:\n                        url = None"""
            if old not in text:
                raise SystemExit('ResolveURL anchor not found')
            text = text.replace(old, new, 1)

            helper = r'''
    def _resolveVoeDirect(self, url, item):
        try:
            if not url:
                return None
            if 'voe' not in str(item.get('source', '')).lower() and 'voe' not in urlparse(str(url).split('|', 1)[0]).netloc.lower():
                return None
            import requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            page_url = str(url).split('|', 1)[0]
            response = requests.get(page_url, headers=headers, timeout=12, allow_redirects=True)
            html = response.text or ''
            real_url = response.url
            for _ in range(3):
                redirect = re.search(r"window\.location\.href\s*=\s*'([^']+)'", html)
                if not redirect:
                    break
                page_url = urljoin(real_url, html_unescape(redirect.group(1)))
                response = requests.get(page_url, headers=headers, timeout=12, allow_redirects=True)
                html = response.text or ''
                real_url = response.url
            packed = re.search(r'json">\["([^"]+)"\]</script>\s*<script\s+src="([^"]+)', html)
            if not packed:
                return None
            script_url = urljoin(real_url, html_unescape(packed.group(2)))
            script = requests.get(script_url, headers=headers, timeout=12).text or ''
            repl = re.search(r"(\[(?:'\W{2}'[,]?){1,9}\])", script)
            if not repl:
                return None
            data = self._decodeVoePayload(packed.group(1), repl.group(1))
            media_url = data.get('direct_access_url') or data.get('source') or data.get('file')
            if not media_url:
                return None
            stream_headers = urlencode({'User-Agent': headers['User-Agent'], 'Referer': real_url})
            log_utils.log('VOE direkt aufgeloest: Provider %s / %s' % (item.get('provider'), item.get('source')), log_utils.LOGINFO)
            return '%s|%s' % (media_url, stream_headers)
        except Exception as e:
            log_utils.log('VOE Direktaufloesung fehlgeschlagen: %s' % str(e), log_utils.LOGWARNING)
            return None

    def _decodeVoePayload(self, encoded, replacements):
        tokens = [re.escape(token) for token in replacements[2:-2].split("','")]
        text = ''
        for char in encoded:
            value = ord(char)
            if 64 < value < 91:
                value = (value - 52) % 26 + 65
            elif 96 < value < 123:
                value = (value - 84) % 26 + 97
            text += chr(value)
        for token in tokens:
            text = re.sub(token, '', text)
        step = base64.b64decode(text).decode('utf-8', errors='replace')
        step = ''.join(chr(ord(char) - 3) for char in step)
        return json.loads(base64.b64decode(step[::-1]).decode('utf-8', errors='replace'))

'''
            anchor = '    def sourcesDialog(self, items):\n'
            if anchor not in text:
                raise SystemExit('sourcesDialog anchor not found')
            text = text.replace(anchor, helper + anchor, 1)
            compile(text, item.filename, 'exec')
            data = text.encode('utf-8')
            patched_sources = True
            print('Patched xShip playback layer in sources.py')

        if lower.endswith('/addon.xml') or lower == 'addon.xml':
            try:
                addon = ET.fromstring(data)
            except Exception:
                addon = None
            if addon is not None and addon.attrib.get('id') == 'plugin.video.xship':
                addon.attrib['version'] = new_version
                data = ET.tostring(addon, encoding='utf-8', xml_declaration=True)
                addon_xml_bytes = data

        zout.writestr(item, data)

if not patched_sources:
    new_zip.unlink(missing_ok=True)
    raise SystemExit('sources.py not patched')
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
