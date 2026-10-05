from pathlib import Path
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET

REPO = Path.cwd()
BASE = REPO / "test-builds/plugin.video.xship-2026.10.05.140-KINOGER-TEST3.zip"
OUT = REPO / "zips/plugin.video.xship/plugin.video.xship-2026.10.05.141.zip"
VERSION = "2026.10.05.141"

if not BASE.exists():
    raise SystemExit(f"Missing base ZIP: {BASE}")

with tempfile.TemporaryDirectory() as td:
    work = Path(td)
    with zipfile.ZipFile(BASE, "r") as zf:
        zf.extractall(work)

    addon_candidates = list(work.rglob("addon.xml"))
    if not addon_candidates:
        raise SystemExit("addon.xml not found")
    root = addon_candidates[0].parent

    # Official version.
    addon = root / "addon.xml"
    tree = ET.parse(addon)
    ar = tree.getroot()
    ar.set("version", VERSION)

    metadata = next(e for e in ar.findall("extension") if e.get("point") == "xbmc.addon.metadata")
    news = metadata.find("news")
    current = (news.text or "").strip() if news is not None else ""

    # Remove temporary test-build news blocks from 2026-10-05.
    blocks = [b.strip() for b in re.split(r"\n\s*\n", current) if b.strip()]
    blocks = [
        b for b in blocks
        if not re.match(r"^2026\.10\.05\.(137|138|139|140)\b", b)
        and "MEINECLOUD TEST1" not in b
        and "KINOGER TEST" not in b
    ]

    release_news = (
        f"{VERSION}\n"
        "- MeineCloud/FHDFilme: API-Quellensuche wiederhergestellt und stabilisiert.\n"
        "- KinoGer: Domain auf kinoger.beer aktualisiert; alte kinoger.com-Einstellung wird beim Start automatisch korrigiert.\n"
        "- KinoGer: Suche liefert wieder Quellen; Wiedergabe einzelner 0gomovies.beer-Links hängt von ResolveURL-Unterstützung ab.\n"
        "- HDFilme und FHDFilme mit aktuellen Domains und funktionierender Quellensuche bestätigt.\n"
        "- TopStreamFilm liefert wieder Quellen.\n"
    )

    if news is None:
        news = ET.SubElement(metadata, "news")
    news.text = release_news + ("\n" + "\n\n".join(blocks) if blocks else "")
    tree.write(addon, encoding="UTF-8", xml_declaration=True)

    # Update popup marker so users see the new changelog exactly once.
    service = root / "service.py"
    service_text = service.read_text(encoding="utf-8-sig")
    service_text, n = re.subn(
        r"_XSHIP_CHANGELOG_BUILD\s*=\s*['\"][^'\"]+['\"]",
        f"_XSHIP_CHANGELOG_BUILD = '{VERSION}'",
        service_text,
        count=1,
    )
    if n != 1:
        raise SystemExit("Could not update _XSHIP_CHANGELOG_BUILD")
    service.write_text(service_text, encoding="utf-8", newline="\n")

    # Official changelog.txt, without test-build noise.
    changelog = root / "changelog.txt"
    old = changelog.read_text(encoding="utf-8-sig").strip() if changelog.exists() else ""
    if old.startswith("xShip – Changelog"):
        old = old[len("xShip – Changelog"):].lstrip()

    release_changelog = (
        "xShip – Changelog\n\n"
        f"{VERSION}\n"
        "- MeineCloud/FHDFilme: API-Quellensuche wiederhergestellt und stabilisiert.\n"
        "- KinoGer: neue Domain kinoger.beer hinterlegt.\n"
        "- KinoGer: Domain-Synchronisierung korrigiert, damit ein alter kinoger.com-Wert die neue Domain nicht mehr überschreibt.\n"
        "- KinoGer: Quellensuche funktioniert wieder; 0gomovies.beer benötigt noch passende ResolveURL-Unterstützung für die Wiedergabe.\n"
        "- HDFilme und FHDFilme mit aktuellen Domains und funktionierender Quellensuche bestätigt.\n"
        "- TopStreamFilm liefert wieder Quellen.\n\n"
    )
    changelog.write_text(release_changelog + old + "\n", encoding="utf-8", newline="\n")

    # Sanity checks for the fixes being promoted.
    kinoger = (root / "scrapers/scrapers_source/de/kinoger.py").read_text(encoding="utf-8-sig")
    meinecloud = (root / "scrapers/modules/meinecloud_shared.py").read_text(encoding="utf-8-sig")
    assert "SITE_DOMAIN = 'kinoger.beer'" in kinoger
    assert "if provider == 'kinoger':" in service_text
    assert "forced_domain = 'kinoger.beer'" in service_text
    assert "/api/embed-links" in meinecloud
    assert "/api/resolve" in meinecloud
    assert f"_XSHIP_CHANGELOG_BUILD = '{VERSION}'" in service_text

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(root.rglob("*")):
            if p.is_file():
                zf.write(p, Path("plugin.video.xship") / p.relative_to(root))

# Final ZIP verification.
with zipfile.ZipFile(OUT, "r") as zf:
    addon_text = zf.read("plugin.video.xship/addon.xml").decode("utf-8")
    service_text = zf.read("plugin.video.xship/service.py").decode("utf-8")
    changelog_text = zf.read("plugin.video.xship/changelog.txt").decode("utf-8")
    kg = zf.read("plugin.video.xship/scrapers/scrapers_source/de/kinoger.py").decode("utf-8")
    mc = zf.read("plugin.video.xship/scrapers/modules/meinecloud_shared.py").decode("utf-8")
    assert f'version="{VERSION}"' in addon_text
    assert "KINOGER TEST" not in addon_text
    assert "MEINECLOUD TEST1" not in addon_text
    assert f"_XSHIP_CHANGELOG_BUILD = '{VERSION}'" in service_text
    assert "SITE_DOMAIN = 'kinoger.beer'" in kg
    assert "/api/embed-links" in mc
    assert changelog_text.startswith(f"xShip – Changelog\n\n{VERSION}")

print(OUT)
