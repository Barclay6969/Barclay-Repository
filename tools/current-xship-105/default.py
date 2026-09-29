

# xShip 2026.08.17.1 startup domain synchronization
try:
    from resources.lib.domain_sync_startup import sync_domains as _xship_sync_domains
    _xship_sync_domains()
except Exception as _xship_domain_sync_error:
    try:
        import xbmc
        xbmc.log('[xShip DomainSync] startup sync failed: %s' % _xship_domain_sync_error, xbmc.LOGWARNING)
    except Exception:
        pass

# 2023-05-10
# edit 2026-08-09

import sys, json
from resources.lib import control

params = dict(control.parse_qsl(control.urlsplit(sys.argv[2]).query))

action = params.get('action')

# xShip als aktiv markieren (fuer Precacher: erst starten wenn xShip geoeffnet wurde)
import xbmcgui
xbmcgui.Window(10000).setProperty('xship.active', '1')

name = params.get('name')
table = params.get('table')
title = params.get('title')
source = params.get('source')

# ------ navigator --------------
if (action == None or action == 'root') and name==None:
    from resources.lib.indexers import navigator
    navigator.navigator().root()

elif action == 'pluginInfo':
    from resources.lib import supportinfo
    supportinfo.pluginInfo()

elif action == 'movieNavigator':
    from resources.lib.indexers import navigator
    navigator.navigator().movies()

elif action == 'tvNavigator':
    from resources.lib.indexers import navigator
    navigator.navigator().tvshows()

elif action == 'toolNavigator':
    from resources.lib.indexers import navigator
    navigator.navigator().tools()

# -------------------------------------------
elif action == 'mediaInfo':
    import xbmcgui
    dialog = xbmcgui.DialogProgress()
    dialog.create('Medien-Info', 'Löse Stream-URL auf... (20 Sek.)')
    dialog.update(0)
    from resources.lib import sources
    sources.sources().mediaInfo(source, dialog)

elif action == 'playExtern':
    import json
    if not control.visible(): control.busy()
    try:
        sysmeta = {}
        for key, value in params.items():
            if key == 'action': continue
            elif key == 'year' or key == 'season' or key == 'episode': value = int(value)
            if value == 0: continue
            sysmeta.update({key : value})
        if int(params.get('season')) == 0:
            mediatype = 'movie'
        else:
            mediatype = 'tvshow'
        sysmeta.update({'mediatype': mediatype})
        # if control.getSetting('hosts.mode') == '2':
        #     sysmeta.update({'select': '2'})
        # else:
        #     sysmeta.update({'select': '1'})
        sysmeta.update({'select': control.getSetting('hosts.mode')})
        sysmeta = json.dumps(sysmeta)
        params.update({'sysmeta': sysmeta})
        from resources.lib import sources
        sources.sources().play(params)
    except:
        pass

elif action == 'resolverSettings':
    import resolveurl as resolver
    resolver.display_settings()

elif action == 'domainCheck':
    # Manueller Domain-Check. check_domains() hat eine 90-Min-Sperre (fuer den Service-
    # Autocheck korrekt). Manuell soll er IMMER laufen -> Sperre durch Reset umgehen.
    try:
        control.busy()
        control.setSetting('lastDomainCheck', '0')
        import service
        service.check_domains()
        control.idle()
        control.infoDialog('Domain Check abgeschlossen', icon='INFO', time=3000)
    except Exception:
        control.idle()
        control.infoDialog('Domain Check fehlgeschlagen', icon='WARNING', time=3000)

elif action == 'resolverUpdate':
    # Manueller ResolveURL-Update (zieht frischen Branch von Gujal00/ResolveURL).
    # busy()/idle() fuer visuelles Feedback waehrend GitHub-Call laeuft.
    # Notifications (erfolgreich / Fehler / kein Update) kommen aus updateManager selbst.
    try:
        control.busy()
        from resources.lib import updateManager
        updateManager.manualResolverUpdate()
        control.idle()
    except Exception:
        control.idle()
        control.infoDialog('Fehler bei ResolveURL Update.', icon='ERROR', sound=True)

