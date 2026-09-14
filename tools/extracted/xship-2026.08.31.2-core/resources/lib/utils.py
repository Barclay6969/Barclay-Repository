

# edit 2026-02-25

# Sammelsurium

import json, os, re
import unicodedata
import requests
import xbmcvfs
from xbmc import sleep
from resources.lib.control import urlparse, showparentdiritems, currentWindowId, getInfoLabel, getSetting, urlretrieve, quote_plus, progressDialog, bold
from six.moves import urllib_error, urllib_request, urllib_parse
from operator import itemgetter
from functools import cmp_to_key
from resources.lib import log_utils


class ResolvedUrl(str):
    """str-Subklasse: traegt die stabile Hoster-URL als Attribut.
    sourcecacheDB cached die hoster_url (stabil, wochenlang gueltig),
    nicht die aufgeloeste CDN-URL (verfaellt nach Stunden)."""
    def __new__(cls, resolved_url, hoster_url=None):
        obj = str.__new__(cls, resolved_url)
        obj.hoster_url = hoster_url
        return obj


def getHostDict():
    hostblockDict = ['supervideo.cc', 'flashx', 'streamlare', 'evoload', 'drop.download']  # permanenter Block
    blockedHoster = getSetting('hosts.filter').split(',')  # aus setting.xml blockieren
    if len(blockedHoster) <= 1: blockedHoster = getSetting('hosts.filter').split()
    for i in blockedHoster: hostblockDict.append(i.lower())
    return  hostblockDict

