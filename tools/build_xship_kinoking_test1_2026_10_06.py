from pathlib import Path
import json
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET

REPO = Path.cwd()
BASE = REPO / "zips/plugin.video.xship/plugin.video.xship-2026.10.05.141.zip"
OUT = REPO / "test-builds/plugin.video.xship-2026.10.06.142-KINOKING-TEST1.zip"
VERSION = "2026.10.06.142"

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

    kg_path = root / "scrapers/scrapers_source/de/kinoking.py"
    kg = kg_path.read_text(encoding="utf-8-sig")

    # KinoKing movie pages now expose all mirrors in:
    #   const SERVERS = [...]
    # Parse those mirrors directly. Keep the old chk_year path as fallback.
    pattern = re.compile(
        r"        if season == 0:\n"
        r"            self\.list = \[\]\n"
        r"            with concurrent\.futures\.ThreadPoolExecutor\(\) as executor:\n"
        r"                futures = \[executor\.submit\(self\.chk_year, i, year\) for i in links\]\n"
        r"                concurrent\.futures\.wait\(futures\)\n"
        r"            if len\(self\.list\) > 0: hoster = self\.list\n"
        r"        else:\n"
    )

    replacement = """        if season == 0:
            self.list = []
            seen_hoster = set()

            for movie_url in links:
                parsed_servers = False
                try:
                    movie_html = cRequestHandler(movie_url).request()
                    m_servers = re.search(r'const\\s+SERVERS\\s*=\\s*(\\[[\\s\\S]*?\\])\\s*;', movie_html, re.I)
                    if m_servers:
                        servers = json.loads(m_servers.group(1))
                        mirror_count = 0
                        for server in servers if isinstance(servers, list) else []:
                            if not isinstance(server, dict):
                                continue
                            mirrors = server.get('mirrors') or []
                            if isinstance(mirrors, str):
                                mirrors = [mirrors]
                            for mirror in mirrors:
                                mirror = str(mirror or '').strip()
                                if not mirror or mirror in seen_hoster:
                                    continue
                                seen_hoster.add(mirror)
                                hoster.append(mirror)
                                mirror_count += 1
                        if mirror_count:
                            parsed_servers = True
                            log_utils.log('[KINOKING-TEST1] SERVERS parsed | url=%s | mirrors=%s' % (movie_url, mirror_count), log_utils.LOGINFO)
                except Exception as e:
                    log_utils.log('[KINOKING-TEST1] SERVERS parse failed | url=%s | error=%s' % (movie_url, e), log_utils.LOGWARNING)

                # Compatibility fallback for older KinoKing movie markup.
                if not parsed_servers:
                    try:
                        self.chk_year(movie_url, year)
                        log_utils.log('[KINOKING-TEST1] legacy chk_year fallback | url=%s' % movie_url, log_utils.LOGINFO)
                    except Exception:
                        pass

            if len(self.list) > 0:
                for old_link in self.list:
                    if old_link and old_link not in seen_hoster:
                        seen_hoster.add(old_link)
                        hoster.append(old_link)
        else:
"""

    kg2, n = pattern.subn(replacement, kg, count=1)
    if n != 1:
        raise SystemExit("KinoKing movie branch insertion point not found in 2026.10.05.141")

    # Add useful movie-search diagnostics without altering the working series flow.
    needle = "        if len(links) == 0: return self.sources\n\n"
    diag = (
        "        if season == 0:\n"
        "            log_utils.log('[KINOKING-TEST1] movie search | titles=%s | year=%s | links=%s' % (titles, year, links), log_utils.LOGINFO)\n"
        "        if len(links) == 0: return self.sources\n\n"
    )
    if needle not in kg2:
        raise SystemExit("KinoKing links diagnostic insertion point not found")
    kg2 = kg2.replace(needle, diag, 1)
    kg_path.write_text(kg2, encoding="utf-8", newline="\n")

    # Test build version only; production repository metadata stays untouched.
    addon = root / "addon.xml"
    tree = ET.parse(addon)
    ar = tree.getroot()
    ar.set("version", VERSION)
    metadata = next(e for e in ar.findall("extension") if e.get("point") == "xbmc.addon.metadata")
    news = metadata.find("news")
    current = (news.text or "").strip() if news is not None else ""
    entry = (
        f"{VERSION} KINOKING TEST1\n"
        "- KinoKing Filme: neue SERVERS-Struktur der Filmseite wird direkt ausgewertet.\n"
        "- Alle mirrors aus const SERVERS werden an den bestehenden xShip-Resolver uebergeben.\n"
        "- Alte KinoKing-Filmlogik bleibt als Fallback erhalten; Serienlogik bleibt unveraendert.\n\n"
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

# Verify final ZIP.
with zipfile.ZipFile(OUT, "r") as zf:
    kg = zf.read("plugin.video.xship/scrapers/scrapers_source/de/kinoking.py").decode("utf-8")
    addon_text = zf.read("plugin.video.xship/addon.xml").decode("utf-8")
    assert "const\\s+SERVERS" in kg
    assert "[KINOKING-TEST1] SERVERS parsed" in kg
    assert "legacy chk_year fallback" in kg
    assert f'version="{VERSION}"' in addon_text

print(OUT)
