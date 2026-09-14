import re
from pathlib import Path


def patch_movie2k(path):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    old = '''    @staticmethod
    def _language_from_watch(data, title=''):
        value = str(data.get('lang', '')).strip()
        if value == '2':
            return 'de', 'Deutsch'
        if value == '3':
            return 'en', 'Englisch'
        if value == '4':
            return 'multi', 'Mehrsprachig'

        title = str(title or '')
        if re.search(r'\\bStaffel\\b', title, re.IGNORECASE):
            return 'de', 'Deutsch'
        if re.search(r'\\bSeason\\b', title, re.IGNORECASE):
            return 'en', 'Englisch'
        return 'de', 'Deutsch'
'''
    new = '''    @staticmethod
    def _language_from_watch(data, title=''):
        title = str(title or '')
        # Serien zuerst anhand des Katalogtitels einordnen. Movie2k liefert
        # Season-Eintraege teilweise mit lang=4 (Multi); xShips zentraler
        # Sprachfilter akzeptiert aber nur de/en und wuerde sie sonst verwerfen.
        if re.search(r'\\bStaffel\\b', title, re.IGNORECASE):
            return 'de', 'Deutsch'
        if re.search(r'\\bSeason\\b', title, re.IGNORECASE):
            return 'en', 'Englisch'

        value = str(data.get('lang', '')).strip()
        if value == '2':
            return 'de', 'Deutsch'
        if value == '3':
            return 'en', 'Englisch'
        if value == '4':
            # Multi-Katalog ohne eindeutigen Serienmarker: fuer xShip als DE
            # weiterreichen statt komplett aus der Quellenliste zu verschwinden.
            return 'de', 'Mehrsprachig'
        return 'de', 'Deutsch'
'''
    if old not in text:
        raise RuntimeError('Movie2k language marker not found')
    p.write_text(text.replace(old, new, 1), encoding='utf-8', newline='\n')


def patch_hoster_compat(path):
    p = Path(path)
    text = p.read_text(encoding='utf-8')

    old_match = "def _match(url, pattern):\n    try:\n        clean_url = str(url or '').split('|', 1)[0]\n        m = re.search(pattern, clean_url, re.I)\n"
    new_match = "def _match(url, pattern):\n    try:\n        clean_url = urllib_parse.unquote(str(url or '').split('|', 1)[0])\n        m = re.search(pattern, clean_url, re.I)\n"
    if old_match not in text:
        raise RuntimeError('hoster compat match marker not found')
    text = text.replace(old_match, new_match, 1)

    old_kg = "def _match_kinoger(url): return _match(url, r'(?://|\\.)((?:%s))/(?:#|api/v1/video\\?id=)([0-9A-Za-z]+)' % '|'.join(re.escape(d) for d in KINOGER_DOMAINS + MOFLIX_KINOGER_DOMAINS))"
    new_kg = "def _match_kinoger(url): return _match(url, r'(?://|\\.)((?:%s))/(?:#|api/v1/video\\?id=)([0-9A-Za-z_-]+)' % '|'.join(re.escape(d) for d in KINOGER_DOMAINS + MOFLIX_KINOGER_DOMAINS))"
    if old_kg not in text:
        raise RuntimeError('kinoger matcher marker not found')
    text = text.replace(old_kg, new_kg, 1)

    p.write_text(text, encoding='utf-8', newline='\n')


def patch_moflix_display(path):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    old = '''            else:
                is_blocked, hoster, clean_url, prio_hoster = isBlockedHoster(original_url, isResolve=False)
                if is_blocked and hoster_compat.is_supported_host(original_host):
                    is_blocked = False
                    hoster = hoster_compat.display_name(original_host)
                    clean_url = original_url
                    prio_hoster = 90
                if is_blocked or not clean_url:
                    continue
'''
    new = '''            else:
                is_blocked, hoster, clean_url, prio_hoster = isBlockedHoster(original_url, isResolve=False)
                if hoster_compat.is_supported_host(original_host):
                    # Spezialdomains immer ueber die Kompatibilitaetsschicht
                    # fuehren, auch wenn ResolveURL sie faelschlich als generisch
                    # akzeptiert. So bleibt die Original-Embed-URL erhalten.
                    is_blocked = False
                    hoster = hoster_compat.display_name(original_host)
                    clean_url = original_url
                    prio_hoster = 90
                if is_blocked or not clean_url:
                    continue
'''
    if old not in text:
        raise RuntimeError('MoFlix compatibility marker not found')
    p.write_text(text.replace(old, new, 1), encoding='utf-8', newline='\n')