def isBlockedHoster(url, isResolve=True):
    import html
    import resolveurl as resolver
    from resources.lib import log_utils

    requests.packages.urllib3.disable_warnings()
    from resources.lib.requestHandler import cRequestHandler
    if url.startswith("//"): url = 'http:%s' % url

    # HEAD-Request + Redirect-Follow nur im isResolve=True-Pfad. Bei reinem
    # Registry-Check (isResolve=False) wuerde der HEAD pro URL bis zu 3s
    # kosten -- bei Scrapern mit vielen Streams (z.B. xcine: 914 pro Film)
    # waere das katastrophal langsam. Reachability wird sowieso spaeter im
    # BG-Probe getestet, daher hier ueberfluessig.
    if isResolve and urlparse(url).hostname and urlparse(url).scheme:
        UA = cRequestHandler.RandomUA()
        headers = {
            "referer": urlparse(url).scheme + '://' + urlparse(url).hostname + '/',
            "user-agent": UA,
        }
        try:
            r = requests.head(url, verify=False, headers=headers, timeout=3)
        except:
            sDomain = urlparse(url).path if urlparse(url).hostname == None else urlparse(url).hostname
            return True, sDomain, url, 100
        status_code = r.status_code
        if 300 <= status_code <= 400:
            url = r.headers['Location']

        ## TODO moflix, fileions etc 404
        # elif status_code != 200:
        #     sDomain = urlparse(url).path if urlparse(url).hostname == None else urlparse(url).hostname
        #     return True, sDomain, url, 100

    sDomain = urlparse(url).path if urlparse(url).hostname == None else urlparse(url).hostname
    hostblockDict = getHostDict()
    prioHoster = 100
    # Token-Boundary-Match: blocke nur, wenn der Block-Eintrag eine echte
    # Domain-Komponente ist. Verhindert dass z.B. "drop.download" auch
    # "m1xdrop.click" oder "mixdrop.co" fälschlich blockt (Substring "drop"
    # in m1xdrop). Match akzeptiert: exakte Domain, Subdomain, oder
    # Vollqualifizierter Suffix.
    sl = sDomain.lower()
    for i in hostblockDict:
        il = i.lower().strip()
        if not il:
            continue
        if sl == il or sl.startswith(il + '.') or ('.' + il) in sl:
            return True, sDomain, url, prioHoster
    if isResolve:
        try:
            url = html.unescape(url)  # https://github.com/Gujal00/ResolveURL/pull/1115
            hmf = resolver.HostedMediaFile(url=url, include_disabled=True, include_universal=False)
            if hmf.valid_url():
                try:
                    if hmf._HostedMediaFile__resolvers[0].isPopup():
                        prioHoster = hmf._HostedMediaFile__resolvers[0].priority
                        return False, sDomain, url, max(prioHoster, 999)
                except:
                    pass
                hoster_url = url  # Stabile Hoster-URL VOR resolve (fuer Cache)
                # pick_source patchen: auto_pick erzwingen damit kein Dialog aufpoppt
                # (Scraper rufen isBlockedHoster waehrend Precache/BG-Probe)
                from resolveurl.lib import helpers as rurl_helpers
                _orig_pick = rurl_helpers.pick_source
                rurl_helpers.pick_source = lambda sources, auto_pick=None: _orig_pick(sources, auto_pick=True)
                try:
                    sUrl = hmf.resolve()
                finally:
                    rurl_helpers.pick_source = _orig_pick
                try:
                    prioHoster = hmf._HostedMediaFile__resolvers[0].priority
                except:
                    pass
                return False, sDomain, ResolvedUrl(sUrl, hoster_url=hoster_url), prioHoster
            else:
                log_utils.log('In resolveUrl keine Domain für Url %s' % url, log_utils.LOGWARNING)
                return True, sDomain, url, prioHoster
        except:
            return True, sDomain, url, prioHoster
    else:
        # Reiner Registry-Check, kein voll-resolve -- daher auch keine
        # Captcha/Cloudflare-Probleme im Background-Thread. Für den Scrape-
        # Pfad ausreichend: der echte Resolve passiert später im BG-Probe
        # oder beim User-Klick durch resolveurl.HostedMediaFile.
        status = resolver.relevant_resolvers(domain=sDomain)
        if status:
            prioHoster = status[0].priority
            return False, sDomain, url, prioHoster
        # Kein Standard-Resolver -- prüfen ob ein Popup-Resolver (Captcha-
        # oder Pairing-Host wie uptobox-free) zuständig wäre. Solche Hoster
        # nicht hart blockieren, sondern mit prio 999 ans Listen-Ende sortieren.
        popup_status = resolver.relevant_resolvers(domain=sDomain, include_popups=True)
        if popup_status:
            try:
                base_prio = popup_status[0].priority
            except AttributeError:
                base_prio = 100
            return False, sDomain, url, max(base_prio, 999)
        return True, sDomain, url, prioHoster

    # elif checkResolver:   # Überprüfung in resolveUrl
    #     if resolver.relevant_resolvers(domain=sDomain) == []: # sDomain nicht in resolveUrl gefunden
    #         log_utils.log('In resolveUrl keine Domain für Url %s' % url, log_utils.LOGWARNING)
    #         return True, sDomain, prioHoster
    # return False, sDomain, prioHoster



