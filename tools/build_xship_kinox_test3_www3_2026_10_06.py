from pathlib import Path
import tempfile
import zipfile
import xml.etree.ElementTree as ET

REPO = Path.cwd()
BASE = REPO / "zips/plugin.video.xship/plugin.video.xship-2026.10.05.141.zip"
OUT = REPO / "test-builds/plugin.video.xship-2026.10.06.147-KINOX-TEST3-WWW3.zip"
VERSION = "2026.10.06.147"

if not BASE.exists():
    raise SystemExit(f"Missing base ZIP: {BASE}")

with tempfile.TemporaryDirectory() as td:
    work = Path(td)
    with zipfile.ZipFile(BASE, "r") as zf:
        zf.extractall(work)

    root = list(work.rglob("addon.xml"))[0].parent
    path = root / "scrapers/scrapers_source/de/kinox.py"
    src = path.read_text(encoding="utf-8-sig")

    if "import xbmc" not in src:
        src = src.replace("import json", "import json\nimport xbmc", 1)

    old_init = """        self.domains, self.base_link = self.getdomain()
        self.search_link = self.base_link +'/Search.html?q=%s'
"""
    new_init = """        # TEST3: pin KinoX to www3.kinoz.to for A/B comparison with www21.
        self.domains = ['www3.kinoz.to']
        self.base_link = 'https://www3.kinoz.to'
        self.search_link = self.base_link +'/Search.html?q=%s'
        xbmc.log('[KINOX-TEST3] pinned base=%s' % self.base_link, xbmc.LOGINFO)
"""
    if old_init not in src:
        raise SystemExit("KinoX init block not found")
    src = src.replace(old_init, new_init, 1)

    old = """                            if not r.startswith('http'): r = urljoin('https:', r)
                            isBlocked, hoster, url, prioHoster = isBlockedHoster(r)
"""

    new = """                            if not r.startswith('http'):
                                original_r = r
                                if r.startswith('//'):
                                    r = 'https:' + r
                                else:
                                    r = urljoin(self.base_link.rstrip('/') + '/', r)
                                xbmc.log('[KINOX-TEST3] normalized relative mirror | from=%s | to=%s' % (original_r, r), xbmc.LOGINFO)

                            if '/redirect/' in r and not getattr(self, '_diag_done', False):
                                self._diag_done = True
                                try:
                                    diag = cRequestHandler(r, caching=False, ignoreErrors=True)
                                    diag_html = diag.request() or ''
                                    diag_status = diag.getStatus()
                                    diag_final = diag.getRealUrl() or r
                                    low = diag_html.lower()
                                    markers = []
                                    for marker in ('captcha', 'turnstile', 'cf-chl', 'challenge', 'just a moment', 'cloudflare'):
                                        if marker in low:
                                            markers.append(marker)
                                    xbmc.log('[KINOX-TEST3] redirect diag | status=%s | final=%s | bytes=%s | markers=%s' % (
                                        diag_status, diag_final, len(diag_html), ','.join(markers) or 'none'
                                    ), xbmc.LOGINFO)
                                except Exception as diag_error:
                                    xbmc.log('[KINOX-TEST3] redirect diag failed | url=%s | error=%s' % (r, diag_error), xbmc.LOGWARNING)

                            isBlocked, hoster, url, prioHoster = isBlockedHoster(r)
"""

    if old not in src:
        raise SystemExit("KinoX relative URL block not found")
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
        f"{VERSION} KINOX TEST3 WWW3\n"
        "- KinoX wird testweise fest ueber https://www3.kinoz.to angesprochen.\n"
        "- Relative /redirect/-Links werden korrekt gegen www3.kinoz.to aufgeloest.\n"
        "- Erster Redirect wird diagnostisch mit Status, finaler URL und Challenge-Markern geloggt.\n"
        "- Keine CAPTCHA-/Cloudflare-Umgehung.\n\n"
    )
    if news is None:
        news = ET.SubElement(metadata, "news")
    news.text = entry + current
    tree.write(addon, encoding="UTF-8", xml_declaration=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(root.rglob("*")):
            if fp.is_file():
                zf.write(fp, Path("plugin.video.xship") / fp.relative_to(root))

with zipfile.ZipFile(OUT, "r") as zf:
    src = zf.read("plugin.video.xship/scrapers/scrapers_source/de/kinox.py").decode("utf-8")
    addon_text = zf.read("plugin.video.xship/addon.xml").decode("utf-8")
    assert "https://www3.kinoz.to" in src
    assert "[KINOX-TEST3] pinned base" in src
    assert "[KINOX-TEST3] redirect diag" in src
    assert f'version="{VERSION}"' in addon_text

print(OUT)
