from pathlib import Path
import re
import shutil
import tempfile
import zipfile

BASE = Path("test-builds/plugin.video.xship-2026.09.28.107-MEINECLOUD-DROPLOAD-NATIVE-TEST3.zip")
OUT = Path("test-builds/plugin.video.xship-2026.09.28.108-MEINECLOUD-DROPLOAD-DS2-TEST4.zip")

with tempfile.TemporaryDirectory() as td_raw:
    td = Path(td_raw)
    with zipfile.ZipFile(BASE, "r") as zf:
        zf.extractall(td)

    root = td / "plugin.video.xship"
    provider = root / "scrapers/scrapers_source/de/meinecloud.py"
    src = provider.read_text(encoding="utf-8")

    if "import time\n" not in src:
        src = src.replace("import requests\n", "import requests\nimport time\n", 1)

    new_func = r'''def _mc_resolve_dropload(url):
    try:
        raw = str(url or '').strip()
        if not raw:
            return ''
        low = raw.lower()
        if 'dropload.' not in low and 'dr0pstream.' not in low and 'dropcdn.' not in low:
            return ''

        clean = raw.split('|', 1)[0].split('?', 1)[0].split('#', 1)[0].rstrip('/')
        match = re.search(r'(?:embed-|/e/|/d/|/)([A-Za-z0-9]+)(?:\.html)?$', clean, flags=re.I)
        if not match:
            _mc_log('file code missing: %s' % raw)
            return ''
        code = match.group(1)

        session = requests.Session()
        candidates = [
            raw.split('|', 1)[0],
            'https://dr0pstream.com/e/%s' % code,
            'https://dropload.pro/e/%s' % code,
        ]
        seen_pages = set()

        def _headers(referer='https://dr0pstream.com/'):
            return {
                'User-Agent': _MC_UA,
                'Accept': '*/*',
                'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
                'Referer': referer,
                'Origin': 'https://dr0pstream.com',
                'X-Requested-With': 'XMLHttpRequest',
            }

        def _cookie_header(html=''):
            cookies = {}
            try:
                cookies.update(session.cookies.get_dict())
            except Exception:
                pass
            for name, value in re.findall(
                r"""\$\.cookie\(\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]*)['"]""",
                html or '',
                flags=re.I
            ):
                cookies[name] = value
            return '; '.join('%s=%s' % (k, v) for k, v in cookies.items())

        def _try_hidden_form(html, page_url):
            form = re.search(r'<form\b([^>]*)>(.*?)</form>', html or '', flags=re.I | re.S)
            if not form:
                return ''
            attrs, body = form.group(1), form.group(2)
            action = re.search(r"""action\s*=\s*['"]([^'"]+)""", attrs, flags=re.I)
            action_url = action.group(1) if action else page_url
            if action_url.startswith('/'):
                action_url = 'https://dr0pstream.com' + action_url
            fields = {}
            for tag in re.findall(r'<input\b[^>]*>', body, flags=re.I):
                nm = re.search(r"""name\s*=\s*['"]([^'"]+)""", tag, flags=re.I)
                if not nm:
                    continue
                vl = re.search(r"""value\s*=\s*['"]([^'"]*)""", tag, flags=re.I)
                fields[nm.group(1)] = vl.group(1) if vl else ''
            if fields.get('file_code', None) == '':
                fields['file_code'] = code
            captcha = bool(re.search(r'(?:g-recaptcha|cf-turnstile|turnstile|data-sitekey)', html or '', flags=re.I))
            _mc_log('form detected | fields=%s | captcha=%s' % (sorted(fields.keys()), captcha))
            try:
                time.sleep(6)
                h = _headers(page_url)
                ck = _cookie_header(html)
                if ck:
                    h['Cookie'] = ck
                resp = session.post(action_url, data=fields, headers=h, timeout=10, allow_redirects=True)
                _mc_log('form POST status=%s bytes=%s final=%s' % (resp.status_code, len(resp.text or ''), resp.url))
                return resp.text or ''
            except Exception as exc:
                _mc_log('form POST error | %r' % (exc,))
                return ''

        def _try_ds2(html, page_url):
            unpacked = _mc_unpack_all(html or '')
            if not unpacked:
                strict = re.search(
                    r"""eval\(function\(p,a,c,k,e,d\)\{.*?return p\}\('(.+?)',(\d+),(\d+),'(.+?)'\.split\('\|'\)\)\)""",
                    html or '',
                    flags=re.I | re.S
                )
                if strict:
                    try:
                        payload = strict.group(1).replace("\\'", "'").replace('\\\\', '\\')
                        radix = int(strict.group(2))
                        count = int(strict.group(3))
                        words = strict.group(4).split('|')
                        mapping = {}
                        for idx in range(count - 1, -1, -1):
                            key = _mc_encode(idx, radix)
                            if key:
                                mapping[key] = words[idx] if idx < len(words) and words[idx] else key
                        unpacked = re.sub(r'\b[0-9A-Za-z]+\b', lambda m: mapping.get(m.group(0), m.group(0)), payload)
                    except Exception:
                        unpacked = ''

            cookies = _cookie_header(html)
            long_numbers = re.findall(r'\b\d{10}\b', unpacked or '')
            hashes = re.findall(r'\b[a-f0-9]{32}\b', unpacked or '', flags=re.I)
            view_ids = re.findall(r'\b\d{6,7}\b', unpacked or '')
            _mc_log('ds2 parse | unpacked=%s | cookies=%s | long=%s | hash=%s | view=%s' % (
                len(unpacked or ''), bool(cookies), len(long_numbers), len(hashes), len(view_ids)
            ))

            if long_numbers and hashes:
                dynamic_hash = '%s-%s' % (long_numbers[-1], hashes[-1])
                view_id = view_ids[-1] if view_ids else '303030'
                beacon = 'https://dr0pstream.com/dl?op=view&file_code=%s&hash=%s&view_id=%s&adb=0' % (
                    code, dynamic_hash, view_id
                )
                try:
                    h = _headers(page_url)
                    if cookies:
                        h['Cookie'] = cookies
                    br = session.get(beacon, headers=h, timeout=10, allow_redirects=True)
                    _mc_log('ds2 beacon status=%s bytes=%s view=%s' % (br.status_code, len(br.text or ''), view_id))
                    stream = _mc_find_stream((unpacked or '') + '\n' + (html or '') + '\n' + (br.text or ''))
                    if stream:
                        return stream
                    rr = session.get(page_url, headers=h, timeout=10, allow_redirects=True)
                    _mc_log('ds2 reload status=%s bytes=%s' % (rr.status_code, len(rr.text or '')))
                    stream = _mc_find_stream(rr.text or '')
                    if stream:
                        return stream
                except Exception as exc:
                    _mc_log('ds2 error | %r' % (exc,))
            return ''

        for page_url in candidates:
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            try:
                response = session.get(page_url, headers=_headers(), timeout=10, allow_redirects=True)
            except Exception as exc:
                _mc_log('GET error %s | %r' % (page_url, exc))
                continue

            html = response.text or ''
            flags = []
            if re.search(r'(?:g-recaptcha|cf-turnstile|turnstile|data-sitekey)', html, flags=re.I):
                flags.append('captcha')
            if '<form' in html.lower():
                flags.append('form')
            if 'function(p,a,c,k,e' in html:
                flags.append('packer')
            _mc_log('GET status=%s bytes=%s final=%s flags=%s' % (
                response.status_code, len(html), response.url, ','.join(flags) or '-'
            ))
            if response.status_code != 200 or not html:
                continue

            stream = _mc_find_stream(html)
            if not stream:
                stream = _try_ds2(html, response.url)

            if not stream and '<form' in html.lower():
                posted = _try_hidden_form(html, response.url)
                if posted:
                    stream = _mc_find_stream(posted)
                    if not stream:
                        stream = _try_ds2(posted, response.url)

            if not stream:
                _mc_log('no direct stream found for %s' % code)
                continue

            stream = stream.replace('&amp;', '&').replace('\\/', '/').strip()
            if 'dropcdn.io' in stream:
                stream = stream.replace('r1.dropcdn.io', 'ds2.dropcdn.io').replace('_o/', '/').replace('_o.m3u8', '.m3u8')
                if 'srv=' not in stream:
                    stream += ('&' if '?' in stream else '?') + 'srv=ds2i'

            cookie = _cookie_header(html)
            stream_headers = {
                'User-Agent': _MC_UA,
                'Referer': 'https://dr0pstream.com/',
                'Origin': 'https://dr0pstream.com',
            }
            if cookie:
                stream_headers['Cookie'] = cookie
            suffix = '&'.join(
                '%s=%s' % (key, quote(value, safe=''))
                for key, value in stream_headers.items()
            )
            _mc_log('native stream found | code=%s | host=%s | cookie=%s' % (
                code, stream.split('/')[2] if '://' in stream else 'relative', bool(cookie)
            ))
            return stream + '|' + suffix
    except Exception as exc:
        _mc_log('resolver ERROR | %r' % (exc,))
    return ''
'''

    pattern = re.compile(r"def _mc_resolve_dropload\(url\):\n.*?\n\nclass source", flags=re.S)
    if not pattern.search(src):
        raise SystemExit("Could not locate TEST3 resolver")
    src = pattern.sub(lambda _m: new_func + "\n\nclass source", src, count=1)

    provider.write_text(src, encoding="utf-8", newline="\n")
    compile(src, str(provider), "exec")

    addon = root / "addon.xml"
    addon_text = addon.read_text(encoding="utf-8")
    addon_text, n = re.subn(
        r'(<addon\b[^>]*\bid="plugin\.video\.xship"[^>]*\bversion=")[^"]+(")',
        r'\g<1>2026.09.28.108\2',
        addon_text, count=1, flags=re.I
    )
    if n != 1:
        raise SystemExit("Could not update addon version")
    addon.write_text(addon_text, encoding="utf-8", newline="\n")

    for cache in list(root.rglob("__pycache__")):
        shutil.rmtree(cache, ignore_errors=True)
    for pyc in root.rglob("*.pyc"):
        pyc.unlink(missing_ok=True)

    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for fp in sorted(root.rglob("*")):
            if fp.is_file():
                zf.write(fp, fp.relative_to(td).as_posix())

with zipfile.ZipFile(OUT, "r") as zf:
    if zf.testzip():
        raise SystemExit("Corrupt output ZIP")
    addon_text = zf.read("plugin.video.xship/addon.xml").decode()
    provider_text = zf.read("plugin.video.xship/scrapers/scrapers_source/de/meinecloud.py").decode()
    assert 'version="2026.09.28.108"' in addon_text
    assert 'ds2 beacon status=' in provider_text
    assert 'form detected | fields=' in provider_text

print("Built", OUT)
