#!/usr/bin/env python3
"""TerrorLite 1.1.24: icon-forward mockup-inspired black-silver badge TEST.
Builds on tested 1.1.23 layout without touching rating lookup logic.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
import math, re, hashlib

SRC=Path('test-builds/skin.terror.lite-1.1.23-LOGOS-TEST.zip')
DST=Path('test-builds/skin.terror.lite-1.1.24-CINEMA-LOGOS-TEST.zip')
ROOT='skin.terror.lite/'
FONTP='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONTB='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def rgb(h,a=255):
    h=h.replace('#','')
    return tuple(int(h[i:i+2],16) for i in (0,2,4))+(a,)
def font(sz,bold=True):
    return ImageFont.truetype(FONTB if bold else FONTP,sz)
def tx(d,box,t,size,color='#FFFFFF',bold=True):
    f=font(size,bold); bx=d.textbbox((0,0),t,font=f)
    while (bx[2]-bx[0]>box[2]-box[0]-2) and size>13:
        size-=1;f=font(size,bold); bx=d.textbbox((0,0),t,font=f)
    x=box[0]+(box[2]-box[0]-(bx[2]-bx[0]))/2-bx[0]
    y=box[1]+(box[3]-box[1]-(bx[3]-bx[1]))/2-bx[1]
    d.text((round(x),round(y)),t,font=f,fill=rgb(color) if isinstance(color,str) else color)

def canvas(w,h,accent='AFC3DD',metal=False):
    im=Image.new('RGBA',(w,h))
    # halo
    gl=Image.new('RGBA',(w,h));g=ImageDraw.Draw(gl)
    g.rounded_rectangle((6,6,w-7,h-7),radius=min(22,h//4),
                        outline=rgb(accent,235),width=5)
    im.alpha_composite(gl.filter(ImageFilter.GaussianBlur(7)))
    inset=Image.new('RGBA',(w,h));d=ImageDraw.Draw(inset)
    rad=min(20,h//4)
    d.rounded_rectangle((6,6,w-7,h-7),radius=rad,fill=(6,12,22,251),
                        outline=rgb('E7F4FF' if metal else accent,245),width=3)
    d.rounded_rectangle((11,11,w-12,h-12),radius=rad-4,
                        outline=rgb(accent,172),width=2)
    # subtle transparent upper-gloss band
    sheen=Image.new('RGBA',(w,h))
    ds=ImageDraw.Draw(sheen)
    ds.rounded_rectangle((15,15,w-16,int(h*.48)),radius=11,
                        fill=(225,243,255,43))
    sheen=sheen.filter(ImageFilter.GaussianBlur(11))
    inset.alpha_composite(sheen)
    d=ImageDraw.Draw(inset)
    d.line((24,12,w-25,12),fill=(255,255,255,210),width=2)
    d.line((24,h-13,w-25,h-13),fill=rgb(accent,183),width=3)
    # gradated highlights along inner edge and bottom accent
    d.line((23,h-18,w-24,h-18),fill=rgb(accent,70),width=3)
    im.alpha_composite(inset)
    return im

def image_bytes(im):
    out=BytesIO(); im.save(out,format='PNG',optimize=True);return out.getvalue()

def logo_plate(kind):
    w,h=310,180
    col={'tmdb':'04E7F8','imdb':'FFBE27','trakt':'FF3292'}[kind]
    im=canvas(w,h,col)
    d=ImageDraw.Draw(im)
    # divide the platform pictogram from the still-live Kodi rating.
    d.line((111,40,111,142),fill=rgb(col,145),width=2)
    if kind=='tmdb':
        tx(d,(25,22,106,69),'TM',36,'48F5FF')
        d.rounded_rectangle((27,80,58,124),radius=11,fill=rgb('2BE8FA'))
        d.rounded_rectangle((65,80,99,124),radius=11,fill=rgb('08A8D4'))
        tx(d,(120,119,290,161),'TMDB',39,'4DF5FF')
    elif kind=='imdb':
        d.rounded_rectangle((22,54,103,130),radius=11,fill=rgb('FFCE35'),
                            outline=rgb('FFF4AD'),width=3)
        tx(d,(26,70,100,112),'IMDb',24,'131112')
        tx(d,(118,119,289,160),'IMDb',39,'FFD05B')
    else:
        d.ellipse((26,46,103,123),outline=rgb('FF69AE'),width=7)
        # recognizable stylized checkmark and upward slash motif
        d.line((42,88,59,105,90,61),fill=rgb('FFF0F8'),width=9,joint='curve')
        d.line((70,100,94,57),fill=rgb('FF3792'),width=5)
        tx(d,(114,119,297,162),'trakt',41,'FF8FC5')
    return image_bytes(im)

def round_fsk(age,color):
    w=h=236; im=canvas(w,h,color)
    d=ImageDraw.Draw(im)
    # luminous concentric metallic ring with multistage reflection
    d.ellipse((20,20,216,216),fill=(12,17,25,255),
              outline=rgb(color),width=9)
    d.ellipse((31,31,205,205),outline=(242,250,255,220),width=3)
    d.ellipse((41,41,195,195),fill=rgb(color,92),
              outline=rgb(color,203),width=4)
    d.arc((35,35,201,201),195,340,fill=(255,255,255,215),width=5)
    tx(d,(44,39,192,90),'FSK',31)
    tx(d,(27,83,211,186),str(age),93,'FFFFFF')
    return image_bytes(im)

def resolution_plate(first,second,color):
    w,h=360,180; im=canvas(w,h,color)
    d=ImageDraw.Draw(im)
    d.rectangle((17,117,343,160),fill=rgb(color))
    d.line((20,116,340,116),fill=(255,255,255,222),width=2)
    tx(d,(20,21,340,117),first,72,'FFFFFF')
    tx(d,(28,116,331,160),second,30,'080D16')
    return image_bytes(im)

def technical_plate(first,second,color='D2E2F3',aspect=False):
    w,h=360,180;im=canvas(w,h,color,True);d=ImageDraw.Draw(im)
    tx(d,(17,19,342,112),first,74,'F9FAFD')
    if aspect:
        d.line((52,140,308,140),fill=rgb('C8EEFF'),width=4)
        d.line((52,140,73,126),fill=rgb('C8EEFF'),width=4)
        d.line((52,140,73,154),fill=rgb('C8EEFF'),width=4)
        d.line((308,140,287,126),fill=rgb('C8EEFF'),width=4)
        d.line((308,140,287,154),fill=rgb('C8EEFF'),width=4)
    else:
        d.rectangle((22,121,338,157),fill=(197,219,237,75))
        tx(d,(24,119,338,160),second,27,'FFFFFF')
    return image_bytes(im)

def audio_plate(kind,label=None):
    w,h=360,180
    if kind.startswith('dolby'):
        accent='F4C044';im=canvas(w,h,accent);d=ImageDraw.Draw(im)
        # Dolby's opposing D pictogram, large & legible
        d.rounded_rectangle((27,41,88,103),radius=3,fill=rgb('F7C741'))
        d.ellipse((28,43,85,99),fill=rgb('050C18'))
        d.rectangle((28,40,55,104),fill=rgb('050C18'))
        d.rounded_rectangle((99,41,160,103),radius=3,fill=rgb('F7C741'))
        d.ellipse((102,44,157,99),fill=rgb('050C18'))
        d.rectangle((129,40,161,104),fill=rgb('050C18'))
        tx(d,(168,35,343,109),'DOLBY',43,'FFD259')
        d.line((25,121,335,121),fill=rgb('FFDB77'),width=3)
        tx(d,(26,123,334,159),label or 'DIGITAL',31,'FFD259')
    elif kind.startswith('dts'):
        accent='7BD7FF';im=canvas(w,h,accent);d=ImageDraw.Draw(im)
        for k in range(6):
            box=(20+9*k,36+7*k,100-6*k,111-7*k)
            d.arc(box,255,70,fill=rgb('FF9A27'),width=5)
        tx(d,(94,22,344,119),'dts',83,'FFFFFF')
        d.line((28,120,332,120),fill=rgb('FFAC43'),width=2)
        tx(d,(22,123,336,164),label or 'SURROUND',28,'FFFFFF')
    elif kind=='aac':
        im=canvas(w,h,'46D5FF');d=ImageDraw.Draw(im)
        for k in range(3):
            d.arc((20+14*k,30+9*k,130+14*k,134-8*k),
                  180,310,fill=rgb('D9F6FF'),width=9)
        tx(d,(149,31,342,117),'AAC',79,'F5FFFF')
        tx(d,(56,121,301,161),'AUDIO',30,'4FDFFD')
    elif kind=='channels':
        im=canvas(w,h,'68D8F9');d=ImageDraw.Draw(im)
        d.polygon([(23,81),(44,81),(63,62),(63,116),(44,99),(23,99)],
                  fill=rgb('C7F3FF'))
        for k in range(3):
            d.arc((46-3*k,58-12*k,104+14*k,121+12*k),
                  -65,65,fill=rgb('C7F3FF'),width=4)
        tx(d,(139,24,345,108),label or '2.0',70,'FFFFFF')
        tx(d,(72,125,311,159),'CHANNELS',28,'6BD9F9')
    else:
        im=technical_plate(kind,label or '',"AFDDF3")
    return image_bytes(im)

def media_dict():
    media={}
    def put(path,content):media[ROOT+'media/'+path]=content
    for k in ('tmdb','imdb','trakt'):
        put('ratings_glossy/'+k+'.png',logo_plate(k))
    for age,col in [(0,'C7D9EC'),(6,'FAC338'),(12,'40E995'),
                    (16,'32B2FF'),(18,'FF4B59')]:
        put(f'flags/default/mpaa/fsk-{age}.png',round_fsk(age,col))
    specs={
        '2160':('4K','ULTRA HD','F5C144'),
        '4k':('4K','ULTRA HD','F5C144'),
        '2048':('2K','QUAD HD','F5C144'),
        '1440':('2K','QUAD HD','F5C144'),
        '2k':('2K','QUAD HD','F5C144'),
        '1080':('1080p','FULL HD','F5BD33'),
        '720':('720p','HD','AED4FA'),
        '576':('576p','SD','BBCFE1'),
        '540':('540p','SD','BBCFE1'),
        '480':('480p','SD','BBCFE1'),
        '288':('288p','SD','BBCFE1'),
        'hd':('HD','HD','AED4FA')}
    for k,v in specs.items():
        put('flags/default/resolution/'+k+'.png',resolution_plate(*v))
    codec={'h264':('H.264','MPEG-4/AVC'), 'avc1':('H.264','MPEG-4/AVC'),
           'hevc':('H.265','HEVC'), 'hev1':('H.265','HEVC'),
           'mpeg2video':('MPEG-2','VIDEO'), 'vc-1':('VC-1','VIDEO'),
           'mkv':('MKV','VIDEO'),'mp4':('MP4','VIDEO'),
           'bluray':('BLU-RAY','VIDEO'),'bluray3d':('BLU-RAY','3D'),
           'xvid':('XVID','VIDEO'),'divx':('DIVX','VIDEO'),
           'hdtv':('HDTV','VIDEO'),'web-dl':('WEB-DL','VIDEO'),
           'dvd':('DVD','VIDEO')}
    for k,(title,sub) in codec.items():
        put('flags/default/videocodec/'+k+'.png',technical_plate(title,sub))
    for k,v in {
        '1.33':'4:3','1.37':'4:3','1.66':'1.66:1','1.78':'16:9',
        '1.85':'1.85:1','2.20':'2.20:1','2.35':'21:9','2.40':'21:9',
        '2.55':'2.55:1','2.76':'2.76:1'}.items():
        put('flags/default/aspectratio/'+k+'.png',technical_plate(v,'','D1E2F2',True))
    audio={
        'aac':('aac',None),'ac3':('dolby','DIGITAL'),
        'eac3':('dolby','DIGITAL PLUS'),'atmos':('dolby','ATMOS'),
        'truehd':('dolby','TRUEHD'),
        'dts':('dts','SURROUND'),'dca':('dts','SURROUND'),
        'dtshd_ma':('dts','HD MASTER AUDIO'),'dtshd_hra':('dts','HD HIGH RES'),
        'dtsma':('dts','HD MASTER AUDIO'),'dtsx':('dts','DTS:X'),
        'flac':('FLAC','LOSSLESS'),'mp3':('MP3','AUDIO'),
        'mp3float':('MP3','AUDIO'),'pcm':('PCM','LOSSLESS'),
        'pcm_bluray':('PCM','LOSSLESS'),'pcm_s16le':('PCM','LOSSLESS'),
        'pcm_s24le':('PCM','LOSSLESS')}
    for k,(title,subtitle) in audio.items():
        put('flags/default/audiocodec/'+k+'.png',audio_plate(title,subtitle))
    channels={'0':'0.0','1':'1.0','2':'2.0','3':'3.0',
              '4':'4.0','5':'5.0','6':'5.1','7':'6.1',
              '8':'7.1','10':'9.1'}
    for k,v in channels.items():
        put('flags/default/audiochannels/'+k+'.png',audio_plate('channels',v))
    return media

def build():
    assert SRC.exists(),f'Missing 1.1.23 base: {SRC}'
    media=media_dict()
    info=ROOT+'16x9/DialogVideoInfo.xml'
    addon=ROOT+'addon.xml'
    with ZipFile(SRC) as src:
        assert src.testzip() is None
        src_names=set(src.namelist())
        assert ET.fromstring(src.read(addon)).get('version')=='1.1.23'
        xml=ET.fromstring(src.read(info))
        updated=0
        for name in ('TMDB Bewertung','IMDb Bewertung','Trakt Bewertung'):
            matches=[n for n in xml.iter('control') if n.get('type')=='group' and n.findtext('description')==name]
            assert len(matches)==1,name
            g=matches[0]
            label=[n for n in g if n.tag=='control' and n.get('type')=='label']
            assert len(label)==1
            assert (label[0].findtext('label') or '').startswith('$VAR[TerrorOmega')
            for tag,val in [('left','57'),('width','95'),('top','4'),('height','55')]:
                child=label[0].find(tag)
                if child is None:
                    child=ET.SubElement(label[0],tag)
                child.text=val
            assert g.findtext('visible')
            updated+=1
        new_info=ET.tostring(xml,encoding='utf-8',xml_declaration=True)
        original_addon=src.read(addon)
        new_addon,n=re.subn(rb'(<addon\s+[^>]*\bversion=")1\.1\.23(")',
                            rb'\g<1>1.1.24\2',original_addon,count=1)
        assert n==1
        changes={info:new_info,addon:new_addon}
        DST.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(DST,'w',compression=ZIP_DEFLATED,compresslevel=7) as out:
            for zi in src.infolist():
                data=changes.get(zi.filename)
                if data is None: data=media.get(zi.filename)
                if data is None: data=src.read(zi.filename)
                out.writestr(zi,data)
            for path,data in sorted(media.items()):
                if path not in src_names:
                    out.writestr(path,data)
        # Verify untouched components byte-by-byte against 1.1.23
        with ZipFile(DST) as dst:
            assert dst.testzip() is None
            assert ET.fromstring(dst.read(addon)).get('version')=='1.1.24'
            assert len(dst.namelist())==len(src_names)+len(set(media)-src_names)
            for path in src_names:
                if path not in media and path not in changes:
                    assert src.getinfo(path).CRC==dst.getinfo(path).CRC, 'Unexpected change: '+path
            assert updated==3
    report=Path('development/terrorlite-glossy/cinema-build-report.txt')
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(
        f'Base ZIP: {SRC}\nCinema mockup-inspired test ZIP: {DST}\n'
        f'Restyled brand & format textures: {len(media)}\n'
        f'Kodi dynamic rating values retained: {updated}\n'
        f'IMDb/Trakt/TMDB lookups unchanged. Filmpalast and widgets unchanged.\n'
        f'CRC: passed\nZIP files: {len(src_names)+len(set(media)-src_names)}\n'
        f'SHA256: {hashlib.sha256(DST.read_bytes()).hexdigest()}\n'
        f'Size: {DST.stat().st_size} bytes\n',
        encoding='utf-8')
    print(report.read_text())

if __name__=='__main__':build()
