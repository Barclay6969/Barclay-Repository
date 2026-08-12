import hashlib
import pathlib
import re
import zipfile
import xml.etree.ElementTree as ET

root = pathlib.Path('.')
xdir = root / 'zips' / 'plugin.video.xship'
old_zip = xdir / 'plugin.video.xship-2026.07.04.zip'
new_version = '2026.07.07'
new_zip = xdir / f'plugin.video.xship-{new_version}.zip'

if new_zip.exists():
    print(f'{new_zip.name} already exists; nothing to do')
    raise SystemExit(0)
if not old_zip.exists():
    raise SystemExit(f'Missing source package: {old_zip}')

patched = False
addon_xml_bytes = None

with zipfile.ZipFile(old_zip, 'r') as zin, zipfile.ZipFile(new_zip, 'w', zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        lower = item.filename.lower()

        if lower.endswith('/serienstream.py') or lower == 'serienstream.py':
            text = data.decode('utf-8').replace('\r\n', '\n')
            before = text

            # Start from the known-good 2026.07.04 scraper. Change only the
            # ordinary page/search domain to .cx. Keep the original hoster and
            # redirect-resolution logic untouched.
            text = text.replace("SITE_DOMAIN = 'serienstream.to'", "SITE_DOMAIN = 'serienstream.cx'", 1)

            # Preserve .to as the legacy/internal host if the scraper already
            # defines it. Remove obsolete s.to only; do not add the direct IP to
            # hoster/redirect recognition because that broke playback in .06.
            text = re.sub(
                r"LEGACY_DOMAINS\s*=\s*set\(([^\n]+)\)",
                "LEGACY_DOMAINS = set(['serienstream.to'])",
                text,
                count=1
            )

            # Optional page-level fallback list only. This list is deliberately
            # not wired into hoster redirect detection.
            marker = "        self.base_link = 'https://' + self.domain\n"
            replacement = """        self.base_link = 'https://' + self.domain
        self.page_fallback_links = [
            'https://serienstream.cx',
            'https://serienstream.to',
            'http://186.2.175.5'
        ]
"""
            if marker in text:
                text = text.replace(marker, replacement, 1)

            if text == before:
                raise SystemExit(f'No safe SerienStream domain change applied in {item.filename}')

            data = text.encode('utf-8')
            patched = True
            print(f'Changed only SerienStream entry domain to .cx in {item.filename}')

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

# Keep previous versions in the repository for rollback/testing.
repo_src = root / 'addons' / 'repository.barclay' / 'addon.xml'
repo_xml = repo_src.read_text(encoding='utf-8-sig').strip()
xship_xml = addon_xml_bytes.decode('utf-8-sig').strip()
repo_xml = re.sub(r'^<\?xml[^>]*\?>\s*', '', repo_xml)
xship_xml = re.sub(r'^<\?xml[^>]*\?>\s*', '', xship_xml)
feed = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n' + repo_xml + '\n\n' + xship_xml + '\n</addons>\n'
(root / 'zips' / 'addons.xml').write_text(feed, encoding='utf-8', newline='\n')
(root / 'zips' / 'addons.xml.md5').write_text(hashlib.md5(feed.encode('utf-8')).hexdigest() + '\n', encoding='ascii', newline='\n')

print(f'Created {new_zip}')
