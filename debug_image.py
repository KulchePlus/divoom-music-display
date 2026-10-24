"""Exactly sized, valid single-frame JPEG loads for manual MiniToo tests."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import io
import math
import struct
from PIL import Image, ImageDraw, ImageFont
import now_playing as core


def parse_size(value):
    try:
        size = Decimal(str(value).strip().replace(',', '.'))
    except InvalidOperation:
        raise ValueError('Введите число от 1 до 1024 КБ.') from None
    if not size.is_finite() or not Decimal(1) <= size <= Decimal(1024):
        raise ValueError('Допустимый размер: от 1 до 1024 КБ.')
    return int((size*1024).to_integral_value(rounding=ROUND_HALF_UP))


def pad_jpeg(jpeg, target):
    """APP15 metadata grows the file without corrupting or trailing junk bytes."""
    if not jpeg.startswith(b'\xff\xd8') or len(jpeg) > target:
        raise ValueError('Не удалось подготовить JPEG заданного размера.')
    remaining = target-len(jpeg)
    segments = bytearray()
    while remaining >= 4:
        payload = min(65533, remaining-4)
        segments += b'\xff\xef'+struct.pack('>H', payload+2)+bytes(payload)
        remaining -= payload+4
    # JPEG permits FF fill bytes before the next marker.
    return jpeg[:2]+bytes(segments)+b'\xff'*remaining+jpeg[2:]


def generate(value):
    target = parse_size(value)
    # 6-byte clip header + 1-byte frame format + 4-byte JPEG length.
    jpeg_target = target-11
    image = Image.new('RGB', (160, 128), '#111824')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 24)
    small = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 12)
    draw.rounded_rectangle((8, 8, 151, 119), radius=12, outline='#ffd34e', width=2)
    draw.text((17, 16), 'DEBUG', font=small, fill='#ffd34e')
    label = f'{target/1024:g} KB'
    while font.getlength(label) > 130 and font.size > 12:
        font = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', font.size-1)
    draw.text((80-font.getlength(label)/2, 48), label, font=font, fill='white')
    draw.text((23, 89), '160 x 128 / JPEG', font=small, fill='#aebbd0')
    jpeg = None
    for quality in (95, 85, 70, 50, 30):
        out = io.BytesIO()
        image.save(out, 'JPEG', quality=quality, subsampling=0, optimize=True)
        if len(out.getvalue()) <= jpeg_target:
            jpeg = out.getvalue()
            break
    if jpeg is None:
        # Very small tests use a simpler image, not a malformed JPEG.
        image = Image.new('RGB', (160, 128), '#111824')
        draw = ImageDraw.Draw(image)
        tiny = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 11)
        draw.text((8, 52), label, font=tiny, fill='white')
        out = io.BytesIO()
        image.save(out, 'JPEG', quality=60, subsampling=0, optimize=True)
        jpeg = out.getvalue()
    jpeg = pad_jpeg(jpeg, jpeg_target)
    blob = bytes([0x23, 1, 0x03, 0xe8, 8, 10, 1])+struct.pack('>I', len(jpeg))+jpeg
    assert len(blob) == target
    with Image.open(io.BytesIO(jpeg)) as decoded:
        preview = decoded.convert('RGB')
    chunks = math.ceil(len(blob)/256)
    wire_bytes = len(core.packet(0x8b, b'\x00'+struct.pack('<I', len(blob))))
    wire_bytes += sum(len(core.packet(0x8b, b'\x01'+struct.pack('<I', len(blob))+struct.pack('<H', i//256)+blob[i:i+256]))
                      for i in range(0, len(blob), 256))
    return preview, blob, {'payload_bytes':len(blob), 'jpeg_bytes':len(jpeg),
                           'wire_bytes':wire_bytes, 'chunks':chunks, 'frames':1}
