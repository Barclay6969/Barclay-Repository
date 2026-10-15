# FilmPalast TMDb Native – confirmed local integration 1.3.1

Status: **lokal im Kodi-Log vom 15.10.2026 bestätigt; NICHT für ein automatisches Release freigegeben**.

* FilmPalast: `plugin.video.filmpalast.ex` v0.6.6.
* TMDb Helper: `plugin.video.themoviedb.helper` v6.17.9.
* Lokaler Patcher: `script.filmpalast.tmdbtest` v1.3.1.
* Archiv des lokal getesteten Patchers SHA-256: `1173dbc99f9257cbff4fe9dd6601f2ddd81224a1bd20ec31c032f3f1b0af196f`.

## Testresultat

Kodi-Log 2026-10-15 16:36–16:39 bestätigt bei sieben Filmen `lib.player - Success!`, `VideoPlayer::OpenFile`, korrekt ausgewählte FilmPalast-Seite und gestarteten HLS-Puffer (320 MiB): Before the Fire, Suddenly, The Hummingbird Project, Nirgendwo, Smugglers, Transporter 3, Bay of Silence.

Es wurden keine Langzeit-, Plattform- oder Neuinstallationstests durchgeführt. Vereinzelte TMDb-Zuordnungen können weiterhin fehlschlagen.

## Architekturbedingung vor Produktiv-Release

Die funktionierende lokale Version modifiziert **nicht nur** FilmPalast, sondern auch
`resources/tmdbhelper/lib/script/method/play_player.py` und
`resources/tmdbhelper/lib/player/dialog/player.py` der *installierten* TMDb Helper Version und legt
`userdata/addon_data/plugin.video.themoviedb.helper/players/filmpalast_tmdb_native_test.json`
an. Ein einfaches Update auf eine neue FilmPalast ZIP würde diese Änderungen nicht korrekt verteilen oder bei Updates erhalten.

Zum Produktiv-Release ist eine updatefeste Integration nötig, die andere TMDb-Helper-Player nicht beeinflusst, keine fremden Dateien unkontrolliert überschreibt und bei fehlendem TMDb Helper sicher auf FilmPalast zurückfällt. Vorher den produktiven Add-on-Stand 0.6.6 beibehalten.

## Lokale Implementierung (zum Nachbau)

1. Film-Kachel öffnet die originale TMDb-Helper-Detail-ListItem; TMDb-ID-Suche toleriert alternative Titel und +/- ein bis zwei Jahre.
2. Pro Infofenster wird über ein kurzes, tokenisiertes Window-Property nur diese FilmPalast-Seite als Playbackziel vorgemerkt.
3. TMDb-Helper-Player wird mit `player=filmpalast_tmdb_native_test.json` und `mode=play` für exakt eine Film-ID erzwungen.
4. Der direkte `play_movie`-Eintrag ist **ein String** (kein Array und keine `dialog:auto`-Suche), der FilmPalast `mode=31` aufruft.
5. `mode=31` prüft die einmalige, zeitlich begrenzte Film-URL-Zuordnung und ruft die bestehende `PLAYVIDEO`-Funktion auf.
6. Bestehender 320-MiB-Puffer, Hosterauswahl und Trakt-Metadaten bleiben erhalten.
7. Alle lokalen Originaldateien werden vor dem Patch mit SHA-256-Manifesteinträgen gesichert; Rollback prüft die Hashes.

Diese Staging-Dokumentation verändert weder das produktive FilmPalast-Addon noch den Repository-Index.
