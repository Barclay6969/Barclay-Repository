from pathlib import Path
import re
import shutil
import subprocess
import zipfile

base = Path('test-builds/plugin.video.xship-2026.08.25.6-MEGAKINO16-TEST.zip')
out = Path('test-builds/plugin.video.xship-2026.08.25.7-EINSCHALTEN-DOOD-TLS-TEST.zip')
work = Path('/tmp/xship-ein')
basework = Path('/tmp/xship-base')
for d in (work, basework):
    if d.exists(): shutil.rmtree(d)
    d.mkdir(parents=True)
with zipfile.ZipFile(base) as z: z.extractall(work)
with zipfile.ZipFile(base) as z: z.extractall(basework)
root = work / 'plugin.video.xship'

matches=[]
for p in root.rglob('einschalten.py'):
    s=p.read_text('utf-8')
    if "SITE_IDENTIFIER = 'einschalten'" in s:
        matches.append(p)
if len(matches) != 1:
    raise SystemExit(f'Expected exactly one Einschalten scraper, found {matches}')
p=matches[0]
s=p.read_text('utf-8')
marker="from scrapers.modules import cleantitle\n"
if marker not in s: raise SystemExit('Import marker missing')
s=s.replace(marker, marker+"from resources.lib import log_utils\n", 1)

old="""                streamUrl = jResult['streamUrl']
                isBlocked, hoster, url, prioHoster = isBlockedHoster(streamUrl)
                if isBlocked: continue
                if url: self.sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': url, 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})
"""
new="""                streamUrl = jResult['streamUrl']

                # Kodi 21 / ResolveURL Dood fallback: use an instance-owned default
                # urllib opener for vide0.net before falling back to ResolveURL.
                url = self._resolve_dood_default_tls(streamUrl)
                if url:
                    self.sources.append({'source': 'DoodStream', 'quality': quality, 'language': 'de', 'url': url, 'direct': True, 'priority': int(self.priority), 'prioHoster': 100})
                    continue

                isBlocked, hoster, url, prioHoster = isBlockedHoster(streamUrl)
                if isBlocked: continue
                if url: self.sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': url, 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})
"""
if old not in s: raise SystemExit('Stream block marker missing')
s=s.replace(old,new,1)

