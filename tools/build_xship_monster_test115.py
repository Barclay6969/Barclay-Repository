from pathlib import Path
import os, re, zipfile, tempfile, shutil

repo = Path.cwd()
base = repo / 'zips/plugin.video.xship/plugin.video.xship-2026.09.28.105.zip'
out = repo / 'test-builds/plugin.video.xship-2026.09.29.115-MONSTER-TEST1.zip'
if not base.exists():
    raise SystemExit(f'Missing base ZIP: {base}')

work = Path(tempfile.mkdtemp(prefix='xship-monster-115-'))
try:
    with zipfile.ZipFile(base, 'r') as z:
        z.extractall(work)

    candidates = [p.parent for p in work.rglob('addon.xml') if p.parent.name == 'plugin.video.xship']
    if not candidates:
        raise SystemExit('plugin.video.xship root not found')
    root = candidates[0]

    # sources.py: normalize literal None/null and expose tmdb id to provider instances.
    p = root / 'resources/lib/sources.py'
    s = p.read_text(encoding='utf-8')
    old = """        tmdb = data.get('tmdb_id') if 'tmdb_id' in data else None
        #if tmdb and not imdb: print 'hallo' #TODO"""
    new = """        tmdb = data.get('tmdb_id') if 'tmdb_id' in data else None
        # External players may pass the literal string "None". Treat that as
        # missing metadata so providers never search for imdb=None.
        if imdb is not None and str(imdb).strip().lower() in ('', 'none', 'null', 'unknown'):
            imdb = None
        self.tmdb_id = tmdb
        #if tmdb and not imdb: print 'hallo' #TODO"""
    if old not in s:
        raise SystemExit('sources.py metadata anchor not found')
    s = s.replace(old, new, 1)

    old = """            try:
                call.mediatype = getattr(self, 'mediatype', None)
            except Exception:
                pass
            if self._acceptsHostDict(call):"""
    new = """            try:
                call.mediatype = getattr(self, 'mediatype', None)
                call.tmdb_id = getattr(self, 'tmdb_id', None)
            except Exception:
                pass
            if self._acceptsHostDict(call):"""
    if old not in s:
        raise SystemExit('sources.py provider metadata anchor not found')
    s = s.replace(old, new, 1)
    compile(s, str(p), 'exec')
    p.write_text(s, encoding='utf-8', newline='\n')

    # SerienStream: TMDb splits Monster into standalone shows; SerienStream stores
    # the anthology as Monster (2022), seasons 1-4.
    p = root / 'scrapers/scrapers_source/de/serienstream.py'
    s = p.read_text(encoding='utf-8')
    anchor = "LEGACY_DOMAINS = set(['.'.join(('s', 'to')), 'www.' + '.'.join(('s', 'to'))])\n"
    inject = """
MONSTER_SERIES_PATH = '/serie/monster-2022'
MONSTER_TMDB_SEASONS = {
    '113988': 1,  # Dahmer
    '225634': 2,  # Menendez brothers
    '286801': 3,  # Ed Gein
    '299939': 4,  # Lizzie Borden
}


def _monster_target_season(titles, tmdb_id=None):
    try:
        key = str(tmdb_id or '').strip()
        if key in MONSTER_TMDB_SEASONS:
            return MONSTER_TMDB_SEASONS[key]
    except:
        pass

    try:
        blob = ' '.join([str(x or '') for x in (titles or [])]).lower()
    except:
        blob = str(titles or '').lower()

    # Current TMDbHelper player URL does not forward tmdb_id to xShip, so keep a
    # narrowly-scoped title fallback for these four Monster entries.
    if 'dahmer' in blob and 'jeffrey' in blob:
        return 1
    if 'menendez' in blob and ('lyle' in blob or 'erik' in blob):
        return 2
    if 'ed gein' in blob or ('gein' in blob and 'monster' in blob):
        return 3
    if 'lizzie borden' in blob:
        return 4
    return None
"""
    if 'MONSTER_TMDB_SEASONS' not in s:
        if anchor not in s:
            raise SystemExit('serienstream constants anchor not found')
        s = s.replace(anchor, anchor + inject + '\n', 1)

    old = """            login_success = self._do_login(login, password)
            if not login_success:
                if log_utils:
                    logger.info('SerienStream - Login failed, but continuing anyway')

            aLinks = []
"""
    new = """            login_success = self._do_login(login, password)
            if not login_success:
                if log_utils:
                    logger.info('SerienStream - Login failed, but continuing anyway')

            # Monster anthology special case:
            # TMDb: four standalone shows, each season 1.
            # SerienStream: /serie/monster-2022 with seasons 1-4.
            monster_season = _monster_target_season(titles, getattr(self, 'tmdb_id', None))
            if monster_season:
                if log_utils:
                    logger.info('SerienStream - Monster mapping: tmdb=%s -> /serie/monster-2022 S%02dE%02d' % (
                        getattr(self, 'tmdb_id', None), monster_season, int(episode or 0)
                    ))
                # Do not compare the standalone show's IMDb id against the
                # anthology entry; the catalogue identities intentionally differ.
                self.run2(MONSTER_SERIES_PATH, year, season=monster_season, episode=episode,
                          hostDict=hostDict, imdb=None)
                return self.sources

            aLinks = []
"""
    if old not in s:
        raise SystemExit('serienstream run anchor not found')
    s = s.replace(old, new, 1)
    compile(s, str(p), 'exec')
    p.write_text(s, encoding='utf-8', newline='\n')

    addon = root / 'addon.xml'
    a = addon.read_text(encoding='utf-8-sig')
    a2, n = re.subn(r'(<addon\s+id="plugin\.video\.xship"\s+version=")[^"]+(")', r'\g<1>2026.09.29.115\2', a, count=1)
    if n != 1:
        raise SystemExit('addon version anchor not found')
    addon.write_text(a2, encoding='utf-8', newline='\n')

    (root / 'MONSTER-TEST1.txt').write_text(
        'xShip 2026.09.29.115 MONSTER-TEST1\n'
        'SerienStream Monster mapping: TMDb standalone series -> Monster (2022) seasons 1-4.\n'
        'Also normalizes literal imdb=None/null before provider calls.\n',
        encoding='utf-8'
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(root.rglob('*')):
            if f.is_file():
                z.write(f, Path('plugin.video.xship') / f.relative_to(root))

    # Sanity checks
    with zipfile.ZipFile(out, 'r') as z:
        addon_text = z.read('plugin.video.xship/addon.xml').decode('utf-8')
        ss_text = z.read('plugin.video.xship/scrapers/scrapers_source/de/serienstream.py').decode('utf-8')
        src_text = z.read('plugin.video.xship/resources/lib/sources.py').decode('utf-8')
    assert 'version="2026.09.29.115"' in addon_text
    assert 'MONSTER_TMDB_SEASONS' in ss_text
    assert 'Monster mapping:' in ss_text
    assert 'self.tmdb_id = tmdb' in src_text
    print(f'Created {out}')
finally:
    shutil.rmtree(work, ignore_errors=True)
