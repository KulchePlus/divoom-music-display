"""Windows system media session -> Divoom MiniToo, USB audio + Bluetooth screen."""
import argparse
import base64
import hashlib
import io
import json
import logging
import math
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, '_MEIPASS', ROOT))
sys.path.insert(0, str(ROOT / '.deps'))
import zstandard
LOG = logging.getLogger('minitoo')
ICON_CACHE = {}


def app_icon(app_id):
    if not app_id:
        return None
    if app_id not in ICON_CACHE:
        cache = ROOT / 'assets' / 'app-icons'
        cache.mkdir(parents=True, exist_ok=True)
        path = cache / (hashlib.sha256(app_id.encode()).hexdigest()[:24]+'.png')
        if not path.exists():
            try:
                result = subprocess.run(
                    ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                     '-File', str(RESOURCE_ROOT/'Export-AppIcon.ps1'), '-AppId', app_id,
                     '-OutputPath', str(path)], capture_output=True, timeout=20,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode:
                    LOG.warning('Application icon unavailable for %s', app_id)
            except (OSError, subprocess.TimeoutExpired):
                LOG.warning('Application icon lookup failed for %s', app_id)
        ICON_CACHE[app_id] = path if path.exists() else None
    return ICON_CACHE[app_id]


def current_track():
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(RESOURCE_ROOT / 'Get-NowPlaying.ps1')],
        capture_output=True, encoding='utf-8-sig', errors='replace', timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    sessions = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    # Prefer the active Windows media session when several apps are playing.
    sessions.sort(key=lambda s: (s['Status'] == 'Playing', s.get('Current', False)), reverse=True)
    return sessions[0] if sessions else {'Title': 'Нет музыки', 'Artist': '', 'Status': 'Stopped', 'App': ''}


def wrap(text, font, width=146):
    lines, line = [], ''
    for word in text.split():
        candidate = (line + ' ' + word).strip()
        if font.getlength(candidate) <= width:
            line = candidate
            continue
        if line:
            lines.append(line.strip())
            line = ''
        for char in word:
            if line and font.getlength(line + char) > width:
                lines.append(line)
                line = ''
            line += char
    if line.strip():
        lines.append(line.strip())
    return lines or ['']


