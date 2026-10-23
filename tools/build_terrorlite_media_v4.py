#!/usr/bin/env python3
"""TerrorLite 1.1.26 Premium Media V4: focused icon refinement.

Exactly 1.1.25 plus new media format PNGs and the addon version number.
The three rating cards, FSK art, rating lookups, Filmpalast and every other skin
file remain byte-identical. Built only in the isolated test branch.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from zipfile import ZipFile, ZIP_DEFLATED
from io import BytesIO
from xml.etree import ElementTree as ET
import hashlib, math, re

BASE=Path('test-builds/skin.terror.lite-1.1.25-ICON-PREMIUM-TEST.zip')
OUT=Path('test-builds/skin.terror.lite-1.1.26-MEDIA-FINISH-TEST.zip')
REPORT=Path('development/terrorlite-glossy/v4-build-report.txt')
PREVIEW=Path('development/terrorlite-glossy/v4-media-preview.png')
PFX='skin.terror.lite/'
ADDON=PFX+'addon.xml'
FONTB='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
W,H=520,248

def col(c,alpha=255):
    c=c.lstrip('#')
    return tuple(int(c[i:i+2],16) for i in (0,2,4))+(int(alpha),)

def text_font(n,bold=True):
    return ImageFont.truetype(FONTB if bold else FONT,max(13,int(n)))

def tbox(d,rect,label,size,color='FFFFFF',bold=True,stroke=None):
    x0,y0,x1,y1=rect
    f=text_font(size,bold);sw=2 if stroke else 0
    bounds=d.textbbox((0,0),label,font=f,stroke_width=sw)
    while bounds[2]-bounds[0] > x1-x0-3 and size>14:
        size-=1;f=text_font(size,bold)
        bounds=d.textbbox((0,0),label,font=f,stroke_width=sw)
    d.text((
        round(x0+(x1-x0-bounds[2]+bounds[0])/2-bounds[0]),
        round(y0+(y1-y0-bounds[3]+bounds[1])/2-bounds[1])
        ),label,font=f,fill=col(color),stroke_width=sw,
        stroke_fill=col(stroke) if stroke else None)

def embossed(img,area,label,size,light='F7FBFF',glow='C7EDFF'):
    layer=Image.new('RGBA',img.size)
    tbox(ImageDraw.Draw(layer),area,label,size,glow,True)
    haze=layer.filter(ImageFilter.GaussianBlur(6))
    haze.putalpha(haze.getchannel('A').point(lambda x:int(x*0.55)))
    img.alpha_composite(haze)
    # dark offset shadow first to increase legibility when shrunk to Kodi size
    shifted=(area[0]+2,area[1]+3,area[2]+2,area[3]+3)
    tbox(ImageDraw.Draw(img),shifted,label,size,'030812')
    tbox(ImageDraw.Draw(img),area,label,size,light,True,'152536')

def alpha_gradient(w,h,kind):
    canvas=Image.new('RGBA',(w,h))
    pixels=canvas.load()
    for y in range(h):
        t=y/(h-1)
        if kind=='gold':
            top=(89,61,18);bottom=(6,10,18)
        elif kind=='cyan':
            top=(27,79,101);bottom=(4,14,23)
        else:
            top=(69,78,97);bottom=(5,11,19)
        fac=(1-t)**1.7
        rgb=tuple(round(bottom[i]+(top[i]-bottom[i])*fac) for i in range(3))
        for x in range(w):
            wave=int(12*(1-abs(x-w*.50)/(w*.50))*(1-t))
            pixels[x,y]=(min(255,rgb[0]+wave),min(255,rgb[1]+wave),min(255,rgb[2]+wave),255)
    return canvas

def baseplate(mode='chrome',accent='BFD8F2'):
    im=Image.new('RGBA',(W,H))
    # saturated but subtle aura only around the border
    aura=Image.new('RGBA',(W,H))
    a=ImageDraw.Draw(aura)
    a.rounded_rectangle((18,17,W-19,H-18),radius=28,outline=col(accent,235),width=9)
    im.alpha_composite(aura.filter(ImageFilter.GaussianBlur(13)))
    surface=alpha_gradient(W,H,'gold' if mode=='gold' else 'cyan' if mode=='cyan' else 'silver')
    mask=Image.new('L',(W,H))
    ImageDraw.Draw(mask).rounded_rectangle((18,17,W-19,H-18),radius=30,fill=255)
    surface.putalpha(mask)
    im.alpha_composite(surface)
    # multi-layer metallic frame and inset enamel
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((13,12,W-14,H-13),radius=36,outline=col('A4B1C5'),width=3)
    d.rounded_rectangle((17,16,W-18,H-17),radius=30,outline=col(accent),width=8)
    d.rounded_rectangle((22,21,W-23,H-22),radius=26,outline=col('F9FBFE',235),width=3)
    d.rounded_rectangle((28,27,W-29,H-28),radius=21,outline=col(accent,115),width=2)
    # bevel across upper 40% 
    gloss=Image.new('RGBA',(W,H))
    g=ImageDraw.Draw(gloss)
    g.rounded_rectangle((32,29,W-33,112),radius=18,fill=(228,244,255,42))
    g.polygon([(48,29),(148,29),(285,161),(175,161)],fill=(255,255,255,42))
    g.polygon([(340,29),(378,29),(447,109),(413,109)],fill=(255,255,255,25))
    im.alpha_composite(gloss.filter(ImageFilter.GaussianBlur(13)))
    d=ImageDraw.Draw(im)
    d.line((46,24,W-46,24),fill=(255,255,255,225),width=3)
    d.line((43,H-25,W-44,H-25),fill=col(accent,230),width=4)
    d.line((43,H-31,W-44,H-31),fill=col('FFFFFF',120),width=2)
    # star-like lens sparkle highlights
    for sx,sy in [(51,25),(W-59,24),(W-42,H-42)]:
        d.line((sx-9,sy,sx+9,sy),fill=(255,255,255,177),width=2)
        d.line((sx,sy-7,sx,sy+7),fill=(255,255,255,177),width=2)
    return im

def footer(im,label,color='C3D2E2',dark=False):
    d=ImageDraw.Draw(im)
    y0=168
    d.rounded_rectangle((31,y0,W-32,216),radius=8,
                        fill=col(color if dark else '26384A'),
                        outline=col('FFFFFF' if dark else color,230),width=3)
    d.line((47,y0+5,W-48,y0+5),fill=col('FFFFFF',185),width=2)
    tbox(d,(42,y0+6,W-43,213),label,37,'111218' if dark else 'F9FAFF')

def png(im):
    buf=BytesIO();im.save(buf,'PNG',optimize=True);return buf.getvalue()

def res_badge(title,subtitle,low=False):
    # Massive gold front plaque with bevelled sidewalls; scaled for 160px Kodi flags.
    im=baseplate('chrome' if low else 'gold','B9E6FF' if low else 'FFC139')
    d=ImageDraw.Draw(im)
    metal='DDEFFF' if low else 'FFD268'
    d.rounded_rectangle((36,33,W-37,159),radius=15,fill=col('040914',245),
                        outline=col(metal),width=4)
    d.line((47,42,W-48,42),fill=col('FFF9E9'),width=3)
    embossed(im,(44,43,W-44,161),title,107,'FFFFFF' if low else 'FFE89B',
             '77CDFF' if low else 'FFD364')
    footer(im,subtitle,'B7DFFE' if low else 'FFCD41',True)
    return png(im)

def micro_film(d,x,y,color='BFD8F2'):
    # Filmstrip glyph: clear on a compact codec badge
    d.rounded_rectangle((x,y,x+88,y+100),radius=10,outline=col(color),width=5)
    d.polygon([(x+14,y+19),(x+71,y+50),(x+14,y+80)],fill=col('F9FCFF'))
    for yy in [y+15,y+41,y+67]:
        d.rounded_rectangle((x+77,yy,x+84,yy+12),radius=2,fill=col(color))

def codec_badge(main,detail,aspect=False):
    im=baseplate('chrome','CCDDEB')
    d=ImageDraw.Draw(im)
    if aspect:
        embossed(im,(33,28,W-33,159),main,112,'F3F7FC')
        d.line((105,192,W-105,192),fill=col('D3E7FF'),width=5)
        d.line((105,192,131,178),fill=col('D3E7FF'),width=5)
        d.line((105,192,131,205),fill=col('D3E7FF'),width=5)
        d.line((W-105,192,W-131,178),fill=col('D3E7FF'),width=5)
        d.line((W-105,192,W-131,205),fill=col('D3E7FF'),width=5)
    else:
        micro_film(d,43,40,'C9E0F1')
        embossed(im,(144,28,W-43,150),main,104,'F5F8FC','BDD2EA')
        footer(im,detail,'AABED4',True)
    return png(im)

def speaker_symbol(d,x=42,y=74,color='DDF9FF'):
    d.polygon([(x,y+26),(x+30,y+26),(x+65,y-6),
               (x+65,y+99),(x+30,y+65),(x,y+65)],fill=col(color))
    for i in range(3):
        d.arc((x+45-i*3,y-22-i*13,x+133+i*22,y+125+i*13),
              -68,68,fill=col(color),width=7)

def sound_wave(d,x=40,y=42,color='FFAD53'):
    for n in range(4):
        yy=n*12
        d.arc((x+n*11,y+yy,x+136-n*8,y+135-yy),
              239,63,fill=col(color),width=8)

def dolby_icon(d):
    for x,reverse in [(38,False),(103,True)]:
        d.rounded_rectangle((x,49,x+62,136),radius=5,fill=col('FFE283'),
                            outline=col('FFFFFF'),width=2)
        d.ellipse((x+8,56,x+57,128),fill=col('091120'))
        if reverse:
            d.rectangle((x+31,57,x+56,129),fill=col('091120'))
        else:
            d.rectangle((x+8,57,x+34,129),fill=col('091120'))

def audio_badge(kind,detail=''):
    # Rich native iconography by codec; brand words remain legible at 150px.
    if kind=='dolby':
        im=baseplate('gold','F9D055');d=ImageDraw.Draw(im)
        dolby_icon(d)
        embossed(im,(173,44,W-37,152),'DOLBY',70,'FFE6A0','FFC34A')
        footer(im,detail or 'DIGITAL','FFD36F',True)
    elif kind=='dts':
        im=baseplate('gold','FFA238');d=ImageDraw.Draw(im)
        sound_wave(d,color='FFA63A')
        embossed(im,(168,35,W-40,158),'dts',117,'FFF5E8','FF8C25')
        footer(im,detail or 'SURROUND','FFC17A',True)
    elif kind=='aac':
        im=baseplate('cyan','46DCFF');d=ImageDraw.Draw(im)
        for n in range(4):
            d.arc((45+10*n,43+11*n,185+15*n,173-9*n),
                  179,307,fill=col('E0FAFF'),width=11)
        embossed(im,(184,31,W-40,156),'AAC',105,'F7FFFF','42ECFF')
        # slim luminous subtitle, not simple monochrome panel
        footer(im,'AUDIO','2C759C',False)
    else:
        im=baseplate('chrome','AED9EC')
        embossed(im,(39,27,W-40,158),kind,95,'F4FAFF')
        footer(im,detail or 'AUDIO','8EB1C8',True)
    return png(im)

def channels_badge(value):
    im=baseplate('cyan','53DCFF');d=ImageDraw.Draw(im)
    speaker_symbol(d)
    embossed(im,(200,33,W-39,158),value,113,'FFFFFF','7FE9FF')
    footer(im,'CHANNELS','226F99',False)
    return png(im)

def asset_changes(z):
    replacements={}
    def put(category,name,data):
        path=PFX+'media/flags/default/'+category+'/'+name+'.png'
        # Don't add or silently invent assets for categories Kodi doesn't use.
        if path in z.namelist():
            replacements[path]=data
    resolution={
        '2160':('4K','ULTRA HD',False),
        '4k':('4K','ULTRA HD',False),
        '2048':('2K','QUAD HD',False),
        '1440':('2K','QUAD HD',False),
        '2k':('2K','QUAD HD',False),
        '1080':('1080p','FULL HD',False),
        '720':('720p','HD',True),
        '576':('576p','SD',True),
        '540':('540p','SD',True),
        '480':('480p','SD',True),
        '288':('288p','SD',True),
        'hd':('HD','HIGH DEF',True)}
    for key,args in resolution.items():
        put('resolution',key,res_badge(*args))
    codecs={
        'h264':('H.264','MPEG-4 / AVC'),
        'avc1':('H.264','MPEG-4 / AVC'),
        'hevc':('H.265','HEVC'),
        'hev1':('H.265','HEVC'),
        'mpeg2video':('MPEG-2','VIDEO'),
        'vc-1':('VC-1','VIDEO'),
        'mkv':('MKV','CONTAINER'),
        'mp4':('MP4','CONTAINER'),
        'bluray':('BLU-RAY','VIDEO'),
        'bluray3d':('BLU-RAY','3D VIDEO'),
        'xvid':('XVID','VIDEO'),
        'divx':('DIVX','VIDEO'),
        'hdtv':('HDTV','SOURCE'),
        'web-dl':('WEB-DL','SOURCE'),
        'dvd':('DVD','VIDEO'),
        'mov':('MOV','CONTAINER')}
    for key,(title,detail) in codecs.items():
        put('videocodec',key,codec_badge(title,detail))
    aspects={'1.33':'4:3','1.37':'4:3','1.66':'1.66:1',
             '1.78':'16:9','1.85':'1.85:1','2.20':'2.20:1',
             '2.35':'21:9','2.40':'21:9','2.55':'2.55:1','2.76':'2.76:1'}
    for key,title in aspects.items():
        put('aspectratio',key,codec_badge(title,'',True))
    audio={
        'aac':('aac',''), 'ac3':('dolby','DIGITAL'),
        'eac3':('dolby','DIGITAL PLUS'),
        'atmos':('dolby','ATMOS'),
        'truehd':('dolby','TRUEHD'),
        'dts':('dts','SURROUND'),
        'dca':('dts','SURROUND'),
        'dtshd_ma':('dts','HD MASTER AUDIO'),
        'dtshd_hra':('dts','HD HIGH RES'),
        'dtsma':('dts','HD MASTER AUDIO'),
        'dtsx':('dts','DTS:X'),
        'flac':('FLAC','LOSSLESS'),
        'mp3':('MP3','AUDIO'),
        'mp3float':('MP3','AUDIO'),
        'pcm':('PCM','LOSSLESS'),
        'pcm_bluray':('PCM','LOSSLESS'),
        'pcm_s16le':('PCM','LOSSLESS'),
        'pcm_s24le':('PCM','LOSSLESS'),
        'wma':('WMA','AUDIO'),
        'wmapro':('WMA PRO','AUDIO'),
        'vorbis':('VORBIS','AUDIO')}
    for key,(title,detail) in audio.items():
        put('audiocodec',key,audio_badge(title,detail))
    channels={'0':'0.0','1':'1.0','2':'2.0','3':'3.0',
              '4':'4.0','5':'5.0','6':'5.1',
              '7':'6.1','8':'7.1','10':'9.1'}
    for key,title in channels.items():
        put('audiochannels',key,channels_badge(title))
    return replacements

def preview(edited):
    keys=[
        'flags/default/resolution/1080.png',
        'flags/default/videocodec/h264.png',
        'flags/default/aspectratio/2.35.png',
        'flags/default/audiocodec/aac.png',
        'flags/default/audiochannels/2.png',
        'flags/default/resolution/2160.png',
        'flags/default/audiocodec/ac3.png',
        'flags/default/audiocodec/dtshd_ma.png']
    names=[PFX+'media/'+k for k in keys]
    images=[Image.open(BytesIO(edited[n])).convert('RGBA') for n in names if n in edited]
    if not images:return
    sheet=Image.new('RGB',(W*2+60,(H+58)*4+48),(7,14,23))
    d=ImageDraw.Draw(sheet)
    for i,im in enumerate(images):
        x=20+(i%2)*(W+20);y=18+(i//2)*(H+58)
        sheet.paste(im,(x,y),im)
        d.text((x+18,y+H+5),keys[i].split('/')[-1],font=text_font(23,False),fill=(197,219,234))
    PREVIEW.parent.mkdir(parents=True,exist_ok=True)
    sheet.save(PREVIEW,optimize=True)

def build():
    assert BASE.exists(), f'Missing reliable 1.1.25 ZIP: {BASE}'
    with ZipFile(BASE) as src:
        assert src.testzip() is None,'Bad base ZIP checksum'
        assert ET.fromstring(src.read(ADDON)).get('version')=='1.1.25'
        original=src.namelist()
        edits=asset_changes(src)
        assert len(edits)>=55,'Too few supported media assets'
        for q in ['ratings_glossy/tmdb.png','ratings_glossy/imdb.png',
                  'ratings_glossy/trakt.png','flags/default/mpaa/fsk-6.png']:
            assert PFX+'media/'+q not in edits
        addon=src.read(ADDON)
        newer,count=re.subn(rb'(<addon\s+[^>]*\bversion=")1\.1\.25(")',
                            rb'\g<1>1.1.26\2',addon,count=1)
        assert count==1
        OUT.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(OUT,'w',ZIP_DEFLATED,compresslevel=7) as dst:
            for zi in src.infolist():
                data = newer if zi.filename==ADDON else edits.get(zi.filename)
                if data is None:data=src.read(zi.filename)
                dst.writestr(zi,data)
        with ZipFile(OUT) as result:
            assert result.testzip() is None,'Test ZIP corrupted'
            assert result.namelist()==original
            assert ET.fromstring(result.read(ADDON)).get('version')=='1.1.26'
            for name in original:
                if name!=ADDON and name not in edits:
                    assert result.getinfo(name).CRC==src.getinfo(name).CRC, f'Unexpected change: {name}'
            # The rating bar, rating images and FSK logos are byte-for-byte untouched.
            for name in ['16x9/DialogVideoInfo.xml',
                'media/ratings_glossy/tmdb.png',
                'media/ratings_glossy/imdb.png',
                'media/ratings_glossy/trakt.png',
                'media/flags/default/mpaa/fsk-6.png']:
                key=PFX+name
                assert result.read(key)==src.read(key)
            for key in edits:
                im=Image.open(BytesIO(result.read(key)))
                im.verify()
        preview(edits)
        REPORT.parent.mkdir(parents=True,exist_ok=True)
        REPORT.write_text(
            f'Source: {BASE}\nTest: {OUT}\n'
            f'Skin version: 1.1.26\n'
            f'Media images upgraded: {len(edits)}\n'
            'Ratings, TMDB/IMDb/Trakt card geometry, FSK, Kodi item properties, '
            'media lookups, widgets, Filmpalast, themes and skin settings unchanged.\n'
            f'ZIP files: {len(original)}\nCRC + asset PNG verification: PASS\n'
            f'SHA256: {hashlib.sha256(OUT.read_bytes()).hexdigest()}\n'
            f'Size: {OUT.stat().st_size} bytes\n',encoding='utf-8')
        print(REPORT.read_text())
if __name__=='__main__':build()
