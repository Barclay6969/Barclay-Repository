from pathlib import Path
import re, shutil, tempfile, zipfile

BASE = Path("test-builds/plugin.video.xship-2026.09.28.109-MEINECLOUD-TVOVERVIEW-TEST5.zip")
OUT = Path("test-builds/plugin.video.xship-2026.09.28.110-MEINECLOUD-DROPLOAD-HEADERS-TEST6.zip")
if not BASE.exists():
    raise SystemExit("Missing TEST5 base ZIP")

with tempfile.TemporaryDirectory() as td_raw:
    td = Path(td_raw)
    with zipfile.ZipFile(BASE, "r") as zf:
        zf.extractall(td)

    root = td / "plugin.video.xship"
    provider = root / "scrapers/scrapers_source/de/meinecloud.py"
    src = provider.read_text(encoding="utf-8")

    old_headers = """            headers = {
                'User-Agent': _MC_UA,
                'Referer': 'https://dr0pstream.com/',
                'Origin': 'https://dr0pstream.com',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
            }
"""
    new_headers = """            # Match current E2iPlayer JWPLAYER behaviour closely:
            # keep a plain browser UA + root Referer, preserve Session cookies,
            # and do not add Origin/X-Requested-With on this XFileSharing flow.
            headers = {
                'User-Agent': _MC_UA,
                'Referer': 'https://dr0pstream.com/',
                'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
            }
"""
    if old_headers not in src:
        raise SystemExit("DropLoad GET header block not found")
    src = src.replace(old_headers, new_headers, 1)

    old_post = """                            post_headers = dict(headers)
                            post_headers['Referer'] = response.url
                            post_headers['Origin'] = 'https://' + response.url.split('/')[2]
                            post_res = session.post(
"""
    new_post = """                            post_headers = dict(headers)
                            post_headers['Referer'] = 'https://dr0pstream.com/'
                            post_headers.pop('Origin', None)
                            post_headers.pop('X-Requested-With', None)
                            _mc_log('form POST headers=e2i-root-referer cookies=%s' % (
                                len(session.cookies.get_dict()),
                            ))
                            post_res = session.post(
"""
    if old_post not in src:
        raise SystemExit("DropLoad POST header block not found")
    src = src.replace(old_post, new_post, 1)

    # Add one diagnostic that tells us whether the form supplied an explicit action.
    old_action = """                        action_m = re.search(r'action\\s*=\\s*["\\']([^"\\']+)', whole, flags=re.I)
                        post_url = urljoin(response.url, action_m.group(1)) if action_m else response.url
"""
    new_action = """                        action_m = re.search(r'action\\s*=\\s*["\\']([^"\\']+)', whole, flags=re.I)
                        post_url = urljoin(response.url, action_m.group(1)) if action_m else response.url
                        _mc_log('form action_present=%s' % ('yes' if action_m else 'no'))
"""
    if old_action not in src:
        raise SystemExit("DropLoad form action block not found")
    src = src.replace(old_action, new_action, 1)

    provider.write_text(src, encoding="utf-8", newline="\n")
    compile(src, str(provider), "exec")

    addon = root / "addon.xml"
    addon_text = addon.read_text(encoding="utf-8")
    addon_text, n = re.subn(
        r'(<addon\\b[^>]*\\bid="plugin\\.video\\.xship"[^>]*\\bversion=")[^"]+(")',
        r'\\g<1>2026.09.28.110\\2',
        addon_text, count=1, flags=re.I)
    if n != 1:
        raise SystemExit("Could not update addon version")
    addon.write_text(addon_text, encoding="utf-8", newline="\n")

    for cache in list(root.rglob("__pycache__")):
        shutil.rmtree(cache, ignore_errors=True)
    for pyc in root.rglob("*.pyc"):
        pyc.unlink(missing_ok=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for fp in sorted(root.rglob("*")):
            if fp.is_file():
                zf.write(fp, fp.relative_to(td).as_posix())

with zipfile.ZipFile(OUT, "r") as zf:
    assert zf.testzip() is None
    addon_text = zf.read("plugin.video.xship/addon.xml").decode("utf-8")
    provider_text = zf.read("plugin.video.xship/scrapers/scrapers_source/de/meinecloud.py").decode("utf-8")
    assert 'version="2026.09.28.110"' in addon_text
    assert "form POST headers=e2i-root-referer" in provider_text
    assert "form action_present=" in provider_text
print("Built", OUT)
