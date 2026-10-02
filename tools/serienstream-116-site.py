# -*- coding: utf-8 -*-
# Python 3

# Always pay attention to the translations in the menu!
# Language selection for hosters included.
# Ajax search function included.
# HTML long-term cache added
# showValue:     24 hours
# showAllSeries: 24 hours
# showEpisodes:   4 hours
# SSsearch:      24 hours
    
# 2022-12-06 Heptamer - Search function reworked
# 2026-12-29 viewIT   - Hotfix for V2 of SerienStream
# 2026-02-02 SatBandit - Hotfix for V2 of SerienStream
import xbmcgui
import string  # MERGED: Required for A-Z loop
import re

from resources.lib.handler.ParameterHandler import ParameterHandler
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger, cParser, cUtil
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from urllib.parse import quote_plus
from html import unescape

SITE_IDENTIFIER = 'serienstream'
SITE_NAME = 'SerienStream'
SITE_ICON = 'serienstream.png'

# Global search function is thus deactivated!
if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'false':
    SITE_GLOBAL_SEARCH = False
    logger.info('-> [SitePlugin]: globalSearch for %s is deactivated.' % SITE_NAME)

# Domain query
DOMAIN = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '.domain') # Domain selection via addon settings
STATUS = cConfig().getSetting('plugin_' + SITE_IDENTIFIER + '_status') # Domain status code query
ACTIVE = cConfig().getSetting('plugin_' + SITE_IDENTIFIER) # Whether plugin is active or not

# URL_MAIN = 'https://s.to/'
if DOMAIN == '186.2.175.5': # For proxy change, update IP here and in settings
    URL_MAIN = 'http://' + DOMAIN
    REFERER = 'http://' + DOMAIN
    proxy = 'true'
else:
    URL_MAIN = 'https://' + DOMAIN
    REFERER = 'https://' + DOMAIN
    proxy = 'false'
URL_SERIES = URL_MAIN + '/serien'
URL_NEW_SERIES = URL_MAIN + '/neu'
URL_NEW_EPISODES = URL_MAIN + '/neue-episoden'
URL_POPULAR = URL_MAIN + '/beliebte-serien'
URL_LOGIN = URL_MAIN + '/login'
URL_SEARCH = URL_MAIN + '/suche?term='

# If DNS bypass active, use proxy server
if cConfig().getSetting('bypassDNSlock') == 'true':
    cConfig().setSetting('plugin_' + SITE_IDENTIFIER + '.domain', '186.2.175.5')

#

def load(): # Menu structure of the site plugin
    logger.info('Load %s' % SITE_NAME)
    params = ParameterHandler()
    username = cConfig().getSetting('serienstream.user')# Username
    password = cConfig().getSetting('serienstream.pass')# Password
    if username == '' or password == '':                # If no username and password were set, close the plugin!
        xbmcgui.Dialog().ok(cConfig().getLocalizedString(30241), cConfig().getLocalizedString(30264))   # Info Dialog!
    else:
        params.setParam('sUrl', URL_SERIES)
        cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30518), SITE_IDENTIFIER, 'showAllSeries'), params)# All Series
        # --- MERGED: A-Z Menu ---
        params = ParameterHandler()
        params.setParam('sUrl', URL_SERIES + "?by=alpha")
        cGui().addFolder(cGuiElement("A-Z", SITE_IDENTIFIER, 'showGenericMenu'), params)
        params = ParameterHandler()
        params.setParam('sUrl', URL_SERIES + "?by=genre")
        cGui().addFolder(cGuiElement("Genre", SITE_IDENTIFIER, 'showGenericMenu'), params)
        # ------------------------
        params.setParam('sUrl', URL_NEW_SERIES)
        # HOTFIX-BROKEN Function: New Series
        # cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30514), SITE_IDENTIFIER, 'showEntries'), params)
        params = ParameterHandler() # Neu initialisieren!
        params.setParam('sUrl', URL_POPULAR)
        # params.setParam('sectionName', 'Neue Staffeln diese Woche')
        cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30516), SITE_IDENTIFIER, 'showRoot'), params)
        params = ParameterHandler() # Neu initialisieren!
        params.setParam('sectionName', 'Meistgesehen gerade')
        params.setParam('sUrl', URL_POPULAR)
        cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30519), SITE_IDENTIFIER, 'showBeliebte'), params)  # Popular Series
        params.setParam('sUrl', URL_MAIN)
        params.setParam('sCont', 'catalogNav')
        # HOTFIX-BROKEN Function: From A-Z
        # cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30517), SITE_IDENTIFIER, 'showValue'), params)
        params.setParam('sCont', 'homeContentGenresList')
        # HOTFIX-BROKEN Function: Genre
        # cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30506), SITE_IDENTIFIER, 'showValue'), params)
        params.setParam('sUrl', URL_SEARCH)
        cGui().addFolder(cGuiElement(cConfig().getLocalizedString(30520), SITE_IDENTIFIER, 'showSearch'), params)   # Search
        cGui().setEndOfDirectory()

import xbmc # Required for logging

