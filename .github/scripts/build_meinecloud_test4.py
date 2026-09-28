from pathlib import Path
import re, shutil, tempfile, zipfile

BASE = Path("test-builds/plugin.video.xship-2026.09.28.107-MEINECLOUD-DROPLOAD-NATIVE-TEST3.zip")
OUT = Path("test-builds/plugin.video.xship-2026.09.28.108-MEINECLOUD-DROPLOAD-FORM-TEST4.zip")
if not BASE.exists():
    raise SystemExit("Missing TEST3 base ZIP")

with tempfile.TemporaryDirectory() as td_raw:
    td = Path(td_raw)
    with zipfile.ZipFile(BASE, "r") as zf:
        zf.extractall(td)

    root = td / "plugin.video.xship"
    provider = root / "scrapers/scrapers_source/de/meinecloud.py"
    src = provider.read_text(encoding="utf-8")

    src = src.replace("import requests\n", "import requests\nimport time\nfrom urllib.parse import urljoin\n", 1)

    anchor = """            stream = _mc_find_stream(html)
            if not stream:
                _mc_log('no direct stream found for %s' % code)
                continue
"""
    replacement = r'''            stream = _mc_find_stream(html)

            # Current DropLoad/dr0pstream may first return a short waiting/form page.
            # Follow an iframe/data-embed hop if present, then mimic the site's
            # hidden-form continuation before falling back to ResolveURL.
            if not stream:
                hop = re.search(r'(?:data-embed|iframe\s+src)=["\']([^"\']+)', html, flags=re.I)
                if hop:
                    hop_url = urljoin(response.url, hop.group(1))
                    try:
                        hop_headers = dict(headers)
                        hop_headers['Referer'] = response.url
                        hop_res = session.get(hop_url, headers=hop_headers, timeout=10, allow_redirects=True)
                        hop_html = hop_res.text or ''
                        _mc_log('hop status=%s bytes=%s final=%s' % (
                            hop_res.status_code, len(hop_html), hop_res.url
                        ))
                        if hop_res.status_code == 200 and hop_html:
                            response = hop_res
                            html = hop_html
                            stream = _mc_find_stream(html)
                    except Exception as exc:
                        _mc_log('hop error | %r' % (exc,))

            if not stream and '<form' in (html or '').lower():
                try:
                    form = re.search(r'<form[^>]*>(.*?)</form>', html, flags=re.I | re.S)
                    if form:
                        whole = form.group(0)
                        body = form.group(1)
                        action_m = re.search(r'action\s*=\s*["\']([^"\']+)', whole, flags=re.I)
                        post_url = urljoin(response.url, action_m.group(1)) if action_m else response.url
                        data = {}
                        for tag in re.findall(r'<input[^>]*>', body, flags=re.I):
                            type_m = re.search(r'type\s*=\s*["\']?([^"\'\s>]+)', tag, flags=re.I)
                            kind = (type_m.group(1).lower() if type_m else '')
                            if kind not in ('hidden', 'submit', ''):
                                continue
                            name_m = re.search(r'name\s*=\s*["\']([^"\']+)', tag, flags=re.I)
                            if not name_m:
                                continue
                            value_m = re.search(r'value\s*=\s*["\']([^"\']*)', tag, flags=re.I)
                            value = value_m.group(1) if value_m else ''
                            if name_m.group(1) == 'file_code' and not value:
                                value = code
                            data[name_m.group(1)] = value

                        if data:
                            _mc_log('form detected | fields=%s | action=%s' % (
                                ','.join(sorted(data.keys())), post_url
                            ))
                            time.sleep(6)
                            post_headers = dict(headers)
                            post_headers['Referer'] = response.url
                            post_headers['Origin'] = 'https://' + response.url.split('/')[2]
                            post_res = session.post(
                                post_url,
                                headers=post_headers,
                                data=data,
                                timeout=12,
                                allow_redirects=True
                            )
                            post_html = post_res.text or ''
                            _mc_log('form POST status=%s bytes=%s final=%s' % (
                                post_res.status_code, len(post_html), post_res.url
                            ))
                            if post_res.status_code == 200 and post_html:
                                response = post_res
                                html = post_html
                                stream = _mc_find_stream(html)
                except Exception as exc:
                    _mc_log('form fallback ERROR | %r' % (exc,))

            if not stream:
                _mc_log('no direct stream found for %s' % code)
                continue
'''
    if anchor not in src:
        raise SystemExit("TEST3 stream anchor not found")
    src = src.replace(anchor, replacement, 1)

    provider.write_text(src, encoding="utf-8", newline="\n")
    compile(src, str(provider), "exec")

    addon = root / "addon.xml"
    addon_text = addon.read_text(encoding="utf-8")
    addon_text, n = re.subn(
        r'(<addon\b[^>]*\bid="plugin\.video\.xship"[^>]*\bversion=")[^"]+(")',
        r'\g<1>2026.09.28.108\2',
        addon_text,
        count=1,
        flags=re.I,
    )
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
    assert 'version="2026.09.28.108"' in addon_text
    assert "form detected" in provider_text
    assert "form POST status" in provider_text
print("Built", OUT)
