

#2021-11-22
#edit 2026-05-18

import sys, re, time, json
import hashlib,os,codecs
from sqlite3 import dbapi2 as database
import xbmc, xbmcplugin
from resources.lib.control import translatePath
from resources.lib import log_utils, control, playcountDB
import xmlrpc.client as _xmlrpclib
from io import BytesIO as _io

# eventuell zur späteren verwendung als meta
#_params = dict(parse_qsl(sys.argv[2].replace('?',''))) if len(sys.argv) > 1 else dict()

class player(xbmc.Player):
    def __init__(self, *args, **kwargs):
        xbmc.Player.__init__(self, *args, **kwargs)
        self.streamFinished = False
        self.totalTime = 0
        self.currentTime = 0
        self.playcount = 0
        self.watcher_control = False
        self.isdebug = True if control.getSetting('status.debug') == 'true' else False
        # Startup-Busy wird bewusst vom Player verwaltet. setResolvedUrl() kann
        # einen zuvor geoeffneten Kodi-Busy-Dialog wieder schliessen, obwohl
        # InputStream/Player den Stream noch vorbereitet.
        self._av_started = False


    def _openStartupBusy(self):
        """Native Kodi-Ladeanzeige bis zum echten AV-Start sichtbar halten."""
        try:
            if self._av_started or self.isPlayingVideo():
                return
            if not control.visible():
                control.busy()
            # ActivateWindow() wird asynchron an die GUI uebergeben. Kurz warten,
            # damit der Skin mindestens einen Frame zeichnen kann.
            for _ in range(6):
                if self._av_started or self.isPlayingVideo() or control.visible():
                    break
                xbmc.sleep(50)
        except:
            pass


    def _closeStartupBusy(self):
        """Beide Kodi-Busy-Varianten sicher schliessen."""
        try:
            control.execute('Dialog.Close(busydialognocancel,true)')
            control.execute('Dialog.Close(busydialog,true)')
        except:
            pass


    def run(self, title, url, meta):
        import xbmc
        try:
            self.meta = meta
            self.mediatype = meta['mediatype']
            self.title = meta['title']
            self.year = str(meta['year']) if 'year' in meta else ''
            if meta['mediatype'] == 'movie':
                self.name = title + ' (%s)' % meta['year'] if meta.get('year', False) else title
            else:
                self.name = title + ' S%02dE%02d' % (int(meta['season']), int(meta['episode']))

            self.imdb = meta['imdb_id'] if 'imdb_id' in meta else None
            self.number_of_seasons = meta['number_of_seasons'] if 'number_of_seasons' in meta else None
            self.season = meta['season'] if 'season' in meta else None
            self.number_of_episodes = meta['number_of_episodes'] if 'number_of_episodes' in meta else None
            self.episode = meta['episode'] if 'episode' in meta else None

            self.playcount = meta['playcount'] if 'playcount' in meta else 0
            self.offset = bookmarks().get(self.name)

            from glob import glob
            os.chdir(os.path.join(control.translatePath('special://database/')))
            self.videoDB = os.path.join(control.translatePath('special://database/'), sorted(glob("MyVideos*.db"), reverse=True)[0])

            self.fileID = self.getVideoDB()

            plot = control.unquote(meta['plot']) if 'plot' in meta else ''

            Info = {'plot': plot}
            if 'imdbnumber' in meta: Info.setdefault('IMDBNumber', meta['imdbnumber'])
            if meta['mediatype'] == 'movie':
                Info.setdefault('OriginalTitle', meta['title'])
                Info.setdefault('year', meta['year'])
            else:
                Info.setdefault('TVshowtitle', meta['title'])
                Info.setdefault('Season', self.season)
                Info.setdefault('Episode', self.episode)

            if meta['mediatype'] == 'movie':
                item = control.item(label=self.title)
            else:
                item = control.item(label=self.name)

            # TS: video/mp2t
            # HLS: application/x-mpegURL or application/vnd.apple.mpegurl
            # Dash: application/dash+xml
            kodiver = int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0])
            # Header (url|User-Agent=...&Referer=...) zuerst abtrennen. maxsplit=1,
            # damit URLs mit mehreren | nicht crashen (Fix ggue 0.9er .split('|')).
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
            item.setProperty('IsPlayable', 'true')
            if kodiver <= 19:
                try:
                    item.setArt({'poster': meta['poster']})
                    item.setInfo(type='Video', infoLabels=Info)
                except:
                    pass

            # Sofort Feedback geben. Wichtig: Nach setResolvedUrl()/play()
            # nochmals pruefen und ggf. neu oeffnen, weil Kodi den vorherigen
            # Busy-Dialog beim Player-Handoff selbst schliessen kann.
            self._openStartupBusy()
            if int(sys.argv[1]) > 0:
                xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)
            else:
                xbmc.Player().play(url, item)

            # Dem Kodi-GUI/Player kurz Zeit fuer den Handoff geben. Falls der
            # AV-Start inzwischen schon kam, verhindert _av_started ein Reopen.
            xbmc.sleep(120)
            self._openStartupBusy()

            self.keepPlaybackAlive()
            return
        except:
            self._closeStartupBusy()
            return


    def keepPlaybackAlive(self):
        if self.isdebug: log_utils.log('Start - keepPlaybackAlive', log_utils.LOGINFO)
        for i in range(0, 240):
            if self.isPlayingVideo() or self.streamFinished:
                break
            xbmc.sleep(1000)

        if self.streamFinished and not self.isPlayingVideo():
            self._closeStartupBusy()
            return

        if self.isPlayingVideo():
            try:
                playcountDB.createEntry(self.mediatype, self.title, self.name, self.imdb, self.number_of_seasons, self.season, self.number_of_episodes, self.episode)
            except:
                pass

        monitor = xbmc.Monitor()
        self.watcher_control = False
        while (not monitor.abortRequested()) & (not self.streamFinished):
            if self.isPlayingVideo():
                self.totalTime = self.getTotalTime()
                self.currentTime = self.getTime()
                watcher = (self.currentTime / self.totalTime >= .85)
                if watcher and not self.watcher_control:
                    playcountDB.updatePlaycount(self.mediatype, self.title, self.name, self.imdb, self.number_of_seasons, self.season, self.number_of_episodes, self.episode, 1)
                    #control.setSetting(id='watcher.control', value='true')
                    self.watcher_control = True
            monitor.waitForAbort(3)

        if self.isdebug: log_utils.log('Ende - keepPlaybackAlive', log_utils.LOGINFO)


    def idleForPlayback(self):
        for i in range(0, 200):
            if control.visible():
                control.idle()
            else:
                break
            xbmc.sleep(100)

    def onPlayBackStarted(self):
        if self.isdebug: log_utils.log('Start - onPlayBackStarted', log_utils.LOGINFO)
        self.onAVStarted()

    def onAVStarted(self):
        if self.isdebug: log_utils.log('Start - onAVStarted', log_utils.LOGINFO)
        # Flag zuerst setzen: verhindert ein Reopen durch den Handoff-Code, falls
        # Callback und run() zeitlich direkt aufeinander treffen.
        self._av_started = True
        self._closeStartupBusy()
        control.execute('Dialog.Close(all,true)')
        if not self.offset == '0': self.seekTime(float(self.offset))
        self.idleForPlayback()
        if control.getSetting('subtitles') == 'true':
            status = subtitles().get(self.name, self.imdb, self.season, self.episode)
            ## Subtitles in Player Menü ausschalten - wird dann bei Bedarf per "Hand" eingeschaltet
            # xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Player.SetSubtitle", "params": {"playerid": 1, "subtitle" : "on"}, "id": "1"}')
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Player.SetSubtitle", "params": {"playerid": 1, "subtitle" : "off"}, "id": "1"}')
        if self.isdebug: log_utils.log('Ende - onAVStarted', log_utils.LOGINFO)


    def onPlayBackError(self):
        if self.isdebug: log_utils.log('onPlayBackError - closing busy dialog', log_utils.LOGINFO)
        self._closeStartupBusy()
        self.streamFinished = True

    def onPlayBackStopped(self):
        if self.isdebug: log_utils.log('Start - onPlayBackStopped', log_utils.LOGINFO)
        self._closeStartupBusy()
        self.runVideoDB()
        self.streamFinished = True
        if self.isdebug: log_utils.log('vor parentDir - onPlayBackStopped', log_utils.LOGINFO)
        if self.watcher_control:
            bookmarks().remove(self.name)
            self.parentDir()
            self.watcher_control = False
        else:  # bookmark setzen
            bookmarks().save(self.currentTime, self.name)
        if self.isdebug: log_utils.log('Ende - onPlayBackStopped', log_utils.LOGINFO)

    def onPlayBackEnded(self):
        self.onPlayBackStopped()
        if self.isdebug: log_utils.log('Ende - onPlayBackEnded', log_utils.LOGINFO)


    def parentDir(self):
        """Navigiert nach Filmende zurück zur Filmliste und aktualisiert Playcount-Anzeige.

        Im Verzeichnis-Modus (hosts.mode='1') erzeugt die Quellenauswahl eine extra
        Navigationsebene. Nach dem Abspielen steht der User in der Quellenliste
        (Container.Content='videos') und muss per ParentDir zurück zur Filmliste
        (Container.Content='movies') navigiert werden.
        """
        try:
            monitor = xbmc.Monitor()
            hosts_mode = control.getSetting('hosts.mode')
            # Verzeichnis-Modus: Quellenliste -> zurück zur Filmliste
            if hosts_mode == '1':
                if self.isdebug: log_utils.log(__name__ + ' - parentDir: start (hosts_mode=%s)' % hosts_mode, log_utils.LOGINFO)
                # Warte bis Kodi die Quellenliste wieder anzeigt (nach Player-Close)
                if not self._wait_for_content('videos', monitor, timeout=5.0):
                    if self.isdebug: log_utils.log(__name__ + ' - parentDir: Timeout waiting for videos', log_utils.LOGINFO)
                    return
                # Eine Ebene hoch: Quellenliste -> Filmliste
                if control.getInfoLabel("Container.Content") != 'movies':
                    control.execute('Action(ParentDir)')
                    if not self._wait_for_content('movies', monitor, timeout=3.0):
                        if self.isdebug: log_utils.log(__name__ + ' - parentDir: Timeout waiting for movies', log_utils.LOGINFO)
                        return

            # Playcount-Häkchen sichtbar machen (nur bei erstmaliger Wiedergabe)
            if self.playcount == 0 and hosts_mode == '2' and not xbmc.getCondVisibility('system.platform.windows'):
                control.execute('Container.Refresh')
            elif self.playcount == 0 and hosts_mode == '1':
                control.execute('Container.Refresh')
            if self.isdebug: log_utils.log(__name__ + ' - parentDir: done (hosts_mode=%s)' % hosts_mode, log_utils.LOGINFO)
        except Exception as e:
            log_utils.log(__name__ + ' - parentDir error: %s' % e, log_utils.LOGERROR)


    def _wait_for_content(self, target, monitor, timeout=3.0):
        """Pollt Container.Content bis Zielwert erreicht oder Timeout.
        100ms-Intervall: schnell genug für reaktive UI, schonend genug für CPU.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if monitor.abortRequested():
                return False
            if control.getInfoLabel("Container.Content") == target:
                return True
            monitor.waitForAbort(0.1)
        return False

# keine Einträge für bookmarks und files in die Kodi DB 'MyVideos116.db' anlegen bzw. sofort löschen
    def runVideoDB(self):
        idFile = self.getVideoDB()
        if idFile != self.fileID:
            self.removeVideoDB(idFile)

    def getVideoDB(self):
        dbcon = database.connect(self.videoDB)
        dbcur = dbcon.cursor()
        dbcur.execute("SELECT * FROM files")
        match = dbcur.fetchall()
        dbcon.close()
        if match and len(match) > 0: idFile = len(match)
        else: idFile = 0
        return idFile

    def removeVideoDB(self, idFile):
        dbcon = database.connect(self.videoDB)
        dbcur = dbcon.cursor()
        dbcur.execute("DELETE FROM files WHERE idFile = '%s'" % idFile) # in DB vorhandener Trigger löscht auch den bookmark
        dbcon.commit()
        dbcon.close()


class subtitles:
    def __init__(self, *args, **kwargs):
        from xbmcaddon import Addon
        __scriptname__ = "XBMC Subtitles Login"
        __version__ = Addon().getAddonInfo('version')  # Module version
        BASE_URL_XMLRPC = u"http://api.opensubtitles.org/xml-rpc"

        self.server = _xmlrpclib.ServerProxy(BASE_URL_XMLRPC, verbose=0)
        login = self.server.LogIn(Addon().getSetting('subtitles.os_user'), Addon().getSetting('subtitles.os_pass'), "en", "%s_v%s" % (__scriptname__.replace(" ", "_"), __version__))
        if login["status"] == "200 OK":
            self.osdb_token = login["token"]

    def get(self, name, imdb, season, episode):
        isdebug = True if control.getSetting('status.debug') == 'true' else False
        if isdebug: log_utils.log('Start - get subtitles', log_utils.LOGINFO)
        subtitlepath = control.translatePath('special://temp/temp/')
        if not os.path.exists(subtitlepath): os.mkdir(subtitlepath)

        # struktur = json.loads(xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.GetSettingValue", "params":{"setting":"subtitles.custompath"},"id":1}'))
        # if struktur["result"]["value"] != subtitlepath:
        #     xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.setSettingValue","id":1,"params":{"setting":"subtitles.custompath", "value": "%s"}}' % subtitlepath.replace('\\', '\\\\'))

        controlfile = control.translatePath('special://temp/temp/%s' % name.replace(' ','-'))+'.ifo'
        if not os.path.exists(controlfile):
            for f in os.listdir(subtitlepath):
                os.remove(os.path.join(subtitlepath, f))
            with open(controlfile, mode='a'):
                pass

        season = str(season)
        episode = str(episode)
        # import pydevd
        # pydevd.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)
        try:
            langDict = {'Afrikaans': 'afr', 'Albanian': 'alb', 'Arabic': 'ara', 'Armenian': 'arm', 'Basque': 'baq', 'Bengali': 'ben', 'Bosnian': 'bos', 'Breton': 'bre', 'Bulgarian': 'bul', 'Burmese': 'bur', 'Catalan': 'cat', 'Chinese': 'chi', 'Croatian': 'hrv', 'Czech': 'cze', 'Danish': 'dan', 'Dutch': 'dut', 'English': 'eng', 'Esperanto': 'epo', 'Estonian': 'est', 'Finnish': 'fin', 'French': 'fre', 'Galician': 'glg', 'Georgian': 'geo', 'German': 'ger', 'Greek': 'ell', 'Hebrew': 'heb', 'Hindi': 'hin', 'Hungarian': 'hun', 'Icelandic': 'ice', 'Indonesian': 'ind', 'Italian': 'ita', 'Japanese': 'jpn', 'Kazakh': 'kaz', 'Khmer': 'khm', 'Korean': 'kor', 'Latvian': 'lav', 'Lithuanian': 'lit', 'Luxembourgish': 'ltz', 'Macedonian': 'mac', 'Malay': 'may', 'Malayalam': 'mal', 'Manipuri': 'mni', 'Mongolian': 'mon', 'Montenegrin': 'mne', 'Norwegian': 'nor', 'Occitan': 'oci', 'Persian': 'per', 'Polish': 'pol', 'Portuguese': 'por,pob', 'Portuguese(Brazil)': 'pob,por', 'Romanian': 'rum', 'Russian': 'rus', 'Serbian': 'scc', 'Sinhalese': 'sin', 'Slovak': 'slo', 'Slovenian': 'slv', 'Spanish': 'spa', 'Swahili': 'swa', 'Swedish': 'swe', 'Syriac': 'syr', 'Tagalog': 'tgl', 'Tamil': 'tam', 'Telugu': 'tel', 'Thai': 'tha', 'Turkish': 'tur', 'Ukrainian': 'ukr', 'Urdu': 'urd'}
            codePageDict = {'ara': 'cp1256', 'ar': 'cp1256', 'ell': 'cp1253', 'el': 'cp1253', 'heb': 'cp1255', 'he': 'cp1255', 'tur': 'cp1254', 'tr': 'cp1254', 'rus': 'cp1251', 'ru': 'cp1251'}

            langs = []
            try:
                try: langs = langDict[control.getSetting('subtitles.lang.1')].split(',')
                except: langs.append(langDict[control.getSetting('subtitles.lang.1')])
            except:
                langs = ['ger']
            ## Einstellungen/Player/Sprache
            # bevorzugte Audiosprache - Sprache der Benutzeroberfläche
            xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.setSettingValue", "params":{"setting":"locale.audiolanguage", "value": "default"},"id":1}')
            # bevorzugte Untertitelsprache - Sprache der Benutzeroberfläche
            xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.setSettingValue", "params":{"setting":"locale.subtitlelanguage", "value": "default"},"id":1}')
            ## Einstellungen/Player/Untertitel
            xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.setSettingValue", "params":{"setting":"subtitles.languages", "value": ["%s"]},"id":1}' % (control.getSetting('subtitles.lang.1')))

            try: subLang = xbmc.Player().getSubtitles()
            except: subLang = ''
            if subLang == langs[0]: raise Exception()

            imdbid = re.sub(r'[^0-9]', '', imdb)
            if season == 'None' or episode == 'None':
                result = self.server.SearchSubtitles(self.osdb_token, [{'sublanguageid': langs[0], 'imdbid': imdbid}])['data']
            else:
                result = self.server.SearchSubtitles(self.osdb_token, [{'sublanguageid': langs[0], 'imdbid': imdbid, 'season': season, 'episode': episode}])['data']
            if result == []: raise Exception()

            if langs == ['ger']: # alles nur deutsch
                result = [i for i in result if i['SubSumCD'] == '1' and i['LanguageName'] == 'German' and i['ISO639'] == 'de' and i['SubLanguageID'] == 'ger']
            else:
                result = [i for i in result if i['SubSumCD'] == '1']

            result=sorted(result, key=lambda k: int(k['SubSize']), reverse=True)

            # filter = []
            # for userrank in ['OS Legend','Administrator','Translator','Platinum member','Gold member','Silver member', 'Bronze member','trusted','']:
            #     for i in result:
            #         if i['UserRank'] == userrank.lower():
            #             filter.append(i)

            count = 0
            for i in result:
                try: lang = xbmc.convertLanguage(i['SubLanguageID'], xbmc.ISO_639_1)
                except: lang = i['SubLanguageID']
                subtitle = os.path.join(subtitlepath, i['SubFileName'])
                if not os.path.exists(subtitle):
                    ZipDownloadID = i['ZipDownloadLink'].split('/')[-1]
                    ZipDownloadLink = 'https://dl.opensubtitles.org/en/download/sub/%s' % ZipDownloadID

                    import requests, zipfile
                    r = requests.get(ZipDownloadLink, timeout=(3, 5))
                    status = r.status_code
                    if status == 200:
                        zf = zipfile.ZipFile(_io(r.content))
                        content = ''
                        for name in zf.namelist():
                            if not name.endswith('.srt'): continue
                            content = zf.read(name)

                        codepage = codePageDict.get(lang, '')
                        if codepage and control.getSetting('subtitles.utf') == 'true':
                            try:
                                content_encoded = codecs.decode(content, codepage)
                                content = codecs.encode(content_encoded, 'utf-8')
                            except:
                                pass

                        output = open(subtitle, 'wb')
                        output.write(content)
                        output.close()
                    else:
                        if count == 0:
                            from xbmcvfs import copy
                            errorfile = translatePath('special://home/addons/plugin.video.xship/resources/error.connect.opensubtitles.org.srt')
                            subtitle = subtitlepath + 'error.connect.opensubtitles.org.srt'
                            copy(errorfile, subtitle)
                            xbmc.Player().setSubtitles(subtitle)
                            return False
                        else: break
                xbmc.Player().setSubtitles(subtitle)
                count += 1
                if count == 3: break

            return True
        except:
            return False



class bookmarks:
    def get(self, name):
        from resources.lib import bookmarkDB
        offset = '0'
        try:
            # if not control.getSetting('bookmarks') == 'true': raise Exception()
            idFile = hashlib.md5()
            for i in name:
                try:
                    idFile.update(str(i).encode('utf-8'))
                except:
                    idFile.update(str(i))
            idFile = str(idFile.hexdigest())

            match = bookmarkDB.get_query(idFile, 'bookmarks.pcl')
            if match:
                self.offset = str(match[1])
                if self.offset == '0': raise Exception()
                minutes, seconds = divmod(float(self.offset), 60)
                hours, minutes = divmod(minutes, 60)
                label = '%02d:%02d:%02d' % (hours, minutes, seconds)
                label = control.py2_encode("Fortsetzen ab : %s" % label)
                if control.getSetting('bookmarks.auto') == 'false':
                    try:
                        yes = control.dialog.contextmenu([label, "Vom Anfang abspielen", ])
                    except:
                        yes = control.yesnoDialog(label, '', '', str(name), "Fortsetzen",
                                                  "Vom Anfang abspielen")
                    if yes:
                        bookmarkDB.remove_query(idFile, 'bookmarks')
                        self.offset = '0'
                return self.offset
            else:
                return offset
        except Exception as e:
            return offset


    def remove(self, name):
        from resources.lib import bookmarkDB
        try:
            idFile = hashlib.md5()
            for i in name:
                try:
                    idFile.update(str(i).encode('utf-8'))
                except:
                    idFile.update(str(i))
            idFile = str(idFile.hexdigest())
            # if (currentTime / totalTime) >= .87:
            bookmarkDB.remove_query(idFile, 'bookmarks')
        except:
            pass

    def save(self, currentTime, name):
        from resources.lib import bookmarkDB
        try:
            if int(currentTime) > 180:
                timeInSeconds = str(currentTime)
                idFile = hashlib.md5()
                for i in name:
                    try:
                        idFile.update(str(i).encode('utf-8'))
                    except:
                        idFile.update(str(i))
                idFile = str(idFile.hexdigest())
                bookmarkDB.save_query(idFile, timeInSeconds, 'bookmarks')
        except:
            pass