def showCatalog():
    params = ParameterHandler()
    sUrl = params.getValue('sUrl')
    sTargetGenre = params.getValue('sGenreFilter')
    
    oRequest = cRequestHandler(sUrl)
    sHtmlContent = oRequest.request()
    if not sHtmlContent: return
    oGui = cGui()

    # --- NEU: Globaler Bilder-Index (Dictionary) ---
    # Wir suchen auf der gesamten Seite nach Bild+Name Kombinationen
    dictThumbs = {}
    # s.to Kacheln haben oft: <img src="URL" alt="Serienname">
    # oder data-src. Dieser Regex fischt alle Bilder mit ihren Titeln ab.
    all_images = re.findall(r'(?:data-src|src)="([^"]+)"[^>]*alt="([^"]+)"', sHtmlContent)
    for sThumb, sTitle in all_images:
        name_key = unescape(sTitle).strip()
        if sThumb.startswith('/'): sThumb = URL_MAIN + sThumb
        dictThumbs[name_key] = sThumb

    # 1. Block-Isolierung (Deine funktionierende Logik)
    if sTargetGenre:
        safe_genre = re.escape(sTargetGenre)
        pattern = r'<h3[^>]*>\s*' + safe_genre + r'\s*</h3>([\s\S]*?)(?=<div[^>]*class="[^"]*mt-4[^"]*"|<h3|$)'
        match = re.search(pattern, sHtmlContent)
        sContent = match.group(1) if match else sHtmlContent
        pattern_list = r'<li[^>]*>\s*<a href="(/serie/[^"]+)"[^>]*>([^<]+)</a>\s*</li>'
    else:
        match_container = re.search(r'class="row g-3">([\s\S]*?)<nav', sHtmlContent)
        sContent = match_container.group(1) if match_container else sHtmlContent
        pattern_list = r'<h6[^>]*>\s*<a href="(/serie/[^"]+)"[^>]*>([^<]+)</a>\s*</h6>'

    results = re.findall(pattern_list, sContent)

    # 2. Schleife mit Bild-Zuweisung
    for sLink, sSeriesName in results:
        sSeriesName = unescape(sSeriesName).strip()
        oGuiElement = cGuiElement(sSeriesName, SITE_IDENTIFIER, 'showSeasons')

        # Erst schauen wir im Dictionary nach (Genre-Modus Vorteil)
        sThumb = dictThumbs.get(sSeriesName, "")

        # Fallback for A-Z mode (window logic for safety)
        if not sThumb and not sTargetGenre:
            thumb_match = re.search(r'href="' + re.escape(sLink) + r'"[\s\S]*?(?:data-src|src)="([^"]+)"', sContent)
            if thumb_match:
                sThumb = thumb_match.group(1)
                if sThumb.startswith('/'): sThumb = URL_MAIN + sThumb
        
        if sThumb:
            oGuiElement.setThumbnail(sThumb)
        
        p = ParameterHandler()
        p.setParam('sUrl', URL_MAIN + sLink if not sLink.startswith('http') else sLink)
        p.setParam('sName', sSeriesName)
        oGui.addFolder(oGuiElement, p)

    # 3. Pagination (unchanged)
    if not sTargetGenre:
        match_next = re.search(r'href="([^"]+)"[^>]*rel="next"', sHtmlContent)
        if match_next:
            next_url = match_next.group(1)
            if not next_url.startswith('http'): next_url = URL_MAIN + next_url
            
            p_next = ParameterHandler()
            p_next.setParam('sUrl', next_url)
            p_next.setParam('sName', params.getValue('sName'))
            oGui.addFolder(cGuiElement(">>> Nächste Seite", SITE_IDENTIFIER, 'showCatalog'), p_next)

    oGui.setEndOfDirectory()
            
def showGenericMenu():
    params = ParameterHandler()
    sUrl = params.getValue('sUrl')
    sHtmlContent = cRequestHandler(sUrl).request()
    if not sHtmlContent: return
    oGui = cGui()

    if 'by=genre' in sUrl:
        # Search for h3 headings
        pattern = r'<h3[^>]*class="[^"]*h5[^"]*"[^>]*>([^<]+)</h3>'
        results = re.findall(pattern, sHtmlContent)
        
        for sGenreName in results:
            sName = sGenreName.strip()
            # Prefix entfernen, falls vorhanden
            sDisplay = sName.replace('filter.genre_', '').replace('_', ' ').capitalize()
            
            p = ParameterHandler()
            p.setParam('sUrl', sUrl)
            p.setParam('sName', sDisplay) # "Action"
            p.setParam('sGenreFilter', sName) # "filter.genre_action" for HTML search
            oGui.addFolder(cGuiElement(sDisplay, SITE_IDENTIFIER, 'showCatalog'), p)
    else:
        # A-Z Logik (bleibt wie gehabt)
        match_bar = re.search(r'class="alphabet-bar[^"]*">([\s\S]*?)</nav>', sHtmlContent)
        if match_bar:
            results = re.findall(r'href="(/katalog/[^"]+)"[^>]*>([^<]+)</a>', match_bar.group(1))
            for sNextUrl, sTitle in results:
                p = ParameterHandler()
                p.setParam('sUrl', URL_MAIN + sNextUrl)
                p.setParam('sName', sTitle.strip())
                oGui.addFolder(cGuiElement(sTitle.strip(), SITE_IDENTIFIER, 'showCatalog'), p)

    oGui.setEndOfDirectory()
                    
def showValue():
    params = ParameterHandler()
    sUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(sUrl)
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 24 # HTML Cache Zeit 1 Tag
    sHtmlContent = oRequest.request()
    isMatch, sContainer = cParser.parseSingleResult(sHtmlContent, '<ul[^>]*class="%s"[^>]*>(.*?)<\\/ul>' % params.getValue('sCont'))
    if isMatch:
        isMatch, aResult = cParser.parse(sContainer, '<li>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)<\\/a>\s*<\\/li>')
    if not isMatch:
        cGui().showInfo()
        return

    for sUrl, sName in aResult:
        sUrl = sUrl if sUrl.startswith('http') else URL_MAIN + sUrl
        params.setParam('sUrl', sUrl)
        cGui().addFolder(cGuiElement(sName, SITE_IDENTIFIER, 'showEntries'), params)
    cGui().setEndOfDirectory()


