from pathlib import Path
import shutil


def patch_movie2k_title_variants(path):
    p = Path(path)
    text = p.read_text(encoding='utf-8')

    marker = "    def _search(self, titles, year, season, episode):\n"
    helper = '''    def _search_titles(self, titles):
        result = []
        seen = set()
        for value in titles or []:
            title = str(value or '').strip()
            if not title:
                continue
            candidates = [title]
            if ' - ' in title:
                candidates.append(title.split(' - ', 1)[0].strip())
            if ':' in title:
                candidates.append(title.split(':', 1)[0].strip())

            plain = title.replace("'", '').replace('’', '').replace('`', '')
            plain = __import__('re').sub(r'\s*[-:]\s*', ' ', plain)
            plain = __import__('re').sub(r'\s+', ' ', plain).strip()
            if plain:
                candidates.append(plain)

            for candidate in candidates:
                key = candidate.lower()
                if candidate and key not in seen:
                    seen.add(key)
                    result.append(candidate)
        return result[:8]

'''
    if helper.strip() not in text:
        if marker not in text:
            raise RuntimeError('Movie2k _search marker missing')
        text = text.replace(marker, helper + marker, 1)

    old = "        clean_titles = set(cleantitle.get(title) for title in set(titles or []) if title)\n        seen_ids = set()\n\n        for lang in self._language_queries():\n            for title in titles or []:\n"
    new = "        search_titles = self._search_titles(titles)\n        clean_titles = set(cleantitle.get(title) for title in search_titles if title)\n        seen_ids = set()\n\n        for lang in self._language_queries():\n            for title in search_titles:\n"
    if old not in text:
        raise RuntimeError('Movie2k title loop marker missing')
    text = text.replace(old, new, 1)
    p.write_text(text, encoding='utf-8', newline='\n')

    # 95 test additions: use the updated Huhu and KKiste scraper snapshots.
    tools = Path(__file__).resolve().parent
    scrapers = p.parent
    for src_name, dst_name in (('huhu95.py', 'huhu.py'), ('kkiste95.py', 'kkiste.py')):
        src = tools / src_name
        dst = scrapers / dst_name
        if not src.exists():
            raise RuntimeError('Missing scraper test file: %s' % src_name)
        shutil.copy2(src, dst)
        compile(dst.read_text(encoding='utf-8'), str(dst), 'exec')
