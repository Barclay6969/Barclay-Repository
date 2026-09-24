# -*- coding: utf-8 -*-
# xShip central domain manager
# Detects HTTP(S) redirects, keeps Kodi settings in sync and periodically rechecks cached domains.

import json
import os
import re
import time
from urllib.parse import urlparse

import requests
import xbmc
import xbmcaddon
import xbmcvfs

_CACHE_FILE = 'domains.json'
_LEGACY_CACHE_FILE = 'domains-test.json'
_TTL_OK = 6 * 60 * 60
_TTL_FAILED = 60 * 60
_USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
               'AppleWebKit/537.36 (KHTML, like Gecko) '
               'Chrome/140.0 Safari/537.36')

# Verified migrations from domains already known to xShip.
# Redirect discovery remains active, so later changes can be learned automatically.
_KNOWN_MIGRATIONS = {
    'kinoger': {
        'kinoger.com': 'kinoger.fun',
        'kinoger.to': 'kinoger.fun',
        'kinoger.ch': 'kinoger.fun',
    },
    'fhdfilme': {
        'hdfilme.my': 'hdfilme.win',
        'hdfilme.blog': 'hdfilme.win',
    },
    'streamcloud': {
        'streamcloud.my': 'streamcloud.bid',
    },
    'megakino': {
        'megakino15.com': 'megakino16.com',
    },
}


def _log(message):
    try:
        xbmc.log('[xShip DomainManager] %s' % message, xbmc.LOGINFO)
    except Exception:
        pass


def _normalize_domain(value):
    value = (value or '').strip()
    if not value:
        return ''
    if '://' not in value:
        value = 'https://' + value
    return (urlparse(value).hostname or '').strip().lower()


def _profile_path(filename):
    profile = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.xship')
    if not xbmcvfs.exists(profile):
        xbmcvfs.mkdirs(profile)
    return os.path.join(profile, filename)


def _load_json(path):
    try:
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


def _read_cache():
    data = _load_json(_profile_path(_CACHE_FILE))
    if data:
        return data

    # One-time compatibility with the MegaKino test cache.
    legacy = _load_json(_profile_path(_LEGACY_CACHE_FILE))
    migrated = {}
    for identifier, value in legacy.items():
        if isinstance(value, str):
            domain = _normalize_domain(value)
            if domain:
                migrated[identifier] = {'domain': domain, 'checked': 0, 'ok': True}
        elif isinstance(value, dict):
            migrated[identifier] = value
    return migrated


def _write_cache(data):
    try:
        f = xbmcvfs.File(_profile_path(_CACHE_FILE), 'w')
        try:
            f.write(json.dumps(data, sort_keys=True))
        finally:
            f.close()
    except Exception as exc:
        _log('cache write failed: %s' % exc)


def _addon():
    return xbmcaddon.Addon('plugin.video.xship')


def _setting_domain(identifier):
    try:
        return _normalize_domain(_addon().getSetting('provider.%s.domain' % identifier))
    except Exception:
        return ''


def _sync_setting(identifier, domain):
    try:
        domain = _normalize_domain(domain)
        if not domain:
            return
        setting_id = 'provider.%s.domain' % identifier
        addon = _addon()
        current = _normalize_domain(addon.getSetting(setting_id))
        if current != domain:
            addon.setSetting(setting_id, domain)
            _log('%s setting updated=%s' % (identifier, domain))
    except Exception as exc:
        _log('%s setting sync failed: %s' % (identifier, exc))


def _cache_entry(cache, identifier):
    value = cache.get(identifier)
    if isinstance(value, str):
        domain = _normalize_domain(value)
        return {'domain': domain, 'checked': 0, 'ok': True} if domain else None
    if isinstance(value, dict):
        domain = _normalize_domain(value.get('domain', ''))
        if not domain:
            return None
        return {
            'domain': domain,
            'checked': int(value.get('checked', 0) or 0),
            'ok': bool(value.get('ok', True)),
            'status': value.get('status'),
        }
    return None


