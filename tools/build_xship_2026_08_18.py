from pathlib import Path
import hashlib
import re
import sys
import xml.etree.ElementTree as ET

NEW_VERSION = "2026.08.18"
OLD_VERSION = "2026.08.17.2"


def patch_addon(root: Path):
    addon = root / "addon.xml"
    text = addon.read_text(encoding="utf-8")
    text, n = re.subn(
        rf'version="{re.escape(OLD_VERSION)}"',
        f'version="{NEW_VERSION}"',
        text,
        count=1,
    )
    if n != 1:
        raise RuntimeError(f"addon.xml version {OLD_VERSION} not found")
    addon.write_text(text, encoding="utf-8")

    candidates = []
    for p in root.rglob("filmo.py"):
        try:
            t = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if "SITE_IDENTIFIER = 'filmo'" in t and "def _mint(" in t:
            candidates.append((p, t))
    if len(candidates) != 1:
        raise RuntimeError(f"expected exactly one Filmo scraper, found {len(candidates)}")

    filmo, ftext = candidates[0]
    lines = ftext.splitlines()
    replaced = False
    for i, line in enumerate(lines):
        if "match = re.search(r'href=" in line and "redirect_html" in line:
            if i + 1 >= len(lines):
                raise RuntimeError("Filmo href fallback return line missing")
            if "return unescape(match.group(1)).strip() if match else" not in lines[i + 1]:
                raise RuntimeError("unexpected Filmo href fallback implementation")
            indent = line[: len(line) - len(line.lstrip())]
            replacement = [
                indent + r"""for match in re.finditer(r'(?is)<a\b[^>]*href=["\']([^"\']+)["\']', redirect_html or ''):""",
                indent + "    candidate = unescape(match.group(1)).strip()",
                indent + "    if candidate.startswith(('http://', 'https://')) and self.domain.lower() not in candidate.lower():",
                indent + "        return candidate",
                indent + "return ''",
            ]
            lines[i : i + 2] = replacement
            replaced = True
            break
    if not replaced:
        raise RuntimeError("Filmo external href fallback not found")

    filmo.write_text("\n".join(lines) + "\n", encoding="utf-8")
    compile(filmo.read_text(encoding="utf-8"), str(filmo), "exec")

    sample = """<html><head><link rel="canonical" href="https://filmo.to/n/hYWQI0WBLjL82sfpqVsafXL3nxkGVnr4"></head>
<body><a href="https://bysezejataos.com/d/n0ligjzogspc" target="_blank">Video extern öffnen</a></body></html>"""
    picked = ""
    for m in re.finditer(r"""(?is)<a\b[^>]*href=["']([^"']+)["']""", sample):
        candidate = m.group(1).strip()
        if candidate.startswith(("http://", "https://")) and "filmo.to" not in candidate.lower():
            picked = candidate
            break
    if picked != "https://bysezejataos.com/d/n0ligjzogspc":
        raise RuntimeError(f"HAR regression failed: {picked!r}")

    changelog = root / "changelog.txt"
    entry = (
        "2026.08.18\n"
        "- Filmo: externe Hoster-Zwischenseiten werden korrekt ausgewertet.\n"
        "- BYSE-Streams werden erkannt und an ResolveURL übergeben.\n\n"
    )
    if changelog.exists():
        c = changelog.read_text(encoding="utf-8")
        if "2026.08.18" not in c:
            marker = "xShip – Changelog\n\n"
            c = c.replace(marker, marker + entry, 1) if marker in c else entry + c
            changelog.write_text(c, encoding="utf-8")
    else:
        changelog.write_text("xShip – Changelog\n\n" + entry, encoding="utf-8")

    tree = ET.parse(addon)
    rootxml = tree.getroot()
    if rootxml.get("version") != NEW_VERSION:
        raise RuntimeError("packaged addon.xml version validation failed")
    metadata = next(
        (e for e in rootxml.findall("extension") if e.get("point") == "xbmc.addon.metadata"),
        None,
    )
    if metadata is None:
        raise RuntimeError("metadata extension not found")
    news = metadata.find("news")
    if news is None:
        news = ET.SubElement(metadata, "news")
    old_news = news.text or ""
    new_head = (
        "2026.08.18\n"
        "- Filmo: BYSE-Streams auf externen Hoster-Zwischenseiten werden nun erkannt.\n"
        "- BYSE-Links werden zur Wiedergabe an ResolveURL weitergereicht.\n\n"
    )
    if not old_news.startswith("2026.08.18"):
        news.text = new_head + old_news
    ET.indent(tree, space="  ")
    xml = ET.tostring(rootxml, encoding="unicode")
    addon.write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + xml + "\n",
        encoding="utf-8",
    )
    return filmo, picked


def patch_repo_metadata(addons_xml: Path):
    s = addons_xml.read_text(encoding="utf-8")
    s, n = re.subn(
        rf'(<addon id="plugin\.video\.xship" version="){re.escape(OLD_VERSION)}(" )',
        rf'\g<1>{NEW_VERSION}\2',
        s,
        count=1,
    )
    if n != 1:
        raise RuntimeError(f"xShip {OLD_VERSION} entry not found in addons.xml")

    block_re = re.compile(r'(<addon id="plugin\.video\.xship".*?</addon>)', re.S)
    bm = block_re.search(s)
    if not bm:
        raise RuntimeError("xShip addon block not found")
    block = bm.group(1)
    nm = re.search(r"<news>(.*?)</news>", block, re.S)
    if not nm:
        raise RuntimeError("xShip news block not found")
    old_news = nm.group(1)
    new_head = (
        "2026.08.18\n"
        "- Filmo: BYSE-Streams auf externen Hoster-Zwischenseiten werden nun erkannt.\n"
        "- BYSE-Links werden zur Wiedergabe an ResolveURL weitergereicht.\n\n"
    )
    if not old_news.startswith("2026.08.18"):
        block = block[: nm.start(1)] + new_head + old_news + block[nm.end(1) :]
        s = s[: bm.start(1)] + block + s[bm.end(1) :]

    addons_xml.write_text(s, encoding="utf-8")
    digest = hashlib.md5(addons_xml.read_bytes()).hexdigest()
    addons_xml.with_name("addons.xml.md5").write_text(digest + "\n", encoding="ascii")
    return digest


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: build_xship_2026_08_18.py <plugin-root> <addons.xml>")
    root = Path(sys.argv[1])
    addons_xml = Path(sys.argv[2])
    filmo, picked = patch_addon(root)
    digest = patch_repo_metadata(addons_xml)
    print("Patched:", filmo)
    print("HAR regression target:", picked)
    print("addons.xml md5:", digest)


if __name__ == "__main__":
    main()
