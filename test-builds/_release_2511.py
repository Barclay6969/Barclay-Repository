from pathlib import Path
import re, shutil, zipfile

repo = Path('.')
basezip = repo / 'test-builds/plugin.video.xship-2026.08.25.10-KINOKING-MEINECLOUD-TEST.zip'
out = repo / 'test-builds/plugin.video.xship-2026.08.25.11.zip'
basework = Path('/tmp/xship-2511-base')
newwork = Path('/tmp/xship-2511-new')

for d in (basework, newwork):
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)

with zipfile.ZipFile(basezip) as z:
    z.extractall(basework)
shutil.copytree(basework / 'plugin.video.xship', newwork / 'plugin.video.xship', dirs_exist_ok=True)
root = newwork / 'plugin.video.xship'

addon = root / 'addon.xml'
s = addon.read_text('utf-8')

s, n = re.subn(r'(<addon\b[^>]*?\bversion=")[^"]+("[^>]*>)', r'\g<1>2026.08.25.11\2', s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('Could not set addon version')

news = '''2026.08.25.11
- KinoKing: Filmsuche an das neue V2-Seitenlayout mit data-id/data-title angepasst; Filmquellen werden wieder erkannt.
- KinoKing: MeineCloud-Zwischenseiten werden über den bereits bewährten gemeinsamen MeineCloud-Auflösungsweg verarbeitet; Hosterquellen werden wieder ausgegeben.

'''
if '<news>' not in s:
    raise SystemExit('news tag not found')
s = s.replace('<news>', '<news>' + news, 1)
addon.write_text(s, 'utf-8')

# Final release must differ from the tested 25.10 only in addon.xml.
base = basework / 'plugin.video.xship'
changed = []
for bp in base.rglob('*'):
    if bp.is_file():
        rel = bp.relative_to(base)
        np = root / rel
        if not np.exists() or bp.read_bytes() != np.read_bytes():
            changed.append(str(rel))
print('CHANGED', changed)
if changed != ['addon.xml']:
    raise SystemExit(f'Unexpected changed files: {changed}')

# Verify all trusted fixes are still present.
checks = {
    'megakino16.com': list(root.rglob('megakino.py')),
    'EINSCHALTEN-DOOD': list(root.rglob('einschalten.py')),
    'get_movie_links': list(root.rglob('kinoking.py')),
    'fav-data-source': list(root.rglob('kinoking.py')),
}
for needle, files in checks.items():
    if not files or not any(needle in p.read_text('utf-8', errors='ignore') for p in files):
        raise SystemExit(f'Missing trusted fix marker: {needle}')

if out.exists():
    out.unlink()
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for fp in root.rglob('*'):
        if fp.is_file():
            z.write(fp, fp.relative_to(newwork))
with zipfile.ZipFile(out) as z:
    bad = z.testzip()
    if bad:
        raise SystemExit(f'Bad ZIP member: {bad}')
print('BUILT', out)
