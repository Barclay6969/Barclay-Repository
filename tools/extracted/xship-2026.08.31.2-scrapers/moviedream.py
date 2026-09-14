# -*- coding: UTF-8 -*-
# moviedream
# 2022-12-21
# edit 2026-04-12

try:
    from Crypto.Cipher import AES  # für Linux
    from Crypto.Util.Padding import unpad
    from Crypto.Hash import MD5
except ImportError:
    from Cryptodome.Cipher import AES  # für Windows und Android
    from Cryptodome.Util.Padding import unpad
    from Cryptodome.Hash import MD5
import base64
from resources.lib.utils import isBlockedHosterFast as isBlockedHoster
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules.tools import cParser
from resources.lib.control import getSetting

SITE_IDENTIFIER = 'moviedream'
SITE_DOMAIN = 'moviedream.cx'
SITE_NAME = SITE_IDENTIFIER.upper()

class source:
    def __init__(self):
        self.priority = getSetting('provider.' + SITE_IDENTIFIER + '.priority', 100)  # je kleiner der Wert um so höher die Priorität
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.sources = []

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
        imdb = cParser.parse(imdb, '\d+')[1][0]
        if season == 0:
            URL_SEARCH = self.base_link + '/film/%s/deutsch' % imdb
        else:
            URL_SEARCH = self.base_link + '/serie/%s/deutsch/staffel-%s/episode-%s' % (imdb, str(season), str(episode))
        REFERER = self.base_link + '/suchergebnisse.php?sprache=Deutsch&imdbid=%s' % imdb
        oRequest = cRequestHandler(URL_SEARCH, caching=True)
        oRequest.addHeaderEntry('Referer', REFERER)
        sHtmlContent = oRequest.request()
        pattern = 'decrypt(\([^\)]+\))'
        isMatch, aResult = cParser.parse(sHtmlContent, pattern)
        for Result in aResult:
            password = eval(Result)[1].encode()
            decryptdict = eval(eval(Result)[0])
            ciphertext = base64.b64decode(decryptdict['ct'])
            salt = bytes.fromhex(decryptdict['s'])
            keyIv = self.bytesToKey(salt, password)
            key = keyIv[:32]
            iv = keyIv[32:]  # from key derivation
            cipher = AES.new(key, AES.MODE_CBC, iv)
            decryptedstring = unpad(cipher.decrypt(ciphertext), 16)
            url = eval(decryptedstring.decode())
            sUrl = url.replace('\\', '')
            isBlocked, hoster, url, prioHoster = isBlockedHoster(sUrl)
            if isBlocked: continue
            quality = 'HD'
            if '1080' in sUrl: quality = '1080p'
            self.sources.append({'source': hoster, 'quality': quality, 'language': 'de', 'url': url, 'direct': True, 'prioHoster': prioHoster})
        return self.sources

    def resolve(self, url):
        try:
            return url
        except:
            return

    def bytesToKey(self, salt, password):
        data = b''
        tmp = b''
        while len(data) < 48:
            md5 = MD5.new()
            md5.update(tmp + password + salt)
            tmp = md5.digest()
            data += tmp
        return data