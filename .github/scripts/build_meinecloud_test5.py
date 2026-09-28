from pathlib import Path
import re, shutil, tempfile, zipfile

BASE = Path("test-builds/plugin.video.xship-2026.09.28.108-MEINECLOUD-DROPLOAD-FORM-TEST4.zip")
OUT = Path("test-builds/plugin.video.xship-2026.09.28.109-MEINECLOUD-TVOVERVIEW-TEST5.zip")
if not BASE.exists():
    raise SystemExit("Missing TEST4 base ZIP")

override = r'''

# --- TEST5: compare episode /api/resolve with TV /api/embed-links overview ---
def get_series_links(imdb, season, episode, base_link):
    import json
    import re
    from urllib.parse import urlparse
    import requests

    def _log(msg):
        try:
            import xbmc
            xbmc.log('[xShip MEINECLOUD-TVTEST] ' + str(msg), xbmc.LOGINFO)
        except Exception:
            pass

    def _norm(url):
        url = (url or '').strip()
        if url.startswith('//'):
            url = 'https:' + url
        return url

    def _host(url):
        try:
            return (urlparse(url).hostname or '').lower()
        except Exception:
            return ''

    def _collect_http(obj):
        out = []
        if isinstance(obj, dict):
            for value in obj.values():
                out.extend(_collect_http(value))
        elif isinstance(obj, list):
            for value in obj:
                out.extend(_collect_http(value))
        elif isinstance(obj, str):
            value = _norm(obj)
            if value.startswith('http'):
                out.append(value)
        return out

    base = (base_link or 'https://meinecloud.click').rstrip('/')
    imdb = str(imdb or '').strip()
    try:
        season_i = int(season)
        episode_i = int(episode)
    except Exception:
        return []
    if not imdb:
        return []

    ua = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    session = requests.Session()
    common = {'User-Agent': ua, 'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8'}

    merged = []
    resolve_links = []
    overview_links = []

    # 1) Episode-specific resolver API
    page_url = '%s/serial/%s/%s/%s' % (base, imdb, season_i, episode_i)
    try:
        r = session.get(page_url, headers=common, timeout=10, allow_redirects=True)
        html = r.text or ''
        _log('episode page status=%s bytes=%s imdb=%s S%sE%s' %
             (r.status_code, len(html), imdb, season_i, episode_i))

        def attr(name, default=''):
            m = re.search(r'%s=["\']([^"\']*)' % re.escape(name), html, re.I)
            return m.group(1) if m else default

        token = attr('data-resolve-token')
        endpoint = attr('data-resolve-endpoint', '/api/resolve')
        if token:
            if not endpoint.startswith('http'):
                endpoint = base + '/' + endpoint.lstrip('/')
            body = {
                'type': attr('data-type', 'tv'),
                'id': attr('data-id', imdb),
                'season': attr('data-season', str(season_i)),
                'episode': attr('data-episode', str(episode_i)),
                'mode': attr('data-mode', 'custom'),
                'token': token
            }
            headers = {
                'User-Agent': ua,
                'Referer': page_url,
                'Origin': base,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            rr = session.post(endpoint, headers=headers, json=body, timeout=10, allow_redirects=True)
            try:
                data = rr.json()
            except Exception:
                data = {}
            for src in (data.get('sources') or []) if isinstance(data, dict) else []:
                if isinstance(src, dict):
                    u = _norm(src.get('url'))
                    if u.startswith('http') and 'meinecloud' not in u.lower() and u not in resolve_links:
                        resolve_links.append(u)
            _log('resolve status=%s sources=%s hosts=%s' %
                 (rr.status_code, len(resolve_links), ','.join(_host(u) for u in resolve_links) or '-'))
        else:
            _log('resolve token missing imdb=%s S%sE%s' % (imdb, season_i, episode_i))
    except Exception as exc:
        _log('resolve ERROR %r' % (exc,))

    # 2) TV overview API. The rebuilt site exposes an episode URL here as well.
    overview_url = '%s/serial/%s' % (base, imdb)
    try:
        ro = session.get(overview_url, headers=common, timeout=10, allow_redirects=True)
        overview_html = ro.text or ''
        token_m = re.search(r'''token:\s*["']([^"']+)''', overview_html)
        _log('overview page status=%s bytes=%s token=%s' %
             (ro.status_code, len(overview_html), 'yes' if token_m else 'no'))
        if token_m:
            headers = {
                'User-Agent': ua,
                'Referer': overview_url,
                'Origin': base,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            rr = session.post(
                base + '/api/embed-links',
                headers=headers,
                json={'type': 'tv', 'id': imdb, 'token': token_m.group(1)},
                timeout=10,
                allow_redirects=True
            )
            try:
                data = rr.json()
            except Exception:
                data = {}
            tv = data.get('tv') if isinstance(data, dict) else None
            matched = None
            for s in (tv or {}).get('seasons') or []:
                try:
                    sn = int(s.get('season_number'))
                except Exception:
                    continue
                if sn != season_i:
                    continue
                for ep in s.get('episodes') or []:
                    try:
                        en = int(ep.get('episode_number'))
                    except Exception:
                        continue
                    if en == episode_i:
                        matched = ep
                        break
                if matched is not None:
                    break

            if isinstance(matched, dict):
                # Prefer explicit episode URL, but inspect all URL fields too.
                candidates = []
                u = _norm(matched.get('url'))
                if u:
                    candidates.append(u)
                candidates.extend(_collect_http(matched))
                for u in candidates:
                    u = _norm(u)
                    if (u.startswith('http') and
                            'meinecloud' not in u.lower() and
                            u not in overview_links):
                        overview_links.append(u)
                _log('overview episode keys=%s' % ','.join(sorted(matched.keys())))
            else:
                _log('overview episode not found S%sE%s' % (season_i, episode_i))

            _log('overview api status=%s sources=%s hosts=%s' %
                 (rr.status_code, len(overview_links),
                  ','.join(_host(u) for u in overview_links) or '-'))
    except Exception as exc:
        _log('overview ERROR %r' % (exc,))

    for u in resolve_links + overview_links:
        if u not in merged:
            merged.append(u)

    _log('merged sources=%s hosts=%s' %
         (len(merged), ','.join(_host(u) for u in merged) or '-'))
    return merged
'''

with tempfile.TemporaryDirectory() as td_raw:
    td = Path(td_raw)
    with zipfile.ZipFile(BASE, "r") as zf:
        zf.extractall(td)

    root = td / "plugin.video.xship"

    helpers = []
    for p in root.rglob("meinecloud_shared.py"):
        helpers.append(p)
    if not helpers:
        for p in root.rglob("*.py"):
            txt = p.read_text(encoding="utf-8", errors="ignore")
            if "def get_series_links" in txt and "MEINECLOUD-API" in txt:
                helpers.append(p)
    if not helpers:
        raise SystemExit("MeineCloud shared helper not found")

    helper = helpers[0]
    src = helper.read_text(encoding="utf-8")
    src += override
    helper.write_text(src, encoding="utf-8", newline="\n")
    compile(src, str(helper), "exec")
    print("Patched helper:", helper.relative_to(root))

    addon = root / "addon.xml"
    addon_text = addon.read_text(encoding="utf-8")
    addon_text, n = re.subn(
        r'(<addon\b[^>]*\bid="plugin\.video\.xship"[^>]*\bversion=")[^"]+(")',
        r'\g<1>2026.09.28.109\2',
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
    assert 'version="2026.09.28.109"' in addon_text
    helper_names = [n for n in zf.namelist() if n.endswith("meinecloud_shared.py")]
    if not helper_names:
        raise SystemExit("Patched helper missing in ZIP")
    helper_text = zf.read(helper_names[0]).decode("utf-8")
    assert "MEINECLOUD-TVTEST" in helper_text
    assert "overview api status" in helper_text
print("Built", OUT)
