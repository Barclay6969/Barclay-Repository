# -*- coding: utf-8 -*-
"""Request one repository refresh after startup, without a local add-on rescan."""
import xbmc

STARTUP_DELAY_SECONDS = 90
POLL_SECONDS = 5
QUIET_SECONDS = 30
MAX_WAIT_SECONDS = 1800
BUSY_CONDITION = (
    "Library.IsScanningVideo | Library.IsScanningMusic | "
    "Player.HasMedia | Window.IsActive(busydialog) | "
    "Window.IsActive(busydialognocancel) | "
    "Window.IsActive(addonbrowser) | Window.IsActive(addoninformation)"
)


def log(message):
    xbmc.log("[Kodi AutoUpdate] " + message, xbmc.LOGINFO)


def main():
    monitor = xbmc.Monitor()
    log("v1.0.1 gestartet. Warte 90 Sekunden vor der Update-Pruefung.")
    if monitor.waitForAbort(STARTUP_DELAY_SECONDS):
        return

    quiet = 0
    waited = 0
    while not monitor.abortRequested() and waited < MAX_WAIT_SECONDS:
        if xbmc.getCondVisibility(BUSY_CONDITION):
            quiet = 0
        elif quiet >= QUIET_SECONDS:
            log("Fordere einmalige Repository-Pruefung im Hintergrund an.")
            xbmc.executebuiltin("UpdateAddonRepos", False)
            log("Pruefung angefordert. Installation erfolgt gemaess Kodi-Einstellungen.")
            return
        if monitor.waitForAbort(POLL_SECONDS):
            return
        waited += POLL_SECONDS
        if not xbmc.getCondVisibility(BUSY_CONDITION):
            quiet += POLL_SECONDS
        else:
            quiet = 0
    if not monitor.abortRequested():
        log("Kodi blieb beschaeftigt. Pruefung fuer diesen Service-Start uebersprungen.")


if __name__ == "__main__":
    main()
