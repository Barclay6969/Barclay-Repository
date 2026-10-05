# -*- coding: UTF-8 -*-

# MeineCloud provider
# Movie4k family database source

from resources.lib.utils import isBlockedHosterFast as isBlockedHoster
from scrapers.modules.meinecloud_shared import get_movie_links, get_series_links
from resources.lib.control import getSetting
from resources.lib.domain_manager import resolve_domain

SITE_IDENTIFIER = 'meinecloud'
SITE_DOMAIN = 'meinecloud.click'
SITE_NAME = SITE_IDENTIFIER.upper()


class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)
        self.language = ['de']
        self.domain = resolve_domain(SITE_IDENTIFIER, SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.sources = []

    def _add_links(self, links, numbered=False):
        seen = set()
        index = 0
        for sUrl in links or []:
            if not sUrl or sUrl in seen:
                continue
            seen.add(sUrl)

            isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl)
            if isBlocked or not url:
                continue

            index += 1
            source_name = hoster
            if numbered and index > 1:
                source_name = '%s(%s)' % (hoster, index)

            self.sources.append({
                'source': source_name,
                'quality': '1080p',
                'language': 'de',
                'url': url,
                'direct': True,
                'priority': int(self.priority),
                'prioHoster': prioHoster
            })

    def run(self, titles, year, season=0, episode=0, imdb=''):
        self.sources = []
        try:
            if int(season or 0) == 0:
                self._add_links(get_movie_links(imdb, self.base_link))
            else:
                self._add_links(
                    get_series_links(imdb, int(season), int(episode), self.base_link),
                    numbered=True
                )
            return self.sources
        except Exception:
            return self.sources

    def resolve(self, url):
        return url
