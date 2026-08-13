# -*- coding: utf-8 -*-
import os, re, sys, json, time, hashlib, urllib.parse
import requests
import xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs

ADDON=xbmcaddon.Addon(); HANDLE=int(sys.argv[1]); BASE=sys.argv[0]
UA='Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
TMDB_KEY='edde6b5e41246ab79a2697cd125e1781'

def log(s): xbmc.log('[xBarc] '+str(s), xbmc.LOGINFO)
def q(): return dict(urllib.parse.parse_qsl(sys.argv[2][1:])) if len(sys.argv)>2 else {}
def u(**k): return BASE+'?'+urllib.parse.urlencode(k)
def add(label, action, folder=False, **kw):
    li=xbmcgui.ListItem(label=label); xbmcplugin.addDirectoryItem(HANDLE,u(action=action,**kw),li,folder)
def play(url):
    li=xbmcgui.ListItem(path=url); li.setProperty('IsPlayable','true'); xbmcplugin.setResolvedUrl(HANDLE,True,li)
def fail(msg):
    log(msg); xbmcgui.Dialog().notification('xBarc',msg,xbmcgui.NOTIFICATION_ERROR,5000); xbmcplugin.setResolvedUrl(HANDLE,False,xbmcgui.ListItem())

def profile():
    p=xbmcvfs.translatePath(ADDON.getAddonInfo('profile')); os.makedirs(p,exist_ok=True); return p

def tmdb_from_imdb(imdb):
    if not imdb:return ''
    try:
        d=requests.get('https://api.themoviedb.org/3/find/%s'%imdb,params={'api_key':TMDB_KEY,'external_source':'imdb_id'},timeout=12).json()
        a=d.get('movie_results') or d.get('tv_results') or []; return str(a[0]['id']) if a else ''
    except Exception as e: log('TMDB lookup: '+repr(e)); return ''

def vix_player(tmdb, season=0, episode=0):
    if int(season or 0)>0: return 'https://vixsrc.to/tv/%s/%s/%s'%(tmdb,season,episode)
    return 'https://vixsrc.to/movie/%s'%tmdb

def parse_master(html):
    block=re.search(r'window\.masterPlaylist\s*=\s*\{([\s\S]*?)\}\s*;?',html,re.I)
    scope=block.group(0) if block else html
    um=re.search(r"url\s*:\s*['\"]([^'\"]+)['\"]",scope,re.I)
    pm=re.search(r'params\s*:\s*\{([\s\S]*?)\}',scope,re.I)
    token=expires=''
    if pm:
        token_m=re.search(r"['\"]?token['\"]?\s*:\s*['\"]([^'\"]+)['\"]",pm.group(1),re.I)
        exp_m=re.search(r"['\"]?expires['\"]?\s*:\s*['\"]?([0-9]+)['\"]?",pm.group(1),re.I)
        token=token_m.group(1) if token_m else ''; expires=exp_m.group(1) if exp_m else ''
    fhd=bool(re.search(r'window\.canPlayFHD\s*=\s*true',html,re.I))
    return (um.group(1).replace('&amp;','&') if um else ''),token,expires,fhd

def local_hls(session, playlist_url, headers, text):
    if '#EXT-X-KEY' not in text:return ''
    key_re=re.compile(r'URI=(?:"([^"]+)"|([^,\s]+))',re.I); keys={}
    try:
        for line in text.splitlines():
            if not line.startswith('#EXT-X-KEY'):continue
            m=key_re.search(line)
            if not m:continue
            uri=m.group(1) or m.group(2)
            if uri in keys:continue
            ku=urllib.parse.urljoin(playlist_url,uri); r=session.get(ku,headers=headers,timeout=15)
            log('AES key status=%s len=%s'%(r.status_code,len(r.content)))
            if r.status_code!=200 or not r.content:return ''
            kp=os.path.join(profile(),'vixkey_'+hashlib.sha1(ku.encode()).hexdigest()[:12]+'.bin')
            with open(kp,'wb') as f:f.write(r.content)
            keys[uri]='file:///'+kp.replace('\\','/') if re.match(r'^[A-Za-z]:',kp) else 'file://'+kp
        out=[]
        for line in text.splitlines():
            s=line.strip()
            if s.startswith('#EXT-X-KEY'):
                def repl(m):
                    uri=m.group(1) or m.group(2); return 'URI="%s"'%keys.get(uri,urllib.parse.urljoin(playlist_url,uri))
                line=key_re.sub(repl,line)
            elif s and not s.startswith('#'): line=urllib.parse.urljoin(playlist_url,s)
            out.append(line)
        pp=os.path.join(profile(),'vix_'+str(int(time.time()*1000))+'.m3u8')
        with open(pp,'w',encoding='utf-8',newline='\n') as f:f.write('\n'.join(out)+'\n')
        log('local AES playlist '+pp)
        return 'file:///'+pp.replace('\\','/') if re.match(r'^[A-Za-z]:',pp) else 'file://'+pp
    except Exception as e: log('local_hls '+repr(e)); return ''

