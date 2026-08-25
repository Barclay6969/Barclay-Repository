from pathlib import Path
import re, shutil, subprocess, zipfile, requests

repo=Path('.')
basezip=repo/'zips/plugin.video.xship/plugin.video.xship-2026.08.25.8.zip'
out=repo/'test-builds/plugin.video.xship-2026.08.25.9-KINOKING-V2-TEST.zip'
basework=Path('/tmp/xship-kk-base')
newwork=Path('/tmp/xship-kk-new')
for d in (basework,newwork):
    shutil.rmtree(d,ignore_errors=True)
    d.mkdir(parents=True)
with zipfile.ZipFile(basezip) as z:
    z.extractall(basework)
shutil.copytree(basework/'plugin.video.xship',newwork/'plugin.video.xship',dirs_exist_ok=True)
root=newwork/'plugin.video.xship'

matches=list(root.rglob('kinoking.py'))
if len(matches)!=1:
    raise SystemExit(f'Expected one kinoking.py, got {matches}')
p=matches[0]
s=p.read_text('utf-8')
start=s.index('                # Titel im alt-Attribut:')
end=s.index('                for id, sName in results:',start)
new_block='''                results = []
                if season == 0:
                    # KinoKing V2 (08/2026): film cards now expose id/title as data attributes.
                    for card in re.findall(r'<[^>]+fav-data-source[^>]*>', sHtmlContent, re.I):
                        id_m = re.search(r'data-id="(\\d+)"', card, re.I)
                        type_m = re.search(r'data-type="([^"]+)"', card, re.I)
                        title_m = re.search(r'data-title="([^"]+)"', card, re.I)
                        if id_m and title_m and (not type_m or type_m.group(1).lower() == 'movie'):
                            results.append((id_m.group(1), title_m.group(1)))

                    # Compatibility fallback for the previous KinoKing markup.
                    if not results:
                        for m in re.finditer(r'onclick="playMovie\\((\\d+)\\)"', sHtmlContent):
                            chunk = sHtmlContent[m.end():m.end() + 300]
                            alt_m = re.search(r'alt="([^"]+)"', chunk)
                            if alt_m:
                                results.append((m.group(1), alt_m.group(1)))
                else:
                    # Keep the existing series parser unchanged.
                    pattern = r"onclick=\\\"playContent\\('(\\d+)'\\)\\\""
                    for m in re.finditer(pattern, sHtmlContent):
                        chunk = sHtmlContent[m.end():m.end() + 300]
                        alt_m = re.search(r'alt="([^"]+)"', chunk)
                        if alt_m:
                            results.append((m.group(1), alt_m.group(1)))
'''
s=s[:start]+new_block+s[end:]
p.write_text(s,'utf-8')

addon=root/'addon.xml'
a=addon.read_text('utf-8')
a2,n=re.subn(r'(<addon\b[^>]*?\bversion=")[^"]+("[^>]*>)',r'\g<1>2026.08.25.9\2',a,count=1,flags=re.S)
if n!=1:
    raise SystemExit('Could not set addon version')
addon.write_text(a2,'utf-8')

# Validate new parser on current KinoKing search page.
h=requests.get('https://kinoking.cc/index.php?search=the+last+house',headers={'User-Agent':'Mozilla/5.0'},timeout=20).text
results=[]
for card in re.findall(r'<[^>]+fav-data-source[^>]*>',h,re.I):
    i=re.search(r'data-id="(\d+)"',card,re.I)
    t=re.search(r'data-title="([^"]+)"',card,re.I)
    ty=re.search(r'data-type="([^"]+)"',card,re.I)
    if i and t and (not ty or ty.group(1).lower()=='movie'):
        results.append((i.group(1),t.group(1)))
print('KINOKING LIVE RESULTS',results[:10])
if ('63514','The Last House') not in results:
    raise SystemExit('Live KinoKing parser did not find The Last House / 63514')

# Validate the current detail page still exposes year and iframe target used by chk_year().
m=requests.get('https://kinoking.cc/movie.php?id=63514',headers={'User-Agent':'Mozilla/5.0'},timeout=20).text
year_m=re.search(r'<title>.*?(\d{4})',m,re.S)
iframe_m=re.search(r'<iframe.*?src="([^"]+)',m,re.S)
print('DETAIL YEAR',year_m.group(1) if year_m else None)
print('DETAIL IFRAME',iframe_m.group(1) if iframe_m else None)
if not year_m or year_m.group(1)!='2026':
    raise SystemExit('Detail year parse failed')
if not iframe_m or 'meinecloud.click/movie/tt32268156' not in iframe_m.group(1):
    raise SystemExit('Detail iframe parse failed')

subprocess.check_call(['python3','-m','compileall','-q',str(root)])
changed=[]
base=basework/'plugin.video.xship'
for bp in base.rglob('*'):
    if bp.is_file():
        rel=bp.relative_to(base)
        np=root/rel
        if not np.exists() or bp.read_bytes()!=np.read_bytes():
            changed.append(str(rel))
print('CHANGED',changed)
if len(changed)!=2 or 'addon.xml' not in changed or not any(x.endswith('kinoking.py') for x in changed):
    raise SystemExit(f'Unexpected changed files: {changed}')

if out.exists(): out.unlink()
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for fp in root.rglob('*'):
        if fp.is_file(): z.write(fp,fp.relative_to(newwork))
with zipfile.ZipFile(out) as z:
    bad=z.testzip()
    if bad: raise SystemExit(f'Bad ZIP member: {bad}')
print('BUILT',out)
