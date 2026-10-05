from pathlib import Path
import os, sys, zipfile, tempfile, shutil
import xml.etree.ElementTree as ET

repo = Path.cwd()
base = repo / 'test-builds/plugin.video.xship-2026.10.05.139-KINOGER-TEST2.zip'
out = repo / 'test-builds/plugin.video.xship-2026.10.05.140-KINOGER-TEST3.zip'

with tempfile.TemporaryDirectory() as td:
    work = Path(td)
    with zipfile.ZipFile(base, 'r') as zf:
        zf.extractall(work)

    addons = list(work.rglob('addon.xml'))
    if not addons:
        raise SystemExit('addon.xml not found')
    root = addons[0].parent

    p = root / 'scrapers/scrapers_source/de/kinoger.py'
    s = p.read_text(encoding='utf-8-sig')
    s = s.replace("SITE_DOMAIN = 'kinoger.com'", "SITE_DOMAIN = 'kinoger.beer'")
    p.write_text(s, encoding='utf-8', newline='\n')

    service = root / 'service.py'
    text = service.read_text(encoding='utf-8-sig')
    needle = (
        "            provider = (item.get('provider') or '').strip()\n"
        "            source_domain = _normalize_provider_domain(item.get('domain'))\n"
        "            if not provider or not source_domain:\n"
        "                continue\n\n"
        "            key = 'provider.%s.domain' % provider\n"
    )
    replacement = (
        "            provider = (item.get('provider') or '').strip()\n"
        "            source_domain = _normalize_provider_domain(item.get('domain'))\n"
        "            if not provider or not source_domain:\n"
        "                continue\n\n"
        "            # KinoGer moved from kinoger.com to kinoger.beer.\n"
        "            # Ignore stale saved overrides for this provider.\n"
        "            if provider == 'kinoger':\n"
        "                forced_domain = 'kinoger.beer'\n"
        "                key = 'provider.%s.domain' % provider\n"
        "                current_kinoger = _normalize_provider_domain(getSetting(key, ''))\n"
        "                if current_kinoger != forced_domain:\n"
        "                    setSetting(key, forced_domain)\n"
        "                    changed = True\n"
        "                    if isLogger:\n"
        "                        logger.info(' -> [service]: KinoGer Domain fix: %s -> %s' % (current_kinoger or '<leer>', forced_domain))\n"
        "                state[provider] = forced_domain\n"
        "                continue\n\n"
        "            key = 'provider.%s.domain' % provider\n"
    )
    if needle not in text:
        raise SystemExit('sync_provider_domains insertion point not found')
    text = text.replace(needle, replacement, 1)
    service.write_text(text, encoding='utf-8', newline='\n')

    addon = root / 'addon.xml'
    tree = ET.parse(addon)
    r = tree.getroot()
    r.set('version', '2026.10.05.140')
    metadata = next(e for e in r.findall('extension') if e.get('point') == 'xbmc.addon.metadata')
    news = metadata.find('news')
    current = (news.text or '').strip() if news is not None else ''
    entry = (
        '2026.10.05.140 KINOGER TEST3\n'
        '- KinoGer: alte gespeicherte kinoger.com-Domain wird beim Start automatisch auf kinoger.beer korrigiert.\n'
        '- Bidirektionaler Domain-Sync darf KinoGer nicht mehr auf .com zurueckschreiben.\n'
        '- MeineCloud-Fix und vorherige Aenderungen bleiben enthalten.\n\n'
    )
    if news is None:
        news = ET.SubElement(metadata, 'news')
    news.text = entry + current
    tree.write(addon, encoding='UTF-8', xml_declaration=True)

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(root.rglob('*')):
            if fp.is_file():
                zf.write(fp, Path('plugin.video.xship') / fp.relative_to(root))

with zipfile.ZipFile(out, 'r') as zf:
    kg = zf.read('plugin.video.xship/scrapers/scrapers_source/de/kinoger.py').decode('utf-8')
    svc = zf.read('plugin.video.xship/service.py').decode('utf-8')
    addon_text = zf.read('plugin.video.xship/addon.xml').decode('utf-8')
    assert "SITE_DOMAIN = 'kinoger.beer'" in kg
    assert "if provider == 'kinoger':" in svc
    assert "forced_domain = 'kinoger.beer'" in svc
    assert '2026.10.05.140' in addon_text

print(out)
