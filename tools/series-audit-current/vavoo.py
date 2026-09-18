# vavoo
# edit 2026-06-15

import json
import requests
from scrapers.modules.tools import cParser
from resources.lib.utils import isBlockedHosterFast as isBlockedHoster
from resources.lib.control import getSetting

SITE_IDENTIFIER = 'vavoo'
SITE_DOMAIN = 'vavoo.to'
SITE_NAME = SITE_IDENTIFIER.upper()

session = requests.session()

class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100) # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.domains = [self.domain]
        self.base_link = 'https://' + self.domains[0] +'/'
        self.BASEURL = self.base_link +'ccapi/'


    def run(self, titles, year, season=0, episode=0, imdb=''):
        sources = []
        #if season != 0: return sources
        #imdb = '48866' # 'tt2661044'
        action = 'links'
        params = dict()
        params['language'] = 'de'
        if season == 0:
            mediatype = 'movie'
            params['id'] = '%s.%s' % (mediatype, imdb)
        else:
            V2_API_KEY = '4a65e1e644af74c98f9f2b3884669deb3fac9531ee71f39babf1dee46d264d17'
            headers = {'Content-Type': 'application/json', 'trakt-api-key': V2_API_KEY, 'trakt-api-version': '2'}
            sUrl = 'https://api.trakt.tv/shows/{0}'.format(imdb)
            result = requests.get(sUrl, headers=headers)
            #if result.status_code == 200:
            result = json.loads(result.content)
            id = result['ids']['tmdb']
            mediatype = 'series'
            params['id'] = '%s.%s.%s.%s' % (mediatype, id, str(season), str(episode))

        data = self.callApi(action, params)

        for i in data:
            try:
                url = i['url']
                if 'filemoon' in url: continue
                if not 'language' in str(i): language = 'de'
                else: language = i['language']
                isMatch, quality = cParser.parseSingleResult(i['name'], "\(([^\)]+)")
                if not isMatch: quality = '720p'
                isBlocked, hoster, sUrl, prioHoster = isBlockedHoster(url)
                if isBlocked: continue
                if sUrl:
                    sources.append({'source': hoster, 'quality': quality, 'language': language, 'url': sUrl, 'info': i['name'], 'direct': True, 'priority': int(self.priority), 'prioHoster': prioHoster})
            except:
                pass
        return sources

    def resolve(self, url):
        return url


    def callApi(self, action, params, method='GET', headers=None, jsonreq=None):
        if not headers: headers = dict()
        headers['auth-token'] = self.getAuthSignature()
        if method == 'GET':
            resp = session.request(method, (self.BASEURL + action), params=params, headers=headers)
        else:
            resp = session.request(method, (self.BASEURL + action), params=params, headers=headers, json=jsonreq)
        data = resp.json()
        return data

    def getAuthSignature(self):
        _headers = {"user-agent": "okhttp/4.11.0", "accept": "application/json", "content-type": "application/json; charset=utf-8", "content-length": "1106", "accept-encoding": "gzip"}
        _data = {"token": "tosFwQCJMS8qrW_AjLoHPQ41646J5dRNha6ZWHnijoYQQQoADQoXYSo7ki7O5-CsgN4CH0uRk6EEoJ0728ar9scCRQW3ZkbfrPfeCXW2VgopSW2FWDqPOoVYIuVPAOnXCZ5g", "reason": "app-blur", "locale": "de",
                 "theme": "dark", "metadata": {"device": {"type": "Handset", "brand": "google", "model": "Nexus", "name": "21081111RG", "uniqueId": "d10e5d99ab665233"},
                                               "os": {"name": "android", "version": "7.1.2", "abis": ["arm64-v8a", "armeabi-v7a", "armeabi"], "host": "android"},
                                               "app": {"platform": "android", "version": "3.1.20", "buildId": "289515000", "engine": "hbc85",
                                                       "signatures": ["6e8a975e3cbf07d5de823a760d4c2547f86c1403105020adee5de67ac510999e"], "installer": "app.revanced.manager.flutter"},
                                               "version": {"package": "tv.vavoo.app", "binary": "3.1.20", "js": "3.1.20"}}, "appFocusTime": 0, "playerActive": False, "playDuration": 0,
                 "devMode": False, "hasAddon": True, "castConnected": False, "package": "tv.vavoo.app", "version": "3.1.20", "process": "app", "firstAppStart": 1743962904623,
                 "lastAppStart": 1743962904623, "ipLocation": "", "adblockEnabled": True,
                 "proxy": {"supported": ["ss", "openvpn"], "engine": "ss", "ssVersion": 1, "enabled": True, "autoServer": True, "id": "pl-waw"}, "iap": {"supported": False}}
        req = requests.post('https://www.vavoo.tv/api/app/ping', json=_data, headers=_headers).json()
        return req.get("addonSig")

