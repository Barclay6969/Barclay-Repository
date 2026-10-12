"""Bounded stream probes. No playback or Trakt API calls in worker threads."""
import queue
import re
import threading
import time
from urllib.parse import parse_qsl, urljoin

import requests


def fetch_sample(url, headers, limit=131072):
    started = time.monotonic()
    request_headers = dict(headers)
    request_headers['Range'] = 'bytes=0-{}'.format(limit - 1)
    with requests.get(url, headers=request_headers, stream=True,
                      timeout=(3, 3), allow_redirects=True) as response:
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '').lower()
        chunks = bytearray()
        for chunk in response.iter_content(16384):
            chunks.extend(chunk[:limit - len(chunks)])
            if len(chunks) >= limit or time.monotonic() - started >= 4:
                break
        if not chunks:
            raise ValueError('empty response')
        return bytes(chunks), content_type, response.url, time.monotonic() - started


def probe(stream):
    url, _, encoded_headers = stream.partition('|')
    headers = dict(parse_qsl(encoded_headers))
    headers.setdefault('User-Agent', 'Mozilla/5.0')
    sample, content_type, final_url, elapsed = fetch_sample(url, headers)
    height = None
    if sample.lstrip().startswith(b'#EXTM3U'):
        manifest = sample.decode('utf-8', errors='replace')
        variants = []
        lines = manifest.splitlines()
        for index, line in enumerate(lines):
            if line.startswith('#EXT-X-STREAM-INF:'):
                match = re.search(r'RESOLUTION=\d+x(\d+)', line)
                target = next((s.strip() for s in lines[index + 1:]
                               if s.strip() and not s.startswith('#')), None)
                if target:
                    variants.append((int(match.group(1)) if match else 0, target))
        if variants:
            height, target = max(variants)
            height = height or None
            sample, _, final_url, _ = fetch_sample(urljoin(final_url, target), headers)
            manifest = sample.decode('utf-8', errors='replace')
        segment = next((s.strip() for s in manifest.splitlines()
                        if s.strip() and not s.startswith('#')), None)
        if not segment:
            raise ValueError('no media segment')
        sample, content_type, _, elapsed = fetch_sample(urljoin(final_url, segment), headers)
        if 'text/html' in content_type or sample.lstrip().startswith((b'<html', b'<!DOCTYPE')):
            raise ValueError('HTML instead of segment')
        kind = 'HLS'
    elif b'ftyp' in sample[:64] or content_type.startswith('video/'):
        kind = 'MP4' if b'ftyp' in sample[:64] or 'mp4' in content_type else 'Video'
    else:
        raise ValueError('no recognizable video or HLS manifest')
    return {'stream': stream, 'format': kind, 'height': height,
            'speed': len(sample) / max(elapsed, 0.001), 'latency': elapsed}


def check_sources(videos, resolve, progress, deadline_seconds=20):
    """Return completed playable probes only; deadline never waits for resolvers."""
    jobs, completed = queue.Queue(), queue.Queue()
    stop = threading.Event()
    unique = list(dict.fromkeys(videos))
    for item in unique:
        jobs.put(item)

    def worker():
        while not stop.is_set():
            try:
                name, url = jobs.get_nowait()
            except queue.Empty:
                return
            result = None
            try:
                stream = resolve(name, url)
                if stream and not stop.is_set():
                    result = probe(stream)
                    result['hoster'] = name
                    result['source'] = url
            except Exception:
                pass
            completed.put(result)

    for _ in range(min(4, len(unique))):
        threading.Thread(target=worker, daemon=True).start()
    results = []
    checked = 0
    deadline = time.monotonic() + deadline_seconds
    try:
        while checked < len(unique) and time.monotonic() < deadline:
            if not progress(checked, len(unique), len(results)):
                return None
            try:
                result = completed.get(timeout=0.1)
            except queue.Empty:
                continue
            checked += 1
            if result:
                results.append(result)
    finally:
        stop.set()
    return sorted(results, key=lambda item: item['speed'], reverse=True)


def manual_choices(videos, results):
    """Keep all original hosters; unconfirmed does not imply definitively broken."""
    confirmed = {(item['hoster'], item['source']): item for item in results}
    choices = []
    for name, source in dict.fromkeys(videos):
        result = confirmed.get((name, source))
        if result:
            height = '{}p'.format(result['height']) if result['height'] else 'Auflösung unbekannt'
            label = '{} | erreichbar | {} | {} | ca. {:.1f} Mbit/s'.format(
                name, result['format'], height, result['speed'] * 8 / 1000000)
            choices.append({'hoster': name, 'label': label, 'url': result['stream'], 'resolved': True})
        else:
            choices.append({'hoster': name, 'label': name + ' | Prüfung nicht bestätigt',
                            'url': source, 'resolved': False})
    return choices
