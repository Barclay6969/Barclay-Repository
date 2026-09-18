# -*- coding: UTF-8 -*-

import re
import threading
from resources.lib.requestHandler import cRequestHandler

_movie_cache = {}
_movie_lock = threading.Lock()

def get_movie_links(imdb):
    """Return MeineCloud movie data-link URLs, fetched once per plugin process/IMDB id."""
    key = str(imdb or '').strip()
    if not key:
        return []
    with _movie_lock:
        if key in _movie_cache:
            return list(_movie_cache[key])
        request = cRequestHandler('https://meinecloud.click/movie/%s' % key, caching=True)
        html = request.request() or ''
        links = re.findall(r'data-link="([^"]+)"', html)
        # Preserve order while removing exact duplicates before any Hoster work.
        links = list(dict.fromkeys(links))
        _movie_cache[key] = tuple(links)
        return list(links)
