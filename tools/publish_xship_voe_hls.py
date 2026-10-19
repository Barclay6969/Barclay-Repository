#!/usr/bin/env python3
"""Publish verified VOE selector from xShip 2026.10.13.157 with HLS as default."""
import base64, hashlib, json, zipfile, zlib
import xml.etree.ElementTree as ET
from pathlib import Path

P = json.loads(zlib.decompress(base64.b64decode('eNrdVl1v2zYU/SsXLgpJgKYkWx+KYB721WxDk6aY0/bBMQxaurYIU6RGUk68Zf99l5RiUbazDCv2MhuwKYq8H+eee8g/RhqNanSO5kTwxUk3zurt6Bym0xEEn4JZBmMwKJbZvMBcFfhR4Xu2FYoVcc3yNRbZSqumjs+SFDTWYveY3MrQVIUFZ/NGC7LnzGYrtHFUcI25nbOcIjDubZSA0sGCNrr92SUXNDd0wJcgle39nA9fu49G22gJ75TEW3krRyn8V9m+gEuVMwEfr9/AUumKWbBo7DkoUTgHlDRXkkxUjEsDBS5ZIyzEFfmE0yQbWqs1LlGjzJHCy5W0WgkHxASt5XIVRxuFmbEaWTXv17agRafRE4VIu+GSoyjSIKpHCNoZguDKrYsdPGkQy2fjPwTsLWINtkRoSw4ffr0E1VhQSxBqZSB2WNKkgZxJjwJBB1atUZp9wGjDvLFcmIxGcTS9n5S89sW4eTO5OZvBlSoaM35pUvjESuEHF4SCH/x8OfH/V+9f0X8ELyE+TKWHIUBuiOjhJtNU8ZnjA6xxCxT9sQZI4ZH0NDpG9ABwbog9llEU8a45yDSRk9iQAJPF8a3kp2batLumtGOWmVpw6qwH8nqWTE9nSVYzWxJ+d6jjJENZmDtuyziOsuqr5rULzg2iJEn+p5lSfvWraL+zyWPPrsvrn355d3GdeDWZpdCqJ3UzzJ3Iio0TkB994rHrqRR833GLVXL+KD/fUl6W5xXaUnVZeAvPtV/QYLcj9/2hVMogME90z0TXL5mTALfPoN6gAd8LkXEzG64aA56tJBUF6ixsy2sptoD3hFbOLfiqn7hfpyoOGnCwGWAawUmPxQKYgbVUd7LTPBO05QfZvmk3UcpkW/AVXwjaXpKKrkrf/UrTpCTpXDIhFqS5u8iGyfbPJAcFJ3QotzFM407OfL39eJZ4IrZpcnmcJ/B5DH2So95rwFLYezPr7XUC2qezp6CBeqbdb9TIBa6ZlDYKKzc4L8hzHEy0R0Kyv1hjMcd7S+sPGtwFFlocQ3QWUfGIal2PpMfWfPm4JhmkOHC3l+GuTGmPghOPJyFpT46J1aTub1XBoURGZAGzpdPh3uPNV1IRQ39rUG8dFnReGrgrkayWmK/pkThu6Qwh/c6O6DzRVbLKAbmTkl04z0jJoTWXf2ew15kBIsn5cYJ1xd+5Th+Biui4iv6mRBEdYwNyvCDuhItPiHVAzZqXDgu7rbG9pbRnZtsT/jBeYMlIMcJWPCjWOKgV4dGvfDr+i67PowN2dAl811hF8XGTl7tE/qnEzkiUg/uuaS9MJruvxPC2+3X3ygMwvh2R5/p2BIItUNDj98jhE0fi1opmvphYpm2WZbTi5JvwGvmMGRJm2uvuad2lMBZqzQQx9oZuh4k312O2M8YL2nv0jkc7Ok8om2rPUx8wvdgw0aChNwGcEN9xhAU3JerkgYhENd4o/XuzQvlAvAkeyUJ3SSUTp08F+i/Am83+/Atu3dpe')).decode('utf8'))
BASE = 'plugin.video.xship/'
OLD = '2026.10.13.157'
NEW = '2026.10.13.158'
DIR = Path(__file__).resolve().parents[1] / 'zips/plugin.video.xship'
OUT = DIR / f'plugin.video.xship-{NEW}.zip'
ENTRY = ('2026.10.13.158\n'
         '- VOE: HLS wird jetzt standardmaessig bevorzugt, sofern verfuegbar; MP4 bleibt als Alternative.\n'
         '- Neue Einstellung unter Wiedergabe: Automatisch / HLS bevorzugen / MP4 bevorzugen.\n'
         '- VOE-Direktaufloesung, Player, InputStream Adaptive und 320-MB-Puffer bleiben erhalten.\n\n')