def showAllSeries(entryUrl=False, sGui=False, sSearchText=False):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    if not entryUrl: entryUrl = params.getValue('sUrl')
    oRequest = cRequestHandler(entryUrl, ignoreErrors=(sGui is not False))
    if cConfig().getSetting('global_search_' + SITE_IDENTIFIER) == 'true':
        oRequest.cacheTime = 60 * 60 * 24 # HTML Cache Zeit 1 Tag
    sHtmlContent = oRequest.request()
    pattern = '<a[^>]*href="(\\/serie\\/[^"]*)"[^>]*>(.*?)</a>'
    isMatch, aResult = cParser.parse(sHtmlContent, pattern)
    if not isMatch:
        if not sGui: oGui.showInfo()
        return

    total = len(aResult)
    for sUrl, sName in aResult:
        # --- FIX HTML-ENTITIES (Satbandit) ---
        #sName = unescape(sName)
        sName = unescape(sName)
        # ----------------------------------
        if sSearchText and not cParser.search(sSearchText, sName):
            continue
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setMediaType('tvshow')
        params.setParam('sUrl', sUrl if sUrl.startswith('http') else URL_MAIN + sUrl)
        params.setParam('TVShowTitle', sName)
        oGui.addFolder(oGuiElement, params, True, total)
    if not sGui:
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()


# Hilfsfunktion: Extrahiert alle Cards aus einem HTML-Block
def extractCards(sHtml):
    # s.to uses 'data-src' for images (lazy load)
    # Das Pattern sucht den Link, das Bild und den Namen
    pattern = r'href="([^"]+)"[^>]*class="show-card[^"]*".*?data-src="([^"]+)"[^>]*alt="([^"]+)"'
    
    # (?s) allows line breaks within a card
    return re.findall(r'(?s)' + pattern, sHtml)

def showGenericSeriesList(entryUrl=False):
    oGui = cGui()
    params = ParameterHandler()
    
    sUrl = params.getValue('sUrl') or (URL_MAIN + '/beliebte-serien')
    sectionName = params.getValue('sectionName')
    
    oRequest = cRequestHandler(sUrl)
    sHtmlContent = oRequest.request()
    dump_to_file(sHtmlContent, 'beliebte.html')

    # Clean HTML: collapse all whitespace/newlines to single space
    sHtmlContent = re.sub(r'\s+', ' ', sHtmlContent)

    if sectionName and sectionName in sHtmlContent:
        # Start: Direkt nach dem Sektionsnamen
        sHtmlContent = sHtmlContent.split(sectionName, 1)[1]
        
        # Ende: Wir suchen das Ende der Liste. 
        # S.to often closes grids with </ul> or </section>
        # A safe anchor is the next <h2 (next section heading)
        if '<h2' in sHtmlContent:
            sHtmlContent = sHtmlContent.split('<h2', 1)[0]
        elif '</section>' in sHtmlContent:
            sHtmlContent = sHtmlContent.split('</section>', 1)[0]
    
    # Cards extrahieren
    aResult = extractCards(sHtmlContent)

    if not aResult:
        # Fallback-Suche, falls das erste Pattern zu streng war
        pattern_fallback = r'href="([^"]+)"[^>]*>.*?data-src="([^"]+)"[^>]*alt="([^"]+)"'
        aResult = re.findall(r'(?s)' + pattern_fallback, sHtmlContent)

    seen = set()
    for sUrl, sThumbnail, sName in aResult:
        if sUrl in seen: continue
        seen.add(sUrl)
        
        if sUrl.startswith('/'): sUrl = URL_MAIN + sUrl
        if sThumbnail.startswith('/'): sThumbnail = URL_MAIN + sThumbnail
            
        oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setThumbnail(sThumbnail)
        oGuiElement.setMediaType('tvshow')
        
        # Important: New parameter instance for each folder!
        p = ParameterHandler()
        p.setParam('sUrl', sUrl)
        p.setParam('sName', sName)
        p.setParam('sThumbnail', sThumbnail)
        oGui.addFolder(oGuiElement, p, True, len(aResult))

    oGui.setView('tvshows')
    oGui.setEndOfDirectory() 

def showRoot():
    oGui = cGui()
    sHtmlContent = cRequestHandler(URL_MAIN, caching=True).request()
    
    if sHtmlContent:
        # Suche alle Buttons: data-bs-target="#section-0">Neueste Episoden</button>
        pattern = r'data-bs-target="#([^"]+)"[^>]*>([^<]+)</button>'
        sections = re.findall(pattern, sHtmlContent)

        seen_ids = set()
        for sId, sName in sections:
            sName = sName.strip()
            # Only add if this section (id) is not yet in the menu
            if sId not in seen_ids and "section-" in sId:
                oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showHomeSection')
                p = ParameterHandler()
                p.setParam('section_id', sId)
                p.setParam('sName', sName)
                oGui.addFolder(oGuiElement, p)
                seen_ids.add(sId)
    
    oGui.addFolder(cGuiElement('Suche', SITE_IDENTIFIER, 'showSearch'), ParameterHandler())
    oGui.setEndOfDirectory()
    
def showHomeSection():
    params = ParameterHandler()
    section_id = params.getValue('section_id')
    oGui = cGui()
    
    sHtmlContent = cRequestHandler(URL_MAIN, caching=True).request()
    if sHtmlContent:
        sHtmlContent = re.sub(r'\s+', ' ', sHtmlContent)
        # Search from ID to next section or end of tab-content
        section_pattern = f'id="{section_id}".*?(?:id="section-|</div> </div> </section>)'
        section_match = re.search(section_pattern, sHtmlContent)
        
        if section_match:
            fragment = section_match.group(0)
            if 'latest-episode-row' in fragment:
                renderEpisodes(oGui, fragment)
            else:
                renderCards(oGui, fragment)

    oGui.setView('tvshows')
    oGui.setEndOfDirectory()

