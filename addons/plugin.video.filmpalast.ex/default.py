#!/usr/bin/python
# kodi18+ (python3+)
import urllib.request
import urllib.parse
import urllib.error
import hashlib
import re
import os
import sys
import html
import unicodedata
import base64
import json
import uuid
from urllib.parse import urlparse, urljoin, urlencode
from html import unescape as html_unescape
import xlibs.urllib3 as urllib3p
from kodi_six import xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs
#import web_pdb; web_pdb.set_trace()

# Constants
BASE_URL = 'https://filmpalast.to'
STREAM_URL_TEMPLATE = 'https://filmpalast.to/stream/{id}/1'
MAX_ITEMS = 32
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0'
DEBUG = True

# Regex patterns
PATTERNS = {
    'genre_section': r'<section id="genre">(.*?)</section>',
    'genre_links': r'<a[^>]*href="([^"]*)">[ ]*([^<]*)</a>',
    'content_entries': r'id="content"[^>]*>(.+?)<[^>]*id="paging"',
    'movie_data': r'</cite>(.*?)<a[^>]*href="//filmpalast.to([^"]*)"[^>]*title="([^"]*)"[^>]*>[^<]*<img[^>]*src=["\']([^"\']*)["\'][^>]*>',
    'next_page': r'<a[^>]*class="[^"]*pageing[^"]*"[^>]*href=["\']([^"\']*)["\'][^>]*>[ ]*vorw',
    'stars': r'star_on.png',
    'votes': r'<sm.*?p;(.*?)&nbsp.*?ll>',
    'video_sources': r'<p class="hostName">(.*?)<.*?<li class="streamPlayBtn clearfix rb">.*?<a.*?class="button.*?(?:url|href)="(.*?)"',
    'imdb_rating': r'>&ndash; Imdb: ([0-9,.]{0,3})/10',
    'fp_rating': r'average">([0-9,.]{0,3})<',
    'year_runtime': r'>Ver&ouml;ffentlicht: ([^\n]*).*?>Spielzeit:.*?>(.*?)<',
    'description': r'itemprop="description">(.*?)<',
    'genres': r'class="rb"[^>]*genre/(.*?)"',
    'actors': r'class="rb".*?"/search/title/(.*?)"',
    'html_entities': r'&#\d+;'
}

# Plugin configuration
def load_settings():
    # Load all plugin settings into a dictionary
    settings = xbmcaddon.Addon(id='plugin.video.filmpalast.ex')
    
    return {
        'auto_hoster': settings.getSetting('autoHoster') == 'true',
        'tmdb_native_info': settings.getSetting('tmdbNativeInfo') != 'false',
        'filter_unknown_hoster': settings.getSetting("filterUnknownHoster") == 'true',
        'force_view_mode': settings.getSetting("forceViewMode") == 'true',
        'view_mode': str(settings.getSetting("viewMode")),
        'show_rating': settings.getSetting("showRating") == 'true',
        'show_votes': settings.getSetting("showVotes") == 'true',
        'show_movie_info': settings.getSetting("showMovieInfo") == 'true',
        'preload_info': settings.getSetting("preloadInfo") == 'true',
        'pre_rating': settings.getSetting("preRating") == 'true',
        'pre_genres': settings.getSetting("preGenres") == 'true',
        'pre_description': settings.getSetting("preDescription") == 'true',
        'pre_year': settings.getSetting("preYear") == 'true',
        'bypass_dns_lock': settings.getSetting("bypassDNSlock") == 'true',
        'caching': settings.getSetting("caching") == 'true' or settings.getSetting("bypassDNSlock") == 'true'
    }

# Global variables
config = load_settings()
pluginhandle = int(sys.argv[1])
itemcnt = 0
temp_dir = xbmcvfs.translatePath("special://temp") + "filmpalast" + os.sep

if DEBUG:
    print("View Mode: " + config['view_mode'])

def ensure_temp_dir():
    #Create temp directory or clean it if caching is disabled
    if not os.path.exists(temp_dir):
        os.mkdir(temp_dir)
    elif not config['caching']:
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))

