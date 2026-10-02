# -*- coding: utf-8 -*-
# Python 3

import xbmc
import xbmcgui
from resources.lib.gui.gui import cGui
from resources.lib.config import cConfig
from xbmc import LOGINFO as LOGNOTICE, LOGERROR, log

class AddonPlayer(xbmc.Player):
    def __init__(self, *args, **kwargs):
        xbmc.Player.__init__(self, *args, **kwargs)
        self.streamFinished = False
        self.streamSuccess = True
        self.playedTime = 0
        self.totalTime = 999999
        self.from_global_search = False  # Track if started from Global Search
        self._navigation_done = False    # Verhindert doppelte Navigation (Bug-Fix)
        log(cConfig().getLocalizedString(30166) + ' -> [player]: player instance created', LOGNOTICE)

    def onPlayBackStarted(self):
        log(cConfig().getLocalizedString(30166) + ' -> [player]: starting Playback', LOGNOTICE)
        try:
            self.totalTime = self.getTotalTime()
        except:
            self.totalTime = 999999

        # Reliable detection via window property (set before setResolvedUrl)
        try:
            win = xbmcgui.Window(10000)
            if win.getProperty('serienstream.from_global_search') == '1':
                self.from_global_search = True
                win.clearProperty('serienstream.from_global_search')
                log(cConfig().getLocalizedString(30166) + ' -> [player]: Global Search Kontext via Property erkannt', LOGNOTICE)
        except Exception as e:
            log(cConfig().getLocalizedString(30166) + ' -> [player]: Fehler beim Lesen der Global Search Property: %s' % str(e), LOGERROR)

        # Fallback: Check Container.FolderPath (still available at onPlayBackStarted)
        if not self.from_global_search:
            try:
                path = xbmc.getInfoLabel('Container.FolderPath')
                if path:
                    low = path.lower()
                    keywords = [
                        'function=globalsearch',
                        'site=globalsearch',
                        'function=searchalter',
                        'function=searchtmdb'
                    ]
                    if any(kw in low for kw in keywords):
                        self.from_global_search = True
                        log(cConfig().getLocalizedString(30166) + ' -> [player]: Global Search Kontext via FolderPath erkannt (Fallback)', LOGNOTICE)
            except:
                pass

    def _navigate_to_menu(self):
        """Navigiert nach Wiedergabe ins Addon-Menü zurück.
        Wird nur einmal ausgeführt (Bug-Fix: verhindert Doppelaufruf durch onPlayBackEnded → onPlayBackStopped).
        Verzögerung verhindert Kodi-Abstürze durch UI-Manipulation aus Player-Callbacks.
        """
        if self._navigation_done:
            return
        self._navigation_done = True

        if self.from_global_search:
            try:
                xbmc.sleep(1000)  # Kodi Zeit geben, den Playback-Zustand sauber zu beenden
                xbmc.executebuiltin('ActivateWindow(Videos,plugin://plugin.video.serienstream/,return)')
                log('serienstream -> [player]: Navigating back to addon menu after global search', LOGNOTICE)
            except Exception as e:
                log('serienstream -> [player]: Error navigating back to menu: %s' % str(e), LOGERROR)

    def onPlayBackStopped(self):
        log(cConfig().getLocalizedString(30166) + ' -> [player]: Playback stopped', LOGNOTICE)
        if self.playedTime == 0 and self.totalTime == 999999:
            self.streamSuccess = False
            log(cConfig().getLocalizedString(30166) + ' -> [player]: Kodi failed to open stream', LOGERROR)
        self.streamFinished = True
        self._navigate_to_menu()

    def onPlayBackEnded(self):
        log(cConfig().getLocalizedString(30166) + ' -> [player]: Playback completed', LOGNOTICE)
        # KEIN Aufruf von onPlayBackStopped() – beide Events separat behandeln,
        # _navigate_to_menu() has internal guard against double execution
        if self.playedTime == 0 and self.totalTime == 999999:
            self.streamSuccess = False
        self.streamFinished = True
        self._navigate_to_menu()



class cPlayer:
    def clearPlayList(self):
        oPlaylist = self.__getPlayList()
        oPlaylist.clear()

    def __getPlayList(self):
        return xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

    def addItemToPlaylist(self, oGuiElement):
        oListItem = cGui().createListItem(oGuiElement)
        self.__addItemToPlaylist(oGuiElement, oListItem)

    def __addItemToPlaylist(self, oGuiElement, oListItem):
        oPlaylist = self.__getPlayList()
        oPlaylist.add(oGuiElement.getMediaUrl(), oListItem)

    def startPlayer(self):
        log(cConfig().getLocalizedString(30166) + ' -> [player]: start player', LOGNOTICE)
        xbmcPlayer = AddonPlayer()
        monitor = xbmc.Monitor()
        while (not monitor.abortRequested()) & (not xbmcPlayer.streamFinished):
            if xbmcPlayer.isPlayingVideo():
                xbmcPlayer.playedTime = xbmcPlayer.getTime()
            monitor.waitForAbort(10)
        # Trakt rating fix: keep playback context alive briefly after stop/end.
        # script.trakt opens the rating dialog asynchronously after the stop event.
        if xbmcPlayer.streamFinished and not monitor.abortRequested():
            log(cConfig().getLocalizedString(30166) + ' -> [player]: waiting for Trakt rating callback', LOGNOTICE)
            monitor.waitForAbort(2.5)

        return xbmcPlayer.streamSuccess