def renderEpisodes(oGui, sHtml):
    # Der Trick: Wir suchen nach 'latest-episode-row' und lassen danach 
    # beliebige Zeichen zu, bis das 'href' kommt.
    pattern = r'class="latest-episode-row[^"]*"\s+href="([^"]+)".*?class="ep-title" title="([^"]+)".*?class="ep-season">([^<]+).*?class="ep-episode">([^<]+).*?use href="#icon-flag-([^"]+)"'
    
    results = re.findall(pattern, sHtml, re.DOTALL)
    
    for sLink, sTitle, sSeason, sEpisode, sLang in results:
        if sLink.startswith('#'): continue
        
        sTitle = unescape(sTitle).strip()
        # Format language labels (german -> DE, english -> EN)
        sLangLabel = 'DE' if 'german' in sLang else 'EN' if 'english' in sLang else sLang.upper()
        
        # Display name including language for overview
        sDisplay = f"{sTitle} ({sSeason.strip()}{sEpisode.strip()}) [{sLangLabel}]"
        
        # Clean URL to season level
        sCleanUrl = re.sub(r'/episode-\d+', '', sLink)
        sFullUrl = URL_MAIN + sCleanUrl if sCleanUrl.startswith('/') else sCleanUrl
        
        # Nur die Zahl aus "E08" -> "8"
        sEpNum = re.sub(r'\D', '', sEpisode)
        
        oGuiElement = cGuiElement(sDisplay, SITE_IDENTIFIER, 'showEpisodes')
        # Falls du das Cover der Serie hast, hier sThumbnail nutzen
        oGuiElement.setThumbnail("DefaultVideo.png") 
        
        p = ParameterHandler()
        p.setParam('sUrl', sFullUrl)
        p.setParam('sName', sTitle)
        p.setParam('sTargetEpisode', sEpNum)
        
        oGui.addFolder(oGuiElement, p)

def renderCards(oGui, sHtml):
    # Dieses Regex deckt die Card-Struktur ab:
    # 1. Das Bild (data-src)
    # 2. Den Link zur Serie (href)
    # 3. Den Titel (im h3-Tag oder title-Attribut)
    pattern = r'<img\s+data-src="([^"]+)"[^>]*>.*?<a\s+href="([^"]+)">\s*<h3\s+title="([^"]+)"'
    
    # re.DOTALL needed due to line breaks between image and link
    results = re.findall(pattern, sHtml, re.DOTALL)
    
    for sThumb, sLink, sTitle in results:
        # If URL is relative, prepend main URL
        sFullUrl = URL_MAIN + sLink if sLink.startswith('/') else sLink
        sTitle = unescape(sTitle).strip()
        
        oGuiElement = cGuiElement(sTitle, SITE_IDENTIFIER, 'showSeasons')
        
        # Hier nutzen wir das extrahierte data-src als Thumbnail
        oGuiElement.setThumbnail(sThumb)
        
        p = ParameterHandler()
        p.setParam('sUrl', sFullUrl)
        p.setParam('sName', sTitle)
        p.setParam('sThumbnail', sThumb)
        oGui.addFolder(oGuiElement, p)
    
def showBeliebte(sGui=False):
    oGui = sGui if sGui else cGui()
    sHtmlContent = cRequestHandler(URL_POPULAR, caching=True).request()
    
    if not sHtmlContent: return
    sHtmlContent = re.sub(r'\s+', ' ', sHtmlContent)

    # Find all H2 and H3 headings
    # Diese markieren den Start jeder Sektion
    titles = re.findall(r'<(?:h2|h3)[^>]*>(.*?)</(?:h2|h3)>', sHtmlContent)

    for sTitle in titles:
        # Remove HTML tags (e.g. <span> or emojis)
        sCleanTitle = re.sub(r'<[^>]*>', '', sTitle).strip()
        # Strip special chars/emojis for submenu matching
        sCleanTitle = ''.join(c for c in sCleanTitle if ord(c) < 128).strip()
        
        if not sCleanTitle or any(x in sCleanTitle for x in ['Kategorien', 'durchsuchen', 'Entdecken']):
            continue

        oGuiElement = cGuiElement(sCleanTitle, SITE_IDENTIFIER, 'showSectionContent')
        p = ParameterHandler()
        p.setParam('sSectionTitle', sCleanTitle)
        oGui.addFolder(oGuiElement, p)

    oGui.setEndOfDirectory()

def showSectionContent():
    params = ParameterHandler()
    sTargetTitle = params.getValue('sSectionTitle')
    oGui = cGui()
    
    sHtmlContent = cRequestHandler(URL_POPULAR, caching=True).request()
    if not sHtmlContent: return
    sHtmlContent = re.sub(r'\s+', ' ', sHtmlContent)

    # Find section from our heading to the next one
    find_section = r'<(?:h2|h3)[^>]*>[^<]*' + re.escape(sTargetTitle) + r'.*?</(?:h2|h3)>(.*?)(?=<h2|<h3|$)'
    match = re.search(find_section, sHtmlContent)

    if match:
        sFragment = match.group(1)
        # Regex for link, thumbnail and alt text
        pattern = r'href="(/serie/[^"]+)".*?<img.*?(?:data-src|src)="([^"]+)".*?alt="([^"]+)"'
        items = re.findall(pattern, sFragment)

        # Um Dubletten zu vermeiden (wegen <picture> Tags)
        seen_links = set()

        for sLink, sThumb, sName in items:
            # 1. HTML Entities dekodieren (macht aus &amp; ein &)
            sName = unescape(sName).strip()
            
            # 2. Staffel-Zusatz im Link entfernen
            sSeriesLink = sLink.split('/staffel-')[0]
            
            # Dubletten-Check
            if sSeriesLink in seen_links: continue
            seen_links.add(sSeriesLink)

            # Platzhalter-GIFs ignorieren
            if 'data:image/gif' in sThumb and 'data-src="' in sFragment:
                continue

            oGuiElement = cGuiElement(sName, SITE_IDENTIFIER, 'showSeasons')
            if sThumb.startswith('/'): sThumb = URL_MAIN + sThumb
            oGuiElement.setThumbnail(sThumb)
            
            p = ParameterHandler()
            p.setParam('sUrl', URL_MAIN + sSeriesLink)
            p.setParam('sName', sName)
            p.setParam('sThumbnail', sThumb)
            oGui.addFolder(oGuiElement, p)

    oGui.setEndOfDirectory()

