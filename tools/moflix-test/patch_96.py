from pathlib import Path


def patch_sources(path):
    p = Path(path)
    text = p.read_text(encoding='utf-8')

    # SerienStream: only keep one VOE source per language.  Dood/CAPTCHA and
    # other provider buttons are known to be unusable in the current xShip
    # playback path and only clutter the source dialog.
    old_filter = """        self.sources = normalized_sources
        if not self.sources:
            return
"""
    new_filter = """        self.sources = normalized_sources

        # SerienStream bewusst sehr konservativ filtern: nur VOE behalten,
        # maximal eine deutsche und eine englische Quelle. Andere Provider
        # (insbesondere Dood/CAPTCHA) werden nicht mehr zur Auswahl angeboten.
        filtered_sources = []
        serienstream_languages = set()
        for item in self.sources:
            provider_name = str(item.get('provider', '') or '').strip().lower()
            if provider_name != 'serienstream':
                filtered_sources.append(item)
                continue

            hoster_name = str(item.get('source', '') or '').strip().lower()
            language = str(item.get('language', '') or '').strip().lower()
            if 'voe' not in hoster_name:
                continue
            if language not in ('de', 'en'):
                continue
            if language in serienstream_languages:
                continue

            serienstream_languages.add(language)
            item['prioHoster'] = 0
            filtered_sources.append(item)

        self.sources = filtered_sources
        if not self.sources:
            return
"""
    if old_filter not in text:
        raise RuntimeError('sourcesFilter marker not found')
    text = text.replace(old_filter, new_filter, 1)

    # MediaInfo regression after deferred resolving: only resolve a small
    # whitelist of fast/non-popup hosters for the background probe.  The
    # original source URL is NEVER replaced, so playback behaviour stays
    # unchanged. SerienStream is excluded completely because its redirect
    # tokens are short-lived.
    marker = """    def _get_resolution(self, source):
"""
    helper = """    def _safe_media_probe_url(self, source):
        url = source.get('url')
        if not url:
            return None
        if source.get('direct') is True:
            return url

        provider = str(source.get('provider', '') or '').strip().lower()
        if provider == 'serienstream':
            return None
        try:
            if int(source.get('prioHoster', 0) or 0) >= 999:
                return None
        except Exception:
            return None

        try:
            raw_url = str(url).split('|', 1)[0]
            host = urlparse(raw_url).netloc.lower()
        except Exception:
            host = ''
        source_name = str(source.get('source', '') or '').lower()
        identity = '%s %s' % (source_name, host)

        # Never background-resolve hosters which are popup/captcha prone,
        # token-sensitive or have shown slow/failing API behaviour.
        unsafe = (
            'dood', 'captcha', 'byse', 'firestream', 'voe', 'kinoger',
            'rpmplay', 'upns.xyz', 'moflix-stream.link'
        )
        if any(token in identity for token in unsafe):
            return None

        # Intentionally small whitelist. More can be added later after tests.
        safe = (
            'streamtape', 'gupload', 'vidara', 'vids.', 'filelions',
            'vidoza', 'veev', 'streamwish', 'filemoon', 'luluvideo',
            'mixdrop', 'upstream', 'vidguard', 'supervideo'
        )
        if not any(token in identity for token in safe):
            return None

        try:
            hmf = resolver.HostedMediaFile(
                url=url,
                include_disabled=True,
                include_universal=False,
                include_popups=False
            )
            if not hmf.valid_url():
                return None
            resolved_url = hmf.resolve()
            if resolved_url and '://' in str(resolved_url):
                log_utils.log(
                    '[BG-Probe] sichere temporaere Aufloesung: %s / %s' %
                    (source.get('provider'), source.get('source')),
                    log_utils.LOGINFO
                )
                return resolved_url
        except Exception as e:
            log_utils.log(
                '[BG-Probe] sichere Aufloesung uebersprungen: %s / %s / %s' %
                (source.get('provider'), source.get('source'), str(e)),
                log_utils.LOGINFO
            )
        return None


"""
    if marker not in text:
        raise RuntimeError('_get_resolution marker not found')
    text = text.replace(marker, helper + marker, 1)

    old_probe = """        try:
            info_str = mediainfo.getMediaInfo(
                source['url'], _NullDialog(), time.time() + 5
            )
"""
    new_probe = """        probe_url = self._safe_media_probe_url(source)
        if not probe_url:
            source.update({'info': info, '_probe': probe})
            self.sources_new.append(source)
            return

        try:
            info_str = mediainfo.getMediaInfo(
                probe_url, _NullDialog(), time.time() + 4
            )
"""
    if old_probe not in text:
        raise RuntimeError('MediaInfo probe marker not found')
    text = text.replace(old_probe, new_probe, 1)

    p.write_text(text, encoding='utf-8', newline='\n')
