# -*- coding: utf-8 -*-
"""TerrorLite: default subtitles to OFF when entering a Live TV channel.

Runs as a small skin-owned script from Home.xml, not as a separate add-on.
Only PVR Live TV is affected.  The script never changes Kodi's global
subtitle-language or video-default settings, and users may enable subtitles
manually for the remainder of the current channel.
"""
import time

import xbmc
import xbmcgui


SKIN_ID = "skin.terror.lite"
RUNNING_PROPERTY = "TerrorLite.PVRSubtitleDefaultsRunning"
SETTLE_SECONDS = 1.0
CHECK_SECONDS = 0.5


def channel_identity():
    """Return a channel identifier only for genuine Live TV playback."""
    if not xbmc.getCondVisibility("VideoPlayer.Content(livetv)"):
        return None

    number = xbmc.getInfoLabel("VideoPlayer.ChannelNumberLabel")
    name = xbmc.getInfoLabel("VideoPlayer.ChannelName")
    if number or name:
        return (number, name)

    # Some backends publish channel infolabels slightly after tuning.
    # Wait for valid channel metadata rather than touching an unrelated video.
    return None


def run():
    home = xbmcgui.Window(10000)
    if home.getProperty(RUNNING_PROPERTY) == "true":
        return

    home.setProperty(RUNNING_PROPERTY, "true")
    monitor = xbmc.Monitor()
    player = xbmc.Player()
    previous = None
    tuned_at = 0.0
    pending = False

    try:
        while not monitor.abortRequested():
            if xbmc.getSkinDir() != SKIN_ID:
                break

            current = channel_identity()
            if current is None:
                previous = None
                pending = False
            elif current != previous:
                previous = current
                tuned_at = time.monotonic()
                pending = True
            elif pending and time.monotonic() - tuned_at >= SETTLE_SECONDS:
                # Do this once per tune, not on every subtitle-state change:
                # a viewer enabling subtitles later must be left alone.
                pending = False
                if xbmc.getCondVisibility("VideoPlayer.SubtitlesEnabled"):
                    try:
                        player.showSubtitles(False)
                    except Exception as exc:
                        xbmc.log(
                            "TerrorLite PVR subtitles: failed to disable: {}".format(exc),
                            xbmc.LOGWARNING,
                        )

            if monitor.waitForAbort(CHECK_SECONDS):
                break
    finally:
        home.clearProperty(RUNNING_PROPERTY)


if __name__ == "__main__":
    run()
