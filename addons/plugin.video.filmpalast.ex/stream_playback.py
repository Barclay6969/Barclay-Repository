"""Stream classification and narrowly scoped playback experiments.

Do not force live/VOD flags on ISA: HLS media playlists decide that themselves.
Do not set ISA buffer properties: the Kodi 21 implementation disables them.
"""
from urllib.parse import parse_qsl, urlsplit

_HLS_TYPES = {'application/vnd.apple.mpegurl', 'application/x-mpegurl',
              'audio/mpegurl', 'audio/x-mpegurl'}


def manifest_kind(url, encoded_headers=None, http_get=None):
    """Detect extensionless manifests with a bounded, closed HTTP probe.

    Known media files do not incur a request. Probe failures retain the native
    playback path. Headers, including authentication, are forwarded unchanged;
    Kodi transport options are not HTTP headers.
    """
    path = urlsplit(url).path.lower()
    if path.endswith(('.m3u8', '.m3u')):
        return 'hls'
    if path.endswith('.mpd'):
        return 'mpd'
    if path.endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.ts', '.m2ts', '.mp3')):
        return None
    if urlsplit(url).scheme.lower() not in ('http', 'https'):
        return None
    headers = dict(parse_qsl(encoded_headers or '', keep_blank_values=True))
    verify = False  # Preserve the existing player TLS behavior.
    for key in list(headers):
        if key.lower() == 'verifypeer':
            verify = headers.pop(key).lower() not in ('false', '0')
        elif key.lower() in ('connection-timeout', 'seekable', 'cache', 'noshout', 'encoding'):
            headers.pop(key)
    headers['Range'] = 'bytes=0-4095'
    response = None
    try:
        if http_get is None:
            import requests
            http_get = requests.get
        response = http_get(url, headers=headers, stream=True,
                            timeout=(3, 5), allow_redirects=True, verify=verify)
        if response.status_code not in (200, 206):
            return None
        mime = response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
        if mime in _HLS_TYPES:
            return 'hls'
        if mime == 'application/dash+xml':
            return 'mpd'
        # A server can ignore Range; never access response.content/text here.
        prefix = response.raw.read(4096).lstrip(b'\xef\xbb\xbf \t\r\n')
        if prefix.startswith(b'#EXTM3U'):
            return 'hls'
        if b'<MPD' in prefix[:2048]:
            return 'mpd'
    except Exception:
        return None
    finally:
        if response is not None:
            response.close()
    return None