def extractPoster(sHtml):
    sThumbnail = ""
    # 1. Versuch: Desktop-Container (aus deinem Dump: col-lg-2)
    match = re.search(r'class="[^"]*col-lg-2[^"]*">.*?<img[^>]+data-src="([^"]+)"', sHtml, re.DOTALL)
    
    # 2. Versuch: Mobile-Container (aus deinem Dump: show-cover-mobile)
    if not match:
        match = re.search(r'class="[^"]*show-cover-mobile[^"]*">.*?<img[^>]+data-src="([^"]+)"', sHtml, re.DOTALL)
        
    if match:
        sThumbnail = match.group(1).strip()
        # Complete relative URLs
        if sThumbnail.startswith('/'):
            sThumbnail = URL_MAIN + sThumbnail
        # Optimize image format for Kodi (jpg instead of webp/avif)
        sThumbnail = sThumbnail.replace('format=webp', 'format=jpg').replace('format=avif', 'format=jpg')
        
    return sThumbnail      
         
def showSeasons():
    params = ParameterHandler()
    sUrl = params.getValue('sUrl')
    sName = params.getValue('sName')
    sThumbnail = params.getValue('sThumbnail')
    sAliasSearch = params.getValue('sAliasSearch')
    
    oGui = cGui()
    sHtmlContent = cRequestHandler(sUrl, caching=True).request()
    if not sHtmlContent: return

    # 1. Serienname fixen (falls von Favoriten/Suche kommend)
    title_match = re.search(r'<title>(.*?)\s+Staffel', sHtmlContent)
    if title_match:
        sName = title_match.group(1).strip()
    elif not sName or sName == 'False':
        sName = "Serie"

    # 2. Description (extract from span "description-text")
    sDesc = ''
    # Suche speziell nach dem span-Inhalt
    match_span = re.search(r'<span class="description-text">(.*?)</span>', sHtmlContent, re.DOTALL)
    if match_span:
        sDesc = unescape(match_span.group(1)).strip()
        # HTML-Reste entfernen (falls vorhanden)
        sDesc = re.sub(r'<[^>]*>', '', sDesc)
    
    # Fallback auf Meta-Description, falls der span leer war
    if not sDesc:
        match_desc = re.search(r'name="description"\s+content="([^"]+)"', sHtmlContent)
        if match_desc:
            sDesc = unescape(match_desc.group(1)).strip()

    # 3. Poster extrahieren
    if not sThumbnail: sThumbnail = extractPoster(sHtmlContent)

    # 4. Staffeln finden (aus deinem Web-Dump)
    # Sucht nach Links wie /staffel-1, /staffel-2 etc.
    pattern = r'href="([^"]+/staffel-(\d+))"'
    results = re.findall(pattern, sHtmlContent)

    # --- FIX START Aki: Sortierung der Staffeln ---
    # Dubletten entfernen und Mapping erstellen
    seasons_map = {}
    for sSeasonUrl, sSeasonNum in results:
        if sSeasonNum not in seasons_map:
            seasons_map[sSeasonNum] = sSeasonUrl

    # Sortieren nach Zahl (damit 0 vor 1 kommt, und 10 nach 2)
    sorted_keys = sorted(seasons_map.keys(), key=lambda x: int(x))

    # 1.0.5: Anthology mapping for TMDb entries that are separate shows but are
    # grouped as seasons on SerienStream. We only activate this for an alias
    # fallback coming from TMDb Helper, so normal/manual browsing is untouched.
    # Example: "Monster – Die Geschichte von Lizzie Borden" is TMDb season 1,
    # while SerienStream stores it as Monster (2022) season 4.
    target_real_season = None
    if sAliasSearch and sDesc:
        try:
            alias_text = unescape(str(sAliasSearch)).strip()

            def _norm_match(value):
                value = unescape(value or '').lower()
                value = re.sub(r'[^a-z0-9äöüß]+', ' ', value)
                value = re.sub(r'\s+', ' ', value).strip()
                return value

            # Compare several meaningful parts of the alias. This covers both
            # "Monster: Die Geschichte von Lizzie Borden" and nested titles such
            # as "Dahmer - Monster: Die Geschichte von Jeffrey Dahmer".
            alias_candidates = [alias_text]
            alias_candidates.extend([
                part.strip() for part in re.split(r'\s+(?:–|—|-)\s+|\s*:\s*', alias_text)
                if part.strip()
            ])
            alias_norms = []
            for candidate in alias_candidates:
                norm = _norm_match(candidate)
                if norm and norm not in alias_norms:
                    alias_norms.append(norm)

            season_descriptions = re.findall(
                r'Staffel\s*(\d+)\s*:\s*([^;\]\r\n]+)',
                sDesc,
                re.IGNORECASE
            )
            # Fuzzy token comparison for small spelling/data differences between
            # TMDb and SerienStream. Example: TMDb "Lyle und Erik Menendez" vs.
            # SerienStream "Die Brüder Lyle ud Erik Menendes".
            from difflib import SequenceMatcher

            stop_words = {
                'die', 'der', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einer',
                'eines', 'von', 'und', 'ud', 'geschichte', 'brüder', 'brueder',
                'bruder', 'the', 'story', 'of'
            }

            def _meaningful_tokens(value):
                norm = _norm_match(value)
                return [tok for tok in norm.split() if tok and tok not in stop_words]

            def _fuzzy_tokens_match(left, right):
                left_tokens = _meaningful_tokens(left)
                right_tokens = _meaningful_tokens(right)
                if not left_tokens or not right_tokens:
                    return False

                # Avoid weak one-word matches. Anthology chapter names normally
                # contain at least a first/last name pair (Ed Gein, Lizzie Borden).
                if min(len(left_tokens), len(right_tokens)) < 2:
                    return False

                smaller, larger = (left_tokens, right_tokens) if len(left_tokens) <= len(right_tokens) else (right_tokens, left_tokens)
                matched_count = 0
                used = set()
                for token in smaller:
                    best_idx = None
                    best_ratio = 0.0
                    for idx, other in enumerate(larger):
                        if idx in used:
                            continue
                        ratio = 1.0 if token == other else SequenceMatcher(None, token, other).ratio()
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_idx = idx
                    if best_idx is not None and best_ratio >= 0.84:
                        matched_count += 1
                        used.add(best_idx)

                # Require all tokens of the shorter meaningful name to match.
                return matched_count == len(smaller)

            for season_num, season_desc in season_descriptions:
                desc_norm = _norm_match(season_desc)
                matched = any(
                    alias_norm and desc_norm and (
                        alias_norm in desc_norm or
                        desc_norm in alias_norm or
                        _fuzzy_tokens_match(alias_norm, desc_norm)
                    )
                    for alias_norm in alias_norms
                )
                if matched and season_num in seasons_map:
                    target_real_season = season_num
                    logger.info('[SerienStream] Anthology mapping: "%s" -> real Staffel %s (%s)' % (
                        alias_text, season_num, season_desc.strip()))
                    break
        except Exception as e:
            logger.error('[SerienStream] Anthology mapping failed: %s' % str(e))

    # If an anthology target was detected, expose only that real season to the
    # TMDb Helper and label it as Staffel 1. TMDb sees Lizzie Borden/Ed Gein etc.
    # as independent shows with season 1, while the URL still points to the real
    # SerienStream season (e.g. /staffel-4).
    iter_keys = [target_real_season] if target_real_season else sorted_keys

    for sSeasonNum in iter_keys:
        sSeasonUrl = seasons_map[sSeasonNum]
        
        if target_real_season:
            sDisplay = "Staffel 1"
        elif sSeasonNum == '0':
            sDisplay = "Specials"
        else:
            sDisplay = "Staffel %s" % sSeasonNum
        
        oGuiElement = cGuiElement(sDisplay, SITE_IDENTIFIER, 'showEpisodes')
        oGuiElement.setThumbnail(sThumbnail)
        oGuiElement.setTVShowTitle(sName)
        
        # Beschreibung hier ebenfalls setzen
        if sDesc:
            oGuiElement.setDescription(sDesc)

        p = ParameterHandler()
        p.setParam('sUrl', URL_MAIN + sSeasonUrl if sSeasonUrl.startswith('/') else sSeasonUrl)
        p.setParam('sName', sName)
        p.setParam('sThumbnail', sThumbnail)
        # Pass description to next level
        p.setParam('sDescription', sDesc) 
        
        oGui.addFolder(oGuiElement, p)
    # --- FIX END ---

    oGui.setView('seasons')
    oGui.setEndOfDirectory()
    