def isBlockedHosterFast(url, isResolve=True):
    """Blocklist + ResolveURL check.

    Optimization 2026-08-20:
    ResolveURL's registry is checked before doing any network HEAD request.
    A HEAD request (up to 3s) is now only used as a compatibility fallback
    when the original host is not known to ResolveURL and may redirect to a
    supported host. This preserves the old redirect behavior but removes one
    unnecessary network roundtrip for the common case.
    """
    import html
    import resolveurl as resolver
    from resources.lib import log_utils

    requests.packages.urllib3.disable_warnings()
    from resources.lib.requestHandler import cRequestHandler
    try:
        from urllib.parse import urljoin as _urljoin
    except ImportError:
        from urlparse import urljoin as _urljoin

    if url.startswith("//"):
        url = 'http:%s' % url

    hostblockDict = getHostDict()
    prioHoster = 100

    def _domain(candidate):
        parsed = urlparse(candidate)
        return parsed.path if parsed.hostname is None else parsed.hostname

    def _is_blocked_domain(domain):
        sl = str(domain or '').lower()
        for entry in hostblockDict:
            il = str(entry or '').lower().strip()
            if not il:
                continue
            if sl == il or sl.startswith(il + '.') or ('.' + il) in sl:
                return True
        return False

    def _resolve_candidate(candidate):
        """Return the normal isBlockedHoster tuple or None if no resolver matches."""
        domain = _domain(candidate)
        try:
            candidate = html.unescape(candidate)
            hmf = resolver.HostedMediaFile(
                url=candidate,
                include_disabled=True,
                include_universal=False
            )
            if not hmf.valid_url():
                return None

            local_prio = 100
            try:
                if hmf._HostedMediaFile__resolvers[0].isPopup():
                    local_prio = hmf._HostedMediaFile__resolvers[0].priority
                    return False, domain, candidate, max(local_prio, 999)
            except Exception:
                pass

            hoster_url = candidate
            # Force auto-pick so scraper/background resolution never opens a
            # source-choice dialog. Preserve the tested legacy behavior.
            from resolveurl.lib import helpers as rurl_helpers
            _orig_pick = rurl_helpers.pick_source
            rurl_helpers.pick_source = lambda sources, auto_pick=None: _orig_pick(sources, auto_pick=True)
            try:
                resolved_url = hmf.resolve()
            finally:
                rurl_helpers.pick_source = _orig_pick

            try:
                local_prio = hmf._HostedMediaFile__resolvers[0].priority
            except Exception:
                pass

            if not resolved_url:
                return True, domain, candidate, local_prio
            return False, domain, ResolvedUrl(resolved_url, hoster_url=hoster_url), local_prio
        except Exception:
            return None

    sDomain = _domain(url)
    if _is_blocked_domain(sDomain):
        return True, sDomain, url, prioHoster

    if not isResolve:
        # Registry-only check: no network request and no full resolve.
        status = resolver.relevant_resolvers(domain=sDomain)
        if status:
            try:
                prioHoster = status[0].priority
            except Exception:
                pass
            return False, sDomain, url, prioHoster

        popup_status = resolver.relevant_resolvers(domain=sDomain, include_popups=True)
        if popup_status:
            try:
                base_prio = popup_status[0].priority
            except Exception:
                base_prio = 100
            return False, sDomain, url, max(base_prio, 999)
        return True, sDomain, url, prioHoster

    # Fast path: supported hosters can be resolved immediately. This avoids
    # the old unconditional HEAD request for every source.
    result = _resolve_candidate(url)
    if result is not None:
        return result

    # Compatibility fallback: unknown URLs may redirect to a supported host.
    # Only those URLs pay the HEAD cost.
    parsed = urlparse(url)
    if parsed.hostname and parsed.scheme:
        UA = cRequestHandler.RandomUA()
        headers = {
            'referer': parsed.scheme + '://' + parsed.hostname + '/',
            'user-agent': UA,
        }
        try:
            r = requests.head(url, verify=False, headers=headers, timeout=3, allow_redirects=False)
            if 300 <= r.status_code < 400 and r.headers.get('Location'):
                redirected = _urljoin(url, r.headers.get('Location'))
                redirected_domain = _domain(redirected)
                if _is_blocked_domain(redirected_domain):
                    return True, redirected_domain, redirected, prioHoster
                result = _resolve_candidate(redirected)
                if result is not None:
                    return result
        except Exception:
            pass

    log_utils.log('In resolveUrl keine Domain für Url %s' % url, log_utils.LOGWARNING)
    return True, sDomain, url, prioHoster



def cmp(x, y):
    """
    Replacement for built-in function cmp that was removed in Python 3

    Compare the two objects x and y and return an integer according to
    the outcome. The return value is negative if x < y, zero if x == y
    and strictly positive if x > y.

    https://portingguide.readthedocs.io/en/latest/comparisons.html#the-cmp-function
    """

    return (x > y) - (x < y)

