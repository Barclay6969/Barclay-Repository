import pathlib
import re
import sys
import tempfile
import urllib.request
import zipfile

repo = pathlib.Path(sys.argv[1]).resolve()
base = repo / 'zips/test/plugin.video.xship-2026.09.14.94-SCRAPERCORETEST.zip'
out = repo / 'zips/test/plugin.video.xship-2026.09.14.95-MULTISCRAPERTEST.zip'

XVAULT_REF = '2bea53e53332fe82d32569b5dddda98a23cfb7e5'
RAW = 'https://raw.githubusercontent.com/mojomedia1812/xVAULT/%s/sites/%s.py'
SCRAPERS = ['huhu', 'kkiste', 'kinokiste', 'netzkino', 'kinoger']


def download_text(name):
    url = RAW % (XVAULT_REF, name)
    req = urllib.request.Request(url, headers={'User-Agent': 'xShip-test-builder/1.0'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode('utf-8')


def adapt(name, text):
    # xShip's central source filter currently accepts de/en only. xVault may
    # return "multi" for lang=4, which would otherwise disappear completely.
    if name in ('kkiste', 'kinokiste'):
        text = text.replace("return 'multi', 'Mehrsprachig'", "return 'de', 'Mehrsprachig'")

    # Preserve xShip's provider priority setting where the xVault scraper uses
    # a fixed priority. The central xShip source collector also enforces it,
    # but keeping it here makes standalone scraper output consistent.
    text = re.sub(
        r"self\.priority\s*=\s*1\b",
        "self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)",
        text
    )

    return text


with tempfile.TemporaryDirectory() as tmpdir:
    tmp = pathlib.Path(tmpdir)
    with zipfile.ZipFile(base) as zf:
        zf.extractall(tmp)

    root = tmp / 'plugin.video.xship'
    scrapers_dir = root / 'scrapers/scrapers_source/de'

    for name in SCRAPERS:
        text = adapt(name, download_text(name))
        target = scrapers_dir / ('%s.py' % name)
        target.write_text(text, encoding='utf-8', newline='\n')
        compile(text, str(target), 'exec')

    # Version bump only; all 94 core/resolver fixes remain untouched.
    addon = root / 'addon.xml'
    addon_text = addon.read_text(encoding='utf-8')
    addon_text, count = re.subn(
        r'(<addon\s+id="plugin\.video\.xship"\s+version=")[^"]+',
        r'\g<1>2026.09.14.95',
        addon_text,
        count=1
    )
    if count != 1:
        raise RuntimeError('addon version patch failed')
    addon.write_text(addon_text, encoding='utf-8', newline='\n')

    # Guardrails for the important changes.
    huhu = (scrapers_dir / 'huhu.py').read_text(encoding='utf-8')
    kkiste = (scrapers_dir / 'kkiste.py').read_text(encoding='utf-8')
    kinokiste = (scrapers_dir / 'kinokiste.py').read_text(encoding='utf-8')
    kinoger = (scrapers_dir / 'kinoger.py').read_text(encoding='utf-8')
    netzkino = (scrapers_dir / 'netzkino.py').read_text(encoding='utf-8')

    if "media_id = f'series.{result[\"id\"]}.{season}.{episode}'" not in huhu:
        raise RuntimeError('Huhu series path missing')
    if "'/data/browse/?lang=%s" not in kkiste:
        raise RuntimeError('KKiste JSON API missing')
    if "'/data/browse/?lang=%s" not in kinokiste:
        raise RuntimeError('KinoKiste JSON API missing')
    if 'hoster_compat' not in kinoger:
        raise RuntimeError('KinoGer resolver compatibility missing')
    if 'NETZKINO_GRAPHQL_ENDPOINT' not in netzkino:
        raise RuntimeError('Netzkino GraphQL update missing')
    if "return 'multi', 'Mehrsprachig'" in kkiste or "return 'multi', 'Mehrsprachig'" in kinokiste:
        raise RuntimeError('xShip multi-language adaptation missing')

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob('*'):
            if path.is_file():
                zf.write(path, path.relative_to(tmp))

with zipfile.ZipFile(out) as zf:
    bad = zf.testzip()
    if bad:
        raise RuntimeError('zip integrity failed: %s' % bad)

print(out)