def set_view_mode():
    # Apply view mode if forced in settings
    if config['force_view_mode']:
        xbmc.executebuiltin('Container.SetViewMode({})'.format(config['view_mode']))

def normalize_url(url, base_url=BASE_URL):
    # Ensure URL has proper protocol and domain
    if not url.lower().startswith('http'):
        return base_url + url
    return url

def START():
    # Main menu
    menu_items = [
        ('Neu', BASE_URL + '/'),
        ('Neue Filme', BASE_URL + '/movies/new'),
        ('Neue Serien', BASE_URL + '/serien/view'),
        ('Top Filme', BASE_URL + '/movies/top'),
        ('English', BASE_URL + '/search/genre/Englisch'),
        ('Kategorien', BASE_URL),
        ('Alphabetisch', BASE_URL),
        ('Suche...', BASE_URL + '/search/title/')
    ]
    
    modes = [1, 1, 1, 1, 1, 2, 3, 4]
    
    for (name, url), mode in zip(menu_items, modes):
        addDir(name, url, mode, '', True)
    
    set_view_mode()

def CATEGORIES(url):
    # Show genre categories
    data = getUrl(url)
    if not data:
        return
        
    genre_sections = re.findall(PATTERNS['genre_section'], data, re.S | re.I)
    for genre_section in genre_sections:
        genre_links = re.findall(PATTERNS['genre_links'], genre_section, re.S | re.I)
        for href, name in genre_links:
            addDir(clean(name), href, 1, '', True)
    
    set_view_mode()

def ALPHA():
    # Show alphabetical navigation
    addDir('#', BASE_URL + '/search/alpha/0-9', 1, '', True)
    for char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        addDir(char, BASE_URL + '/search/alpha/' + char, 1, '', True)
    
    set_view_mode()

def INDEX(caturl):
    # Display movie/series listings with pagination
    if DEBUG:
        xbmc.log(caturl)
    
    global itemcnt
    data = getUrl(caturl)
    if not data:
        return
    
    # Process entries
    content_entries = re.findall(PATTERNS['content_entries'], data, re.S | re.I)
    for entry in content_entries:
        if DEBUG:
            print(entry)
        
        process_movie_entries(entry)
    
    # Handle pagination
    handle_pagination(data)
    set_view_mode()

def process_movie_entries(entry):
    # Process individual movie entries from HTML
    global itemcnt
    
    movie_matches = re.findall(PATTERNS['movie_data'], entry, re.S | re.I)
    for rating, url, title, image in movie_matches:
        url = normalize_url(url)
        image = normalize_url(image)
        
        title = enhance_title_with_ratings(title, rating, url)
        description = get_preload_description(url) if config['preload_info'] else ""
        
        movie_mode = 30 if (config.get('tmdb_native_info') and url.startswith(BASE_URL + '/stream/')) else 10
        addLink(clean(title), url, movie_mode, image, description)
        itemcnt += 1

def enhance_title_with_ratings(title, rating, url):
    # Add rating information to title based on settings
    if config['show_rating']:
        stars = len(re.findall(PATTERNS['stars'], rating, re.S | re.I))
        title += "  [COLOR=blue]" + str(stars) + "/10[/COLOR]"
    
    if config['show_votes']:
        votes = re.findall(PATTERNS['votes'], rating, re.S | re.I)
        if votes:
            title += "  [COLOR=blue](" + str(votes[0]) + " votes)[/COLOR]"
    
    if config['preload_info']:
        info = getInfos(url)
        title = add_preload_info_to_title(title, info)
    
    return title

def add_preload_info_to_title(title, info):
    # Add preloaded info to title based on settings
    if config['pre_rating'] and info['imdb']:
        title += " [COLOR=red]" + info['imdb'] + "/10[/COLOR]"
    if config['pre_genres'] and info['genres']:
        title += " [COLOR=green]" + info['genres'] + "[/COLOR]"
    if config['pre_year'] and info['year']:
        title += " [COLOR=blue](" + info['year'] + ")[/COLOR]"
    
    return title

