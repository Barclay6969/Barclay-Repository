"""Keep the playback-scoped HLS RAM proxy alive until Kodi stops playback."""
import threading
from kodi_six import xbmc, xbmcaddon, xbmcgui
from hls_prebuffer import HLSPrebuffer
from stream_playback import manifest_kind


class BufferedPlayback(xbmc.Player):
    def __init__(self, proxy, addon):
        super().__init__()
        self.proxy = proxy
        self.addon = addon
        self.ended = threading.Event()
        self.paused = False
        self.label = self.window = None
        self.overlay_failed = False

    def onPlayBackPaused(self):
        self.paused = True
        if self.addon.getSetting('playback.hls_buffer_notifications') == 'true':
            try:
                used, limit, hits = self.proxy.status()
                xbmcgui.Dialog().notification('FilmPalast HLS-Puffer',
                    'Aktuell %.1f MB gepuffert (max. %d MB)' % (used / 1048576., limit // 1048576),
                    time=3000, sound=False)
            except Exception:
                pass

    def onPlayBackResumed(self):
        self.paused = False
        self.remove_overlay()

    def onPlayBackStopped(self):
        self.ended.set()

    def onPlayBackEnded(self):
        self.ended.set()

    def onPlayBackError(self):
        self.ended.set()

    def remove_overlay(self):
        label, window = self.label, self.window
        self.label = self.window = None
        if label is not None and window is not None:
            try:
                window.removeControl(label)
            except Exception:
                pass

    def update_overlay(self):
        if not self.paused or self.addon.getSetting('playback.hls_buffer_status') != 'true':
            self.remove_overlay()
            return
        if self.overlay_failed:
            return
        try:
            if self.label is None:
                window = xbmcgui.Window(12005)
                label = xbmcgui.ControlLabel(20, max(20, window.getHeight() - 120),
                    max(100, window.getWidth() - 40), 35, '', font='font13',
                    textColor='FFFFFFFF', shadowColor='FF000000')
                window.addControl(label)
                label.setVisibleCondition('Window.IsActive(fullscreenvideo)')
                self.window, self.label = window, label
            used, limit, hits = self.proxy.status()
            self.label.setLabel('FilmPalast HLS-Puffer: %.1f / %d MB | Cache-Treffer: %d' %
                (used / 1048576., limit // 1048576, hits))
        except Exception:
            self.overlay_failed = True
            self.remove_overlay()
            xbmc.log('[FilmPalast HLS-PREBUFFER] overlay unavailable', xbmc.LOGWARNING)

    def wait(self):
        monitor = xbmc.Monitor()
        started = False
        for _ in range(60):
            if monitor.abortRequested() or self.ended.is_set():
                return
            if self.isPlayingVideo():
                started = True
                break
            monitor.waitForAbort(1)
        if not started:
            xbmc.log('[FilmPalast HLS-PREBUFFER] playback start timeout', xbmc.LOGWARNING)
            return
        missing = 0
        while not monitor.abortRequested() and not self.ended.is_set():
            if self.isPlayingVideo():
                missing = 0
                self.update_overlay()
            else:
                missing += 1
                if missing >= 2:
                    break
            monitor.waitForAbort(1)

    def close(self):
        self.remove_overlay()
        self.proxy.close()


def prepare(stream_url):
    """Wrap detected HLS without changing FilmPalast's native demuxer."""
    addon = xbmcaddon.Addon('plugin.video.filmpalast.ex')
    if addon.getSetting('playback.hls_prebuffer_test') != 'true':
        return stream_url, None
    url, separator, headers = stream_url.partition('|')
    proxy = None
    try:
        if manifest_kind(url, headers or None) != 'hls':
            return stream_url, None
        proxy = HLSPrebuffer(headers or None,
            lambda msg: xbmc.log('[FilmPalast] ' + msg, xbmc.LOGINFO),
            cache_mb=addon.getSetting('playback.hls_prebuffer_mb'))
        local_url = proxy.start(url)
        playback = BufferedPlayback(proxy, addon)
        return local_url + (separator + headers if separator else ''), playback
    except Exception as error:
        if proxy:
            proxy.close()
        xbmc.log('[FilmPalast HLS-PREBUFFER] startup fallback: ' + type(error).__name__, xbmc.LOGWARNING)
        return stream_url, None