def multikeysort(items, columns):
    # a = multikeysort(b, ['-column1', 'column2']) # - revers / b z.B. self.list
    comparers = [
        ((itemgetter(col[1:].strip()), -1) if col.startswith('-') else (itemgetter(col.strip()), 1))
        for col in columns
    ]
    def comparer(left, right):
        comparer_iter = (
            cmp(fn(left), fn(right)) * mult
            for fn, mult in comparers
        )
        return next((result for result in comparer_iter if result), 0)
    return sorted(items, key=cmp_to_key(comparer))


def get_titles(title, originaltitle, imdb, content_typ):
    aliases, localtitle = getAliases(imdb, content_typ)
    if localtitle and title != localtitle and originaltitle != localtitle:
        if not title in aliases: aliases.append(title)
        title = localtitle
    titles_temp = get_titles_for_search(title, originaltitle, set(aliases))
    titles = [title for title in titles_temp if cjk_detect(title)==False]
    return titles


def getExtIDS(imdb, type): # get external IDS
    # V2_API_KEY = getSetting('api.trakt').strip()
    # e:\__DEV-19\devkodi\addons\metadata.themoviedb.org.python\python\lib\tmdbscraper\
    V2_API_KEY = '5f2dc73b6b11c2ac212f5d8b4ec8f3dc4b727bb3f026cd254d89eda997fe64ae' # 4a65e1e644af74c98f9f2b3884669deb3fac9531ee71f39babf1dee46d264d17
    headers = {'Content-Type': 'application/json', 'trakt-api-key': V2_API_KEY, 'trakt-api-version': '2'}
    url = 'https://api.trakt.tv/{0}/{1}/?extended=full'.format(type, imdb)
    result = requests.get(url, headers=headers)
    if result.status_code == 200:
        result = json.loads(result.content)
        return result['ids']
    else:
        return [], ''


def getAliases(imdb, type):
    # V2_API_KEY = getSetting('api.trakt').strip()
    V2_API_KEY = '5f2dc73b6b11c2ac212f5d8b4ec8f3dc4b727bb3f026cd254d89eda997fe64ae'
    headers = {'Content-Type': 'application/json', 'trakt-api-key': V2_API_KEY, 'trakt-api-version': '2'}
    aliasesUrl = 'https://api.trakt.tv/{0}/{1}/aliases'.format(type, imdb)
    result = requests.get(aliasesUrl, headers=headers)
    if result.status_code == 200:
        result = json.loads(result.content)
        localtitle = [i['title'] for i in result if i['country'] in ['de']]
        localtitle = localtitle[0] if any(localtitle) else None
        return [i['title'] for i in result if i['country'] in ['de', 'us', 'en', 'at', '']], localtitle
    else:
        return [], ''


def aliases_to_array(aliases, filter=None):
    try:
        if not filter:
            filter = []
        if isinstance(filter, type(u"")):
            filter = [filter]
        return [x.get('title') for x in aliases if not filter or x.get('country') in filter]
    except:
        return []


def cjk_detect(texts):
    # korean
    if re.search(r"[\uac00-\ud7a3]", texts):
        return True # "ko"
    # japanese
    elif re.search(r"[\u3040-\u30ff]", texts):
        return True # "ja"
    # chinese
    elif re.search(r"[\u4e00-\u9FFF]", texts):
        return True # "zh"
    # thai
    elif re.search(r"[\u0E00-\u0E7F]", texts):
        return True  # "th"
    # arabisch
    elif re.search(r"[\u0600-\u06FF]", texts):
        return True
    # devanagari (hindi), bengali, tamil, telugu, etc.
    elif re.search(r"[\u0900-\u0DFF]", texts):
        return True
    else:
        return False


def getsearch(title):
    if title is None:
        return
    title = title.lower()
    title = re.sub(r'&#(\d+);', '', title)
    title = re.sub(r'(&#[0-9]+)([^;^0-9]+)', r'\\1;\\2', title)
    title = title.replace('&quot;', '\"').replace('&amp;', '&')
  # title = re.sub('\\\|/|-|–|:|;|\*|\?|"|\'|<|>|\|', '', title).lower()
    title = re.sub(r'[\\\\/\\-–:;*?"\'<>|]', '', title).lower()
    title = re.sub(r'\s+', ' ', title)
    return title