def get_preload_description(url):
    # Get description for preloading if enabled
    if config['pre_description']:
        info = getInfos(url)
        return info.get('description', '')
    return ''

def handle_pagination(data):
    # Handle next page navigation
    global itemcnt
    
    next_pages = re.findall(PATTERNS['next_page'], data, re.S | re.I)
    if next_pages:
        if DEBUG:
            print(next_pages)
        
        next_url = next_pages[0]
        if itemcnt >= MAX_ITEMS:
            addDir('Weiter >>', next_url, 1, '', True)
        else:
            INDEX(next_url)

def SEARCH(url):
    # Handle search functionality
    keyboard = xbmc.Keyboard('', 'Suche')
    keyboard.doModal()
    
    if keyboard.isConfirmed() and keyboard.getText():
        search_string = urllib.parse.quote(keyboard.getText())
        INDEX(url + search_string)

def normalized_title(value):
    value = html.unescape(re.sub(r'\[[^\]]*\]', '', value or ''))
    value = value.casefold().replace('ä', 'a').replace('ö', 'o').replace('ü', 'u')
    value = ''.join(c for c in unicodedata.normalize('NFKD', value)
                    if not unicodedata.combining(c))
    return ''.join(c for c in value if c.isalnum())

def foreign_release(title, url='', query=''):
    if re.search(r'\b(?:english|englisch)\b', query, re.I):
        return False
    title = html.unescape(title or '').strip()
    slug = urllib.parse.urlparse(url or '').path.rstrip('/').rsplit('/', 1)[-1]
    return bool(re.search(r'(?:[\s\-*([:])(?:english|englisch|ov|omu)[\s\]*)]*$', title, re.I)
                or re.search(r'-(?:english|englisch|ov|omu)$', slug, re.I))


def title_match_score(query, title):
    if normalized_title(query) == normalized_title(title):
        return 100
    parts = re.split(r'\s*[-–—:]\s*', query, maxsplit=1)
    if len(parts) == 2 and parts[0] and parts[1]:
        numbered = re.sub(r'^(%s)\s+\d+\s*[-–—:]\s*' % re.escape(parts[0]),
                          r'\1: ', title, flags=re.I)
        if numbered != title and normalized_title(numbered) == normalized_title(query):
            return 90
    return 0

def TMDBSEARCH(params):
    query = urllib.parse.unquote_plus(params.get('query', ''))
    season = urllib.parse.unquote_plus(params.get('season', ''))
    episode = urllib.parse.unquote_plus(params.get('episode', ''))
    variants = [query, re.sub(r'[^\w\s]', ' ', query)]
    prefix = re.split(r'\s*[-–—:]\s*', query, maxsplit=1)[0]
    if prefix != query:
        variants.append(prefix)
    words = query.split()
    if len(words) > 1:
        variants.append(' '.join(words[:2]))
        variants.append(words[0])
    found, seen = [], set()
    for term in dict.fromkeys(' '.join(v.split()) for v in variants if v.strip()):
        data = getUrl(BASE_URL + '/search/title/' + urllib.parse.quote(term, safe=''))
        if not data:
            xbmc.log('[FilmPalast] TMDb search: no response for ' + term, xbmc.LOGINFO)
            continue
        sections = re.findall(PATTERNS['content_entries'], data, re.S | re.I) or [data]
        for section in sections:
            for rating, url, title, image in re.findall(PATTERNS['movie_data'], section, re.S | re.I):
                url = normalize_url(url)
                if url not in seen:
                    seen.add(url)
                    found.append((html.unescape(title), url, normalize_url(image)))
        xbmc.log('[FilmPalast] TMDb search: %s -> %d entries' % (term, len(found)), xbmc.LOGINFO)
        if any(title_match_score(query, item[0]) and not foreign_release(item[0], item[1], query) for item in found):
            break
    exact = [item for item in found if title_match_score(query, item[0]) and not foreign_release(item[0], item[1], query)]
    # A series-name match alone cannot identify the requested episode.
    if not season and not episode and len(exact) == 1:
        found = exact
        xbmc.log('[FilmPalast] Unique normalized title match', xbmc.LOGINFO)
    if not found:
        keyboard = xbmc.Keyboard(query, 'Filmpalast: Suchbegriff anpassen')
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            INDEX(BASE_URL + '/search/title/' + urllib.parse.quote(keyboard.getText(), safe=''))
        return
    found.sort(key=lambda item: (foreign_release(item[0], item[1], query), -title_match_score(query, item[0])))
    if len(found) == 1 and foreign_release(found[0][0], found[0][1], query):
        if not xbmcgui.Dialog().yesno('FilmPalast: Sprachversion', 'Nur eine als fremdsprachig markierte Version gefunden. Diese auswählen?'):
            return
    for title, url, image in found:
        addLink(title, url, 10, image)