elif action == 'playURL':
    try:
        import resolveurl
        import xbmcgui, xbmc
        #url = 'https://streamvid.net/embed-uhgo683xes41'
        #url = 'https://moflix-stream.click/v/gcd0aueegeia'
        url = xbmcgui.Dialog().input("URL Input")
        hmf = resolveurl.HostedMediaFile(url=url, include_disabled=True, include_universal=False)
        try:
            if hmf.valid_url(): url = hmf.resolve()
        except:
            pass
        item = xbmcgui.ListItem('URL-direkt')
        kodiver = int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0])
        # Header zuerst abtrennen, maxsplit=1 (Fix ggue 0.9er .split('|')).
        strhdr = None
        if '|' in url:
            url, strhdr = url.split('|', 1)
        # HLS UND DASH komplett ueber InputStream Adaptive (wie 0.9er).
        # ISA-Auto-Install passiert beim Kodi-Start im service.py, nicht hier.
        if ".m3u" in url or '.mpd' in url:
            item.setProperty("inputstream", "inputstream.adaptive")
            item.setProperty('inputstream.adaptive.config', '{"ssl_verify_peer":false}')
            if '.mpd' in url:
                if kodiver < 21: item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
                item.setMimeType('application/dash+xml')
            else:
                if kodiver < 21: item.setProperty('inputstream.adaptive.manifest_type', 'hls')
                item.setMimeType('application/x-mpegURL')
            item.setContentLookup(False)
            if strhdr:
                item.setProperty('inputstream.adaptive.stream_headers', strhdr)
                if kodiver > 19: item.setProperty('inputstream.adaptive.manifest_headers', strhdr)
        else:
            # Sonstige (mp4 etc.): Header ggf. wieder anhaengen, sonst clean durchreichen.
            if strhdr:
                url = url + '|' + strhdr
        item.setPath(url)
        xbmc.Player().play(url, item)
    except:
        #print('Kein Video Link gefunden')
        control.infoDialog("Keinen Video Link gefunden", sound=True, icon='WARNING', time=1000)

elif action == 'playTrailer':
    if not control.visible(): control.busy()
    try:
        from resources.lib.trailer import playTrailer
        playTrailer(
            tmdb_id   = params.get('tmdb_id', ''),
            mediatype = params.get('mediatype', 'movie'),
            title     = params.get('title', ''),
            year      = params.get('year', ''),
            poster    = params.get('poster', ''),
            pref_lang = 'de',
            season    = params.get('season', None),
        )
        if control.visible(): control.idle()
    except Exception:
        if control.visible(): control.idle()
        control.infoDialog('Trailer-Suche fehlgeschlagen', sound=True, icon='WARNING')

elif action == 'UpdatePlayCount':
    from resources.lib import playcountDB
    playcountDB.UpdatePlaycount(params)
    control.execute('Container.Refresh')

# listings -------------------------------
elif action == 'listings':
    from resources.lib.indexers import listings
    listings.listings().get(params)

elif action == 'movieYears':
    from resources.lib.indexers import listings
    listings.listings().movieYears()

elif action == 'movieYearsByDecade':
    from resources.lib.indexers import listings
    listings.listings().movieYearsByDecade(params)

elif action == 'movieGenres':
    from resources.lib.indexers import listings
    listings.listings().movieGenres()

elif action == 'tvGenres':
    from resources.lib.indexers import listings
    listings.listings().tvGenres()

elif action == 'movieProviders':
    from resources.lib.indexers import listings
    listings.listings().movieProviders()

elif action == 'tvProviders':
    from resources.lib.indexers import listings
    listings.listings().tvProviders()

elif action == 'tvYears':
    from resources.lib.indexers import listings
    listings.listings().tvYears()

elif action == 'tvYearsByDecade':
    from resources.lib.indexers import listings
    listings.listings().tvYearsByDecade(params)

# search ----------------------
elif action == 'searchNew':
    from resources.lib import searchDB
    searchDB.search_new(table)

elif action == 'searchClear':
    from resources.lib import searchDB
    searchDB.remove_all_query(table)
    # if len(searchDB.getSearchTerms()) == 0:
    #     control.execute('Action(ParentDir)')

