from pathlib import Path
import tempfile
import zipfile
import xml.etree.ElementTree as ET

REPO = Path.cwd()
BASE = REPO / "zips/plugin.video.xship/plugin.video.xship-2026.10.05.141.zip"
OUT = REPO / "test-builds/plugin.video.xship-2026.10.06.146-KINOX-TEST2-DIAG.zip"
VERSION = "2026.10.06.146"

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

    old = """                            if not r.startswith('http'): r = urljoin('https:', r)
                            isBlocked, hoster, url, prioHoster = isBlockedHoster(r)
"""

    new = """                            if not r.startswith('http'):
                                original_r = r
                                if r.startswith('//'):
                                    r = 'https:' + r
                                else:
                                    r = urljoin(self.base_link.rstrip('/') + '/', r)
                                xbmc.log('[KINOX-TEST2] normalized relative mirror | from=%s | to=%s' % (original_r, r), xbmc.LOGINFO)

                            # Diagnostic only: inspect the first KinoX redirect response.
                            # No CAPTCHA/Turnstile solving or bypass is attempted.
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
                                    xbmc.log('[KINOX-TEST2] redirect diag | status=%s | final=%s | bytes=%s | markers=%s' % (
                                        diag_status, diag_final, len(diag_html), ','.join(markers) or 'none'
                                    ), xbmc.LOGINFO)
                                except Exception as diag_error:
                                    xbmc.log('[KINOX-TEST2] redirect diag failed | url=%s | error=%s' % (r, diag_error), xbmc.LOGWARNING)

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
        f"{VERSION} KINOX TEST2 DIAG\n"
        "- KinoX relative Redirect-Links werden korrekt normalisiert.\n"
        "- Nur der erste /redirect/-Link wird diagnostisch abgerufen.\n"
        "- Loggt HTTP-Status, finale URL, Antwortgroesse und erkennbare CAPTCHA/Challenge-Marker.\n"
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
    assert "[KINOX-TEST2] redirect diag" in src
    assert "getRealUrl()" in src
    assert "'turnstile'" in src
    assert "urljoin(self.base_link.rstrip('/') + '/', r)" in src
    assert f'version="{VERSION}"' in addon_text

print(OUT)
