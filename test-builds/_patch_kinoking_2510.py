from pathlib import Path
import re, shutil, zipfile

repo = Path('.')
basezip = repo / 'test-builds/plugin.video.xship-2026.08.25.9-KINOKING-V2-TEST.zip'
out = repo / 'test-builds/plugin.video.xship-2026.08.25.10-KINOKING-MEINECLOUD-TEST.zip'
basework = Path('/tmp/xship-kk2510-base')
newwork = Path('/tmp/xship-kk2510-new')
for d in (basework, newwork):
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
with zipfile.ZipFile(basezip) as z:
    z.extractall(basework)
shutil.copytree(basework / 'plugin.video.xship', newwork / 'plugin.video.xship', dirs_exist_ok=True)
root = newwork / 'plugin.video.xship'

matches = list(root.rglob('kinoking.py'))
if len(matches) != 1:
    raise SystemExit(f'Expected one kinoking.py, got {matches}')
p = matches[0]
s = p.read_text('utf-8')

# Reuse the exact helper already used by the working MEINECLOUD provider.
needle = 'from scrapers.modules import cleantitle\n'
replacement = needle + 'from scrapers.modules.meinecloud_shared import get_movie_links\n'
if 'from scrapers.modules.meinecloud_shared import get_movie_links' not in s:
    if needle not in s:
        raise SystemExit('Import insertion point not found')
    s = s.replace(needle, replacement, 1)

old = '''        for link in hoster:\n            isBlocked, sDomain, sUrl, prioHoster = isBlockedHoster(link)\n            if isBlocked: continue\n            self.sources.append({'source': sDomain, 'quality': 'HD', 'language': 'de', 'url': sUrl, 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})\n'''
new = '''        for link in hoster:\n            # KinoKing V2 can expose a MeineCloud movie page as an iframe target.\n            # That URL is an intermediate page, not a playable hoster. Reuse the\n            # same shared resolver path as the working MEINECLOUD provider.\n            resolve_links = [link]\n            if 'meinecloud.click/movie/' in link:\n                try:\n                    mc_imdb = link.rstrip('/').rsplit('/', 1)[-1] or imdb\n                    resolve_links = get_movie_links(mc_imdb) or []\n                except:\n                    resolve_links = []\n\n            for resolve_link in resolve_links:\n                if resolve_link.startswith('/'):\n                    resolve_link = 'https:' + resolve_link\n                isBlocked, sDomain, sUrl, prioHoster = isBlockedHoster(resolve_link)\n                if isBlocked: continue\n                if sUrl:\n                    self.sources.append({'source': sDomain, 'quality': 'HD', 'language': 'de', 'url': sUrl, 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})\n'''
if old not in s:
    raise SystemExit('Hoster loop not found')
s = s.replace(old, new, 1)
p.write_text(s, 'utf-8')

addon = root / 'addon.xml'
a = addon.read_text('utf-8')
a2, n = re.subn(r'(<addon\b[^>]*?\bversion=")[^"]+("[^>]*>)', r'\g<1>2026.08.25.10\2', a, count=1, flags=re.S)
if n != 1:
    raise SystemExit('Could not set addon version')
addon.write_text(a2, 'utf-8')

# Validate only addon.xml + kinoking.py changed versus 25.9.
base = basework / 'plugin.video.xship'
changed = []
for bp in base.rglob('*'):
    if bp.is_file():
        rel = bp.relative_to(base)
        np = root / rel
        if not np.exists() or bp.read_bytes() != np.read_bytes():
            changed.append(str(rel))
print('CHANGED', changed)
if len(changed) != 2 or 'addon.xml' not in changed or not any(x.endswith('kinoking.py') for x in changed):
    raise SystemExit(f'Unexpected changed files: {changed}')

# Syntax-check only the modified scraper without creating pycache files.
compile(p.read_text('utf-8'), str(p), 'exec')

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
