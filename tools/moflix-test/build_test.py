import pathlib, re, shutil, sys, tempfile, zipfile

repo = pathlib.Path(sys.argv[1]).resolve()
base = repo / 'zips/plugin.video.xship/plugin.video.xship-2026.08.31.2.zip'
replacement = repo / 'tools/moflix-test/moflix.py'
out = repo / 'zips/test/plugin.video.xship-2026.09.14.90-MOFLIXTEST.zip'

with tempfile.TemporaryDirectory() as td:
    td = pathlib.Path(td)
    with zipfile.ZipFile(base) as zf:
        zf.extractall(td)
    root = td / 'plugin.video.xship'
    target = root / 'scrapers/scrapers_source/de/moflix.py'
    shutil.copy2(replacement, target)

    addon = root / 'addon.xml'
    text = addon.read_text(encoding='utf-8')
    text, n = re.subn(r'(<addon\s+id="plugin\.video\.xship"\s+version=")[^"]+("\s+name="xShip")', r'\g<1>2026.09.14.90\2', text, count=1)
    if n != 1:
        raise SystemExit('addon version not found')
    addon.write_text(text, encoding='utf-8', newline='\n')

    compile(target.read_text(encoding='utf-8'), str(target), 'exec')
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in root.rglob('*'):
            if p.is_file():
                zf.write(p, p.relative_to(td))

with zipfile.ZipFile(out) as zf:
    bad = zf.testzip()
    if bad:
        raise SystemExit('bad zip member: ' + bad)
print(out)