def resolve_vix(tmdb, season=0, episode=0):
    page=vix_player(tmdb,season,episode); s=requests.Session()
    h={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8','Accept-Language':'en-US,en;q=0.9','Referer':'https://vixsrc.to/'}
    r=s.get(page,headers=h,timeout=15); log('VixSrc page status=%s len=%s'%(r.status_code,len(r.text or '')))
    if r.status_code!=200:return ''
    base,token,expires,fhd=parse_master(r.text or '')
    log('masterPlaylist url=%s token=%s expires=%s'%(bool(base),bool(token),bool(expires)))
    if not (base and token and expires):return ''
    sep='&' if '?' in base else '?'; pu='%s%sexpires=%s&token=%s%s'%(base,sep,expires,token,'&h=1' if fhd else '')
    sh={'User-Agent':UA,'Accept':'*/*','Referer':page}
    pr=s.get(pu,headers=sh,timeout=15); txt=pr.text or ''; log('playlist status=%s m3u8=%s key=%s'%(pr.status_code,'#EXTM3U' in txt,'#EXT-X-KEY' in txt))
    if pr.status_code!=200 or '#EXTM3U' not in txt:return ''
    local=local_hls(s,pu,sh,txt)
    return local or (pu+'|'+urllib.parse.urlencode(sh))

def clean(s): return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',s or '')).strip()
def filmo_candidates(title):
    s=requests.Session(); s.headers.update({'User-Agent':UA,'Accept-Language':'de,en-US;q=0.7,en;q=0.3'})
    base='https://filmo.to'; out=[]
    try:
        s.get(base+'/',timeout=12,verify=False)
        r=s.get(base+'/search',params={'q':title},timeout=12,verify=False)
        for m in re.finditer(r'(?is)<a\b[^>]+href=["\']([^"\']*/movies/[^"\']+)["\'][^>]*>(.*?)</a>',r.text or ''):
            url=urllib.parse.urljoin(base,m.group(1)); name=clean(m.group(2));
            if (url,name) not in out:out.append((url,name))
    except Exception as e:log('FILMO search '+repr(e))
    return s,out[:12]

def attr(html,name):
    m=re.search(r'\b%s\s*=\s*["\']([^"\']*)["\']'%re.escape(name),html,re.I); return m.group(1) if m else ''
def filmo_links(session,page):
    base='https://filmo.to'; out=[]
    try:
        r=session.get(page,headers={'Referer':base+'/'},timeout=12,verify=False); html=r.text or ''
        csrf=''; cm=re.search(r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)',html,re.I); csrf=cm.group(1) if cm else ''
        om=re.search(r'(?:openMint|mintUrl)[^"\']*["\']([^"\']*/n)["\']',html,re.I); mint=urllib.parse.urljoin(base,om.group(1)) if om else base+'/n'
        for m in re.finditer(r'(?is)<div\b[^>]*data-provider-chip\b[^>]*>.*?</div>',html):
            chip=m.group(0); p=attr(chip,'data-p');
            if not p:continue
            hh={'Accept':'application/json, text/plain, */*','Content-Type':'application/json','X-Requested-With':'XMLHttpRequest','Origin':base,'Referer':page}
            if csrf:hh['X-CSRF-TOKEN']=csrf
            rr=session.post(mint,json={'p':p},headers=hh,timeout=12,verify=False)
            if rr.status_code not in (200,201):continue
            try:tok=rr.json().get('x')
            except:tok=''
            if not tok:continue
            fr=session.get(mint.rstrip('/')+'/'+urllib.parse.quote_plus(tok),headers={'Referer':page},timeout=12,verify=False,allow_redirects=True)
            fu=fr.url or ''
            if fu and '/n/' not in fu and fu not in out:out.append(fu)
    except Exception as e:log('FILMO links '+repr(e))
    return out

def resolve_hoster(url):
    try:
        import resolveurl
        h=resolveurl.HostedMediaFile(url=url)
        return h.resolve() if h.valid_url() else ''
    except Exception as e:log('ResolveURL '+repr(e)); return ''

def filmo_play(title):
    s,c=filmo_candidates(title)
    if not c:return ''
    for page,name in c:
        for h in filmo_links(s,page):
            log('FILMO hoster '+h)
            r=resolve_hoster(h)
            if r:return r
    return ''

def action_root():
    add('Vixstream - TMDB-ID testen','vix_prompt'); add('FILMO - Film suchen','filmo_prompt'); xbmcplugin.endOfDirectory(HANDLE)
def vix_prompt():
    tm=xbmcgui.Dialog().input('TMDB-ID');
    if tm: xbmc.executebuiltin('PlayMedia(%s)'%u(action='vix',tmdb=tm))
def filmo_prompt():
    t=xbmcgui.Dialog().input('Filmtitel');
    if t: xbmc.executebuiltin('PlayMedia(%s)'%u(action='filmo',title=t))

def main():
    p=q(); a=p.get('action','root')
    try:
        if a=='root':return action_root()
        if a=='vix_prompt':return vix_prompt()
        if a=='filmo_prompt':return filmo_prompt()
        if a in ('vix','play','playExtern'):
            tm=p.get('tmdb') or p.get('tmdb_id') or tmdb_from_imdb(p.get('imdb','') or p.get('imdbnumber',''))
            if not tm:return fail('Keine TMDB-ID')
            r=resolve_vix(tm,p.get('season',0),p.get('episode',0)); return play(r) if r else fail('Vixstream konnte nicht aufgeloest werden')
        if a=='filmo':
            r=filmo_play(p.get('title','')); return play(r) if r else fail('FILMO konnte nicht aufgeloest werden')
    except Exception as e: fail('Fehler: '+str(e)); log(repr(e))
main()
