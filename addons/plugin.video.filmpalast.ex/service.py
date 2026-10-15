# -*- coding: utf-8 -*-
"""One-time FilmPalast update changelog popup (Kodi service)."""
import os
import re
import traceback
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON_ID = 'plugin.video.filmpalast.ex'

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
        return
    filename = os.path.join(addon.getAddonInfo('path'), 'changelog.txt')
    with open(filename, 'r', encoding='utf-8') as f:
        changelog = f.read()
    # Show only new version's notes in the popup; the full log remains
    # available via the addon information dialog / changelog.txt.
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

if __name__ == '__main__':
    monitor = xbmc.Monitor()
    if not monitor.waitForAbort(12):
        try:
            popup_for_new_version()
        except Exception as exc:
            xbmc.log('[FilmPalast Changelog Popup] %s: %s\n%s' % (
                type(exc).__name__, exc, traceback.format_exc()), xbmc.LOGWARNING)
