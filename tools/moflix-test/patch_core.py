import re
from pathlib import Path


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError('Patch marker not found: %s' % label)
    return text.replace(old, new, 1)


def patch_sources(path):
    p = Path(path)
    text = p.read_text(encoding='utf-8')

    text = replace_once(
        text,
        'from resources.lib import log_utils, control',
        'from resources.lib import log_utils, control, hoster_compat',
        'sources import hoster_compat'
    )

    text = replace_once(
        text,
        '            return sorted(set(domains))\n        except Exception as e:',
        '            domains.extend(hoster_compat.extra_domains())\n            return sorted(set(domains))\n        except Exception as e:',
        'host dict compatibility domains'
    )

    old_invalid = """                        elif not hmf.valid_url():
                            log_utils.log(
                                '[xShip Resolver] Kein passender ResolveURL-Resolver: %s / %s -> naechste Quelle' %
                                (item.get('source'), str(url)),
                                log_utils.LOGWARNING
                            )
                            url = None
"""
    new_invalid = """                        elif not hmf.valid_url():
                            compat_url = hoster_compat.resolve(url)
                            if compat_url:
                                log_utils.log(
                                    '[xShip Resolver] Kompatibilitaets-Resolver: %s / %s' %
                                    (item.get('source'), str(url)),
                                    log_utils.LOGINFO
                                )
                                url = compat_url
                                resolved = True
                            else:
                                log_utils.log(
                                    '[xShip Resolver] Kein passender ResolveURL-Resolver: %s / %s -> naechste Quelle' %
                                    (item.get('source'), str(url)),
                                    log_utils.LOGWARNING
                                )
                                url = None
"""
    text = replace_once(text, old_invalid, new_invalid, 'resolver invalid-url fallback')

    old_empty = """                            url = hmf.resolve()
                            resolved = True
                            if url == False or url == None or url == '':
                                log_utils.log(
                                    '[xShip Resolver] ResolveURL ohne Stream: %s -> naechste Quelle' % item.get('source'),
                                    log_utils.LOGWARNING
                                )
                                url = None
"""
    new_empty = """                            original_hoster_url = url
                            url = hmf.resolve()
                            resolved = True
                            if url == False or url == None or url == '':
                                compat_url = hoster_compat.resolve(original_hoster_url)
                                if compat_url:
                                    url = compat_url
                                else:
                                    log_utils.log(
                                        '[xShip Resolver] ResolveURL ohne Stream: %s -> naechste Quelle' % item.get('source'),
                                        log_utils.LOGWARNING
                                    )
                                    url = None
"""
    text = replace_once(text, old_empty, new_empty, 'resolver empty fallback')

    old_exc = """                    except Exception as e:
                        log_utils.log(
                            '[xShip Resolver] ResolveURL Fehler fuer %s: %s -> naechste Quelle' %
                            (item.get('source'), str(e)),
                            log_utils.LOGWARNING
                        )
                        url = None
"""
    new_exc = """                    except Exception as e:
                        compat_url = hoster_compat.resolve(url)
                        if compat_url:
                            url = compat_url
                            resolved = True
                        else:
                            log_utils.log(
                                '[xShip Resolver] ResolveURL Fehler fuer %s: %s -> naechste Quelle' %
                                (item.get('source'), str(e)),
                                log_utils.LOGWARNING
                            )
                            url = None
"""
    text = replace_once(text, old_exc, new_exc, 'resolver exception fallback')

    p.write_text(text, encoding='utf-8', newline='\n')


def patch_moflix(path):
    p = Path(path)
    text = p.read_text(encoding='utf-8')

    text = replace_once(
        text,
        'from resources.lib import log_utils',
        'from resources.lib import log_utils, hoster_compat',
        'moflix import hoster_compat'
    )

    start = text.index('    def _add_videos(self, videos):')
    end = text.index('    def _json(self, url, referer):', start)
    replacement = '''    def _add_videos(self, videos):
        for video in videos or []:
            if not isinstance(video, dict):
                continue

            original_url = html_unescape(str(video.get('src') or '').strip())
            if not original_url or original_url in self._seen:
                continue
            if 'youtube.' in original_url.lower() or 'youtu.be/' in original_url.lower():
                continue
            self._seen.add(original_url)

            original_host = (urlparse(original_url).hostname or '').lower()
            quality = self._quality('%s %s' % (video.get('quality') or '', original_url))
            language = self._language(video.get('language'), video.get('quality'), video.get('name'), original_url)
            info = self._info(video)
            direct = self._is_direct(original_url, video)
            clean_url = original_url

            if direct:
                if self._is_moflix_hls(original_url) and not self._direct_hls_usable(original_url):
                    log_utils.log('[MOFLIX] unusable direct HLS skipped: %s' % original_host, log_utils.LOGINFO)
                    continue
                hoster = self._host_name(original_url) or SITE_NAME
                prio_hoster = 20
            else:
                is_blocked, hoster, clean_url, prio_hoster = isBlockedHoster(original_url, isResolve=False)
                if is_blocked and hoster_compat.is_supported_host(original_host):
                    is_blocked = False
                    hoster = hoster_compat.display_name(original_host)
                    clean_url = original_url
                    prio_hoster = 90
                if is_blocked or not clean_url:
                    continue
                try:
                    prio_hoster = min(int(prio_hoster), int(self._mirror_priority(clean_url)))
                except Exception:
                    prio_hoster = self._mirror_priority(clean_url)

            self.sources.append({
                'source': hoster or SITE_NAME,
                'quality': quality,
                'language': language,
                'url': clean_url,
                'info': info,
                'direct': direct,
                'priority': int(self.priority),
                'prioHoster': prio_hoster
            })

'''
    text = text[:start] + replacement + text[end:]

    if '    def _is_direct(self, url, video):' not in text and '    @staticmethod\n    def _is_direct(url, video):' not in text:
        marker = '    @staticmethod\n    def _is_moflix_hls(url):'
        helper = '''    @staticmethod
    def _is_direct(url, video):
        path = str(url or '').split('|', 1)[0].split('?', 1)[0].lower()
        video_type = str(video.get('type') or '').lower()
        return video_type == 'stream' or path.endswith(('.m3u8', '.m3u', '.mpd', '.mp4'))

'''
        if marker not in text:
            raise RuntimeError('Patch marker not found: moflix is_direct insertion')
        text = text.replace(marker, helper + marker, 1)

    p.write_text(text, encoding='utf-8', newline='\n')