resolve_marker="""    def resolve(self, url):
        return  url
"""
helper='''    def _resolve_dood_default_tls(self, stream_url):
        try:
            import random
            import re
            import string
            import time
            from urllib.parse import quote_plus, urljoin, urlparse
            from urllib.request import Request, build_opener, HTTPHandler, HTTPSHandler
            from urllib.error import HTTPError

            parsed = urlparse(stream_url)
            host = (parsed.hostname or '').lower()
            match_id = re.search(r'/(?:e|d)/([0-9A-Za-z]+)', parsed.path or '')
            if host not in ('vide0.net', 'vvide0.com') or not match_id:
                return None

            media_id = match_id.group(1)
            ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0.0.0 Safari/537.36'
            opener = build_opener(HTTPHandler(), HTTPSHandler())
            candidates = ['https://playmogo.com/e/' + media_id, stream_url]

            for page_url in candidates:
                try:
                    log_utils.log('[EINSCHALTEN-DOOD] Default-TLS page: %s' % page_url, log_utils.LOGINFO)
                    req = Request(page_url, headers={
                        'User-Agent': ua,
                        'Referer': self.base_link + '/',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    })
                    response = opener.open(req, timeout=8)
                    final_url = response.geturl()
                    html = response.read().decode('utf-8', 'replace')
                    status = getattr(response, 'status', 200)
                    log_utils.log('[EINSCHALTEN-DOOD] Page OK: status=%s final=%s bytes=%s' % (status, final_url, len(html)), log_utils.LOGINFO)

                    pattern = r"dsplayer\\.hotkeys[^']+'([^']+).+?function\\s*makePlay.+?return[^?]+([^\\\"]+)"
                    m = re.search(pattern, html, re.DOTALL)
                    if not m:
                        log_utils.log('[EINSCHALTEN-DOOD] pass_md5/token nicht gefunden', log_utils.LOGWARNING)
                        continue

                    pass_url = urljoin(final_url, m.group(1))
                    token = m.group(2)
                    req2 = Request(pass_url, headers={
                        'User-Agent': ua,
                        'Referer': final_url,
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': '*/*',
                    })
                    response2 = opener.open(req2, timeout=8)
                    base = response2.read().decode('utf-8', 'replace').strip()
                    status2 = getattr(response2, 'status', 200)
                    log_utils.log('[EINSCHALTEN-DOOD] pass_md5: status=%s bytes=%s' % (status2, len(base)), log_utils.LOGINFO)
                    if not base.startswith('http'):
                        continue

                    direct = base + ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10)) + token + str(int(time.time() * 1000))
                    headers = 'User-Agent=%s&Referer=%s' % (quote_plus(ua), quote_plus(final_url))
                    log_utils.log('[EINSCHALTEN-DOOD] Direct URL erzeugt: host=%s' % (urlparse(direct).hostname or ''), log_utils.LOGINFO)
                    return direct + '|' + headers
                except HTTPError as exc:
                    try:
                        cf = exc.headers.get('cf-mitigated', '')
                        server = exc.headers.get('server', '')
                    except Exception:
                        cf = ''
                        server = ''
                    log_utils.log('[EINSCHALTEN-DOOD] HTTPError %s | server=%s | cf=%s | %s' % (getattr(exc, 'code', '?'), server, cf, page_url), log_utils.LOGWARNING)
                except Exception as exc:
                    log_utils.log('[EINSCHALTEN-DOOD] Fehler %s: %s' % (type(exc).__name__, exc), log_utils.LOGWARNING)
            return None
        except Exception as exc:
            try:
                log_utils.log('[EINSCHALTEN-DOOD] Setup-Fehler %s: %s' % (type(exc).__name__, exc), log_utils.LOGWARNING)
            except Exception:
                pass
            return None

    def resolve(self, url):
        return  url
'''
if resolve_marker not in s: raise SystemExit('Resolve marker missing')
s=s.replace(resolve_marker, helper, 1)
p.write_text(s,'utf-8')

addon=root/'addon.xml'
a=addon.read_text('utf-8')
a2,n=re.subn(r'(<addon\\b[^>]*?\\bversion=")[^"]+("[^>]*>)',r'\\g<1>2026.08.25.7\\2',a,count=1,flags=re.S)
if n != 1: raise SystemExit('Could not set addon version')
addon.write_text(a2,'utf-8')

# Validate exactly addon.xml + einschalten.py differ from 25.6.
changed=[]
for bp in (basework/'plugin.video.xship').rglob('*'):
    if not bp.is_file(): continue
    rel=bp.relative_to(basework/'plugin.video.xship')
    np=root/rel
    if not np.exists() or bp.read_bytes()!=np.read_bytes(): changed.append(str(rel))
print('CHANGED', sorted(changed))
if len(changed)!=2 or 'addon.xml' not in changed or not any(x.endswith('einschalten.py') for x in changed):
    raise SystemExit('Unexpected changed files: %r' % changed)

mk=list(root.rglob('megakino.py'))
if len(mk)!=1 or "SITE_DOMAIN = 'megakino16.com'" not in mk[0].read_text('utf-8'):
    raise SystemExit('MegaKino16 base was not preserved')

subprocess.check_call(['python3','-m','compileall','-q',str(root)])
if out.exists(): out.unlink()
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for fp in root.rglob('*'):
        if fp.is_file(): z.write(fp, fp.relative_to(work))
with zipfile.ZipFile(out) as z:
    bad=z.testzip()
    if bad: raise SystemExit('Bad zip member: '+bad)
    addon_txt=z.read('plugin.video.xship/addon.xml').decode('utf-8')
    if 'version="2026.08.25.7"' not in addon_txt: raise SystemExit('Version validation failed')
print('BUILT',out)