elif action == 'searchDelTerm':
    from resources.lib import searchDB
    searchDB.remove_query(name, table)
    # if len(searchDB.getSearchTerms()) == 0:
    #     control.execute('Action(ParentDir)')

# person ----------------------
elif action == 'person':
    from resources.lib.indexers import person
    person.person().get(params)

elif action == 'personSearch':
    from resources.lib.indexers import person
    person.person().search()

elif action == 'personCredits':
    from resources.lib.indexers import person
    person.person().getCredits(params)

elif action == 'playfromPerson':
    if not control.visible(): control.busy()
    sysmeta = json.loads(params['sysmeta'])
    if sysmeta['mediatype'] == 'movie':
        from resources.lib.indexers import movies
        sysmeta = movies.movies().super_meta(sysmeta['tmdb_id'])
        sysmeta = json.dumps(sysmeta)
    else:
        from resources.lib.indexers import tvshows
        sysmeta = tvshows.tvshows().super_meta(sysmeta['tmdb_id'])
        sysmeta = control.quote_plus(json.dumps(sysmeta))

    params.update({'sysmeta': sysmeta})
    from resources.lib import sources
    sources.sources().play(params)

# similar movies ----------------------
elif action == 'similarMovies':
    from resources.lib.indexers import similar
    similar.similar().showCategories(params)

elif action == 'similarByTmdb':
    from resources.lib.indexers import similar
    similar.similar().byTmdbRecommendations(params)

elif action == 'similarByDirector':
    from resources.lib.indexers import similar
    similar.similar().byDirector(params)

elif action == 'similarByStudio':
    from resources.lib.indexers import similar
    similar.similar().byStudio(params)

elif action == 'similarByCast':
    from resources.lib.indexers import similar
    similar.similar().byCast(params)

elif action == 'similarByCastYear':
    from resources.lib.indexers import similar
    similar.similar().byCastYear(params)

elif action == 'similarByGenreYear':
    from resources.lib.indexers import similar
    similar.similar().byGenreYear(params)

elif action == 'similarDirectorList':
    from resources.lib.indexers import similar
    similar.similar().showDirectorList(params)

elif action == 'similarStudioList':
    from resources.lib.indexers import similar
    similar.similar().showStudioList(params)

elif action == 'similarCastList':
    from resources.lib.indexers import similar
    similar.similar().showCastList(params)

elif action == 'similarGenreYearSelect':
    from resources.lib.indexers import similar
    similar.similar().showYearList(params)

# movies ----------------------
elif action == 'movies':
    from resources.lib.indexers import movies
    movies.movies().get(params)

elif action == 'moviesSearch':
    from resources.lib.indexers import movies
    movies.movies().search()

# tvshows ---------------------------------
elif action == 'tvshows': # 'tvshowPage'
    from resources.lib.indexers import tvshows
    tvshows.tvshows().get(params)

elif action == 'tvshowsSearch':
    from resources.lib.indexers import tvshows
    tvshows.tvshows().search()

# seasons ---------------------------------
elif action == 'seasons':
    from resources.lib.indexers import seasons
    seasons.seasons().get(params)  # params

# episodes ---------------------------------
elif action == 'episodes':
    from resources.lib.indexers import episodes
    episodes.episodes().get(params)

# sources ---------------------------------
elif action == 'play':
    from resources.lib import sources
    sources.sources().play(params)

elif action == 'addItem':
    from resources.lib import sources
    sources.sources().addItem(title)

elif action == 'playItem':
    if not control.visible(): control.busy()
    from resources.lib import sources
    sources.sources().playItem(title, source)

# Settings ------------------------------
elif action == "settings":  # alle Quellen aktivieren / deaktivieren
    from resources import settings
    settings.run(params)

elif action == 'addonSettings':
    # query = None
    query = params.get('query')
    control.openSettings(query)

elif action == 'resetSettings':
    status = control.resetSettings()
    if status:
        control.reload_profile()
        control.sleep(0.1)
        control.execute('RunAddon("%s")' % control.addonId)
        
elif action == 'resolverSettings':
    import resolveurl as resolver
    resolver.display_settings()

try:
    import pydevd
    if pydevd.connected: pydevd.kill_all_pydev_threads()
except:
    pass
finally:
    exit()
