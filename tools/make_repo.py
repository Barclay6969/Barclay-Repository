#!/usr/bin/env python3
import os, zipfile, hashlib, xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ADDONS_DIR = os.path.join(ROOT, "addons")
ZIPS_DIR = os.path.join(ROOT, "zips")

BASE_RAW_URL = "https://raw.githubusercontent.com/Barclay6969/Barclay-Repository/main/"

def md5_for_text(text):
    m = hashlib.md5(); m.update(text.encode("utf-8")); return m.hexdigest()

def gather_entries():
    entries = []
    rx = os.path.join(ADDONS_DIR, "repository.barclay", "addon.xml")
    if os.path.exists(rx):
        with open(rx, "r", encoding="utf-8") as f:
            entries.append(f.read())
    for r,_,files in os.walk(ZIPS_DIR):
        for fn in files:
            if fn.endswith(".zip"):
                zp = os.path.join(r, fn)
                try:
                    with zipfile.ZipFile(zp, "r") as zf:
                        for n in zf.namelist():
                            if n.endswith("addon.xml"):
                                entries.append(zf.read(n).decode("utf-8", errors="ignore").lstrip("\ufeff"))
                                break
                except Exception:
                    pass
    return entries

def write_addons_xml(entries):
    txt = "<addons>\n" + "\n".join(entries) + "\n</addons>\n"
    with open(os.path.join(ZIPS_DIR, "addons.xml"), "w", encoding="utf-8") as f:
        f.write(txt)
    with open(os.path.join(ZIPS_DIR, "addons.xml.md5"), "w", encoding="utf-8") as f:
        f.write(md5_for_text(txt))

def zip_repo():
    repo_id = "repository.barclay"
    repo_dir = os.path.join(ADDONS_DIR, repo_id)
    tree = ET.parse(os.path.join(repo_dir, "addon.xml")); root = tree.getroot()
    ver = root.attrib.get("version", "1.0.0")
    out = os.path.join(ZIPS_DIR, repo_id); os.makedirs(out, exist_ok=True)
    with zipfile.ZipFile(os.path.join(out, f"{repo_id}-{ver}.zip"), "w", zipfile.ZIP_DEFLATED) as zf:
        for rr,_,files in os.walk(repo_dir):
            for fn in files:
                ap = os.path.join(rr, fn)
                rel = os.path.relpath(ap, os.path.dirname(repo_dir))
                zf.write(ap, rel)

def main():
    write_addons_xml(gather_entries())
    zip_repo()
    print("Fertig gebaut.")

if __name__ == "__main__":
    main()