def clean(text):
    # Clean HTML entities from text
    matches = re.findall(PATTERNS['html_entities'], text)
    for hit in set(matches):
        try:
            text = text.replace(hit, chr(int(hit[2:-1])))
        except ValueError:
            pass
    return urllib.parse.unquote_plus(text)

def selectVideoDialog(videos, url, data=None):
    # Show dialog to select video source
    titles = [name for name, src in videos]
    infostring = ""
    
    if config['show_movie_info']:
        info = getInfos(url, data)
        infostring = "FP: {}/10 Imdb: {}/10 Jahr: {}\nDauer: {} Genre: {}".format(
            info['fp'], info['imdb'], info['year'], info['runtime'], info['genres']
        )
    
    idx = xbmcgui.Dialog().select(infostring, titles)
    return videos[idx][1] if idx > -1 else False

def getInfos(url, data=None):
    # Extract movie information from page or cache
    info = {
        'fp': '0', 'imdb': '0', 'genres': '', 'actors': '', 
        'year': '', 'runtime': '', 'description': ''
    }
    
    # Check cache
    if config['caching']:
        cached_info = get_cached_info(url)
        if cached_info:
            return cached_info
    
    # Get data if not provided
    if data is None:
        data = getUrl(url)
    
    if not data:
        return info
    
    # Extract information using regex patterns
    extract_ratings(data, info)
    extract_year_runtime(data, info)
    extract_description(data, info)
    extract_genres_actors(data, info)
    
    # Cache the result
    if config['caching']:
        cache_info(url, info)
    
    return info

def get_cached_info(url):
    # Get cached movie info if available
    cache_file = get_cache_filename(url)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return eval(f.read())
        except Exception:
            pass
    return None

def cache_info(url, info):
    # Cache movie info to file
    cache_file = get_cache_filename(url)
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(str(info))
    except Exception:
        pass

def get_cache_filename(url):
    # Generate cache filename for URL
    md5hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    return os.path.join(temp_dir, md5hash)

def extract_ratings(data, info):
    # Extract IMDB and FP ratings
    imdb_match = re.search(PATTERNS['imdb_rating'], data, re.S | re.I)
    if imdb_match:
        info['imdb'] = imdb_match.group(1)
    
    fp_match = re.search(PATTERNS['fp_rating'], data, re.S | re.I)
    if fp_match:
        info['fp'] = fp_match.group(1)

def extract_year_runtime(data, info):
    # Extract year and runtime information
    match = re.search(PATTERNS['year_runtime'], data, re.S | re.I)
    if match:
        info['year'] = match.group(1).replace('false', '')
        info['runtime'] = match.group(2)

def extract_description(data, info):
    # Extract movie description
    match = re.search(PATTERNS['description'], data, re.S | re.I)
    if match:
        info['description'] = match.group(1)

def extract_genres_actors(data, info):
    # Extract genres and actors
    genres = re.findall(PATTERNS['genres'], data, re.S | re.I | re.DOTALL)
    info['genres'] = " / ".join(genres)
    
    actors = re.findall(PATTERNS['actors'], data, re.S | re.I | re.DOTALL)
    info['actors'] = " / ".join(actors)