def render(track, page=0, draw_title=True, colon_visible=True, clock_text=None):
    cover = None
    if track.get('Cover'):
        try:
            cover = Image.open(io.BytesIO(base64.b64decode(track['Cover']))).convert('RGB')
        except Exception:
            LOG.warning('Could not decode album cover')
    if cover is None:
        icon_path = app_icon(track.get('App', ''))
        if icon_path:
            with Image.open(icon_path) as icon:
                rgba = icon.convert('RGBA')
                background = Image.new('RGBA', rgba.size, '#080c14')
                background.alpha_composite(rgba)
                cover = background.convert('RGB')
    accent = (255, 205, 75)
    if cover:
        colors = cover.resize((24, 24)).quantize(colors=8).convert('RGB')
        accent = max((color for _, color in colors.getcolors(576)), key=lambda c: max(c)-min(c)+max(c)*.3)
        peak = max(accent)
        accent = tuple(int(c*210/max(peak, 1)+35) for c in accent)
        image = ImageOps.fit(cover, (160, 128)).filter(ImageFilter.GaussianBlur(12))
        image = ImageEnhance.Color(image).enhance(1.45)
        image = ImageEnhance.Brightness(image).enhance(1.15)
    else:
        image = Image.new('RGB', (160, 128), '#1e293e')
    # Keep the cover's hues instead of blending almost entirely into navy.
    # Shade the title and clock more than the central ambient background.
    shade = Image.new('L', (1, 128))
    anchors = [(0, 145), (22, 100), (65, 95), (86, 150), (127, 175)]
    for (y0, a0), (y1, a1) in zip(anchors, anchors[1:]):
        for y in range(y0, y1+1):
            shade.putpixel((0, y), round(a0+(a1-a0)*(y-y0)/(y1-y0)))
    image = Image.composite(Image.new('RGB', image.size, '#030305'), image,
                            shade.resize(image.size))
    draw = ImageDraw.Draw(image)
    regular = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 12)
    bold = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 15)
    small = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 9)
    clock_font = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 18)
    active = track['Status'] == 'Playing'
    draw.rounded_rectangle((7, 5, 10, 13), radius=1, fill=accent)
    draw.text((15, 2), 'NOW PLAYING' if active else 'PAUSED', font=small, fill='#d4dce9')
    clock = clock_text or datetime.now(ZoneInfo('Europe/Moscow')).strftime('%H:%M')
    x = 153-clock_font.getlength(clock)
    hours, minutes = clock.split(':')
    draw.text((x, -3), hours, font=clock_font, fill='#ffffff')
    if colon_visible:
        draw.text((x+clock_font.getlength(hours), -3), ':', font=clock_font, fill='#ffffff')
    draw.text((x+clock_font.getlength(hours+':'), -3), minutes, font=clock_font, fill='#ffffff')
    draw.rounded_rectangle((6, 21, 63, 78), radius=7, fill='#05080e')
    if cover:
        thumb = ImageOps.fit(cover, (54, 54), method=Image.Resampling.LANCZOS)
        mask = Image.new('L', (54, 54))
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 53, 53), radius=5, fill=255)
        image.paste(thumb, (8, 23), mask)
    else:
        draw.ellipse((12, 27, 57, 72), fill='#182232', outline='#41516b')
        draw.ellipse((24, 39, 45, 60), fill=accent)
        draw.ellipse((32, 47, 37, 52), fill='#101722')
    artist = wrap(track['Artist'] or 'Музыка', regular, 84)
    artist_pages = max(1, (len(artist)+2)//3)
    for i, line in enumerate(artist[(page % artist_pages)*3: (page % artist_pages)*3+3]):
        draw.text((70, 22+i*14), line, font=regular, fill='#d0d9e8')
    # Decorative player mark; these bars do not imply live audio analysis.
    for i, height in enumerate([5, 11, 8, 15, 10, 6, 12]):
        h = height if active else 3
        draw.rounded_rectangle((72+i*5, 77-h, 74+i*5, 77), radius=1, fill=accent)
    if active:
        draw.polygon([(141, 65), (141, 76), (150, 70)], fill=accent)
    else:
        draw.rectangle((140, 65, 142, 76), fill=accent)
        draw.rectangle((146, 65, 148, 76), fill=accent)
    # A full-width edge fades only downwards through half the remaining height.
    separator_mask = Image.new('L', (160, 128))
    separator_y = 84
    fade_height = (image.height-separator_y-1)//2
    for offset in range(fade_height+1):
        opacity = round(110*(1-offset/fade_height)**2)
        separator_mask.paste(opacity, (0, separator_y+offset, image.width, separator_y+offset+1))
    image = Image.composite(Image.new('RGB', image.size, accent), image, separator_mask)
    draw = ImageDraw.Draw(image)
    if draw_title:
        title = wrap(track['Title'] or 'Без названия', bold)
        title_pages = max(1, (len(title)+1)//2)
        for i, line in enumerate(title[(page % title_pages)*2: (page % title_pages)*2+2]):
            draw.text((7, 87+i*18), line, font=bold, fill='#ffffff')
    return image


def animation(track):
    """Each frame is the next complete two-line page, without motion."""
    font = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 15)
    lines = wrap(track['Title'] or 'Без названия', font)
    clock = datetime.now(ZoneInfo('Europe/Moscow')).strftime('%H:%M')
    base = render(track, draw_title=False, colon_visible=True, clock_text=clock)
    frames = []
    for start in range(0, min(len(lines), 128), 2):
        image = base.copy()
        draw = ImageDraw.Draw(image)
        for row, line in enumerate(lines[start:start+2]):
            draw.text((7, 87+row*18), line, font=font, fill='#ffffff')
        frames.append(image)
    return frames, 3000


def encode_jpeg_animation(frames, speed_ms):
    if not 1 <= len(frames) <= 64:
        raise ValueError('JPEG animation must have 1 to 64 frames')
    for quality in (95, 93, 90, 87, 84):
        blob = bytes([0x23, len(frames)]) + struct.pack('>H', speed_ms) + bytes([8, 10])
        for image in frames:
            out = io.BytesIO()
            image.save(out, 'JPEG', quality=quality, subsampling=0, optimize=True)
            jpeg = out.getvalue()
            blob += b'\x01' + struct.pack('>I', len(jpeg)) + jpeg
        if len(blob) <= 980000:
            if quality != 95:
                LOG.info('Animation JPEG quality=%s to stay within upload budget', quality)
            return blob
    raise ValueError('Animation exceeds the conservative upload budget')


def packet(opcode, data=b''):
    body = struct.pack('<H', len(data)+3) + bytes([opcode]) + data
    return b'\x01' + body + struct.pack('<H', sum(body) & 0xffff) + b'\x02'


def encode_lossless(image):
    return encode_animation([image], 1000)


def encode_animation(frames, speed_ms):
    if not 1 <= len(frames) <= 255 or not 40 <= speed_ms <= 65535:
        raise ValueError('Invalid animation frame count or timing')
    if any(image.size != (160, 128) for image in frames):
        raise ValueError('MiniToo requires 160x128 frames')
    raw = b''.join(image.convert('RGB').tobytes() for image in frames)
    compressed = zstandard.ZstdCompressor(level=19).compress(raw)
    if len(compressed) > 65535:
        raise ValueError('Compressed RGB image exceeds protocol limit')
    return bytes([0x25, len(frames)]) + struct.pack('>H', speed_ms) + bytes([8, 10, 0, 0]) + struct.pack('>H', len(compressed)) + compressed


class Display:
    def __init__(self, mac):
        self.sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        self.buf = bytearray()
        try:
            self.sock.settimeout(6)
            self.sock.connect((mac, 1))
        except BaseException:
            self.sock.close()
            raise

    def close(self):
        self.sock.close()

    def receive(self, timeout):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            while len(self.buf) >= 4:
                if self.buf[0] != 1:
                    del self.buf[0]
                    continue
                size = int.from_bytes(self.buf[1:3], 'little') + 4
                if size < 7 or size > 65539:
                    del self.buf[0]
                    continue
                if len(self.buf) < size:
                    break
                frame = bytes(self.buf[:size])
                del self.buf[:size]
                if frame[-1] == 2 and (sum(frame[1:-3]) & 65535) == int.from_bytes(frame[-3:-1], 'little'):
                    yield frame
            self.sock.settimeout(max(.001, deadline-time.monotonic()))
            try:
                data = self.sock.recv(4096)
            except socket.timeout:
                return
            if not data:
                raise ConnectionError('MiniToo disconnected')
            self.buf.extend(data)

    def send_image(self, image, pace_s=0, batch_size=65536):
        blob = encode_lossless(image)
        return self.send_blob(blob, pace_s, batch_size)

    def send_blob(self, blob, pace_s=0, batch_size=65536):
        total = struct.pack('<I', len(blob))
        chunks = [packet(0x8b, b'\x01'+total+struct.pack('<H', i//256)+blob[i:i+256]) for i in range(0, len(blob), 256)]
        list(self.receive(.05))
        started = time.monotonic()
        self.sock.sendall(packet(0x8b, b'\x00'+total))
        ready = False
        for frame in self.receive(3):
            if frame[3:8] == b'\x04\x8b\x55\x00\x01':
                ready = True
                break
        if not ready:
            raise TimeoutError('MiniToo did not acknowledge the screen upload')
        self.sock.settimeout(6)
        sending = time.monotonic()
        if pace_s:
            for chunk in chunks:
                self.sock.sendall(chunk)
                time.sleep(pace_s)
        else:
            # Retain 256-byte protocol chunks, but batch their framed bytes.
            wire = b''.join(chunks)
            for offset in range(0, len(wire), batch_size):
                self.sock.sendall(wire[offset:offset+batch_size])
        queued = time.monotonic()
        completed = False
        for frame in self.receive(4):
            LOG.debug('Reply: %s', frame.hex())
            if frame[3:-3] == b'\x04\xbd\x55\x13\x01\x05\x00':
                completed = True
                break
        elapsed = time.monotonic()-started
        LOG.info('Screen upload %s: %s bytes, %s chunks, playback ACK=%s, queue=%.3fs, total=%.3fs, pace=%.3fs', 'JPEG animation' if blob[0] == 0x23 else 'RGB+Zstd (lossless)', len(blob), len(chunks), completed, queued-sending, elapsed, pace_s)
        if not completed:
            raise TimeoutError('MiniToo did not acknowledge playback after upload')
        return elapsed


def main():
    import ctypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel.CreateMutexW(None, False, 'Local\\DivoomMiniTooNowPlaying')
    if ctypes.get_last_error() == 183:
        print('MiniToo Now Playing is already running.')
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mac', help='Bluetooth address of your paired MiniToo')
    parser.add_argument('--once', action='store_true', help='Send one update and exit')
    parser.add_argument('--preview', action='store_true', help='Save preview only')
    parser.add_argument('--animation', dest='animation', action='store_true', default=True, help='On-device JPEG scrolling (default)')
    parser.add_argument('--static', dest='animation', action='store_false', help='Use static lossless pages instead of animation')
    args = parser.parse_args()
    if not args.preview and not args.mac:
        parser.error('--mac is required for device uploads; use the desktop app for device selection')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', handlers=[logging.StreamHandler(), logging.FileHandler(ROOT/'now-playing.log', encoding='utf-8')])
    display, previous = None, None
    try:
        while True:
            try:
                track = current_track()
                key = (track['App'], track['Title'], track['Artist'], track['Status'],
                       track.get('Cover'), datetime.now(ZoneInfo('Europe/Moscow')).strftime('%H:%M'))
                page = int(time.monotonic()//5)
                if not args.animation:
                    title_font = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 15)
                    artist_font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 12)
                    key += (page % max(1, math.ceil(len(wrap(track['Title'], title_font))/2)),
                            page % max(1, math.ceil(len(wrap(track['Artist'], artist_font, 84))/3)))
                if args.preview:
                    image = render(track)
                    image.save(ROOT/'preview.png')
                    print(json.dumps(track, ensure_ascii=False))
                    return
                if display is None:
                    display = Display(args.mac)
                    LOG.info('Connected to %s', args.mac)
                if key != previous:
                    if args.animation:
                        frames, speed = animation(track)
                    else:
                        frames, speed = [render(track, page)], 1000
                    blob = (encode_jpeg_animation(frames, speed) if len(frames)>1
                            else encode_lossless(frames[0]))
                    display.send_blob(blob)
                    frames[0].save(ROOT/'preview.png')
                    LOG.info('Device animation: %s frames, %s ms/frame, %s bytes', len(frames), speed, len(blob))
                    LOG.info('%s — %s (%s)', track['Artist'], track['Title'], track['Status'])
                    previous = key
                if args.once:
                    return
                time.sleep(2)
            except Exception:
                LOG.exception('Update failed')
                if display:
                    display.close()
                display, previous = None, None
                if args.once or args.preview:
                    raise
                time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        if display:
            display.close()


if __name__ == '__main__':
    main()