def showEpisodes():
    params = ParameterHandler()
    sUrl = params.getValue('sUrl')
    sTVShowTitle = params.getValue('TVShowTitle')
    sThumbnail = params.getValue('sThumbnail')
    sDesc = params.getValue('sDescription')
    
    oRequest = cRequestHandler(sUrl)
    sHtmlContent = oRequest.request()
    if not sHtmlContent: return

    # 1. Serienname & Beschreibung (wie gehabt)
    if not sTVShowTitle or sTVShowTitle == 'False':
        title_match = re.search(r'<title>(.*?)\s+Staffel', sHtmlContent)
        if title_match: sTVShowTitle = title_match.group(1).strip()
        
    if not sDesc:
       # 1. Plot/Beschreibung extrahieren
       match_plot = re.search(r'<span class="description-text">(.*?)</span>', sHtmlContent, re.DOTALL)
       if match_plot:
          sDesc = unescape(match_plot.group(1)).strip()

    if not sThumbnail: sThumbnail = extractPoster(sHtmlContent)
		
    # 2. Episoden-Tabelle parsen
    # Wir suchen die Nummer (episode-number-cell) und den deutschen Titel (episode-title-ger)
    # Und wir brauchen den Link zur Episode (den wir aus der Navigation oder den Zeilen holen)
    
    # Extract rows/blocks to link URLs and titles
    # Da die Links in der Navigation oben stehen und die Titel unten in der Tabelle,
    # Most stable approach: use the table for names:
    pattern = r'<th[^>]*>\s*(\d+)\s*</th>[\s\S]*?class="[^"]*episode-title-(?:ger|eng)"[^>]*>\s*([^<]+)\s*<'
    titles_dict = dict(re.findall(pattern, sHtmlContent, re.DOTALL))

    # Jetzt holen wir die Links aus der Navigation (wie zuvor)
    pattern_nav = r'href="([^"]*/episode-(\d+))"'
    nav_links = re.findall(pattern_nav, sHtmlContent)
    
    # Dubletten aus der Navigation entfernen (da oft mehrfach vorhanden)
    seen_eps = set()
    unique_nav = []
    for url, ep_nr in nav_links:
        if ep_nr not in seen_eps:
            seen_eps.add(ep_nr)
            unique_nav.append((url, ep_nr))

    oGui = cGui()
    total = len(unique_nav)
    
    for sUrl2, sEpNr in unique_nav:
        # Den passenden Titel aus unserem Tabellen-Dict holen
        sEpName = titles_dict.get(sEpNr, "").strip()
        sEpName = unescape(sEpName)
        
        # Formatierung: "1 - Der Tote am See"
        sDisplayTitle = "Episode %s" % sEpNr
        if sEpName:
            sDisplayTitle += " - %s" % sEpName
        
        oGuiElement = cGuiElement(sDisplayTitle, SITE_IDENTIFIER, 'showHosters')
        oGuiElement.setMediaType('episode')

        # Preserve episode identity on the actual Kodi ListItem.
        # TMDb Helper knows season/episode before resolving SerienStream, but
        # SerienStream previously dropped both values here. script.trakt then
        # saw an "episode" without S/E numbers and skipped the rating dialog.
        try:
            season_match = re.search(r'/staffel-(\\d+)', str(sUrl), re.IGNORECASE)
            if season_match:
                oGuiElement.setSeason(int(season_match.group(1)))
            oGuiElement.setEpisode(int(sEpNr))
        except Exception as e:
            logger.error('[SerienStream] Failed to set episode metadata: %s' % str(e))
        
        if sThumbnail: oGuiElement.setThumbnail(sThumbnail)
        if sDesc: oGuiElement.setDescription(sDesc)
        
        oGuiElement.setTVShowTitle(sTVShowTitle)
        
        p = ParameterHandler()
        p.setParam('sUrl', URL_MAIN + sUrl2 if not sUrl2.startswith('http') else sUrl2)
        p.setParam('sThumbnail', sThumbnail)
        p.setParam('sDescription', sDesc)
        
        oGui.addFolder(oGuiElement, p, False, total)
        
    oGui.setView('episodes')
    oGui.setEndOfDirectory()


