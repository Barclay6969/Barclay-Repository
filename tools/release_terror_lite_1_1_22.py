#!/usr/bin/env python3
"""Rebuild the approved 1.1.22 widget-glass release from stable 1.1.18."""
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from io import BytesIO
from PIL import Image, ImageDraw, ImageFilter
import hashlib, re

src=Path("zips/skin.terror.lite/skin.terror.lite-1.1.18.zip")
dst=Path("zips/skin.terror.lite/skin.terror.lite-1.1.22.zip")
widgets_file="skin.terror.lite/16x9/Includes_Widgets.xml"
addon_file="skin.terror.lite/addon.xml"
asset_file="skin.terror.lite/media/homewidgets/glass_focus.png"
expected_png="c7c54d2ed07544539b16fe2c2ec88f837653e84fb9889e47812abd17e272df84"
assert src.is_file(),f"Missing source ZIP: {src}"
assert hashlib.sha256(src.read_bytes()).hexdigest()=="8012aba544f08008d46415b2cf6de4893d111c7b8c900915dc879d0fabfccf25","Unexpected 1.1.18 base"

size=512
img=Image.new('RGBA',(size,size),(0,0,0,0))
margin=2
r=32
for expand, alpha, blur, width in [(0,115,0,2),(2,78,3,2),(6,42,8,3),(10,18,15,4)]:
    layer=Image.new('RGBA',(size,size),(0,0,0,0))
    d=ImageDraw.Draw(layer)
    d.rounded_rectangle((margin-expand, margin-expand, size-margin+expand-1, size-margin+expand-1),
                        radius=r+expand, outline=(214,235,255,alpha), width=width)
    if blur:
        layer=layer.filter(ImageFilter.GaussianBlur(blur))
    img=Image.alpha_composite(img, layer)
fill=Image.new('RGBA',(size,size),(0,0,0,0))
d=ImageDraw.Draw(fill)
d.rounded_rectangle((margin+1,margin+1,size-margin-2,size-margin-2), radius=r-1, fill=(36,46,62,54))
img=Image.alpha_composite(img, fill)
hl=Image.new('RGBA',(size,size),(0,0,0,0))
h=ImageDraw.Draw(hl)
h.rounded_rectangle((margin+5, margin+5, size-margin-6, int(size*0.47)), radius=28, fill=(255,255,255,42))
hl=hl.filter(ImageFilter.GaussianBlur(26))
img=Image.alpha_composite(img, hl)
band=Image.new('RGBA',(size,size),(0,0,0,0))
b=ImageDraw.Draw(band)
b.rounded_rectangle((margin+8, int(size*0.34), size-margin-9, int(size*0.72)), radius=20, fill=(150,190,240,24))
band=band.filter(ImageFilter.GaussianBlur(26))
img=Image.alpha_composite(img, band)
sheen=Image.new('RGBA',(size,size),(0,0,0,0))
s=ImageDraw.Draw(sheen)
s.polygon([(28,26),(118,26),(262,260),(172,260)], fill=(255,255,255,36))
s.polygon([(175,22),(245,22),(400,250),(330,250)], fill=(255,255,255,22))
s.polygon([(330,26),(390,26),(500,165),(440,165)], fill=(255,255,255,16))
sheen=sheen.filter(ImageFilter.GaussianBlur(20))
img=Image.alpha_composite(img, sheen)
bottom=Image.new('RGBA',(size,size),(0,0,0,0))
bd=ImageDraw.Draw(bottom)
bd.rounded_rectangle((margin+18, int(size*0.80), size-margin-18, size-margin-18), radius=18, fill=(248,250,255,52))
bottom=bottom.filter(ImageFilter.GaussianBlur(14))
img=Image.alpha_composite(img, bottom)
rim=Image.new('RGBA',(size,size),(0,0,0,0))
rd=ImageDraw.Draw(rim)
rd.rounded_rectangle((margin+4, margin+3, size-margin-5, margin+15), radius=9, fill=(255,255,255,32))
rim=rim.filter(ImageFilter.GaussianBlur(2))
img=Image.alpha_composite(img, rim)
f=ImageDraw.Draw(img)
f.rounded_rectangle((margin,margin,size-margin-1,size-margin-1), radius=r, outline=(236,244,255,138), width=2)
f.rounded_rectangle((margin+2,margin+2,size-margin-3,size-margin-3), radius=r-2, outline=(178,198,228,68), width=1)

png_buf=BytesIO()
img.save(png_buf,format='PNG')
png=png_buf.getvalue()
actual_png=hashlib.sha256(png).hexdigest()
assert actual_png==expected_png,f"Focus image mismatch: {actual_png}"

with ZipFile(src) as source:
    root=ET.fromstring(source.read(widgets_file))
    n=0
    for tx in root.iter('texture'):
        if (tx.text or '').strip()=='listselect_fo.png' and tx.get('colordiffuse')=='$VAR[WidgetHighlightBarColor]':
            tx.text='homewidgets/glass_focus.png'
            tx.attrib.pop('colordiffuse')
            tx.set('border','8')
            n+=1
    assert n==7,f"Unexpected focus count: {n}"
    portrait=next(x for x in root.findall('include') if x.get('name')=='PortraitArt')
    focus=portrait.find('focusedlayout')
    assert focus is not None
    focus_grp=focus.find("control[@type='group']")
    assert focus_grp is not None
    poster=focus_grp.find("./control[@type='group']/control[@type='image']")
    assert poster is not None
    border=poster.find('bordertexture')
    assert border is not None and border.text=='thumbs/thumbnail_focused.png'
    poster.remove(border)
    bordersize=poster.find('bordersize')
    assert bordersize is not None
    poster.remove(bordersize)
    glass=ET.SubElement(focus_grp,'control',{'type':'image'})
    for key,value in (
        ('left','$PARAM[leftArt]'),('top','$PARAM[topArt]'),
        ('width','$PARAM[widthArt]'),('height','$PARAM[heightArt]')):
        ET.SubElement(glass,key).text=value
    ET.SubElement(glass,'texture',{'border':'8'}).text='homewidgets/glass_focus.png'
    new_widgets=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    metadata=source.read(addon_file)
    new_addon,count=re.subn(rb'(<addon\s+[^>]*\bversion=")1\.1\.18(")',rb'\g<1>1.1.22\2',metadata,count=1)
    assert count==1,"Skin version replacement failed"
    dst.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(dst,'w') as output:
        for info in source.infolist():
            data=source.read(info.filename)
            if info.filename==widgets_file: data=new_widgets
            elif info.filename==addon_file: data=new_addon
            output.writestr(info,data)
        output.writestr(asset_file,png)

with ZipFile(dst) as package:
    assert package.testzip() is None
    assert ET.fromstring(package.read(addon_file)).get('version')=='1.1.22'
    assert len(package.namelist())==1020
    actual_widget=ET.fromstring(package.read(widgets_file))
    assert sum((x.text or '').strip()=='homewidgets/glass_focus.png' for x in actual_widget.iter('texture'))==8
    assert hashlib.sha256(package.read(asset_file)).hexdigest()==expected_png
print('Built official Terror-Lite 1.1.22:', dst, dst.stat().st_size)
print('ZIP SHA256:',hashlib.sha256(dst.read_bytes()).hexdigest())
