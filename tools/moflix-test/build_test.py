import pathlib, re, shutil, sys, tempfile, zipfile

repo = pathlib.Path(sys.argv[1]).resolve()
base = repo / 'zips/plugin.video.xship/plugin.video.xship-2026.08.31.2.zip'
moflix_replacement = repo / 'tools/moflix-test/moflix.py'
movie2k_replacement = repo / 'tools/moflix-test/movie2k.py'
out = repo / 'zips/test/plugin.video.xship-2026.09.14.91-MOFLIX-MOVIE2KTEST.zip'

with tempfile.TemporaryDirectory() as td:
    td = pathlib.Path(td)
    with zipfile.ZipFile(base) as zf:
        zf.extractall(td)

    root = td / 'plugin.video.xship'
    moflix_target = root / 'scrapers/scrapers_source/de/moflix.py'
    movie2k_target = root / 'scrapers/scrapers_source/de/movie2k.py'
    shutil.copy2(moflix_replacement, moflix_target)
    shutil.copy2(movie2k_replacement, movie2k_target)

    addon = root / 'addon.xml'
    text = addon.read_text(encoding='utf-8')
    text, n = re.subn(
        r'(<addon\s+id="plugin\.video\.xship"\s+version=")[^"]+("\s+name="xShip")',
        r'\g<1>2026.09.14.91\2',
        text,
        count=1
    )
    if n != 1:
        raise SystemExit('addon version not found')
    addon.write_text(text, encoding='utf-8', newline='\n')

    compile(moflix_target.read_text(encoding='utf-8'), str(moflix_target), 'exec')
    compile(movie2k_target.read_text(encoding='utf-8'), str(movie2k_target), 'exec')

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob('*'):
            if path.is_file():
                zf.write(path, path.relative_to(td))

with zipfile.ZipFile(out) as zf:
    bad = zf.testzip()
    if bad:
        raise SystemExit('bad zip member: ' + bad)

print(out)