def _cache_is_fresh(entry, now):
    if not entry:
        return False
    checked = int(entry.get('checked', 0) or 0)
    if checked <= 0:
        return False
    ttl = _TTL_OK if entry.get('ok', True) else _TTL_FAILED
    return (now - checked) < ttl


def _migrate_known(identifier, domain):
    domain = _normalize_domain(domain)
    target = _normalize_domain(_KNOWN_MIGRATIONS.get(identifier, {}).get(domain, ''))
    if target and target != domain:
        _log('%s known migration=%s -> %s' % (identifier, domain, target))
        return target
    return domain


def _root_label(domain):
    host = _normalize_domain(domain)
    if host.startswith('www.'):
        host = host[4:]
    label = host.split('.')[0] if host else ''
    return re.sub(r'[^a-z]+', '', label)


def _related_redirect(start, target):
    start = _normalize_domain(start)
    target = _normalize_domain(target)
    if not start or not target:
        return False
    if start == target:
        return True
    a = _root_label(start)
    b = _root_label(target)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    common = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        common += 1
    return common >= 5


def _probe(domain, timeout):
    headers = {
        'User-Agent': _USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
    }
    last_error = None
    for scheme in ('https', 'http'):
        try:
            response = requests.get(
                '%s://%s/' % (scheme, domain),
                headers=headers,
                allow_redirects=True,
                timeout=timeout,
                stream=True,
            )
            try:
                final = _normalize_domain(response.url)
                status = int(response.status_code or 0)
            finally:
                response.close()
            return final or domain, status, None
        except Exception as exc:
            last_error = exc
    return domain, 0, last_error


def resolve_domain(identifier, default_domain, timeout=2.5):
    """Return the current domain for a provider and keep its Kodi setting synchronized.

    Resolution order:
      1. User-visible provider setting / existing cache
      2. Known verified migration
      3. HTTP(S) redirect discovery
      4. Default domain fallback

    Successful entries are rechecked every six hours; failed probes after one hour.
    """
    now = int(time.time())
    default = _normalize_domain(default_domain)
    configured = _setting_domain(identifier) or default
    cache = _read_cache()
    entry = _cache_entry(cache, identifier)

    # A manually edited setting wins over an old cache entry.
    if entry and configured and configured != entry.get('domain'):
        _log('%s manual/configured domain=%s (cache was %s)' % (
            identifier, configured, entry.get('domain')))
        entry = None

    candidate = entry.get('domain') if entry else configured
    candidate = _migrate_known(identifier, candidate or default)

    if entry and candidate == entry.get('domain') and _cache_is_fresh(entry, now):
        _sync_setting(identifier, candidate)
        _log('%s cached=%s' % (identifier, candidate))
        return candidate

    # Try the selected/current domain first, then the shipped default if different.
    attempts = []
    for domain in (candidate, default):
        domain = _migrate_known(identifier, domain)
        if domain and domain not in attempts:
            attempts.append(domain)

    for domain in attempts:
        _log('%s check=%s' % (identifier, domain))
        final, status, error = _probe(domain, timeout)
        if error is not None:
            _log('%s probe failed=%s (%s)' % (identifier, domain, error))
            continue

        resolved = domain
        if final != domain:
            if _related_redirect(domain, final):
                resolved = final
                _log('%s redirected=%s -> %s' % (identifier, domain, resolved))
            else:
                _log('%s rejected unrelated redirect=%s -> %s' % (identifier, domain, final))

        cache[identifier] = {
            'domain': resolved,
            'checked': now,
            'ok': True,
            'status': status,
        }
        _write_cache(cache)
        _sync_setting(identifier, resolved)
        _log('%s active=%s status=%s' % (identifier, resolved, status))
        return resolved

    # Avoid repeating long failures on every source search.
    fallback = candidate or default
    cache[identifier] = {
        'domain': fallback,
        'checked': now,
        'ok': False,
        'status': 0,
    }
    _write_cache(cache)
    _sync_setting(identifier, fallback)
    _log('%s unavailable; keeping=%s' % (identifier, fallback))
    return fallback