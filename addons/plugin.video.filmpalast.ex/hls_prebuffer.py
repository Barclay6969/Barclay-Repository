"""Experimental, playback-scoped HLS read-ahead proxy.

Configurable 16-512 MiB cache, one speculative downloader, no disk writes.
VOD and live media playlists are prefetched. All URL-bearing manifest lines/attributes are
rewritten, preserving keys, audio playlists, queries and request headers.
"""
import base64
import queue
import re
import secrets
import threading
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urljoin, urlsplit
import requests

CACHE_LIMIT = 320 * 1024 * 1024
OBJECT_LIMIT = 32 * 1024 * 1024
MANIFEST_LIMIT = 1024 * 1024
LOOKAHEAD = 24


class HLSPrebuffer:
    def __init__(self, encoded_headers=None, log=None, cache_mb=320):
        try:
            size = int(float(cache_mb))
        except (TypeError, ValueError, OverflowError):
            size = 320
        self.cache_limit = max(16, min(512, size)) * 1024 * 1024
        self.object_limit = min(OBJECT_LIMIT, self.cache_limit // 2)
        self.lookahead = max(LOOKAHEAD, self.cache_limit // (2 * 1024 * 1024))
        self.headers = dict(parse_qsl(encoded_headers or '', keep_blank_values=True))
        self.verify = False  # Match ISA ssl_verify_peer=false in the 150 player.
        for key in list(self.headers):
            if key.lower() == 'verifypeer':
                self.verify = self.headers.pop(key).lower() not in ('false', '0')
            elif key.lower() in ('connection-timeout', 'seekable', 'cache', 'noshout', 'encoding', 'range'):
                self.headers.pop(key)
        self.log = log or (lambda _: None)
        self.token = secrets.token_urlsafe(24)
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.cache = OrderedDict()
        self.cache_bytes = 0
        self.positions = {}
        self.playlists = {}
        self.scheduled = set()
        self.tasks = queue.Queue(maxsize=self.lookahead * 4)
        self.hits = self.downloads = self.failures = 0
        self.server = None

    def start(self, url):
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # Signed URLs and authentication never enter the Kodi log.

            def do_HEAD(self):
                if not self.path.startswith('/' + owner.token + '/'):
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'application/vnd.apple.mpegurl' if self.path.endswith('.m3u8') else 'application/octet-stream')
                self.end_headers()

            def do_GET(self):
                owner._serve(self)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.base = 'http://127.0.0.1:%s/%s/' % (self.server.server_port, self.token)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        threading.Thread(target=self._worker, daemon=True).start()
        self.log('[HLS-PREBUFFER] started: cache=%sMiB, lookahead=%s, VOD/live' %
                 (self.cache_limit // 1048576, self.lookahead))
        return self.local_url(url, manifest=True)

    def local_url(self, url, manifest=False):
        if urlsplit(url).scheme not in ('http', 'https'):
            return url
        encoded = base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')
        path = urlsplit(url).path.lower()
        suffix = '.m3u8' if manifest or path.endswith(('.m3u8', '.m3u')) else '.ts'
        if not manifest:
            for extension in ('.ts', '.m4s', '.mp4', '.aac', '.vtt', '.key'):
                if path.endswith(extension):
                    suffix = extension
                    break
        return self.base + encoded + '/stream' + suffix

    def rewrite(self, text, upstream_url):
        segments = []
        result = []
        segment_pending = False
        byte_range = None
        next_offset = 0
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith('#EXTINF:'):
                segment_pending = True
            elif stripped.startswith('#EXT-X-BYTERANGE:'):
                value = stripped.split(':', 1)[1]
                length, _, offset = value.partition('@')
                start = int(offset) if offset else next_offset
                next_offset = start + int(length)
                byte_range = 'bytes=%s-%s' % (start, next_offset - 1)
            if stripped and not stripped.startswith('#'):
                target = urljoin(upstream_url, stripped)
                result.append(self.local_url(target))
                if segment_pending:
                    segments.append((target, byte_range))
                segment_pending = False
                byte_range = None
            else:
                result.append(re.sub(r'URI="([^"]+)"',
                    lambda match: 'URI="%s"' % self.local_url(urljoin(upstream_url, match.group(1))), line))
        if segments:
            with self.lock:
                # Retain only the latest snapshot for each audio/video playlist.
                self.playlists[upstream_url] = segments
                if len(self.playlists) > 16:
                    self.playlists.pop(next(iter(self.playlists)))
                self.positions = {key: (items, i)
                    for items in self.playlists.values() for i, key in enumerate(items)}
                active = set(self.positions)
                for key in list(self.cache):
                    if key not in active:
                        self.cache_bytes -= len(self.cache.pop(key))
            self._schedule(segments[:self.lookahead])
        return ('\n'.join(result) + '\n').encode('utf-8')

    def _schedule(self, urls):
        for url in urls:
            if self.stop.is_set():
                return
            with self.lock:
                if url in self.cache or url in self.scheduled:
                    continue
                self.scheduled.add(url)
            try:
                self.tasks.put_nowait(url)
            except queue.Full:
                with self.lock:
                    self.scheduled.discard(url)

    def _after_request(self, url):
        with self.lock:
            location = self.positions.get(url)
        if location:
            urls, index = location
            self._schedule(urls[index + 1:index + 1 + self.lookahead])

    def _worker(self):
        while not self.stop.is_set():
            try:
                url = self.tasks.get(timeout=.2)
            except queue.Empty:
                continue
            try:
                with self.lock:
                    room = self.cache_limit - self.cache_bytes
                    present = url in self.cache
                if present or room < 65536:
                    continue
                upstream, byte_range = url
                headers = dict(self.headers)
                if byte_range:
                    headers['Range'] = byte_range
                with requests.get(upstream, headers=headers, stream=True,
                                  timeout=(3, 5), verify=self.verify) as response:
                    response.raise_for_status()
                    if byte_range and response.status_code != 206:
                        continue
                    data = bytearray()
                    for chunk in response.iter_content(65536):
                        if self.stop.is_set() or len(data) + len(chunk) > min(self.object_limit, room):
                            data = None
                            break
                        data.extend(chunk)
                if data is not None and not self.stop.is_set():
                    with self.lock:
                        if not self.stop.is_set() and url not in self.cache and self.cache_bytes + len(data) <= self.cache_limit:
                            self.cache[url] = bytes(data)
                            self.cache_bytes += len(data)
                            self.downloads += 1
                            if self.downloads % 4 == 0:
                                self.log('[HLS-PREBUFFER] prefetched=%s cache=%.1fMiB hits=%s' %
                                         (self.downloads, self.cache_bytes / 1048576., self.hits))
            except Exception:
                self.failures += 1  # Playback still fetches normally on a cache miss.
            finally:
                with self.lock:
                    self.scheduled.discard(url)
                self.tasks.task_done()

    def _serve(self, handler):
        prefix = '/' + self.token + '/'
        if not handler.path.startswith(prefix) or self.stop.is_set():
            handler.send_error(404)
            return
        try:
            encoded = handler.path[len(prefix):].split('/', 1)[0]
            url = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)).decode()
            if urlsplit(url).scheme not in ('http', 'https'):
                handler.send_error(400)
                return
        except Exception:
            handler.send_error(400)
            return
        # Byte-range segments must retain upstream Range/Content-Range semantics.
        ranged = handler.headers.get('Range')
        cache_key = (url, None if ranged in (None, 'bytes=0-') else ranged)
        with self.lock:
            data = self.cache.pop(cache_key, None)
            if data is not None:
                self.cache_bytes -= len(data)
                self.hits += 1
        sent = False
        try:
            if data is not None:
                handler.send_response(206 if ranged else 200)
                if ranged == 'bytes=0-':
                    handler.send_header('Content-Range', 'bytes 0-%s/%s' % (len(data) - 1, len(data)))
                elif ranged:
                    match = re.fullmatch(r'bytes=(\d+)-(\d+)', ranged)
                    if match:
                        handler.send_header('Content-Range', 'bytes %s-%s/*' % match.groups())
                handler.send_header('Content-Length', str(len(data)))
                handler.end_headers()
                sent = True
                handler.wfile.write(data)
            else:
                headers = dict(self.headers)
                # Kodi/FFmpeg may probe manifests with Range. A rewritten
                # playlist must be complete, so fetch known manifests in full.
                if ranged and not handler.path.endswith('.m3u8'):
                    headers['Range'] = ranged
                with requests.get(url, headers=headers, stream=True,
                                  timeout=(3, 8), verify=self.verify) as response:
                    mime = response.headers.get('Content-Type', '')
                    is_manifest = ('mpegurl' in mime.lower() or
                                   urlsplit(response.url).path.lower().endswith(('.m3u', '.m3u8')))
                    chunks = response.iter_content(65536)
                    first = next(chunks, b'')
                    is_manifest = is_manifest or first.lstrip(b'\xef\xbb\xbf \t\r\n').startswith(b'#EXTM3U')
                    if is_manifest and response.status_code == 206:
                        # Extensionless child playlists can also arrive as a
                        # partial response. Re-fetch without Range before rewriting.
                        response.close()
                        full_headers = dict(self.headers)
                        with requests.get(url, headers=full_headers, stream=True,
                                          timeout=(3, 8), verify=self.verify) as full:
                            full.raise_for_status()
                            complete = bytearray()
                            for chunk in full.iter_content(65536):
                                if len(complete) + len(chunk) > MANIFEST_LIMIT:
                                    raise ValueError('manifest too large')
                                complete.extend(chunk)
                            body = self.rewrite(complete.decode('utf-8-sig'), full.url)
                        handler.send_response(200)
                        handler.send_header('Content-Type', 'application/vnd.apple.mpegurl')
                        handler.send_header('Content-Length', str(len(body)))
                        handler.end_headers()
                        sent = True
                        handler.wfile.write(body)
                    elif is_manifest and response.status_code == 200:
                        body = bytearray(first)
                        for chunk in chunks:
                            if len(body) + len(chunk) > MANIFEST_LIMIT:
                                raise ValueError('manifest too large')
                            body.extend(chunk)
                        body = self.rewrite(body.decode('utf-8-sig'), response.url)
                        handler.send_response(200)
                        handler.send_header('Content-Type', 'application/vnd.apple.mpegurl')
                        handler.send_header('Content-Length', str(len(body)))
                        handler.end_headers()
                        sent = True
                        handler.wfile.write(body)
                    else:
                        handler.send_response(response.status_code)
                        for key in ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges'):
                            if key in response.headers:
                                if key == 'Content-Length' and response.headers.get('Content-Encoding', 'identity') != 'identity':
                                    continue
                                handler.send_header(key, response.headers[key])
                        handler.end_headers()
                        sent = True
                        if first:
                            handler.wfile.write(first)
                        for chunk in chunks:
                            if self.stop.is_set():
                                break
                            handler.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            if not sent:
                handler.send_error(502)
        finally:
            self._after_request(cache_key)

    def status(self):
        with self.lock:
            return self.cache_bytes, self.cache_limit, self.hits

    def close(self):
        self.stop.set()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        with self.lock:
            self.cache.clear()
            self.cache_bytes = 0
            self.positions.clear()
            self.playlists.clear()
        self.log('[HLS-PREBUFFER] closed: downloaded=%s hits=%s failures=%s' %
                 (self.downloads, self.hits, self.failures))
