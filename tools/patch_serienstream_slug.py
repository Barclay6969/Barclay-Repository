import pathlib
import zipfile

root = pathlib.Path('.')
xdir = root / 'zips' / 'plugin.video.xship'
source_zip = xdir / 'plugin.video.xship-2026.07.07.zip'
out_file = root / 'tools' / 'serienstream_2026.07.07_extracted.py'

if not source_zip.exists():
    raise SystemExit(f'Missing source package: {source_zip}')

with zipfile.ZipFile(source_zip, 'r') as zf:
    matches = [n for n in zf.namelist() if n.lower().endswith('/serienstream.py') or n.lower() == 'serienstream.py']
    if not matches:
        raise SystemExit('serienstream.py not found in xShip 2026.07.07')
    name = matches[0]
    text = zf.read(name).decode('utf-8').replace('\r\n', '\n')
    out_file.write_text(text, encoding='utf-8', newline='\n')
    print(f'Extracted {name} -> {out_file}')