def _decodeVoePayload(encoded, replacements):
    tokens = [re.escape(token) for token in replacements[2:-2].split("','")]
    text = ''
    for char in encoded:
        value = ord(char)
        if 64 < value < 91:
            value = (value - 52) % 26 + 65
        elif 96 < value < 123:
            value = (value - 84) % 26 + 97
        text += chr(value)
    for token in tokens:
        text = re.sub(token, '', text)
    step = base64.b64decode(text).decode('utf-8', errors='replace')
    step = ''.join(chr(ord(char) - 3) for char in step)
    return json.loads(base64.b64decode(step[::-1]).decode('utf-8', errors='replace'))


def _resolveVoeDirect(url, item):
    try:
        if 'voe' not in str(item.get('source', '')).lower() and 'voe' not in urlparse(str(url).split('|', 1)[0]).netloc.lower():
            return None

        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        page_url = str(url).split('|', 1)[0]
        response = requests.get(page_url, headers=headers, timeout=12, allow_redirects=True)
        html = response.text or ''
        real_url = response.url

        for _ in range(3):
            redirect = re.search(r"window\.location\.href\s*=\s*'([^']+)'", html)
            if not redirect:
                break
            page_url = urljoin(real_url, html_unescape(redirect.group(1)))
            response = requests.get(page_url, headers=headers, timeout=12, allow_redirects=True)
            html = response.text or ''
            real_url = response.url

        packed = re.search(r'json">\["([^"]+)"\]</script>\s*<script\s+src="([^"]+)', html)
        if not packed:
            return None

        script_url = urljoin(real_url, html_unescape(packed.group(2)))
        script = requests.get(script_url, headers=headers, timeout=12).text or ''
        repl = re.search(r"(\[(?:'\W{2}'[,\]]){1,9})", script)
        if not repl:
            return None

        data = _decodeVoePayload(packed.group(1), repl.group(1))
        media_url = data.get('direct_access_url') or data.get('source') or data.get('file')
        if not media_url:
            return None

        stream_headers = urlencode({
            'User-Agent': headers['User-Agent'],
            'Referer': real_url,
        })
        xbmc.log('[FilmPalast] VOE direct field: ' + ('direct_access_url' if data.get('direct_access_url') else 'source/file'), xbmc.LOGINFO)
        return '%s|%s' % (media_url, stream_headers)
    except Exception as e:
        xbmc.log('[FilmPalast] VOE direct failed: ' + str(e), xbmc.LOGWARNING)
        return None


def resolveUrl(media_url, validate_only=False):
    # Resolve media URL using available resolver
    try:
        try:
            import resolveurl as resolver
        except ImportError:
            import urlresolver as resolver
        
        if media_url:
            if validate_only:
                return resolver.HostedMediaFile(media_url).valid_url()
            return resolver.resolve(media_url)
    except Exception as e:
        if DEBUG:
            print("Resolve error:", e)
    return False

