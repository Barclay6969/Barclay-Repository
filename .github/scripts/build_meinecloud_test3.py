from pathlib import Path
import re
import shutil
import tempfile
import zipfile

BASE = Path("test-builds/plugin.video.xship-2026.09.28.106-MEINECLOUD-SERIES-DEFERRED-TEST2.zip")
OUT = Path("test-builds/plugin.video.xship-2026.09.28.107-MEINECLOUD-DROPLOAD-NATIVE-TEST3.zip")

if not BASE.exists():
    raise SystemExit("Missing TEST2 base ZIP")

with tempfile.TemporaryDirectory() as td_raw:
    td = Path(td_raw)
    with zipfile.ZipFile(BASE, "r") as zf:
        zf.extractall(td)

    root = td / "plugin.video.xship"
    provider = root / "scrapers/scrapers_source/de/meinecloud.py"
    src = provider.read_text(encoding="utf-8")

    import_anchor = "from resources.lib.domain_manager import resolve_domain\n"
    imports = """from resources.lib.domain_manager import resolve_domain
import base64
import re
from html import unescape
from urllib.parse import quote
import requests
"""
    if import_anchor not in src:
        raise SystemExit("Import anchor missing")
    src = src.replace(import_anchor, imports, 1)

    marker = "SITE_NAME = SITE_IDENTIFIER.upper()\n\n\n"
    helper = r'''SITE_NAME = SITE_IDENTIFIER.upper()


_MC_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
_MC_CHARS = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'


def _mc_log(message):
    try:
        import xbmc
        xbmc.log('[xShip MEINECLOUD-DROP] ' + str(message), xbmc.LOGINFO)
    except Exception:
        pass


def _mc_encode(num, radix):
    if num == 0:
        return '0'
    out = ''
    while num > 0:
        rem = num % radix
        if rem >= len(_MC_CHARS):
            return ''
        out = _MC_CHARS[rem] + out
        num //= radix
    return out


def _mc_unpack_one(block):
    try:
        match = re.search(
            r"}\s*\(\s*'(.*?)'\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*'(.*?)'\.split\('\|'\)",
            block,
            flags=re.S
        )
        if not match:
            return ''
        payload = match.group(1).replace("\\'", "'")
        radix = int(match.group(2))
        count = int(match.group(3))
        words = match.group(4).split('|')
        mapping = {}
        for index in range(count - 1, -1, -1):
            key = _mc_encode(index, radix)
            if not key:
                continue
            value = words[index] if index < len(words) and words[index] else key
            mapping[key] = value
        return re.sub(r'\b\w+\b', lambda m: mapping.get(m.group(0), m.group(0)), payload)
    except Exception:
        return ''


def _mc_unpack_all(html):
    output = []
    pattern = re.compile(
        r"eval\(function\(p,a,c,k,e,[dr]\)\{[\s\S]*?\.split\('\|'\)[^)]*\)\)",
        flags=re.I
    )
    for match in pattern.finditer(html or ''):
        unpacked = _mc_unpack_one(match.group(0))
        if unpacked:
            output.append(unpacked)
    return '\n'.join(output)


def _mc_find_stream(html):
    flat = ((html or '') + '\n' + _mc_unpack_all(html or '')).replace('\\/', '/')
    flat = unescape(flat)

    match = re.search(r"""https?://[^"'\s\\]+\.m3u8[^"'\s\\]*""", flat, flags=re.I)
    if match:
        return match.group(0)

    for token in re.findall(
        r"""atob\s*\(\s*["']([A-Za-z0-9+/=]{20,})["']\s*\)""",
        html or '',
        flags=re.I
    ):
        try:
            padded = token + ('=' * (-len(token) % 4))
            decoded = base64.b64decode(padded).decode('utf-8', 'ignore').replace('\\/', '/')
            match = re.search(r"""https?://[^"'\s\\]+\.m3u8[^"'\s\\]*""", decoded, flags=re.I)
            if match:
                return match.group(0)
        except Exception:
            pass

    match = re.search(
        r"""(?:file|source|src)\s*:\s*["']([^"']+\.(?:m3u8|mp4)[^"']*)["']""",
        flat,
        flags=re.I
    )
    if match:
        return match.group(1).replace('\\/', '/')

    match = re.search(r"""https?://[^"'\s\\]+\.mp4[^"'\s\\]*""", flat, flags=re.I)
    if match:
        return match.group(0)
    return ''


def _mc_resolve_dropload(url):
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

        candidates = [raw.split('|', 1)[0]]
        canonical = 'https://dr0pstream.com/e/%s' % code
        if canonical not in candidates:
            candidates.append(canonical)

        session = requests.Session()
        for page_url in candidates:
            headers = {
                'User-Agent': _MC_UA,
                'Referer': 'https://dr0pstream.com/',
                'Origin': 'https://dr0pstream.com',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
            }
            try:
                response = session.get(page_url, headers=headers, timeout=10, allow_redirects=True)
            except Exception as exc:
                _mc_log('GET error %s | %r' % (page_url, exc))
                continue

            html = response.text or ''
            _mc_log('GET status=%s bytes=%s final=%s' % (
                response.status_code, len(html), response.url
            ))
            if response.status_code != 200 or not html:
                continue

            stream = _mc_find_stream(html)
            if not stream:
                _mc_log('no direct stream found for %s' % code)
                continue

            stream = stream.replace('&amp;', '&').strip()
            origin = 'https://%s' % (re.sub(r'^www\.', '', response.url.split('/')[2]))
            stream_headers = {
                'User-Agent': _MC_UA,
                'Referer': response.url,
                'Origin': origin,
            }
            suffix = '&'.join(
                '%s=%s' % (key, quote(value, safe=''))
                for key, value in stream_headers.items()
            )
            _mc_log('native stream found | code=%s | host=%s' % (
                code, stream.split('/')[2] if '://' in stream else 'relative'
            ))
            return stream + '|' + suffix
    except Exception as exc:
        _mc_log('resolver ERROR | %r' % (exc,))
    return ''


'''
    if marker not in src:
        raise SystemExit("SITE_NAME marker missing")
    src = src.replace(marker, helper, 1)

    add_anchor = """            seen.add(sUrl)

            try:
"""
    add_native = """            seen.add(sUrl)

            if defer_resolve:
                native_url = _mc_resolve_dropload(sUrl)
                if native_url:
                    index += 1
                    source_name = 'DropLoad'
                    if numbered and index > 1:
                        source_name = '%s(%s)' % (source_name, index)
                    self.sources.append({
                        'source': source_name,
                        'quality': '1080p',
                        'language': 'de',
                        'url': native_url,
                        'direct': True,
                        'priority': int(self.priority),
                        'prioHoster': 100
                    })
                    continue

            try:
"""
    if add_anchor not in src:
        raise SystemExit("_add_links anchor missing")
    src = src.replace(add_anchor, add_native, 1)

    provider.write_text(src, encoding="utf-8", newline="\n")
    compile(src, str(provider), "exec")

    addon = root / "addon.xml"
    addon_text = addon.read_text(encoding="utf-8")
    addon_text, n = re.subn(
        r'(<addon\b[^>]*\bid="plugin\.video\.xship"[^>]*\bversion=")[^"]+(")',
        r'\g<1>2026.09.28.107\2',
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
    bad = zf.testzip()
    if bad:
        raise SystemExit("Corrupt ZIP member: " + bad)
    addon_text = zf.read("plugin.video.xship/addon.xml").decode("utf-8")
    provider_text = zf.read("plugin.video.xship/scrapers/scrapers_source/de/meinecloud.py").decode("utf-8")
    assert 'version="2026.09.28.107"' in addon_text
    assert "_mc_resolve_dropload" in provider_text
    assert "[xShip MEINECLOUD-DROP]" in provider_text

print("Built", OUT)
