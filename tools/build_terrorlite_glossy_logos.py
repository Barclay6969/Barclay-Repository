#!/usr/bin/env python3
"""Build an isolated TerrorLite 1.1.23 glossy metadata badge test from 1.1.22.

Keep all working Filmpalast, widget, ratings and IMDb bridge logic unchanged.
Only metadata badge images, ratings group presentation, media flag tint and version change.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from io import BytesIO
from xml.etree import ElementTree as ET
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import re, hashlib, math

SOURCE = Path("zips/skin.terror.lite/skin.terror.lite-1.1.22.zip")
DEST = Path("test-builds/skin.terror.lite-1.1.23-LOGOS-TEST.zip")
ROOT = "skin.terror.lite/"
INFO_XML = ROOT + "16x9/DialogVideoInfo.xml"
COMMON_XML = ROOT + "16x9/Includes_CommonValues.xml"
ADDON_XML = ROOT + "addon.xml"
MEDIA = ROOT + "media/"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def rgba(hexstr, a=255):
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i+2],16) for i in (0,2,4))+(a,)

def font(sz, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, sz)

def center_text(draw, box, text, size, color, bold=True):
    f=font(size,bold)
    # shrink exceptionally long names without chopping
    while draw.textbbox((0,0),text,font=f)[2] > box[2]-box[0]-8 and size > 16:
        size-=1
        f=font(size,bold)
    bounds=draw.textbbox((0,0),text,font=f)
    w,h=bounds[2]-bounds[0],bounds[3]-bounds[1]
    x=(box[0]+box[2]-w)/2-bounds[0]
    y=(box[1]+box[3]-h)/2-bounds[1]
    draw.text((int(x),int(y)),text,font=f,fill=color,stroke_width=0)

def glass(w,h,accent="A9BFDB",roundness=24,fill_alpha=228):
    """Alpha-aware black-silver frame with a restrained tinted highlight."""
    base=Image.new("RGBA",(w,h))
    d=ImageDraw.Draw(base)
    # Soft exterior glow: restrained enough to suit black-silver skin.
    glow=Image.new("RGBA",(w,h))
    g=ImageDraw.Draw(glow)
    g.rounded_rectangle((8,8,w-9,h-9),radius=roundness,
                        outline=rgba(accent,92),width=5)
    glow=glow.filter(ImageFilter.GaussianBlur(10))
    base.alpha_composite(glow)
    panel=Image.new("RGBA",(w,h))
    p=ImageDraw.Draw(panel)
    p.rounded_rectangle((5,5,w-6,h-6),radius=roundness,
                        fill=(8,13,20,fill_alpha),outline=(207,220,235,210),width=3)
    p.rounded_rectangle((10,10,w-11,h-11),radius=roundness-5,
                        outline=rgba(accent,135),width=2)
    # Top-to-bottom glass gradient masked to rounded interior.
    grad=Image.new("RGBA",(w,h))
    pix=grad.load()
    for y in range(h):
        t=y/max(1,h-1)
        a=int(82*(1-t)**2+13)
        for x in range(w):
            pix[x,y]=(210,226,244,a)
    mask=Image.new("L",(w,h))
    md=ImageDraw.Draw(mask)
    md.rounded_rectangle((13,12,w-14,h-13),radius=roundness-7,fill=255)
    grad.putalpha(Image.composite(grad.getchannel("A"),Image.new("L",(w,h)),mask))
    panel.alpha_composite(grad)
    sheen=Image.new("RGBA",(w,h))
    sh=ImageDraw.Draw(sheen)
    sh.polygon([(w//6,14),(w//3,14),(int(w*.65),int(h*.52)),(int(w*.52),int(h*.52))],
               fill=(255,255,255,28))
    sheen=sheen.filter(ImageFilter.GaussianBlur(10))
    panel.alpha_composite(sheen)
    last=ImageDraw.Draw(panel)
    last.line((25,14,w-30,14),fill=(250,254,255,150),width=2)
    last.rounded_rectangle((16,h-19,w-17,h-14),radius=3,fill=rgba(accent,170))
    base.alpha_composite(panel)
    return base

def pack_png(im):
    o=BytesIO()
    im.save(o,format="PNG",optimize=True)
    return o.getvalue()

def rating_plate(brand,accent):
    w,h=310,180
    im=glass(w,h,accent,32)
    d=ImageDraw.Draw(im)
    # All top-center space stays clear for Kodi's live numeric rating.
    d.line((26,112,w-27,112),fill=rgba(accent,175),width=2)
    center_text(d,(20,115,w-20,165),brand,41,
                rgba(accent) if brand!="IMDb" else rgba("FFD45E"))
    return pack_png(im)

def fsk_plate(age,accent):
    w=h=240
    im=glass(w,h,accent,35,247)
    d=ImageDraw.Draw(im)
    d.ellipse((34,34,w-35,h-35),outline=rgba(accent,175),width=5)
    d.ellipse((42,42,w-43,h-43),outline=(231,241,251,112),width=2)
    center_text(d,(28,37,w-28,91),"FSK",31,rgba("F2F6FC"))
    center_text(d,(24,90,w-24,200),str(age),102,rgba("FFFFFF"))
    return pack_png(im)

def flat_plate(primary,secondary="",accent="A9BFDB",kind="video"):
    w,h=360,180
    im=glass(w,h,accent,25,245)
    d=ImageDraw.Draw(im)
    large=primary
    psize=69 if len(primary)<7 else (55 if len(primary)<11 else 43)
    if secondary:
        center_text(d,(20,18,w-20,108),large,psize,rgba("FFFFFF"))
        d.line((40,115,w-41,115),fill=rgba(accent,180),width=2)
        center_text(d,(18,121,w-18,161),secondary,29,rgba(accent))
    else:
        center_text(d,(16,32,w-16,147),large,psize,rgba("FFFFFF"))
    return pack_png(im)

# Generate fully resolved media flags. Filenames are intentionally identical
# to existing Kodi flag lookup targets, leaving all media detection untouched.
new_media={}
def asset(name,data):
    new_media[MEDIA+name]=data

for brand,acc in [("TMDB","22CDE8"),("IMDb","F7BC43"),("TRAKT","EE598A")]:
    asset("ratings_glossy/"+brand.lower()+".png",rating_plate(brand,acc))

for age,acc in [(0,"DDE5F0"),(6,"EAC056"),(12,"54D49B"),(16,"56ABF1"),(18,"FF5C6B")]:
    asset(f"flags/default/mpaa/fsk-{age}.png",fsk_plate(age,acc))

res={
    "2160":("4K","ULTRA HD","E6BD65"),"4k":("4K","ULTRA HD","E6BD65"),
    "1440":("2K","QUAD HD","DAB76C"),"2k":("2K","QUAD HD","DAB76C"),
    "2048":("2K","QUAD HD","DAB76C"),
    "1080":("1080p","FULL HD","A9D9FD"),
    "720":("720p","HD","A7C4E2"),
    "576":("576p","SD","A9BFDB"),"540":("540p","SD","A9BFDB"),
    "480":("480p","SD","A9BFDB"),"288":("288p","SD","A9BFDB"),
    "hd":("HD","","A9D9FD")
}
for k,(p,s,c) in res.items():
    asset("flags/default/resolution/"+k+".png",flat_plate(p,s,c))

codecs={
    "h264":("H.264","MPEG-4 AVC"),
    "avc1":("H.264","MPEG-4 AVC"),
    "hevc":("H.265","HEVC"),
    "hev1":("H.265","HEVC"),
    "mpeg2video":("MPEG-2","VIDEO"),
    "vc-1":("VC-1","VIDEO"),
    "bluray":("BLU-RAY","VIDEO"),
    "bluray3d":("BLU-RAY","3D"),
    "mkv":("MKV","VIDEO"),
    "mp4":("MP4","VIDEO"),
    "xvid":("XVID","VIDEO"),
    "divx":("DIVX","VIDEO"),
    "hdtv":("HDTV","VIDEO"),
    "web-dl":("WEB-DL","VIDEO"),
    "dvd":("DVD","VIDEO")
}
for k,(p,s) in codecs.items():
    asset("flags/default/videocodec/"+k+".png",flat_plate(p,s,"B6C9E4"))

audios={
    "aac":("AAC","AUDIO","90DFFE"),
    "ac3":("DOLBY","DIGITAL","E8BD5B"),
    "eac3":("DOLBY","DIGITAL PLUS","E8BD5B"),
    "atmos":("DOLBY","ATMOS","E8BD5B"),
    "truehd":("DOLBY","TRUEHD","E8BD5B"),
    "dts":("dts","SURROUND","E5AB54"),
    "dca":("dts","SURROUND","E5AB54"),
    "dtshd_ma":("dts","HD MASTER AUDIO","E5AB54"),
    "dtshd_hra":("dts","HD HIGH RES","E5AB54"),
    "dtsma":("dts","HD MASTER AUDIO","E5AB54"),
    "dtsx":("dts:X","AUDIO","E5AB54"),
    "flac":("FLAC","LOSSLESS","B6C9E4"),
    "mp3":("MP3","AUDIO","A8BEDC"),
    "mp3float":("MP3","AUDIO","A8BEDC"),
    "pcm":("PCM","LOSSLESS","B6C9E4"),
    "pcm_bluray":("PCM","LOSSLESS","B6C9E4"),
    "pcm_s16le":("PCM","LOSSLESS","B6C9E4"),
    "pcm_s24le":("PCM","LOSSLESS","B6C9E4")
}
for k,(p,s,c) in audios.items():
    asset("flags/default/audiocodec/"+k+".png",flat_plate(p,s,c,"audio"))

channels={"0":"0.0","1":"1.0","2":"2.0","3":"3.0","4":"4.0",
          "5":"5.0","6":"5.1","7":"6.1","8":"7.1","10":"9.1"}
for k,p in channels.items():
    asset("flags/default/audiochannels/"+k+".png",
          flat_plate(p,"CHANNELS","9EDCEB","audio"))

ratios={
    "1.33":"4:3","1.37":"4:3","1.66":"1.66:1",
    "1.78":"16:9","1.85":"1.85:1","2.20":"2.20:1",
    "2.35":"21:9","2.40":"21:9","2.55":"2.55:1","2.76":"2.76:1"
}
for k,p in ratios.items():
    asset("flags/default/aspectratio/"+k+".png",
          flat_plate(p,"ASPECT","B5C8E0"))

if not SOURCE.exists():
    raise SystemExit(f"Stable 1.1.22 ZIP not present: {SOURCE}")
DEST.parent.mkdir(parents=True,exist_ok=True)
with ZipFile(SOURCE,"r") as inputzip:
    original_names=inputzip.namelist()
    assert len(original_names)==1020,f"Unexpected source file count: {len(original_names)}"
    assert inputzip.testzip() is None,"Source ZIP is invalid"
    raw_info=inputzip.read(INFO_XML)
    root=ET.fromstring(raw_info)
    changed=[]
    # Preserve all <visible> rules and dynamic <label>$VAR[...]</label> values.
    for description,icon in [("TMDB Bewertung","tmdb"),("IMDb Bewertung","imdb"),("Trakt Bewertung","trakt")]:
        matches=[x for x in root.iter("control") if x.get("type")=="group"
                 and x.findtext("description")==description]
        assert len(matches)==1, f"Expected exactly one {description}, found {len(matches)}"
        grp=matches[0]
        labels=[x for x in grp if x.tag=="control" and x.get("type")=="label"]
        assert len(labels)==2, f"Unexpected rating controls: {description}"
        assert labels[0].findtext("label","").startswith("$VAR[TerrorOmega"),description
        assert (labels[1].findtext("label") or "").casefold() in ("tmdb","imdb","trakt")
        grp.remove(labels[1])
        image=ET.Element("control",{"type":"image"})
        ET.SubElement(image,"left").text="0"
        ET.SubElement(image,"top").text="0"
        ET.SubElement(image,"width").text="155"
        ET.SubElement(image,"height").text="90"
        ET.SubElement(image,"aspectratio").text="stretch"
        ET.SubElement(image,"texture").text="ratings_glossy/"+icon+".png"
        first_control=next(i for i,c in enumerate(grp) if c.tag=="control")
        grp.insert(first_control,image)
        # Foreground number remains live, bright and readable.
        col=labels[0].find("textcolor")
        assert col is not None
        col.text="FFFFFFFF"
        changed.append(description)
    new_info=ET.tostring(root,encoding="utf-8",xml_declaration=True)

    common=ET.fromstring(inputzip.read(COMMON_XML))
    vals=[x for x in common.findall("include") if x.get("name")=="MediaFlagValues"]
    assert len(vals)==1
    tint=vals[0].find("colordiffuse")
    assert tint is not None and tint.text=="grey"
    tint.text="FFFFFFFF"
    new_common=ET.tostring(common,encoding="utf-8",xml_declaration=True)

    addon=inputzip.read(ADDON_XML)
    old=ET.fromstring(addon)
    assert old.get("id")=="skin.terror.lite" and old.get("version")=="1.1.22"
    new_addon,cnt=re.subn(rb'(<addon\s+[^>]*\bversion=")1\.1\.22(")',
                          rb'\g<1>1.1.23\2',addon,count=1)
    assert cnt==1 and ET.fromstring(new_addon).get("version")=="1.1.23"

    updates={INFO_XML:new_info,COMMON_XML:new_common,ADDON_XML:new_addon}
    allpaths=set(original_names)
    overwritten_media=set(new_media)&allpaths
    added_media=set(new_media)-allpaths
    with ZipFile(DEST,"w",compression=ZIP_DEFLATED,compresslevel=7) as out:
        for zi in inputzip.infolist():
            payload=updates.get(zi.filename)
            if payload is None:
                payload=new_media.get(zi.filename)
            if payload is None:
                payload=inputzip.read(zi.filename)
            out.writestr(zi,payload)
        for p in sorted(added_media):
            out.writestr(p,new_media[p])

with ZipFile(DEST,"r") as built:
    assert built.testzip() is None,"Built ZIP failed CRC"
    assert len(built.namelist())==len(original_names)+len(added_media)
    assert ET.fromstring(built.read(ADDON_XML)).get("version")=="1.1.23"
    assert all(p in built.namelist() for p in new_media)
    for description in changed:
        assert description in built.read(INFO_XML).decode("utf-8")

report=Path("development/terrorlite-glossy/build-report.txt")
report.parent.mkdir(parents=True,exist_ok=True)
report.write_text(
    f"Base: {SOURCE}\nTest: {DEST}\n"
    f"Original members: {len(original_names)}\n"
    f"Upgraded existing flag PNGs: {len(overwritten_media)}\n"
    f"Added PNGs: {len(added_media)}\n"
    f"Preserved all IMDb and TMDb/Trakt rating lookups and all Filmpalast widgets.\n"
    f"Only edited XML: {INFO_XML}, {COMMON_XML}, {ADDON_XML}\n"
    f"ZIP SHA256: {hashlib.sha256(DEST.read_bytes()).hexdigest()}\n"
    f"ZIP bytes: {DEST.stat().st_size}\n",encoding="utf-8")
print(report.read_text())