def PLAYVIDEO(url):
    # Play video from selected URL
    data = getUrl(url)
    if not data:
        return
    
    # Find available video sources
    videos = get_video_sources(data)
    
    if not videos:
        xbmc.executebuiltin("XBMC.Notification(Fehler!, Video nicht gefunden, 4000)")
        return
    
    from auto_hoster import check_sources, manual_choices
    automatic = config.get('auto_hoster', False)
    progress = xbmcgui.DialogProgress()
    progress.create('FilmPalast: Hosterprüfung', 'Quellen werden geprüft …')
    def report(checked, total, working):
        progress.update(int(checked * 100 / max(total, 1)),
                        '{} von {} geprüft · {} erreichbar'.format(checked, total, working))
        return not progress.iscanceled() and not xbmc.Monitor().abortRequested()
    def resolve_source(name, source):
        return _resolveVoeDirect(source, {'source': name}) or resolveUrl(source)
    try:
        results = check_sources(videos, resolve_source, report)
    finally:
        progress.close()
    if results is None:
        xbmcplugin.setResolvedUrl(pluginhandle, False, xbmcgui.ListItem())
        return
    if automatic and results:
        selected = results[0]
        height = '{}p'.format(selected['height']) if selected['height'] else 'Auflösung unbekannt'
        xbmcgui.Dialog().notification('FilmPalast: Auto-Hoster',
            '{} | {} | {} | ca. {:.1f} Mbit/s'.format(selected['hoster'], selected['format'],
                height, selected['speed'] * 8 / 1000000), time=4000)
        xbmc.log('[FilmPalast] Auto-Hoster selected: {} / {} / {:.1f} Mbit/s'.format(
            selected['hoster'], selected['format'], selected['speed'] * 8 / 1000000), xbmc.LOGINFO)
        play_resolved_video(selected['stream'], already_resolved=True)
        return
    choices = manual_choices(videos, results)
    index = xbmcgui.Dialog().select('FilmPalast: Hoster wählen', [item['label'] for item in choices])
    if index < 0:
        xbmcplugin.setResolvedUrl(pluginhandle, False, xbmcgui.ListItem())
        return
    selected = choices[index]
    xbmc.log('[FilmPalast] Manual hoster selected: {} / probe={}'.format(
        selected['hoster'], 'confirmed' if selected['resolved'] else 'unconfirmed'), xbmc.LOGINFO)
    play_resolved_video(selected['url'], already_resolved=selected['resolved'])

def get_video_sources(data):
    # Extract video sources from page data
    videos = []
    video_matches = re.findall(PATTERNS['video_sources'], data, re.S | re.I | re.DOTALL)
    
    for hoster, media_url in video_matches:
        if config['filter_unknown_hoster'] and not resolveUrl(media_url, True):
            continue
        videos.append((hoster, media_url))
    
    return videos

def select_video_source(videos, url, data):
    # Select video source (single or via dialog)
    if len(videos) == 1:
        return videos[0][1]
    return selectVideoDialog(videos, url, data)

def apply_playback_metadata(listitem, params):
    def value(key):
        raw = params.get(key, '')
        decoded = urllib.parse.unquote_plus(str(raw))
        return '' if decoded in ('', 'None', 'null') else decoded
    media_type = value('mediatype')
    if media_type not in ('movie', 'episode'):
        return
    info = {'mediatype': media_type}
    for key in ('title', 'tvshowtitle'):
        if value(key):
            info[key] = value(key)
    for key in ('year', 'season', 'episode'):
        if value(key).isdigit():
            info[key] = int(value(key))
    listitem.setInfo('video', info)
    if info.get('title'):
        listitem.setLabel(info['title'])
    tag = listitem.getVideoInfoTag()
    tag.setMediaType(media_type)
    if info.get('title'):
        tag.setTitle(info['title'])
    if info.get('tvshowtitle'):
        tag.setTvShowTitle(info['tvshowtitle'])
    if 'year' in info:
        tag.setYear(info['year'])
    ids = {key: value(key) for key in ('tmdb', 'imdb') if value(key)}
    if ids:
        tag.setUniqueIDs(ids, 'imdb' if 'imdb' in ids else 'tmdb')
    if 'imdb' in ids:
        tag.setIMDBNumber(ids['imdb'])
    listitem.setProperty('IsPlayable', 'true')
    if media_type == 'episode':
        if 'season' in info:
            tag.setSeason(info['season'])
        if 'episode' in info:
            tag.setEpisode(info['episode'])
    xbmc.log('[FilmPalast] Playback metadata: type={} IDs={} season={} episode={}'.format(
        media_type, ','.join(sorted(ids)), info.get('season', '-'), info.get('episode', '-')), xbmc.LOGINFO)
    xbmc.log('[FilmPalast] Final video tag: type={} title={} year={} imdb={} season={} episode={}'.format(
        tag.getMediaType(), tag.getTitle(), tag.getYear(), tag.getIMDBNumber(),
        tag.getSeason(), tag.getEpisode()), xbmc.LOGINFO)

