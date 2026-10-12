"""Keep Trakt stream IDs scoped to one FilmPalast playback; no API requests."""
import sys
import time
from kodi_six import xbmc, xbmcgui


def run(owner):
    home = xbmcgui.Window(10000)
    payload = home.getProperty('filmpalast.trakt.payload')
    title = home.getProperty('filmpalast.trakt.title')
    player = xbmc.Player()
    monitor = xbmc.Monitor()
    started = False
    deadline = time.monotonic() + 120
    try:
        while not monitor.abortRequested():
            if home.getProperty('filmpalast.trakt.owner') != owner:
                return
            if home.getProperty('script.trakt.ids') != payload:
                return  # Another addon owns the public property now.
            playing = player.isPlayingVideo()
            current_title = ''
            if playing:
                try:
                    current_title = player.getVideoInfoTag().getTitle()
                except RuntimeError:
                    playing = False
            if playing and current_title == title:
                started = True
            elif started or (playing and current_title and current_title != title):
                break
            elif time.monotonic() >= deadline:
                break
            if monitor.waitForAbort(0.25):
                break
    finally:
        if home.getProperty('filmpalast.trakt.owner') == owner:
            if home.getProperty('script.trakt.ids') == payload:
                home.clearProperty('script.trakt.ids')
            for key in ('owner', 'payload', 'title'):
                home.clearProperty('filmpalast.trakt.' + key)
            xbmc.log('[FilmPalast] Trakt bridge: owned IDs cleared', xbmc.LOGINFO)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        run(sys.argv[1])