def single(s, old, new):
    n = s.count(old)
    if n != 1:
        raise ValueError(f'Expected 1 replacement, got {n}, old={old[:80]!r}')
    return s.replace(old,new,1)

source = DIR / f'plugin.video.xship-{OLD}.zip'
assert source.is_file() and not OUT.exists()
with zipfile.ZipFile(source) as zi:
    assert zi.testzip() is None
    entries = {i.filename: zi.read(i) for i in zi.infolist()}
    info = zi.infolist()

for short, patches in P.items():
    path = BASE + short
    content = entries[path].decode('utf8')
    for prev, later in patches:
        content = single(content, prev, later)
    if short == 'resources/settings.xml':
        content = single(content, 'VOE-Streamformat (lokaler Test)', 'VOE-Streamformat')
        content = single(content, 'values="Automatisch (wie bisher)|HLS bevorzugen|MP4 bevorzugen" default="0"',
                         'values="Automatisch (wie bisher)|HLS bevorzugen|MP4 bevorzugen" default="1"')
        ET.fromstring(content)
    else:
        content = single(content, '# Local VOE format test: old selection remains default (mode 0).', '# VOE format preference from the user settings.')
        content = single(content, '[xShip VOE TEST1]', '[xShip VOE]')
        compile(content,path,'exec')
    entries[path] = content.encode('utf8')

addon = BASE + 'addon.xml'
xml = entries[addon].decode('utf8')
xml = single(xml, 'version="2026.10.13.157" name="xShip"', 'version="2026.10.13.158" name="xShip"')
xml = single(xml, '<news>', '<news>' + ENTRY)
assert ET.fromstring(xml).get('version') == NEW
entries[addon] = xml.encode('utf8')
clog = BASE + 'changelog.txt'
assert entries[clog].startswith(b'2026.10.13.157')
entries[clog] = ENTRY.encode('utf8')+entries[clog]

with zipfile.ZipFile(OUT,'w') as zo:
    for item in info:
        zo.writestr(item,entries[item.filename])
with zipfile.ZipFile(OUT) as zo:
    assert zo.testzip() is None
    setting=ET.fromstring(zo.read(BASE+'resources/settings.xml'))
    pref=[a for a in setting.iter('setting') if a.get('id')=='voe.stream_preference']
    assert len(pref)==1 and pref[0].get('default')=='1'
    assert '[xShip VOE TEST1]' not in zo.read(BASE+'resources/lib/sources.py').decode('utf8')
    for item in info:
        if item.filename not in {BASE+'resources/lib/sources.py',BASE+'resources/settings.xml',addon,clog}:
            assert entries[item.filename]==zo.read(item.filename)
sha=hashlib.sha256(OUT.read_bytes()).hexdigest()
assert sha=='5561dd8c44155f4fee3528b287ecadb4daf98c3694968d8b8bdcd5ae2f8b3b8a', sha
(DIR/'changelog.txt').write_bytes(entries[clog])
print(f'Built xShip {NEW}: {sha}, HLS default=1, unchanged remaining files')
