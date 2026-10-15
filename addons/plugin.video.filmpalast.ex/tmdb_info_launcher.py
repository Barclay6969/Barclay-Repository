# -*- coding: utf-8 -*-
"""Open FilmPalast's native TMDb Info dialog outside the Kodi directory callback.

Android Kodi can terminate the process when TMDbHelper's player progress dialog
opens while the clicked folder's original directory-busy dialog is still active.
This launcher only starts after the directory callback has been completed.
"""
import base64
import json
import os
import sys
import traceback
import xbmc

def log(message, level=xbmc.LOGINFO):
    xbmc.log('[FilmPalast TMDb Launcher] ' + str(message), level)

def main():
    if len(sys.argv) < 2:
        log('No movie information supplied', xbmc.LOGWARNING)
        return
    token = sys.argv[1].strip()
    try:
        encoded = token + ('=' * (-len(token) % 4))
        payload = json.loads(base64.urlsafe_b64decode(encoded.encode('ascii')).decode('utf-8'))
        movie_url = payload.get('url') or ''
        params = payload.get('params') or {}
        if not movie_url.startswith('https://filmpalast.to/stream/'):
            raise ValueError('Invalid movie page URL')
    except (ValueError, TypeError, KeyError) as exc:
        log('Invalid launch request: %s' % exc, xbmc.LOGERROR)
        return
    monitor = xbmc.Monitor()
    # Release the previous directory navigation before requesting TMDb details.
    if monitor.waitForAbort(0.85):
        return
    # Kodi Android 21.x may otherwise have a lingering directory busy dialog.
    xbmc.executebuiltin('Dialog.Close(busydialog,force)')
    if monitor.waitForAbort(0.18):
        return
    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from tmdb_native import open_tmdb_info
        log('Info dialog started for %s' % movie_url)
        open_tmdb_info(movie_url, params)
    except Exception:
        log('Info launcher error:\n' + traceback.format_exc(), xbmc.LOGERROR)

if __name__ == '__main__':
    main()
