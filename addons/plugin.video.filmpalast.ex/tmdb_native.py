# -*- coding: utf-8 -*-
"""Native TMDb movie details with a FilmPalast playback URL.

Deliberately does not patch TMDb Helper, its player JSON, or user settings.
Kodi 21+ / TMDb Helper 6.17.9. Only loaded when a film is selected.
"""
import html
import os
import re
import sys
import unicodedata
from urllib.parse import quote_plus, urlencode, unquote_plus
import xbmc
import xbmcaddon
import xbmcgui

HELPER = 'plugin.video.themoviedb.helper'
FILMPALAST = 'plugin.video.filmpalast.ex'

def log(message, level=xbmc.LOGINFO):
    xbmc.log('[FilmPalast TMDb Native] ' + str(message), level)

def normalize(text):
    return ''.join(ch for ch in unicodedata.normalize(
        'NFKD', html.unescape(str(text or '')).casefold())
        if ch.isalnum() and not unicodedata.combining(ch))

def clean_title(value):
    value = html.unescape(unquote_plus(str(value or '')))
    value = re.sub(r'\[[^]]*\]', '', value)
    value = re.sub(r'\s+\d+(?:[.,]\d+)?\s*/\s*10\b.*$', '', value, flags=re.I)
    value = re.sub(r'\s*\((19|20)\d\d\)\s*$', '', value)
    return ' '.join(value.split()).strip(' -:')

def get_year(value):
    match = re.search(r'\b(?:19|20)\d\d\b', str(value or ''))
    return int(match.group(0)) if match else 0

def candidates(title):
    variants = [title]
    for marker in (' - ', ' – ', ' — ', ': '):
        if marker in title:
            first, second = title.split(marker, 1)
            variants.extend((first.strip(), second.strip()))
    result, seen = [], set()
    for entry in variants:
        entry = clean_title(entry)
        key = normalize(entry)
        if len(key) >= 3 and key not in seen:
            result.append(entry)
            seen.add(key)
    return result[:5]

def load_helper():
    """Kodi only includes modules declared by a plugin on that plugin's path."""
    import xml.etree.ElementTree as ET
    dependencies = (
        'script.module.requests', 'script.module.addon.signals',
        'script.module.pil', 'script.module.infotagger',
        'script.module.qrcode', 'script.module.jurialmunkey', HELPER)
    for addon_id in dependencies:
        root = xbmcaddon.Addon(addon_id).getAddonInfo('path')
        manifest = os.path.join(root, 'addon.xml')
        if not os.path.isfile(manifest):
            raise ImportError('Kodi module unavailable: %s' % addon_id)
        for extension in ET.parse(manifest).findall('extension'):
            if extension.get('point') == 'xbmc.python.module':
                lib = os.path.join(root, extension.get('library') or '')
                if os.path.isdir(lib) and lib not in sys.path:
                    sys.path.insert(0, lib)
        if addon_id == HELPER:
            resources = os.path.join(root, 'resources')
            if resources not in sys.path:
                sys.path.insert(0, resources)
    import jurialmunkey
    import infotagger
    import tmdbhelper

def select_movie(title, year):
    """Preserve the successful alternate title / tolerant year search in v1.3.1."""
    from tmdbhelper.lib.query.database.database import FindQueriesDatabase
    finder = FindQueriesDatabase()
    api = finder.tmdb_api
    variations = candidates(title)
    names = {normalize(x) for x in variations}
    target = normalize(title)
    preferred = normalize(variations[1]) if len(variations) > 1 else target
    pool = {}
    for query in variations[:4]:
        try:
            data = api.get_response_json('search', 'movie',
                query=quote_plus(query)) or {}
        except Exception as exc:
            log('Search error for %r: %s' % (query, type(exc).__name__))
            continue
        for movie in (data.get('results') or [])[:20]:
            mid = movie.get('id')
            variants = (movie.get('title') or '', movie.get('original_title') or '')
            keys = [normalize(s) for s in variants if s]
            if not mid or not keys:
                continue
            if target in keys:
                score = 105
            elif any(k in names for k in keys):
                score = 88
            elif any(len(k) >= 8 and (k in target or target in k) for k in keys):
                score = 69
            else:
                tokens = set(re.findall(r'\w+', title.casefold()))
                similarity = max((
                    len(tokens & set(re.findall(r'\w+', x.casefold()))) /
                    max(1, len(tokens | set(re.findall(r'\w+', x.casefold()))))
                    for x in variants if x), default=0)
                if similarity < 0.72:
                    continue
                score = round(58 * similarity)
            released = get_year(movie.get('release_date'))
            if year and released:
                score += {0:24, 1:14, 2:4}.get(abs(released - year), -35)
            if normalize(query) == target:
                score += 5
            elif normalize(query) == preferred:
                score += 12
            movie = dict(movie)
            movie['_score'], movie['_year'] = score, released
            old = pool.get(str(mid))
            if not old or score > old['_score']:
                pool[str(mid)] = movie
    ranked = sorted(pool.values(), key=lambda x:x['_score'], reverse=True)
    log('TMDb candidates %r (%s): %s' % (
        title, year, [(x.get('id'), x.get('title'), x['_year'], x['_score'])
        for x in ranked[:4]]))
    if not ranked:
        for query in variations:
            try:
                mid = finder.get_tmdb_id(tmdb_type='movie', query=query)
                if mid:
                    return str(mid)
            except Exception:
                continue
        return None
    best = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    if best['_score'] >= 80 and (not second or best['_score']-second['_score'] >= 12):
        return str(best['id'])
    plausible = [x for x in ranked[:6] if x['_score'] >= max(45,best['_score']-38)]
    labels = ['%s (%s) – Original: %s' % (
        x.get('title') or '?', x['_year'] or '?', x.get('original_title') or '?')
        for x in plausible]
    selected = xbmcgui.Dialog().select('FilmPalast: Richtigen TMDb-Film wählen', labels)
    return str(plausible[selected]['id']) if selected >= 0 else None

