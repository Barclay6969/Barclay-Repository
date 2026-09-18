# -*- coding: UTF-8 -*-

import re
import threading
from html import unescape
from resources.lib.requestHandler import cRequestHandler

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
DEFAULT_BASE = 'https://meinecloud.click'

_movie_cache = {}
_series_cache = {}
_cache_lock = threading.Lock()


def _unique(values):
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _normalize_link(value, base_link):
    value = unescape(str(value or '')).strip().replace('\\/', '/')
    if not value:
        return ''
    if value.startswith('//'):
        return 'https:' + value
    if value.startswith('/'):
        return base_link.rstrip('/') + value
    return value


def _attrs(tag):
    return {
        key.lower(): unescape(value)
        for key, _, value in re.findall(
            r'([\w:-]+)\s*=\s*([\'\"])(.*?)\2',
            tag or '',
            flags=re.I | re.S
        )
    }


def _extract_data_links(html, base_link, season=None, episode=None):
    html = html or ''
    result = []

    # Parse whole tags so data-label and data-link can appear in either order,
    # with extra attributes/newlines between them.
    for tag in re.findall(r'<[^>]+\bdata-link\s*=\s*[\'\"][^>]+>', html, flags=re.I | re.S):
        attrs = _attrs(tag)
        link = attrs.get('data-link')
        if not link:
            continue

        if season is not None and episode is not None:
            label = attrs.get('data-label', '')
            if not re.search(
                r'\bS0*%d\s*[-._ ]?\s*E0*%d\b' % (int(season), int(episode)),
                label,
                flags=re.I
            ):
                continue

        normalized = _normalize_link(link, base_link)
        if normalized:
            result.append(normalized)

    # Movie pages historically expose data-link attributes. Keep a fallback
    # for minor markup changes where the attribute is no longer on a normal
    # opening tag.
    if season is None and not result:
        for link in re.findall(r'\bdata-link\s*=\s*[\'\"]([^\'\"]+)[\'\"]', html, flags=re.I | re.S):
            normalized = _normalize_link(link, base_link)
            if normalized:
                result.append(normalized)

    # Last-resort movie fallback: some variants use iframe src directly.
    if season is None and not result:
        for link in re.findall(r'<iframe[^>]+\bsrc\s*=\s*[\'\"]([^\'\"]+)[\'\"]', html, flags=re.I | re.S):
            normalized = _normalize_link(link, base_link)
            low = normalized.lower()
            if not normalized or 'youtube.' in low or 'youtu.be' in low or 'vpns.html' in low:
                continue
            result.append(normalized)

    return _unique(result)


def _request(url, base_link):
    request = cRequestHandler(url, caching=False)
    request.addHeaderEntry('User-Agent', UA)
    request.addHeaderEntry('Referer', base_link.rstrip('/') + '/')
    try:
        request.addHeaderEntry('Origin', base_link.rstrip('/'))
    except Exception:
        pass
    return request.request() or ''


def get_movie_links(imdb, base_link=DEFAULT_BASE):
    """Return MeineCloud movie hoster/embed URLs.

    Positive results are cached per plugin process. Empty results are never
    cached, so a temporary challenge/incomplete response cannot poison all
    later retries for the same title.
    """
    base_link = (base_link or DEFAULT_BASE).rstrip('/')
    imdb = str(imdb or '').strip()
    if not imdb:
        return []

    key = (base_link, imdb)
    with _cache_lock:
        if key in _movie_cache:
            return list(_movie_cache[key])

    try:
        html = _request('%s/movie/%s' % (base_link, imdb), base_link)
        links = _extract_data_links(html, base_link)
    except Exception:
        links = []

    if links:
        with _cache_lock:
            _movie_cache[key] = tuple(links)
    return list(links)


def get_series_links(imdb, season, episode, base_link=DEFAULT_BASE):
    """Return hoster/embed URLs for one MeineCloud episode."""
    base_link = (base_link or DEFAULT_BASE).rstrip('/')
    imdb = str(imdb or '').strip()
    if not imdb:
        return []

    numeric_imdb = imdb[2:] if imdb.lower().startswith('tt') else imdb
    key = (base_link, numeric_imdb, int(season), int(episode))

    with _cache_lock:
        if key in _series_cache:
            return list(_series_cache[key])

    try:
        html = _request('%s/serial/%s' % (base_link, numeric_imdb), base_link)
        links = _extract_data_links(html, base_link, season=season, episode=episode)
    except Exception:
        links = []

    if links:
        with _cache_lock:
            _series_cache[key] = tuple(links)
    return list(links)