def get_titles_for_search(localtitle, title, aliases):
    titles = []
    try:
        if "country':" in str(aliases): aliases = aliases_to_array(aliases)
        if localtitle != '':
            localtitle = localtitle.lower()
            titles.append(localtitle)
            # titles.append(getsearch(localtitle))
        if title != '':
            title = title.lower()
            if localtitle != title:
                titles.append(title)
                # titles.append(getsearch(title))
        for i in aliases:
            try:
                #if str(i).lower() != title and str(i).lower() != localtitle and i != '' :
                if not str(i).lower() in titles:
                    titles.append(str(i).lower())
                # j = getsearch(str(i))
                # if not j.lower() in titles:
                #     titles.append(j)
            except:
                pass
        #titles = [str(i) for i in titles if all(ord(c) < 128 for c in i)]
        titles = [item for i, item in enumerate(titles) if item not in titles[:i]]
        titles = more_titles(titles)


        return titles
    except:
        return titles

#TODO
# def title_article(titles):
#     try:
#         articles_en = ['the']  # ['the', 'a', 'an']
#         articles_de = ['die', 'der']  # ['der', 'die', 'das']
#         for title in titles:
#             match = re.match('^((\w+)\s+)', title.lower())
#             if match and match.group(2) in articles_en:
#                 for i in articles_de:
#                     title = title.replace(title[:3], i)
#                     if title not in titles: titles.append(title)
#         return titles
#     except:
#         return titles


def more_titles(titles):
    for i in titles:
        temp = _titleclean(i)
        if temp and temp not in titles:
            titles.append(temp)
    return titles

def _titleclean(title):
    try:
        if 'IV' == title.rsplit(' ',1)[1]:
            title.replace(' IV', ' 4')
        elif 'VI' == title.rsplit(' ',1)[1]:
            title.replace(' VI', ' 6')
        elif 'V' == title.rsplit(' ',1)[1]:
            title.replace(' V', ' 5')
        elif 'III' == title.rsplit(' ',1)[1]:
            title.replace(' III', ' 3')
        elif 'II' == title.rsplit(' ',1)[1]:
            title.replace(' II', ' 2')
        # elif 'I' == title.rsplit(' ',1)[1]:
        #     title.replace('I', '1')
        elif '2' == title.rsplit(' ',1)[1]:
            title.replace(' 2', ' II')
        elif '3' == title.rsplit(' ',1)[1]:
            title.replace(' 3', ' III')
        elif '4' == title.rsplit(' ',1)[1]:
            title.replace(' 4', ' IV')
        elif '5' == title.rsplit(' ',1)[1]:
            title.replace(' 5', ' V')
        elif '6' == title.rsplit(' ',1)[1]:
            title.replace(' 6', ' VI')
        return title
    except:
        pass


def check_302(url, headers={}):
    try:
        while True:
            host = urlparse(url).netloc
            headers.update({'Host': host})
            r = requests.get(url, allow_redirects=False, headers=headers, timeout=7)
            if 300 <= r.status_code <= 400:
                url = r.headers['Location']
            elif 400 <= r.status_code:
                return
            elif 200 == r.status_code:
                return url
            elif 300 > r.status_code:
                return url
            else:
                break
        return
    except:
        return