def playback_url(url, title, year, tmdb='', imdb=''):
    # Use existing, tested FilmPalast mode=10 rather than an extra TMDb player.
    return 'plugin://' + FILMPALAST + '/?' + urlencode({
        'mode':'10','url':url,'mediatype':'movie','title':title,
        'year':str(year or ''),'tmdb':str(tmdb or ''),'imdb':str(imdb or '')
    })

def direct_play(url, title, year):
    xbmc.executebuiltin('PlayMedia(%s)' % playback_url(url,title,year))

def open_tmdb_info(site_url, params):
    title = clean_title(params.get('title') or
        site_url.rstrip('/').split('/')[-1].replace('-', ' '))
    year = get_year(params.get('year'))
    if not site_url.startswith('https://filmpalast.to/stream/'):
        log('Refused unrelated URL: %r' % site_url, xbmc.LOGERROR)
        return
    if not xbmc.getCondVisibility('System.HasAddon(%s)' % HELPER):
        direct_play(site_url, title, year)
        return
    try:
        load_helper()
        from tmdbhelper.lib.items.router import Router
        raw_id = unquote_plus(params.get('tmdb') or '')
        tmdb_id = raw_id if raw_id.isdigit() else select_movie(title, year)
        if not tmdb_id:
            if xbmcgui.Dialog().yesno('FilmPalast',
                'Kein eindeutiger TMDb-Film gefunden.\nFilm direkt abspielen?'):
                direct_play(site_url, title, year)
            return
        route = urlencode({
            'info':'details', 'tmdb_type':'movie', 'tmdb_id':str(tmdb_id)})
        items = Router(-1, route).get_directory(items_only=True)
        if not items:
            raise ValueError('TMDb Helper returned no details')
        movie = items[0]
        name = clean_title(movie.label)
        found_year = get_year(movie.infolabels.get('year'))
        exact = normalize(name) == normalize(title)
        overlap = (len(normalize(name)) >= 8 and (
            normalize(name) in normalize(title) or normalize(title) in normalize(name)))
        if year and found_year and abs(year-found_year) > 2 and not exact:
            log('Rejected title/year mismatch: %s %s' % (name, found_year))
            return
        if not (exact or overlap):
            if not xbmcgui.Dialog().yesno('FilmPalast: TMDb-Treffer',
                'FilmPalast: %s\nTMDb Helper: %s\nDiesen Film öffnen?' % (title,name)):
                return
        item = movie.get_listitem()
        # The native Helper ListItem supplies all artwork and metadata.
        # The Play button targets FilmPalast's existing resolved URL callback.
        imdb = (movie.unique_ids or {}).get('imdb') or ''
        item.setPath(playback_url(site_url, title, year, tmdb_id, imdb))
        item.setProperty('IsPlayable', 'true')
        log('Native TMDb details: title=%r tmdb=%s, direct FilmPalast' % (title,tmdb_id))
        xbmcgui.Dialog().info(item)
    except Exception as exc:
        log('Native info error %s: %s' % (type(exc).__name__, exc), xbmc.LOGERROR)
        if xbmcgui.Dialog().yesno('FilmPalast',
            'TMDb-Details konnten nicht geöffnet werden.\nFilm direkt abspielen?'):
            direct_play(site_url,title,year)
