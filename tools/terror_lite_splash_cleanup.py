# -*- coding: utf-8 -*-
"""TerrorLite: safe retirement of Kodi's separate startup splash.

Runs from Startup.xml after the skin loads. Kodi reads advancedsettings.xml
at process launch, so this takes effect on the following Kodi restart.
Backs up a writable user Splash.png; never touches Kodi's packaged system image.
"""
import hashlib
import os
import shutil
from xml.dom import minidom

import xbmc
import xbmcvfs

LOG_TAG = '[TerrorLite Splash Cleanup] '


def log(message, level=None):
    if level is None:
        level = xbmc.LOGINFO
    xbmc.log(LOG_TAG + message, level)


def path(url):
    return xbmcvfs.translatePath(url)


def digest(filename):
    sha = hashlib.sha256()
    with open(filename, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 128), b''):
            sha.update(block)
    return sha.digest()


def disable_splash_setting():
    """Preserve all other advancedsettings elements, attributes and comments."""
    dest = path('special://masterprofile/advancedsettings.xml')
    if os.path.isfile(dest):
        with open(dest, 'rb') as stream:
            original = stream.read()
        doc = minidom.parseString(original)
        root = doc.documentElement
        if root.tagName != 'advancedsettings':
            raise ValueError('unexpected advancedsettings.xml root: ' + root.tagName)
        splash_nodes = [node for node in root.childNodes
                        if node.nodeType == node.ELEMENT_NODE and node.tagName == 'splash']
        if len(splash_nodes) > 1:
            raise ValueError('duplicate splash settings found; refusing automatic edit')
        if splash_nodes:
            current = splash_nodes[0]
            value = ''.join(n.data for n in current.childNodes
                            if n.nodeType in (n.TEXT_NODE, n.CDATA_SECTION_NODE)).strip()
            if value.lower() == 'false':
                log('Kodi native splash already disabled')
                return
            for n in list(current.childNodes):
                if n.nodeType in (n.TEXT_NODE, n.CDATA_SECTION_NODE):
                    current.removeChild(n)
            current.appendChild(doc.createTextNode('false'))
        else:
            root.appendChild(doc.createTextNode('\n    '))
            node = doc.createElement('splash')
            node.appendChild(doc.createTextNode('false'))
            root.appendChild(node)
            root.appendChild(doc.createTextNode('\n'))
        revised = doc.toxml(encoding='utf-8')
        if original == revised:
            return
        backup = dest + '.terrorlite-splash-backup'
        if not os.path.exists(backup):
            shutil.copy2(dest, backup)
            if digest(dest) != digest(backup):
                raise IOError('advancedsettings backup does not match original')
    else:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        revised = (b'<?xml version="1.0" encoding="utf-8"?>\n'
                   b'<advancedsettings>\n    <splash>false</splash>\n'
                   b'</advancedsettings>\n')
    tmp = dest + '.terrorlite-splash-tmp'
    try:
        with open(tmp, 'wb') as stream:
            stream.write(revised)
        minidom.parse(tmp)
        os.replace(tmp, dest)
    finally:
        if os.path.isfile(tmp):
            os.remove(tmp)
    log('set splash=false in special://masterprofile/advancedsettings.xml')


def backup_custom_splash():
    """Retire writable media overrides; Kodi APK/system files are untouched."""
    folder = path('special://home/media/')
    if not os.path.isdir(folder):
        return
    backups = path('special://masterprofile/addon_data/skin.terror.lite/splash-backup/')
    for name in os.listdir(folder):
        if name.lower() != 'splash.png':
            continue
        source = os.path.join(folder, name)
        if not os.path.isfile(source):
            continue
        os.makedirs(backups, exist_ok=True)
        backup = os.path.join(backups, name)
        if os.path.exists(backup) and digest(source) != digest(backup):
            count = 2
            while os.path.exists(os.path.join(backups, '%s.%d.bak' % (name, count))):
                count += 1
            backup = os.path.join(backups, '%s.%d.bak' % (name, count))
        if not os.path.exists(backup):
            shutil.copy2(source, backup)
            if digest(source) != digest(backup):
                raise IOError('splash image backup checksum mismatch')
        os.remove(source)
        log('retired user startup image %s (backup saved)' % name)


def main():
    if xbmc.getSkinDir() != 'skin.terror.lite':
        return
    for action in (disable_splash_setting, backup_custom_splash):
        try:
            action()
        except Exception as exc:
            log('unable to update Kodi splash configuration: %s' % exc, xbmc.LOGERROR)


if __name__ == '__main__':
    main()