def showHosters():
    hosters = []
    sUrl = ParameterHandler().getValue('sUrl')
    sHtmlContent = cRequestHandler(sUrl, caching=False).request()
    
    if not sHtmlContent:
        return []

    # Find all buttons (containers)
    button_pattern = r'<button[^>]*class="[^"]*link-box[^"]*"[^>]*>'
    buttons = re.findall(button_pattern, sHtmlContent)

    for sButton in buttons:
        # Individual extraction: HTML order does not matter
        url_match = re.search(r'data-play-url="([^"]+)"', sButton)
        name_match = re.search(r'data-provider-name="([^"]+)"', sButton)
        lang_match = re.search(r'data-language-id="([^"]+)"', sButton)

        if url_match and name_match and lang_match:
            sHUrl = url_match.group(1)
            sName = name_match.group(1)
            sLang = lang_match.group(1)

            # --- Language filter logic ---
            if cConfig().isBlockedHoster(sName)[0]: continue
            
            sLanguage = cConfig().getSetting('prefLanguage')
            if sLanguage == '1' and sLang != '1': continue
            if sLanguage == '2' and sLang != '2': continue
            
            sLangLabel = '(DE)' if sLang == '1' else '(EN)' if sLang == '2' else sLang
            sQuality = '720'
            
            # Structure required by the core for display
            hoster = {
                'link': [sHUrl, sName], 
                'name': sName, 
                'displayedName': '%s [I]%s [%sp][/I]' % (sName, sLangLabel, sQuality), 
                'quality': sQuality, 
                'languageCode': sLangLabel
            }
            hosters.append(hoster)

    # Append function name for core callback
    if hosters:
        hosters.append('getHosterUrl')
    if not hosters:
        cGui().showLanguage()
    return hosters

def getHosterUrl(hUrl):
    if type(hUrl) == str: hUrl = eval(hUrl)
    Request = cRequestHandler(URL_MAIN + hUrl[0], caching=False)
    Request.addHeaderEntry('Referer', ParameterHandler().getValue('entryUrl'))
    Request.addHeaderEntry('Upgrade-Insecure-Requests', '1')
    Request.request()
    sUrl = Request.getRealUrl()

    if 'voe' in hUrl[1].lower():
        isBlocked, sDomain = cConfig().isBlockedHoster(sUrl)  # Function returns 2 values!
        if isBlocked:  # VOE pseudo domain not known in resolveUrl
            sUrl = sUrl.replace(sDomain, 'voe.sx')
            return [{'streamUrl': sUrl, 'resolved': False}]

    return [{'streamUrl': sUrl, 'resolved': False}]

def showSearch():
    sSearchText = cGui().showKeyBoard(sHeading=cConfig().getLocalizedString(30281))
    if not sSearchText: return
    _search(False, sSearchText)
    cGui().setEndOfDirectory()

def _search(oGui, sSearchText):
    SSsearch(oGui, sSearchText)