def test_stream(stream_url):
    """
    Returns True if the stream_url gets a non-failure http status (i.e. <400) back from the server
    otherwise return False

    Intended to catch stream urls returned by resolvers that would fail to playback
    """
    # parse_qsl doesn't work because it splits elements by ';' which can be in a non-quoted UA
    try:
        headers = dict([item.split('=') for item in (stream_url.split('|')[1]).split('&')])
    except:
        headers = {}
    for header in headers:
        headers[header] = urllib_parse.unquote_plus(headers[header])
    log_utils.log('Setting Headers on UrlOpen: %s' % headers, log_utils.LOGDEBUG)

    import ssl
    try:
        #- streamurl mit ungültigen Zertifikat abweisen
        ssl_context = ssl.create_default_context()
        #ssl_context.check_hostname = False
        #ssl_context.verify_mode = ssl.CERT_NONE
        opener = urllib_request.build_opener(urllib_request.HTTPSHandler(context=ssl_context))
        urllib_request.install_opener(opener)
    except:
        pass

    try:
        msg = ''
        request = urllib_request.Request(stream_url.split('|')[0], headers=headers)
        # only do a HEAD request. gujal
        request.get_method = lambda: 'HEAD'
        #  set urlopen timeout to 15 seconds
        http_code = urllib_request.urlopen(request, timeout=15).getcode()
    except urllib_error.HTTPError as e:
        if isinstance(e, urllib_error.HTTPError):
            http_code = e.code
            if http_code == 405:
                http_code = 200
        else:
            http_code = 600
    except urllib_error.URLError as e:
        http_code = 500
        if hasattr(e, 'reason'):
            # treat an unhandled url type as success
            if 'unknown url type' in str(e.reason).lower():
                return True
            elif 'certificate verify failed' in str(e.reason).lower():
                return True
            else:
                msg = e.reason
        if not msg:
            msg = str(e)

    except Exception as e:
        http_code = 601
        msg = str(e)
        if msg == "''":
            http_code = 504

    # added this log line for now so that we can catch any logs on streams that are rejected due to test_stream failures
    # we can remove it once we are sure this works reliably
    if int(http_code) >= 400 and int(http_code) != 504:
        log_utils.log('Stream UrlOpen Failed: Url: %s \n HTTP Code: %s Msg: %s' % (stream_url, http_code, msg), log_utils.LOGWARNING)

    return int(http_code) < 400 or int(http_code) == 504

#TODO
def m3u8_check(stream_url):
    if not '.m3u8' in (stream_url.split('|')[0]).lower(): return stream_url
    try:
        headers = dict([item.split('=') for item in (stream_url.split('|')[1]).split('&')])
    except:
        headers = {}
    for header in headers:
        headers[header] = urllib_parse.unquote_plus(headers[header])
    req = urllib_request.Request(stream_url.split('|')[0], headers=headers)
    try:
        line = (urllib_request.urlopen(req).readlines())
        if re.search(r'\.m4.', str(line)): return
        # if '.m4s' in str(line):
        #     return
        # elif 'http' in str(line):
        #     return stream_url
        else:
            return stream_url # new_m3u8(req, stream_url.split('|')[0])

    except urllib_error.URLError as e:
        if hasattr(e, 'reason')and 'certificate verify failed' in str(e.reason).lower():
            return stream_url
        return


def normalize(title):
    from sys import version_info
    try:
       if version_info[0] > 2: return title
       else:
        try: return title.decode('ascii').encode("utf-8")
        except: return str(''.join(c for c in unicodedata.normalize('NFKD', unicode(title.decode('utf-8'))) if unicodedata.category(c) != 'Mn'))
    except:
        return title


## setzt Auswahl nach letzte als gesehen markierte Episode / Staffel
def setPosition(pos, _name, content='movies'): # org.: episodes
    isdebug = True if getSetting('status.debug') == 'true' else False
    win = currentWindowId  # win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    pos = int(pos)
    pos_sp = pos if showparentdiritems() else pos - 1
    count = 0

    for count in range(1, 15):
        ccont = getInfoLabel("Container.Content")
        if ccont == content: break
        sleep(100)

    if isdebug:
        log_utils.log(_name + ' - Container.Content (1) - soll: %s ist: %s  count: %s' % (content, getInfoLabel("Container.Content"), count), log_utils.LOGINFO)
        log_utils.log(_name + ' - System.CurrentControlID - old: %s ' % getInfoLabel("System.CurrentControlID"), log_utils.LOGINFO)
        log_utils.log(_name + ' - pos: %s - check: %s' % (pos, int(getInfoLabel("Container().CurrentItem"))), log_utils.LOGINFO)

    # setze Position
    for count in range(1, 15):
        try:
            cid = getInfoLabel("System.CurrentControlID")
            ctrl = win.getControl(int(cid))
        except:
            sleep(200)
            continue

        ctrl.selectItem(pos_sp)
        sleep(100)
        check = int(getInfoLabel("Container().CurrentItem"))  # % cid)) # Container().CurrentItem
        if pos == check: break

    if isdebug:
        log_utils.log(_name + ' - pos: %s - check: %s - count: %s' % (pos, int(getInfoLabel("Container().CurrentItem")),count), log_utils.LOGINFO)
        log_utils.log(_name + ' - System.CurrentControlID:  %s' % getInfoLabel("System.CurrentControlID"), log_utils.LOGINFO)


