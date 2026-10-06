from pathlib import Path
import tempfile
import zipfile
import xml.etree.ElementTree as ET

REPO = Path.cwd()
BASE = REPO / "zips/plugin.video.xship/plugin.video.xship-2026.10.05.141.zip"
OUT = REPO / "test-builds/plugin.video.xship-2026.10.06.143-KINOKING-TEST2.zip"
VERSION = "2026.10.06.143"

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
    if "import requests" not in kg:
        kg = kg.replace("import json", "import json\nimport requests", 1)

    old = """        else:
            self.list = []
            pages = [self.base_link + '/movie.php?id=%s' % mid for mid in candidates]
            if pages:
                with concurrent.futures.ThreadPoolExecutor() as ex:
                    concurrent.futures.wait([ex.submit(self.chk_year, p, year) for p in pages])
            links = list(self.list)
"""

    new = """        else:
            self.list = []
            pages = [self.base_link + '/movie.php?id=%s' % mid for mid in candidates]
            seen_movie_links = set()

            for page in pages:
                parsed_servers = False
                try:
                    session = requests.Session()
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                        'Accept-Language': 'de-CH,de;q=0.9,en;q=0.8',
                        'Referer': self.base_link + '/',
                        'Connection': 'keep-alive'
                    }
                    session.get(self.base_link + '/', headers=headers, timeout=6)
                    r = session.get(page, headers=headers, timeout=8)
                    print('[KINOKING-TEST2] movie GET | page=%s | status=%s | bytes=%s | cookies=%s' % (page, r.status_code, len(r.content or b''), len(session.cookies)))
                    html = r.text or ''

                    # Keep the previous year guard where KinoKing exposes a year.
                    ym = re.search(r'<title>.*?(\\d{4})', html, re.I | re.S)
                    if ym and year and int(ym.group(1)) != int(year):
                        continue

                    # Current KinoKing movie pages expose every provider/mirror
                    # as JSON in: const SERVERS = [...]
                    sm = re.search(r'const\\s+SERVERS\\s*=\\s*(\\[[\\s\\S]*?\\])\\s*;', html, re.I)
                    if sm:
                        servers = json.loads(sm.group(1))
                        mirror_count = 0
                        for server in servers if isinstance(servers, list) else []:
                            if not isinstance(server, dict):
                                continue
                            mirrors = server.get('mirrors') or []
                            if isinstance(mirrors, str):
                                mirrors = [mirrors]
                            for mirror in mirrors:
                                mirror = str(mirror or '').replace('\\/', '/').strip()
                                if not mirror or mirror in seen_movie_links:
                                    continue
                                seen_movie_links.add(mirror)
                                self.list.append(mirror)
                                mirror_count += 1

                        if mirror_count:
                            parsed_servers = True
                            print('[KINOKING-TEST2] SERVERS parsed | page=%s | mirrors=%s' % (page, mirror_count))
                except Exception as e:
                    print('[KINOKING-TEST2] SERVERS parse failed | page=%s | error=%s' % (page, e))

                # Compatibility fallback for an older KinoKing layout.
                if not parsed_servers:
                    self.chk_year(page, year)
                    print('[KINOKING-TEST2] legacy chk_year fallback | page=%s' % page)

            links = list(self.list)
"""

    if old not in kg:
        raise SystemExit("Current KinoKing movie block not found")
    kg = kg.replace(old, new, 1)

    # Test diagnostics: confirms whether movie search found a KinoKing movie id.
    needle = "        links = []\n        if int(season or 0) > 0:\n"
    diag = (
        "        if int(season or 0) == 0:\n"
        "            print('[KINOKING-TEST2] movie search | titles=%s | year=%s | candidates=%s' % (titles, year, candidates))\n\n"
        "        links = []\n"
        "        if int(season or 0) > 0:\n"
    )
    if needle not in kg:
        raise SystemExit("KinoKing diagnostics insertion point not found")
    kg = kg.replace(needle, diag, 1)
    kg_path.write_text(kg, encoding="utf-8", newline="\n")

    addon = root / "addon.xml"
    tree = ET.parse(addon)
    ar = tree.getroot()
    ar.set("version", VERSION)
    metadata = next(e for e in ar.findall("extension") if e.get("point") == "xbmc.addon.metadata")
    news = metadata.find("news")
    current = (news.text or "").strip() if news is not None else ""
    entry = (
        f"{VERSION} KINOKING TEST2\n"
        "- KinoKing Filme: Browser-aehnliche requests.Session fuer movie.php.\n- const SERVERS der Filmseite wird direkt ausgewertet.\n"
        "- Alle mirrors werden an den bestehenden xShip-Resolver uebergeben.\n"
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

with zipfile.ZipFile(OUT, "r") as zf:
    kg = zf.read("plugin.video.xship/scrapers/scrapers_source/de/kinoking.py").decode("utf-8")
    addon_text = zf.read("plugin.video.xship/addon.xml").decode("utf-8")
    assert "movie GET" in kg\n    assert "requests.Session" in kg\n    assert "SERVERS parsed" in kg
    assert "server.get('mirrors')" in kg
    assert "legacy chk_year fallback" in kg
    assert f'version="{VERSION}"' in addon_text

print(OUT)
