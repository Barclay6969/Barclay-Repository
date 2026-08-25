from pathlib import Path
import re
import shutil
import zipfile
import py_compile

base_zip = Path('test-builds/plugin.video.xship-2026.08.25.11.zip')
work = Path('/tmp/xship-megakino-domain-test')
out_dir = Path('test-output')
out = out_dir / 'plugin.video.xship-2026.08.25.11.1-MEGAKINO-DOMAIN-TEST.zip'

shutil.rmtree(work, ignore_errors=True)
shutil.rmtree(out_dir, ignore_errors=True)
work.mkdir(parents=True)
out_dir.mkdir(parents=True)

with zipfile.ZipFile(base_zip) as z:
    z.extractall(work)
root = work / 'plugin.video.xship'

helper = root / 'resources/lib/domain_manager.py'
helper.write_text(r'''# -*- coding: utf-8 -*-
# xShip test domain resolver - redirect detection + isolated Kodi profile cache
import json
import os
from urllib.parse import urlparse

import requests
import xbmc
import xbmcvfs

_CACHE_FILE = 'domains-test.json'
_USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
               'AppleWebKit/537.36 (KHTML, like Gecko) '
               'Chrome/140.0 Safari/537.36')


def _log(message):
    try:
        xbmc.log('[xShip DomainTest] %s' % message, xbmc.LOGINFO)
    except Exception:
        pass


def _normalize_domain(value):
    value = (value or '').strip()
    if not value:
        return ''
    if '://' not in value:
        value = 'https://' + value
    host = (urlparse(value).hostname or '').strip().lower()
    if host.startswith('www.'):
        host = host[4:]
    return host


def _cache_path():
    profile = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.xship')
    if not xbmcvfs.exists(profile):
        xbmcvfs.mkdirs(profile)
    return os.path.join(profile, _CACHE_FILE)


def _read_cache():
    try:
        path = _cache_path()
        if not xbmcvfs.exists(path):
            return {}
        f = xbmcvfs.File(path, 'r')
        try:
            raw = f.read()
        finally:
            f.close()
        data = json.loads(raw or '{}')
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        _log('cache read failed: %s' % exc)
        return {}


def _write_cache(data):
    try:
        f = xbmcvfs.File(_cache_path(), 'w')
        try:
            f.write(json.dumps(data, sort_keys=True))
        finally:
            f.close()
    except Exception as exc:
        _log('cache write failed: %s' % exc)


def resolve_domain(identifier, start_domain, timeout=7):
    """Return cached domain or discover an HTTP(S) redirect target."""
    start = _normalize_domain(start_domain)
    cache = _read_cache()
    cached = _normalize_domain(cache.get(identifier, ''))
    if cached:
        _log('%s cached=%s' % (identifier, cached))
        return cached

    _log('%s start=%s' % (identifier, start))
    headers = {'User-Agent': _USER_AGENT, 'Accept': 'text/html,application/xhtml+xml'}
    for scheme in ('https', 'http'):
        try:
            response = requests.get(
                '%s://%s/' % (scheme, start),
                headers=headers,
                allow_redirects=True,
                timeout=timeout
            )
            final = _normalize_domain(response.url)
            if final and final != start:
                cache[identifier] = final
                _write_cache(cache)
                _log('%s redirected=%s' % (identifier, final))
                return final
            _log('%s no redirect (%s)' % (identifier, response.status_code))
            return start
        except Exception as exc:
            _log('%s %s probe failed: %s' % (identifier, scheme, exc))

    return start
''', encoding='utf-8')

mega = root / 'scrapers/scrapers_source/de/megakino.py'
text = mega.read_text(encoding='utf-8')
if "SITE_DOMAIN = 'megakino16.com'" not in text:
    raise SystemExit('Current megakino16.com marker not found')
import_line = 'from resources.lib.control import getSetting, urljoin'
if import_line not in text:
    raise SystemExit('MegaKino control import not found')
text = text.replace(import_line, import_line + '\nfrom resources.lib.domain_manager import resolve_domain', 1)
text = text.replace("SITE_DOMAIN = 'megakino16.com'", "SITE_DOMAIN = 'megakino15.com'", 1)
old = "self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)"
new = "self.domain = resolve_domain(SITE_IDENTIFIER, SITE_DOMAIN)"
if old not in text:
    raise SystemExit('MegaKino domain assignment not found')
text = text.replace(old, new, 1)
mega.write_text(text, encoding='utf-8')

settings = root / 'resources/settings.xml'
settings_text = settings.read_text(encoding='utf-8')
# Current 25.11 already carries 15.com as the settings default; force it for determinism.
settings_text = re.sub(
    r'(id="provider\.megakino\.domain"[^>]*default=")[^"]+("[^>]*/>)',
    r'\g<1>megakino15.com\2',
    settings_text,
    count=1
)
settings.write_text(settings_text, encoding='utf-8')

addon = root / 'addon.xml'
addon_text = addon.read_text(encoding='utf-8')
addon_text, count = re.subn(
    r'(<addon\b[^>]*?\bversion=")[^"]+("[^>]*>)',
    r'\g<1>2026.08.25.11.1\2', addon_text, count=1, flags=re.S
)
if count != 1:
    raise SystemExit('Could not set test addon version')
news = ('2026.08.25.11.1 - MegaKino Domain-Test\n'
        '- MegaKino starts deliberately at megakino15.com.\n'
        '- HTTP(S) redirect target is detected and cached separately in domains-test.json.\n\n')
if '<news>' in addon_text:
    addon_text = addon_text.replace('<news>', '<news>' + news, 1)
addon.write_text(addon_text, encoding='utf-8')

py_compile.compile(str(helper), doraise=True)
py_compile.compile(str(mega), doraise=True)

with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for fp in root.rglob('*'):
        if fp.is_file() and '__pycache__' not in fp.parts:
            z.write(fp, fp.relative_to(work))

with zipfile.ZipFile(out) as z:
    bad = z.testzip()
    if bad:
        raise SystemExit('Bad ZIP member: %s' % bad)
    mega_built = z.read('plugin.video.xship/scrapers/scrapers_source/de/megakino.py').decode('utf-8')
    helper_built = z.read('plugin.video.xship/resources/lib/domain_manager.py').decode('utf-8')
    addon_built = z.read('plugin.video.xship/addon.xml').decode('utf-8')
    settings_built = z.read('plugin.video.xship/resources/settings.xml').decode('utf-8')
    assert "SITE_DOMAIN = 'megakino15.com'" in mega_built
    assert 'resolve_domain(SITE_IDENTIFIER, SITE_DOMAIN)' in mega_built
    assert '[xShip DomainTest]' in helper_built
    assert 'version="2026.08.25.11.1"' in addon_built
    assert 'provider.megakino.domain' in settings_built and 'default="megakino15.com"' in settings_built

print('BUILT', out, out.stat().st_size)