def getParams(_params):
    for key, value in _params.items():
        try:
            exec("%s = %s" % (key, value))
        except:
            exec ("%s = '%s'" % (key, value))


# Funktionen ab hier auch für xstream
def translatePath(*args):
    from sys import version_info
    if version_info.major == 2:
        from xbmc import translatePath
        return translatePath(*args).decode("utf-8")
    else:
        from xbmcvfs import translatePath
        return translatePath(*args)

def download_url(url, dest, dp=None):
    # download_url(url, src, dp=[None / True / False / Dialog])
    if dp == None or dp == True:
        dp = progressDialog
        dp.create("URL Downloader", " \n  Downloading  File:  %s" % bold(url.split('/')[-1]))
    elif dp == False:
        return urlretrieve(url, dest)
    try:
        dp.update(0)
        urlretrieve(url, dest, lambda nb, bs, fs, url=url: _pbhook(nb, bs, fs, dp))
        dp.close()
    except:
        urlretrieve(url, dest)

def _pbhook(numblocks, blocksize, filesize, dp):
    try:
        percent = min((numblocks * blocksize * 100) / filesize, 100)
        dp.update(int(percent))
    except:
        percent = 100
        dp.update(percent)
    if dp.iscanceled():
        dp.close()
        raise Exception("Canceled")


def unzip_recursive(path, dirs, dest):
    for directory in dirs:
        dirs_dir = os.path.join(path, directory)
        dest_dir = os.path.join(dest, directory)
        xbmcvfs.mkdir(dest_dir)
        dirs2, files = xbmcvfs.listdir(dirs_dir)
        if dirs2:
            unzip_recursive(dirs_dir, dirs2, dest_dir)
        for file in files:
            # unzip_file(os.path.join(dirs_dir, file.decode('utf-8')), os.path.join(dest_dir, file.decode('utf-8')))
            unzip_file(os.path.join(dirs_dir, file), os.path.join(dest_dir, file))

def unzip_file(path, dest):
    ''' Unzip specific file. Path should start with zip:// '''
    xbmcvfs.copy(path, dest)
    #LOG.debug("unzip: %s to %s", path, dest)

def unzip(path, dest, folder=None):
    import zipfile
    try:
        with zipfile.ZipFile(path, 'r') as zip:  zip.extractall(dest)
    except:
        pass

# def unzip(sPath, dest, folder=None):
#     ''' Unzip file. zipfile module seems to fail on android with badziperror.'''
#     path = quote_plus(sPath)
#     root = "zip://" + path + '/'
#
#     if folder:
#         xbmcvfs.mkdir(os.path.join(dest, folder))
#         dest = os.path.join(dest, folder)
#         root = get_zip_directory(root, folder)
#     dirs, files = xbmcvfs.listdir(root)
#     if dirs:
#         unzip_recursive(root, dirs, dest)
#
#     for file in files:
#         unzip_file(os.path.join(root, file), os.path.join(dest, file))
#     #LOG.warn("Unzipped %s", path)


def get_zip_directory(path, folder):
    dirs, files = xbmcvfs.listdir(path)
    if folder in dirs:
        return os.path.join(path, folder)
    for directory in dirs:
        result = get_zip_directory(os.path.join(path, directory), folder)
        if result:
            return result



