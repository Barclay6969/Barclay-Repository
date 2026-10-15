# -*- coding: utf-8 -*-
"""FilmPalast service: open TMDb movie details after directory closure.

The service is an xbmc.service entrypoint belonging to FilmPalast, so Kodi
provides a real addon context. A standalone RunScript(filename.py) does not,
causing xbmcaddon.Addon() to raise on Android. The service also shows the
changelog popup once per version when Kodi is idle.
"""
import json
import os
import re
import sys
import time
import traceback

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON_ID = 'plugin.video.filmpalast.ex'
INFO_QUEUE_KEY = 'filmpalast.barclay.native_info_queue_0611'


def log(message, level=xbmc.LOGINFO):
    xbmc.log('[FilmPalast TMDb Service] ' + str(message), level)


def popup_for_new_version():
    addon = xbmcaddon.Addon(ADDON_ID)
    current = addon.getAddonInfo('version')
    profile = xbmcvfs.translatePath('special://profile/addon_data/' + ADDON_ID)
    os.makedirs(profile, exist_ok=True)
    marker = os.path.join(profile, 'last_changelog_popup_version.txt')
    old = ''
    if os.path.isfile(marker):
        with open(marker, 'r', encoding='utf-8') as f:
            old = f.read().strip()
    if current == old:
        return True
    filename = os.path.join(addon.getAddonInfo('path'), 'changelog.txt')
    with open(filename, 'r', encoding='utf-8') as f:
        changelog = f.read()
    match = re.search(r'(?m)^' + re.escape(current) + r'[^\n]*\n', changelog)
    if match:
        rest = changelog[match.end():]
        next_version = re.search(r'(?m)^\d+\.\d+\.\d+\b', rest)
        notes = rest[:next_version.start()].strip() if next_version else rest.strip()
    else:
        notes = changelog[:1800].strip()
    if not notes:
        notes = 'Änderungen und Fehlerbehebungen in Version ' + current
    xbmcgui.Dialog().textviewer('FilmPalast ' + current + ' – Was ist neu?', notes)
    with open(marker, 'w', encoding='utf-8') as f:
        f.write(current)
    return True


def kodi_idle():
    try:
        if xbmc.Player().isPlaying():
            return False
        if xbmc.getCondVisibility('Window.IsVisible(busydialog)'):
            return False
        if xbmc.getCondVisibility('Window.IsVisible(progressdialog)'):
            return False
        return xbmcgui.getCurrentWindowDialogId() in (0, 9999)
    except Exception:
        return False


def consume_info_request(window):
    raw = window.getProperty(INFO_QUEUE_KEY)
    if not raw:
        return False
    try:
        request = json.loads(raw)
        issued = float(request.get('issued') or 0)
        target = str(request.get('url') or '')
        params = request.get('params') or {}
        if not isinstance(params, dict):
            raise ValueError('Bad movie params')
        if not target.startswith('https://filmpalast.to/stream/'):
            raise ValueError('Bad movie URL')
        if time.time() > issued + 45:
            log('Expired pending info request', xbmc.LOGWARNING)
            window.clearProperty(INFO_QUEUE_KEY)
            return False
        # EndOfDirectory must have returned and Kodi must have released its
        # directory-busy dialog before the native Info window opens.
        if time.time() < issued + 1.2 or not kodi_idle():
            return False
    except Exception as exc:
        window.clearProperty(INFO_QUEUE_KEY)
        log('Invalid info request: %s' % exc, xbmc.LOGWARNING)
        return False

    # Delete before calling Dialog.info to prevent replays after closing it.
    window.clearProperty(INFO_QUEUE_KEY)
    log('Native Info requested through real FilmPalast addon context: %s' % target)
    try:
        from tmdb_native import open_tmdb_info
        open_tmdb_info(target, params)
    except Exception:
        log('Native info exception:\n' + traceback.format_exc(), xbmc.LOGERROR)
    return True


def run():
    # Fail loudly if this script is ever launched via a raw RunScript path.
    active_addon = xbmcaddon.Addon().getAddonInfo('id')
    if active_addon != ADDON_ID:
        log('Invalid Kodi addon context: %r' % active_addon, xbmc.LOGERROR)
        return
    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    log('Service ready with Kodi addon context: ' + active_addon)
    monitor = xbmc.Monitor()
    window = xbmcgui.Window(10000)
    started = time.monotonic()
    did_popup = False
    idle_count = 0
    # Stay alive throughout the Kodi session so later film clicks also work.
    while not monitor.abortRequested():
        processed = consume_info_request(window)
        if processed:
            idle_count = 0
        elif not did_popup and time.monotonic() - started > 25:
            # The Changelog must not interrupt TMDb info, movie playback,
            # or an outstanding film request.
            if kodi_idle() and not window.getProperty(INFO_QUEUE_KEY):
                idle_count += 1
            else:
                idle_count = 0
            if idle_count >= 12:  # 3 seconds fully idle
                try:
                    did_popup = popup_for_new_version()
                except Exception:
                    log('Changelog popup exception:\n' + traceback.format_exc(), xbmc.LOGWARNING)
                    did_popup = True
        if monitor.waitForAbort(0.25):
            break


if __name__ == '__main__':
    run()
