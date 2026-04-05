import argparse
import asyncio
import json
from aiohttp import web
import os
import random

MUSIC_DIR = "/home/samisthefbi/Music"

MUSIC_EXTENSIONS = ('.flac', '.ogg', '.wav', '.aac', '.m4a', '.opus')
ICY_METAINT = 8192


async def get_metadata(filepath):
    try:
        proc = await asyncio.create_subprocess_exec(
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_entries', 'format_tags=title,artist',
            '-i', filepath,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        tags = json.loads(stdout).get('format', {}).get('tags', {})
        title = tags.get('title') or tags.get('TITLE')
        artist = tags.get('artist') or tags.get('ARTIST')
        if artist and title:
            return f'{artist} - {title}'
        return title or os.path.splitext(os.path.basename(filepath))[0]
    except Exception:
        return os.path.splitext(os.path.basename(filepath))[0]


class RadioStation:
    def __init__(self, music_dir):
        self.music_dir = music_dir
        self.client_queues = set()
        self.current_meta = ''

    def _get_files(self):
        files = [
            os.path.join(self.music_dir, f)
            for f in os.listdir(self.music_dir)
            if f.lower().endswith(MUSIC_EXTENSIONS)
        ]
        random.shuffle(files)
        return files

    async def _broadcast(self):
        while True:
            files = self._get_files()
            if not files:
                await asyncio.sleep(5)
                continue
            for filepath in files:
                self.current_meta = await get_metadata(filepath)
                print(f'[radio] Now playing: {self.current_meta}')
                proc = await asyncio.create_subprocess_exec(
                    'ffmpeg', '-re', '-i', filepath,
                    '-vn',
                    '-c:a', 'libmp3lame',
                    '-b:a', '128k',
                    '-compression_level', '0',
                    '-f', 'mp3', 'pipe:1',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                while True:
                    chunk = await proc.stdout.read(ICY_METAINT)
                    if not chunk:
                        break
                    dead = set()
                    for q in list(self.client_queues):
                        try:
                            q.put_nowait((chunk, self.current_meta))
                        except asyncio.QueueFull:
                            dead.add(q)
                    self.client_queues -= dead
                await proc.wait()
                if proc.returncode != 0:
                    stderr = await proc.stderr.read()
                    print(f'[radio] ffmpeg error (code {proc.returncode}): {stderr.decode()}')

    async def _broadcast_forever(self):
        while True:
            try:
                await self._broadcast()
            except Exception as e:
                print(f'[radio] Broadcast crashed: {e}, restarting in 3s...')
                await asyncio.sleep(3)

    async def start(self, app):
        asyncio.ensure_future(self._broadcast_forever())

    async def stream(self, request):
        icy = request.headers.get('Icy-MetaData') == '1'
        headers = {'Content-Type': 'audio/mpeg'}
        if icy:
            headers['icy-metaint'] = str(ICY_METAINT)
            headers['icy-name'] = 'Radio Station'

        response = web.StreamResponse(headers=headers)
        await response.prepare(request)

        q = asyncio.Queue(maxsize=16)
        self.client_queues.add(q)
        print(f'[radio] Listener joined ({len(self.client_queues)} total)')

        bytes_since_meta = 0
        last_meta = None

        try:
            while True:
                chunk, meta = await q.get()

                if not icy:
                    await response.write(chunk)
                    continue

                # slice chunk at ICY_METAINT boundaries, injecting metadata blocks
                offset = 0
                while offset < len(chunk):
                    space = ICY_METAINT - bytes_since_meta
                    segment = chunk[offset:offset + space]
                    await response.write(segment)
                    bytes_since_meta += len(segment)
                    offset += len(segment)

                    if bytes_since_meta >= ICY_METAINT:
                        # only send non-empty metadata block on song change
                        if meta != last_meta:
                            meta_bytes = f"StreamTitle='{meta}';".encode('utf-8', errors='replace')
                            last_meta = meta
                        else:
                            meta_bytes = b''
                        block_count = (len(meta_bytes) + 15) // 16
                        await response.write(
                            bytes([block_count]) + meta_bytes.ljust(block_count * 16, b'\x00')
                        )
                        bytes_since_meta = 0

        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            self.client_queues.discard(q)
            print(f'[radio] Listener left ({len(self.client_queues)} total)')
        return response

    async def radio_m3u(self, request):
        m3u = f'#EXTM3U\n#EXTINF:-1,Radio Station\nhttp://{request.host}/stream\n'
        return web.Response(text=m3u, content_type='audio/x-mpegurl')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Radio station')
    parser.add_argument('--port', type=int, default=6769)
    args = parser.parse_args()

    app = web.Application()
    radio = RadioStation(MUSIC_DIR)
    app.on_startup.append(radio.start)
    app.add_routes([web.get('/stream', radio.stream)])
    app.add_routes([web.get('/radio.m3u', radio.radio_m3u)])

    web.run_app(app, host='0.0.0.0', port=args.port)