def prepare_trakt_ids(params):
    def value(key):
        decoded = urllib.parse.unquote_plus(str(params.get(key, '')))
        return '' if decoded in ('', 'None', 'null') else decoded
    media_type = value('mediatype')
    keys = {'imdb': 'imdb', 'tmdb': 'tmdb'} if media_type == 'movie' else (
        {'imdb': 'showimdb', 'tmdb': 'showtmdb'} if media_type == 'episode' else {})
    ids = {}
    for provider, key in keys.items():
        identity = value(key)
        if provider == 'imdb' and re.fullmatch(r'tt\d+', identity):
            ids[provider] = identity
        elif provider == 'tmdb' and identity.isdigit() and int(identity) > 0:
            ids[provider] = int(identity)
    if not ids:
        return
    home = xbmcgui.Window(10000)
    owner = uuid.uuid4().hex
    payload = json.dumps(ids, sort_keys=True)
    home.setProperty('filmpalast.trakt.owner', owner)
    home.setProperty('filmpalast.trakt.payload', payload)
    home.setProperty('filmpalast.trakt.title', value('title'))
    home.setProperty('script.trakt.ids', payload)
    script = os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'trakt_bridge.py')
    xbmc.executebuiltin('RunScript("{}",{})'.format(script, owner))
    xbmc.log('[FilmPalast] Trakt bridge: {} IDs supplied ({})'.format(media_type, ','.join(sorted(ids))), xbmc.LOGINFO)

def play_resolved_video(url, already_resolved=False):
    # Resolve and play the video URL
    stream_url = url if already_resolved else (_resolveVoeDirect(url, {'source': urlparse(str(url)).netloc}) or resolveUrl(url))
    if stream_url:
        if DEBUG:
            print('Opening stream:', stream_url)
        media_path = stream_url.split('|', 1)[0].lower().split('?', 1)[0]
        stream_type = 'MP4' if media_path.endswith('.mp4') else ('HLS' if media_path.endswith('.m3u8') else 'unknown')
        xbmc.log('[FilmPalast] Playback stream type: ' + stream_type, xbmc.LOGINFO)
        from buffered_playback import prepare
        stream_url, buffered = prepare(stream_url)
        listitem = xbmcgui.ListItem(path=stream_url)
        if buffered is not None:
            listitem.setMimeType('application/vnd.apple.mpegurl')
            listitem.setContentLookup(False)
        if stream_type == 'MP4':
            listitem.setMimeType('video/mp4')
            listitem.setContentLookup(False)
        try:
            metadata = get_params()
            apply_playback_metadata(listitem, metadata)
            art = {key: urllib.parse.unquote_plus(metadata[key])
                   for key in ('poster', 'fanart', 'thumb') if metadata.get(key) and metadata[key] not in ('None', 'null')}
            if art:
                art.setdefault('thumb', art.get('poster', ''))
                art.setdefault('icon', art.get('poster', art.get('thumb', '')))
                listitem.setArt(art)
            prepare_trakt_ids(metadata)
            result = xbmcplugin.setResolvedUrl(pluginhandle, True, listitem)
            if buffered is not None:
                buffered.wait()
            return result
        finally:
            if buffered is not None:
                buffered.close()
    raise Exception("Could not resolve stream URL")

def getUrl(url):
    # Fetch URL content with proper headers
    try:
        if config['bypass_dns_lock']:
            return urllib3p.get_request(url, userAgent=USER_AGENT)
        
        req = urllib.request.Request(url)
        req.add_header('User-Agent', USER_AGENT)
        req.add_header('Referer', url)
        
        response = urllib.request.urlopen(req, timeout=30)
        data = response.read().decode('utf-8', errors='ignore')
        response.close()
        return data
    except Exception as e:
        if DEBUG:
            print("Error fetching URL:", e)
        return None

def get_params():
    # Parse URL parameters
    if len(sys.argv) < 3:
        return {}
    
    paramstring = sys.argv[2]
    if len(paramstring) < 2:
        return {}
    
    params = {}
    cleanedparams = paramstring.replace('?', '')
    
    if cleanedparams.endswith('/'):
        cleanedparams = cleanedparams[:-1]
    
    for pair in cleanedparams.split('&'):
        if '=' in pair:
            key, value = pair.split('=', 1)
            params[key] = value
    
    return params

