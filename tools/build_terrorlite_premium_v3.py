#!/usr/bin/env python3
"""TerrorLite 1.1.25: icon-rich cinema badges, a strict nonproduction test.

Build from previously successful 1.1.24; media art and rating-card geometry only.
Keep all existing rating extraction/IMDb bridges, widgets and Filmpalast untouched.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import importlib.util, math, hashlib, re

BASE=Path('test-builds/skin.terror.lite-1.1.24-CINEMA-LOGOS-TEST.zip')
OUT=Path('test-builds/skin.terror.lite-1.1.25-ICON-PREMIUM-TEST.zip')
PFX='skin.terror.lite/'
INFO=PFX+'16x9/DialogVideoInfo.xml'
ADDON=PFX+'addon.xml'
COLORS={'tmdb':'1AE6FC','imdb':'FFC43B','trakt':'FF4398'}
S='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
B='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

def c(h,opacity=255):
    h=h.replace('#','');return tuple(int(h[i:i+2],16) for i in (0,2,4))+(opacity,)
def F(size,bold=True):return ImageFont.truetype(B if bold else S,max(12,int(size)))
def word(d,area,s,size,fill='FFFFFF',bold=True,outline=None):
    x0,y0,x1,y1=area
    ff=F(size,bold);b=d.textbbox((0,0),s,font=ff,stroke_width=2 if outline else 0)
    while b[2]-b[0]>x1-x0-5 and size>14:
        size-=1;ff=F(size,bold);b=d.textbbox((0,0),s,font=ff,stroke_width=2 if outline else 0)
    pos=(round((x0+x1-(b[2]-b[0]))/2-b[0]),round((y0+y1-(b[3]-b[1]))/2-b[1]))
    d.text(pos,s,font=ff,fill=c(fill),
           stroke_width=2 if outline else 0,
           stroke_fill=c(outline) if outline else None)

def glowy_border(im,color,padding=9,radius=25,thickness=5):
    w,h=im.size
    glow=Image.new('RGBA',(w,h))
    d=ImageDraw.Draw(glow)
    d.rounded_rectangle((padding+2,padding+2,w-padding-3,h-padding-3),
                        radius=radius,outline=c(color,245),width=thickness+3)
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))

def panel(w,h,accent,style='silver'):
    im=Image.new('RGBA',(w,h))
    r=max(14,min(29,h//6))
    glowy_border(im,accent,radius=r)
    body=Image.new('RGBA',(w,h))
    mask=Image.new('L',(w,h))
    md=ImageDraw.Draw(mask)
    md.rounded_rectangle((11,10,w-12,h-11),radius=r,fill=255)
    fill=Image.new('RGBA',(w,h)); p=fill.load()
    if style=='gold':
        shades=[(58,39,14),(25,18,10),(9,13,21),(10,13,19)]
    elif style=='blue':
        shades=[(30,61,88),(14,30,47),(5,16,27),(4,14,24)]
    else:
        shades=[(53,65,82),(20,30,42),(9,15,26),(7,14,23)]
    for y in range(h):
        f=y/max(1,h-1)
        idx=min(3,int(f*4))
        r0,g0,b0=shades[idx]
        line=(r0,g0,b0,250)
        for x in range(w):
            p[x,y]=line
    fill.putalpha(Image.composite(fill.getchannel('A'),Image.new('L',(w,h),0),mask))
    body.alpha_composite(fill)
    shine=Image.new('RGBA',(w,h))
    sd=ImageDraw.Draw(shine)
    sd.polygon([(23,18),(int(w*.24),18),(int(w*.57),int(h*.65)),(int(w*.41),int(h*.65))],
               fill=(255,255,255,43))
    sd.polygon([(int(w*.60),15),(int(w*.67),15),(int(w*.84),int(h*.42)),(int(w*.79),int(h*.42))],
               fill=(255,255,255,31))
    shine=shine.filter(ImageFilter.GaussianBlur(7))
    body.alpha_composite(shine)
    d=ImageDraw.Draw(body)
    frame=c('E4F5FF') if style=='silver' else c('FFE298') if style=='gold' else c('B8F4FF')
    d.rounded_rectangle((8,8,w-9,h-9),radius=r+2,outline=c(accent),width=5)
    d.rounded_rectangle((13,12,w-14,h-13),radius=r-2,outline=frame,width=3)
    d.rounded_rectangle((19,18,w-20,h-19),radius=r-6,outline=c(accent,98),width=2)
    d.line((33,14,w-34,14),fill=(255,255,255,205),width=3)
    d.line((26,h-17,w-27,h-17),fill=c(accent,238),width=3)
    d.line((33,h-23,w-34,h-23),fill=c('FFFFFF',85),width=2)
    # tiny chrome edge points mimic glass light reflections
    for x,y in [(23,23),(w-25,26),(w-25,h-25)]:
        d.ellipse((x-2,y-2,x+2,y+2),fill=(255,255,255,220))
    im.alpha_composite(body)
    return im

def shadow_word(im,area,s,size,light='FFFFFF',bold=True,outline='060C14'):
    glow=Image.new('RGBA',im.size)
    d=ImageDraw.Draw(glow)
    word(d,area,s,size,light,bold)
    gl=glow.filter(ImageFilter.GaussianBlur(6))
    gl.putalpha(gl.getchannel('A').point(lambda a:int(a*.72)))
    im.alpha_composite(gl)
    word(ImageDraw.Draw(im),area,s,size,light,bold,outline)

def pbytes(im):
    b=BytesIO();im.save(b,format='PNG',optimize=True);return b.getvalue()

def rating_icon(kind):
    # 440x180 for a 220x90 Kodi group: native shape never clipped.
    w,h=440,180
    accent=COLORS[kind]
    im=panel(w,h,accent,'blue' if kind=='tmdb' else 'gold' if kind=='imdb' else 'silver')
    d=ImageDraw.Draw(im)
    # Left logo zone: 180px; right 240px reserved for live $VAR rating.
    d.line((184,31,184,148),fill=c(accent,170),width=3)
    if kind=='tmdb':
        # two-column TMDB visual mark, plus COMPLETE name underneath
        d.rounded_rectangle((35,38,85,95),radius=19,fill=c('3AEDE9'))
        d.rounded_rectangle((94,38,152,95),radius=19,fill=c('049FD6'))
        d.ellipse((37,40,73,61),fill=c('C8FFFF',120))
        word(d,(20,109,174,158),'TMDB',46,'76FEFF')
        word(d,(209,125,414,163),'TMDB',37,'73FCFC')
    elif kind=='imdb':
        d.rounded_rectangle((32,38,160,113),radius=11,
                            fill=c('F6C13B'),outline=c('FFF1AC'),width=4)
        word(d,(37,44,155,104),'IMDb',43,'111316')
        word(d,(213,125,412,163),'IMDb',39,'FFD65D')
    else:
        d.ellipse((48,38,141,131),outline=c('FA5498'),width=10)
        d.line((70,81,86,98,126,57),fill=c('FFFFFF'),width=11,joint='curve')
        word(d,(209,124,414,164),'trakt',39,'FF81B8')
    return pbytes(im)

def resolution(t,subtitle,color):
    im=panel(400,195,color,'gold' if color!='BDD8FF' else 'blue')
    d=ImageDraw.Draw(im);w,h=im.size
    # metallic inset and bright rectangular lower metal plaque
    d.rounded_rectangle((23,26,w-24,126),radius=12,
                        fill=c('080A11',235),outline=c('FFD476' if color!='BDD8FF' else 'D6EBFF'),width=2)
    shadow_word(im,(25,20,w-25,129),t,84,
                'FFE37E' if color!='BDD8FF' else 'F5F9FF')
    gold=color!='BDD8FF'
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((22,132,w-23,178),radius=4,
                        fill=c('FFC137' if gold else 'BCCFDF'),
                        outline=c('FFEAA1' if gold else 'FFFFFF'),width=3)
    word(d,(25,133,w-25,177),subtitle,36,'111218')
    return pbytes(im)

def codec(t,subtitle,accent='D7E9FA',aspect=False):
    im=panel(400,195,accent,'silver')
    if aspect:
        shadow_word(im,(25,20,375,125),t,83,'F0F3F8')
        d=ImageDraw.Draw(im)
        d.line((67,145,333,145),fill=c('DBE8F5'),width=5)
        d.line((67,145,85,132),fill=c('DBE8F5'),width=4)
        d.line((67,145,85,158),fill=c('DBE8F5'),width=4)
        d.line((333,145,315,132),fill=c('DBE8F5'),width=4)
        d.line((333,145,315,158),fill=c('DBE8F5'),width=4)
    else:
        shadow_word(im,(28,18,372,123),t,86,'F6F8FD')
        d=ImageDraw.Draw(im)
        d.rounded_rectangle((27,129,373,174),radius=5,
                            fill=c('C8D4E0'),outline=c('FFFFFF'),width=3)
        word(d,(29,130,372,174),subtitle,32,'141820')
    return pbytes(im)

def audio(kind,second=None):
    if kind.startswith('dolby'):
        im=panel(400,195,'F4C43D','gold')
        d=ImageDraw.Draw(im)
        # double-D pictogram as filled polished gold; legible at Kodi size
        for x,flip in [(29,False),(99,True)]:
            d.rounded_rectangle((x,39,x+64,108),radius=4,
                                fill=c('FFD255'),outline=c('FFF3AC'),width=2)
            d.ellipse((x+5,45,x+59,104),fill=c('060A10'))
            if flip:
                d.rectangle((x+34,45,x+59,105),fill=c('060A10'))
            else:
                d.rectangle((x+5,45,x+29,105),fill=c('060A10'))
        shadow_word(im,(174,28,380,116),'DOLBY',57,'FFE8A1')
        d=ImageDraw.Draw(im)
        d.line((25,128,375,128),fill=c('FFC951'),width=3)
        word(d,(24,132,376,173),second or 'DIGITAL',38,'FFD45E')
        return pbytes(im)
    if kind.startswith('dts'):
        im=panel(400,195,'FDAC45','gold');d=ImageDraw.Draw(im)
        # distinctive orange sound wave emblem
        for k in range(5):
            q=k*12
            d.arc((19+q,36+8*k,140-5*k,131-6*k),246,65,
                  fill=c('FD8C1C'),width=6)
        shadow_word(im,(120,22,380,121),'dts',104,'FFF6E6')
        d=ImageDraw.Draw(im)
        d.line((25,128,375,128),fill=c('FF8D1E'),width=3)
        word(d,(24,129,376,176),second or 'SURROUND',34,'FEE1AC')
        return pbytes(im)
    if kind=='aac':
        im=panel(400,195,'36CFFE','blue');d=ImageDraw.Draw(im)
        # Audio ripple mark dominates left third
        for k in range(4):
            d.arc((32+10*k,24+9*k,140+17*k,142-8*k),
                  175,305,fill=c('D9F9FF'),width=10)
        shadow_word(im,(176,17,379,130),'AAC',87,'FAFFFF')
        d=ImageDraw.Draw(im)
        word(d,(145,138,355,171),'AUDIO',34,'5DEBFF')
        return pbytes(im)
    if kind=='channels':
        im=panel(400,195,'74DFFF','blue');d=ImageDraw.Draw(im)
        d.polygon([(25,80),(50,80),(84,51),(84,132),(50,103),(25,103)],
                  fill=c('DDF9FF'))
        for k in range(3):
            d.arc((65,40-8*k,150+14*k,146+8*k),-65,65,
                  fill=c('A8ECFF'),width=7)
        shadow_word(im,(172,20,385,123),second or '2.0',93,'FFFFFF')
        d=ImageDraw.Draw(im)
        word(d,(141,135,383,174),'CHANNELS',31,'71DFFD')
        return pbytes(im)
    return codec(kind,second or 'AUDIO')

def fsk(age,accent):
    im=panel(238,238,accent,'silver' if age==0 else 'gold' if age==6 else 'blue')
    d=ImageDraw.Draw(im)
    d.ellipse((20,20,218,218),fill=c('071321',236),outline=c(accent),width=10)
    d.ellipse((30,30,208,208),outline=c('FFFFFF',230),width=4)
    d.ellipse((40,40,198,198),fill=c(accent,112),outline=c(accent),width=4)
    d.arc((30,30,208,208),204,315,fill=c('FFFFFF'),width=7)
    word(d,(41,44,197,89),'FSK',36,'FFFFFF')
    shadow_word(im,(36,94,201,187),str(age),102,'FFFFFF')
    return pbytes(im)

def build():
    spec=importlib.util.spec_from_file_location('cinema',Path('tools/build_terrorlite_cinema_logos.py'))
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    old.logo_plate=rating_icon
    old.round_fsk=fsk
    old.resolution_plate=resolution
    old.technical_plate=codec
    old.audio_plate=audio
    assert BASE.exists(),f'Missing: {BASE}'
    artwork=old.media_dict()
    # Resolution/codec flags get tuned premium palette for all standard values.
    for name,cap,sub in [
        ('2160','4K','ULTRA HD'),('4k','4K','ULTRA HD'),
        ('2048','2K','QUAD HD'),('1440','2K','QUAD HD'),('2k','2K','QUAD HD'),
        ('1080','1080p','FULL HD'),('720','720p','HD')]:
        artwork[PFX+'media/flags/default/resolution/'+name+'.png']=resolution(
            cap,sub,'E9B12B' if name!='720' else 'BDD8FF')
    # FSK 0/6/12/16/18 retain easily recognizable classification colors.
    with ZipFile(BASE) as src:
        assert src.testzip() is None
        basefiles=set(src.namelist())
        assert ET.fromstring(src.read(ADDON)).get('version')=='1.1.24'
        tree=ET.fromstring(src.read(INFO))
        wanted={'TMDB Bewertung':'tmdb','IMDb Bewertung':'imdb','Trakt Bewertung':'trakt'}
        for descr,platform in wanted.items():
            groups=[x for x in tree.iter('control')
                    if x.get('type')=='group' and x.findtext('description')==descr]
            assert len(groups)==1,descr
            group=groups[0]
            assert group.find('visible') is not None
            assert group.findtext('width')=='155',descr
            group.find('width').text='220'
            labels=[x for x in group if x.tag=='control' and x.get('type')=='label']
            assert len(labels)==1
            label=labels[0]
            assert (label.findtext('label') or '').startswith('$VAR[TerrorOmega'),descr
            for k,v in [('left','101'),('width','112'),('top','3'),('height','57')]:
                n=label.find(k)
                assert n is not None,k
                n.text=v
            img=[x for x in group if x.tag=='control' and x.get('type')=='image']
            assert len(img)==1
            assert img[0].findtext('texture')=='ratings_glossy/'+platform+'.png'
            img[0].find('width').text='220'
            img[0].find('height').text='90'
        changedinfo=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
        # No modification to <visible>, ratings variables, onload script or other controls.
        addon=src.read(ADDON)
        modified,cnt=re.subn(rb'(<addon\s+[^>]*\bversion=")1\.1\.24(")',
                             rb'\g<1>1.1.25\2',addon,count=1)
        assert cnt==1
        delta={INFO:changedinfo,ADDON:modified}
        OUT.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(OUT,'w',compression=ZIP_DEFLATED,compresslevel=7) as dst:
            for meta in src.infolist():
                data=delta.get(meta.filename)
                if data is None:data=artwork.get(meta.filename)
                if data is None:data=src.read(meta.filename)
                dst.writestr(meta,data)
            for path,data in sorted(artwork.items()):
                if path not in basefiles:dst.writestr(path,data)
        with ZipFile(OUT) as made:
            assert made.testzip() is None
            assert ET.fromstring(made.read(ADDON)).get('version')=='1.1.25'
            assert len(made.namelist())==len(basefiles)+len(set(artwork)-basefiles)
            for fname in basefiles:
                if fname not in delta and fname not in artwork:
                    assert src.getinfo(fname).CRC==made.getinfo(fname).CRC,f'Unexpected edit: {fname}'
            chk=ET.fromstring(made.read(INFO))
            for desc in wanted:
                cards=[x for x in chk.iter('control') if x.get('type')=='group'
                       and x.findtext('description')==desc]
                assert len(cards)==1 and cards[0].findtext('width')=='220'
        report=Path('development/terrorlite-glossy/v3-build-report.txt')
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(
            f'Base: {BASE}\nTest: {OUT}\n'
            f'Updated logo art: {len(artwork)}\n'
            f'TMDb IMDb Trakt card widths: 155 -> 220 Kodi px\n'
            f'Ratings calculation expressions, conditional visibility and sources: UNCHANGED\n'
            f'Filmpalast, Widgets, IMDb bridge and selectors: byte-identical to base\n'
            f'ZIP CRC: OK\n'
            f'Bytes: {OUT.stat().st_size}\n'
            f'SHA256: {hashlib.sha256(OUT.read_bytes()).hexdigest()}\n',
            encoding='utf-8')
        print(report.read_text())
if __name__=='__main__':build()
