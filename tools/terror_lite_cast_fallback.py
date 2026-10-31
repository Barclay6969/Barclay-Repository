"""TerrorLite 1.1.36: TMDb Helper cast fallback for movie info without Kodi cast data.

Invoked only from DialogVideoInfo.xml's supplementary Cast button.
Preserves Kodi's built-in cast control when native ListItem.Cast is available.
"""
import re
from urllib.parse import urlencode, quote

import xbmc
import xbmcgui


def label(name):
    try:
        return (xbmc.getInfoLabel(name) or "").strip()
    except Exception:
        return ""


def build_cast_uri():
    media_type = label("ListItem.DBType").lower()
    tmdb_type = "tv" if media_type in ("tvshow", "season", "episode", "tv") else "movie"

    tmdb_id = label("ListItem.Property(TMDb_ID)") or label("ListItem.UniqueID(tmdb)")
    imdb_id = label("ListItem.Property(IMDb_ID)") or label("ListItem.UniqueID(imdb)") or label("ListItem.IMDbNumber")
    title = label("ListItem.Title") or label("ListItem.Label")
    year = label("ListItem.Year")

    params = [("info", "cast"), ("tmdb_type", tmdb_type)]
    if re.fullmatch(r"[0-9]+", tmdb_id or ""):
        params.append(("tmdb_id", tmdb_id))
    elif re.fullmatch(r"tt[0-9]+", imdb_id or ""):
        params.append(("imdb_id", imdb_id))
    elif title:
        params.append(("query", title))
        if re.fullmatch(r"[0-9]{4}", year or ""):
            params.append(("year", year))
    else:
        return None

    return "plugin://plugin.video.themoviedb.helper/?" + urlencode(params, quote_via=quote)


def main():
    if not xbmc.getCondVisibility("System.HasAddon(plugin.video.themoviedb.helper)"):
        xbmcgui.Dialog().notification("TerrorLite", "TMDb Helper ist nicht installiert")
        return

    uri = build_cast_uri()
    if not uri:
        xbmcgui.Dialog().notification("TerrorLite", "Keine Filmdaten fuer die Schauspielersuche")
        return

    try:
        # Capture all ListItem info before dismissing the movie information dialog.
        xbmc.executebuiltin("Dialog.Close(MovieInformation)")
        xbmc.sleep(150)
        xbmc.executebuiltin('ActivateWindow(Videos,"' + uri + '",return)')
    except Exception as exc:
        xbmc.log("[TerrorLite] Cast fallback error: {}".format(exc), xbmc.LOGWARNING)
        xbmcgui.Dialog().notification("TerrorLite", "Schauspielerliste konnte nicht geoeffnet werden")


if __name__ == "__main__":
    main()