def remove_dir(folder):
    import os, shutil, stat
    for filename in os.listdir(folder):
        if filename == '.idea': continue
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                if os.path.isfile(file_path): os.chmod(file_path, stat.S_IWRITE)
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))



def countdown(bKill=False):
    from xbmcaddon import Addon
    from xbmcgui import DialogProgress
    from xbmc import executebuiltin, Monitor

    addonInfo = Addon().getAddonInfo
    addonName = addonInfo('name')

    Addon().setSetting('xs_logo', 'true')   # wird noch nicht ausgewertet
    executebuiltin("Dialog.Close(all)")
    executebuiltin("ActivateWindow(Home)")

    seconds = 5
    percentage = 100
    monitor = Monitor()
    pDialog = DialogProgress()
    pDialog.create(addonName + ' Manipulation')
    # while not monitor.abortRequested() and percentage > 0:
    while percentage > 0:
        # percentage -= 20
        # secondsTxt = "seconds" if seconds > 1 else "second"
        # pDialog.update(percentage, f"Kodi wird in {seconds} {secondsTxt} beendet.")
        pDialog.update(percentage, f"{addonName} bzw. Kodi wird in wenigen Sekunden beendet.")
        seconds -= 1
        percentage -= 20
        if monitor.waitForAbort(1): dummy =''
        #if monitor.waitForAbort(1): break
        #if pDialog.iscanceled(): return True
    pDialog.close()

    ## Addon deaktivieren & Kodi beenden
    if not bKill:
        from xbmc import executeJSONRPC
        for addonId in ('plugin.video.xstream', 'plugin.video.xship', 'repository.xstream', 'repository.xship'):
            try:
                # addonInfo = Addon().getAddonInfo
                # addonId = addonInfo('id')  # 'plugin.video.xship'
                executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.SetAddonEnabled","id":1,"params":{"addonid":"%s", "enabled":false}}' % addonId)
            except:
                continue
        # Kodi beenden
        executebuiltin('Quit')
        exit()

def kill():     # Löschfunktion
    countdown(True)
    from os import path
    from xbmc import executebuiltin, executeJSONRPC
    try: from xbmcvfs import translatePath
    except: from xbmc import translatePath

    for addonId in ('plugin.video.xstream', 'plugin.video.xship', 'repository.xstream', 'repository.xship'):
        try:
            addonPath = translatePath('special://home/addons/%s') % addonId
            addonProfilePath = translatePath('special://profile/addon_data/%s') % addonId
            executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.SetAddonEnabled","id":1,"params":{"addonid":"%s", "enabled":false}}' % addonId)
            if path.exists(addonPath): remove_dir(addonPath)
            if path.exists(addonProfilePath): remove_dir(addonProfilePath)
        except:
            pass
    # Kodi beenden
    executebuiltin('Quit')
    exit()

# Todo - soll mal Hilfefunktion werden
def help():
    return 'OK' # Platzhalter

# ## der patch nicht mehr notwendig
# def patchResolver():
#     from os import path
#     search = 'if order_matters'
#     insert = 'for i in relevant: i.priority = i._get_priority()'
#     file = translatePath('special://home/addons/script.module.resolveurl/lib/resolveurl/__init__.py')
#     ln = 0
#     column = 0
#     if path.isfile(file):
#         isEdit = False
#         with open(file) as f:
#             for lineno, line in enumerate(f):
#                 if search in line:
#                         # print("{} {}".format(lineno + 1, line.find(search) + 1))
#                         ln = lineno
#                         column = line.find(search)
#                 elif insert in line:
#                     isEdit = True
#                     break
#
#         if isEdit == False:
#             with open(file, 'r+') as f:
#                 lines = f.readlines()
#                 lines[ln+2] = lines[ln][0:column] + insert + '\n\n'# + lines[ln][column:]
#                 # Delete the file
#                 f.seek(0)
#                 for i in lines:
#                     # Append the lines
#                     f.write(i)