def SSsearch(sGui=False, sSearchText=False, iPage=1):
    oGui = sGui if sGui else cGui()
    params = ParameterHandler()
    
    # Suchtext priorisieren: Erst aus dem Argument, dann aus den Params
    if not sSearchText:
        sSearchText = params.getValue('sSearchText')
    
    # If iPage comes as string from params (when browsing)
    if params.getValue('iPage'):
        iPage = params.getValue('iPage')

    if not sSearchText:
        return

    # Wir bauen die URL jetzt explizit so, wie s.to sie bei direkten Aufrufen erwartet
    # Wichtig: Seite als Zahl mitschicken
    sUrl = f"{URL_MAIN}/suche?term={quote_plus(str(sSearchText))}&tab=shows&page={str(iPage)}"
    
    oRequest = cRequestHandler(sUrl, caching=True)
    sHtmlContent = oRequest.request()
    
    if not sHtmlContent:
        return

    sHtmlContent = re.sub(r'\s+', ' ', sHtmlContent)
    found_links = set()

    # Regex for card structure
    pattern = r'class="card cover-card.*?href="(/serie/[^"]+)".*?(?:data-src|src)="([^"]+)".*?alt="([^"]+)"'
    aResult = re.findall(pattern, sHtmlContent)

    # 1.0.4: Robust fallback for TMDb titles with subtitles / anthology season names.
    # Example 1: "Steel Buddies – Stahlharte Geschäfte" -> "Steel Buddies"
    # Example 2: "Monster – Die Geschichte von Lizzie Borden" -> "Monster (2022)"
    #
    # Important: TMDb Helper can use strict title matching. Therefore, when the
    # fallback finds the canonical SerienStream title, we keep its real URL but
    # expose the ORIGINAL requested title as the list label. This lets TMDb Helper
    # select the series and then continue with its requested season/episode.
    sOriginalSearchText = str(sSearchText).strip()
    sFallbackText = ''
    bFallbackUsed = False
    bAliasFallbackResult = False

    if not aResult and int(iPage) == 1:
        # Build fallback candidates from the TMDb title. Most titles work with the
        # first part ("Steel Buddies – ..." -> "Steel Buddies"). Some anthology
        # entries however carry an alternate title before the real parent series,
        # e.g. "Dahmer - Monster: Die Geschichte von Jeffrey Dahmer". In that
        # case the useful canonical SerienStream title is "Monster", not "Dahmer".
        fallback_candidates = []

        first_part = re.split(r'\s+(?:–|—|-)\s+|\s*:\s+', sOriginalSearchText, maxsplit=1)[0].strip()
        if first_part:
            fallback_candidates.append(first_part)

        # If the title contains " - ParentSeries: Subtitle", also try ParentSeries.
        parent_match = re.search(r'\s+(?:–|—|-)\s+([^:]+?)\s*:\s*.+$', sOriginalSearchText)
        if parent_match:
            parent_title = parent_match.group(1).strip()
            if parent_title:
                fallback_candidates.append(parent_title)

        # De-duplicate candidates while preserving order and never retry the exact
        # original title.
        seen_candidates = set()
        fallback_candidates = [
            c for c in fallback_candidates
            if c and c.lower() != sOriginalSearchText.lower()
            and not (c.lower() in seen_candidates or seen_candidates.add(c.lower()))
        ]

        def _norm_title(value):
            value = unescape(value or '').strip().lower()
            value = re.sub(r'\s*\((?:19|20)\d{2}\)\s*$', '', value)
            value = re.sub(r'\s+', ' ', value)
            return value.strip()

        best_fallback_results = None
        best_fallback_text = ''

        for candidate in fallback_candidates:
            logger.info('[SerienStream] Search fallback: "%s" -> "%s"' % (sOriginalSearchText, candidate))
            sFallbackUrl = f"{URL_MAIN}/suche?term={quote_plus(candidate)}&tab=shows&page=1"
            oFallbackRequest = cRequestHandler(sFallbackUrl, caching=True)
            sFallbackHtml = oFallbackRequest.request()
            if not sFallbackHtml:
                continue

            sFallbackHtml = re.sub(r'\s+', ' ', sFallbackHtml)
            fallbackResults = re.findall(pattern, sFallbackHtml)
            if not fallbackResults:
                continue

            bFallbackUsed = True
            exactCanonical = [r for r in fallbackResults if _norm_title(r[2]) == _norm_title(candidate)]
            if exactCanonical:
                aResult = exactCanonical
                sFallbackText = candidate
                bAliasFallbackResult = True
                logger.info('[SerienStream] Search fallback canonical match: %s' % ', '.join([unescape(r[2]) for r in exactCanonical]))
                break

            # Keep the first non-empty fallback only as a last resort, but continue
            # trying later candidates because they may produce an exact canonical
            # parent-series match (e.g. Dahmer -> Monster).
            if best_fallback_results is None:
                best_fallback_results = fallbackResults
                best_fallback_text = candidate

        if not aResult and best_fallback_results:
            aResult = best_fallback_results
            sFallbackText = best_fallback_text

        if aResult and sFallbackText:
            # Keep pagination tied to the query that actually produced results.
            sSearchText = sFallbackText
            logger.info('[SerienStream] Search fallback found %d result(s)' % len(aResult))

    total = len(aResult)
    for sLink, sThumbnail, sTitle in aResult:
        if sLink in found_links: continue
        found_links.add(sLink)
        
        if 'data:image/gif' in sThumbnail: continue

        sTitle = unescape(sTitle)
        sRealTitle = sTitle
        sDisplayTitle = sOriginalSearchText if bAliasFallbackResult else sRealTitle
        sFullUrl = URL_MAIN + sLink if sLink.startswith('/') else sLink
        sFullThumb = URL_MAIN + sThumbnail if sThumbnail.startswith('/') else sThumbnail

        if bAliasFallbackResult:
            logger.info('[SerienStream] TMDb alias: "%s" -> "%s" (%s)' % (sOriginalSearchText, sRealTitle, sFullUrl))

        oGuiElement = cGuiElement(sDisplayTitle, SITE_IDENTIFIER, 'showSeasons')
        oGuiElement.setThumbnail(sFullThumb)
        
        p = ParameterHandler()
        p.setParam('sUrl', sFullUrl)
        # Keep the canonical SerienStream name internally while exposing the alias
        # only as the selectable list label for TMDb Helper strict matching.
        p.setParam('sName', sRealTitle)
        p.setParam('sThumbnail', sFullThumb)
        # Preserve the original TMDb title only for alias-fallback results.
        # showSeasons can use its subtitle to map anthology entries to the
        # correct real SerienStream season (e.g. Lizzie Borden -> season 4).
        if bAliasFallbackResult:
            p.setParam('sAliasSearch', sOriginalSearchText)
        
        oGui.addFolder(oGuiElement, p)

    # Next page logic
    if total >= 20:
        p = ParameterHandler()
        p.setParam('sSearchText', sSearchText)
        p.setParam('iPage', str(int(iPage) + 1)) # Explicitly increment page
        oGui.addNextPage(SITE_IDENTIFIER, 'SSsearch', p)

    if not sGui:
        oGui.setView('tvshows')
        oGui.setEndOfDirectory()
                
def getMetaInfo(link, title):   # Setzen von Metadata in Suche:
    oGui = cGui()
    oRequest = cRequestHandler(link if link.startswith('http') else URL_MAIN + link, caching=False)
    sHtmlContent = oRequest.request()
    if not sHtmlContent:
        return

    pattern = 'show-cover-mobile.*?(?:data-src|src)="([^"]+)".*?class="series-description".*?<span[^>]*class="description-text">([^<]+)</span>' #img , descr

    aResult = cParser.parse(sHtmlContent, pattern)

    if not aResult[0]:
        return

    for sImg, sDescr in aResult[1]:
        return sImg, sDescr
        
def dump_to_file(content, filename="/tmp/debug_sto.html"):
    try:
        # Pfad im Home-Verzeichnis deines Debian-Users oder im Kodi-Temp-Ordner
        import os
        path = os.path.join(os.path.expanduser("~"), filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"[{SITE_IDENTIFIER}] Dump erstellt unter: {path}")
    except Exception as e:
        logger.error(f"[{SITE_IDENTIFIER}] Dump fehlgeschlagen: {str(e)}")