def addLink(name, url, mode, image, description=""):
    # Add playable link to directory
    # Handle image caching
    if image and config['bypass_dns_lock']:
        cache_image(image)
        image = get_image_cache_path(image)
    
    u = "{}?url={}&mode={}".format(
        sys.argv[0], 
        urllib.parse.quote_plus(url), 
        str(mode)
    )
    
    if mode == 30:
        u += '&title=' + urllib.parse.quote_plus(name)
    liz = xbmcgui.ListItem(name)
    metadata = get_params()
    for key in ('poster', 'fanart', 'thumb', 'mediatype', 'title', 'tvshowtitle', 'year', 'season', 'episode', 'tmdb', 'imdb', 'showtmdb', 'showimdb'):
        if metadata.get(key) and metadata[key] not in ('None', 'null'):
            u += '&' + key + '=' + metadata[key]
    liz.setArt({'icon': 'DefaultVideo.png', 'thumb': image})
    liz.setInfo(type="Video", infoLabels={"Title": name, "plot": description})
    liz.setProperty('IsPlayable', 'false' if mode == 30 else 'true')
    
    return xbmcplugin.addDirectoryItem(
        handle=int(sys.argv[1]), 
        url=u, 
        listitem=liz,
        isFolder=(mode == 30)
    )

def addDir(name, url, mode, image, is_folder=False):
    # Add directory to listing
    u = "{}?url={}&mode={}".format(
        sys.argv[0], 
        urllib.parse.quote_plus(url), 
        str(mode)
    )
    
    liz = xbmcgui.ListItem(name)
    liz.setArt({'icon': 'DefaultFolder.png', 'thumb': image})
    liz.setInfo(type="Video", infoLabels={"Title": name})
    
    return xbmcplugin.addDirectoryItem(
        handle=int(sys.argv[1]), 
        url=u, 
        listitem=liz, 
        isFolder=is_folder
    )

def cache_image(image_url):
    # Cache image if needed
    cache_path = get_image_cache_path(image_url)
    try:
        if os.path.exists(cache_path) and os.stat(cache_path).st_size > 0 and config['caching']:
            return
        
        if config['bypass_dns_lock']:
            urllib3p.get_request(image_url, path=cache_path, userAgent=USER_AGENT)
    except Exception:
        pass

def get_image_cache_path(image_url):
    # Get cache path for image
    md5hash = hashlib.md5(image_url.encode('utf-8')).hexdigest()
    extension = image_url[-4:] if len(image_url) >= 4 else ''
    return os.path.join(temp_dir, md5hash + extension)

# Main execution
def main():
    # Main plugin execution
    ensure_temp_dir()
    
    params = get_params()
    url = urllib.parse.unquote_plus(params.get("url", ""))
    mode = int(params.get("mode", "0")) if params.get("mode") else None
    
    try:
        if mode is None or not url:
            START()
        elif mode == 1:
            INDEX(url)
        elif mode == 2:
            CATEGORIES(url)
        elif mode == 3:
            ALPHA()
        elif mode == 4:
            SEARCH(url)
        elif mode == 20:
            TMDBSEARCH(params)
        elif mode == 30:
            from tmdb_native import open_tmdb_info
            open_tmdb_info(url, params)
        elif mode == 31:
            from tmdb_native import native_direct_url
            exact_page = native_direct_url(params)
            if exact_page:
                PLAYVIDEO(exact_page)
            else:
                xbmc.log('[FilmPalast TMDb Native] Missing or expired film scope', xbmc.LOGWARNING)
                xbmcplugin.setResolvedUrl(pluginhandle, False, xbmcgui.ListItem())
        elif mode == 10:
            PLAYVIDEO(url)
        
        xbmcplugin.endOfDirectory(pluginhandle)
    
    except Exception as e:
        if DEBUG:
            print("Plugin error:", e)
        xbmcplugin.endOfDirectory(pluginhandle, succeeded=False)

if __name__ == "__main__":
    main()
