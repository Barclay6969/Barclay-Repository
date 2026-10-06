from pathlib import Path
import tempfile
import zipfile
import xml.etree.ElementTree as ET

REPO = Path.cwd()
BASE = REPO / "zips/plugin.video.xship/plugin.video.xship-2026.10.05.141.zip"
OUT = REPO / "test-builds/plugin.video.xship-2026.10.06.145-KINOX-TEST1.zip"
VERSION = "2026.10.06.145"

if not BASE.exists():
    raise SystemExit(f"Missing base ZIP: {BASE}")

with tempfile.TemporaryDirectory() as td:
    work = Path(td)
    with zipfile.ZipFile(BASE, "r") as zf:
        zf.extractall(work)

    addons = list(work.rglob("addon.xml"))
    if not addons:
        raise SystemExit("addon.xml not found")
    root = addons[0].parent

    path = root / "scrapers/scrapers_source/de/kinox.py"
    src = path.read_text(encoding="utf-8-sig")

    if "import xbmc" not in src:
        src = src.replace("import json", "import json\nimport xbmc", 1)

    old = """                            if not r.startswith('http'): r = urljoin('https:', r)
                            isBlocked, hoster, url, prioHoster = isBlockedHoster(r)
"""

    new = """                            if not r.startswith('http'):
                                original_r = r
                                if r.startswith('//'):
                                    r = 'https:' + r
                                else:
                                    r = urljoin(self.base_link.rstrip('/') + '/', r)
                                xbmc.log('[KINOX-TEST1] normalized relative mirror | from=%s | to=%s' % (original_r, r), xbmc.LOGINFO)
                            isBlocked, hoster, url, prioHoster = isBlockedHoster(r)
"""

    if old not in src:
        raise SystemExit("Current KinoX relative URL block not found")

    src = src.replace(old, new, 1)
    path.write_text(src, encoding="utf-8", newline="\n")

    addon = root / "addon.xml"
    tree = ET.parse(addon)
    ar = tree.getroot()
    ar.set("version", VERSION)
    metadata = next(e for e in ar.findall("extension") if e.get("point") == "xbmc.addon.metadata")
    news = metadata.find("news")
    current = (news.text or "").strip() if news is not None else ""
    entry = (
        f"{VERSION} KINOX TEST1\n"
        "- KinoX: relative /redirect/-Links werden gegen die aktive KinoX/KinoZ-Domain aufgeloest.\n"
        "- Protocol-relative //host/-Links werden weiterhin mit https behandelt.\n"
        "- Keine weiteren Provider oder Suchlogiken geaendert.\n\n"
    )
    if news is None:
        news = ET.SubElement(metadata, "news")
    news.text = entry + current
    tree.write(addon, encoding="UTF-8", xml_declaration=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(root.rglob("*")):
            if fp.is_file():
                zf.write(fp, Path("plugin.video.xship") / fp.relative_to(root))

with zipfile.ZipFile(OUT, "r") as zf:
    src = zf.read("plugin.video.xship/scrapers/scrapers_source/de/kinox.py").decode("utf-8")
    addon_text = zf.read("plugin.video.xship/addon.xml").decode("utf-8")
    assert "urljoin(self.base_link.rstrip('/') + '/', r)" in src
    assert "[KINOX-TEST1] normalized relative mirror" in src
    assert "import xbmc" in src
    assert f'version="{VERSION}"' in addon_text

print(OUT)
