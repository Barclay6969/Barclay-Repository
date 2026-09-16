import pathlib, re, shutil, sys, tempfile, zipfile

repo = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo / 'tools/moflix-test'))
import patch_core
import patch_93
import patch_94
import patch_96

base = repo / 'zips/plugin.video.xship/plugin.video.xship-2026.08.31.2.zip'
tools = repo / 'tools/moflix-test'
out = repo / 'zips/test/plugin.video.xship-2026.09.14.94-SCRAPERCORETEST.zip'

with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    with zipfile.ZipFile(base) as zf:
        zf.extractall(tmp)
    root = tmp / 'plugin.video.xship'
    scrapers = root / 'scrapers/scrapers_source/de'
    lib = root / 'resources/lib'

    for name in ('moflix.py', 'movie2k.py', 'movie2k2.py', 'filmpalast.py'):
        shutil.copy2(tools / name, scrapers / name)
    shutil.copy2(tools / 'hoster_compat.py', lib / 'hoster_compat.py')

    patch_core.patch_moflix(scrapers / 'moflix.py')
    patch_core.patch_sources(lib / 'sources.py')
    patch_93.patch_movie2k(scrapers / 'movie2k.py')
    patch_93.patch_hoster_compat(lib / 'hoster_compat.py')
    patch_93.patch_moflix_display(scrapers / 'moflix.py')
    patch_94.patch_movie2k_title_variants(scrapers / 'movie2k.py')
    patch_96.patch_sources(lib / 'sources.py')

    addon = root / 'addon.xml'
    text = addon.read_text(encoding='utf-8')
    text, count = re.subn(r'(<addon\s+id="plugin\.video\.xship"\s+version=")[^"]+', r'\g<1>2026.09.16.96', text, count=1)
    if count != 1:
        raise RuntimeError('addon version patch failed')
    addon.write_text(text, encoding='utf-8', newline='\n')

    checks = [scrapers/'moflix.py', scrapers/'movie2k.py', scrapers/'movie2k2.py', scrapers/'filmpalast.py', scrapers/'huhu.py', scrapers/'kkiste.py', scrapers/'kinokiste.py', scrapers/'netzkino.py', scrapers/'kinoger.py', lib/'hoster_compat.py', lib/'sources.py']
    for path in checks:
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')

    movie2k_text = (scrapers/'movie2k.py').read_text(encoding='utf-8')
    if '_search_titles' not in movie2k_text or "split(' - ', 1)[0]" not in movie2k_text:
        raise RuntimeError('Movie2k title variant fix missing')

    sources_text = (lib/'sources.py').read_text(encoding='utf-8')
    if '_safe_media_probe_url' not in sources_text:
        raise RuntimeError('safe MediaInfo probe patch missing')
    if "provider_name != 'serienstream'" not in sources_text or "'voe' not in hoster_name" not in sources_text:
        raise RuntimeError('SerienStream VOE-only filter missing')

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob('*'):
            if path.is_file():
                zf.write(path, path.relative_to(tmp))

with zipfile.ZipFile(out) as zf:
    if zf.testzip():
        raise RuntimeError('zip integrity failed')
print(out)
