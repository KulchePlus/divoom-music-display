"""Per-frame payload budget, shared palette and explicit animation frame cap."""
from dataclasses import dataclass, asdict
import io
import json
import math
import struct
from PIL import Image
import now_playing as core
from debug_image import parse_size


COLOR_CHOICES = (8, 16, 32, 64, 128, 256)


@dataclass(frozen=True)
class Settings:
    budget_bytes: int = 24*1024
    colors: int = 256
    max_frames: int = 64

    @classmethod
    def parse(cls, kb, colors, frames):
        budget = parse_size(kb)
        try:
            colors, frames = int(colors), int(str(frames).strip())
        except (ValueError, TypeError):
            raise ValueError('Максимум кадров должен быть целым числом от 1 до 64.') from None
        if colors not in COLOR_CHOICES:
            raise ValueError('Выберите палитру от 8 до 256 цветов из списка.')
        if not 1 <= frames <= 64:
            raise ValueError('Максимум кадров: от 1 до 64.')
        return cls(budget, colors, frames)


def load_settings():
    try:
        data = json.loads((core.ROOT/'settings.json').read_text(encoding='utf-8'))
        settings = Settings(**data)
        if settings.colors not in COLOR_CHOICES:
            settings = Settings(settings.budget_bytes,
                                min(COLOR_CHOICES, key=lambda color:(abs(color-settings.colors), -color)),
                                settings.max_frames)
        return Settings.parse(settings.budget_bytes/1024, settings.colors, settings.max_frames)
    except (OSError, ValueError, TypeError):
        return Settings()


def save_settings(settings):
    path = core.ROOT/'settings.json'
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(asdict(settings), indent=2), encoding='utf-8')
    temporary.replace(path)


class SizeLimitError(ValueError):
    pass


def prepare(frames, speed, settings):
    if not frames or any(frame.size != (160, 128) for frame in frames):
        raise ValueError('Ожидаются кадры 160 × 128.')
    original_count = len(frames)
    limit = min(original_count, settings.max_frames)
    frames = frames[:limit]
    # A shared palette avoids independent per-frame quantization flicker.
    samples = sorted({round(i*(limit-1)/max(1, min(8, limit)-1)) for i in range(min(8, limit))})
    sheet = Image.new('RGB', (160, 128*len(samples)))
    for i, index in enumerate(samples):
        sheet.paste(frames[index].convert('RGB'), (0, i*128))
    palette = sheet.quantize(colors=settings.colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette_data = palette.getpalette()
    palette.putpalette(palette_data[:settings.colors*3]+palette_data[:3]*(256-settings.colors))
    quantized = [frame.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE).convert('RGB') for frame in frames]
    count = limit
    indices = list(range(count))
    selected = [quantized[i] for i in indices]
    adjusted_speed = speed if count>1 else 1000
    if count == 1:
        lossless = core.encode_lossless(selected[0])
        if len(lossless) <= settings.budget_bytes:
            return selected, adjusted_speed, lossless, metadata(settings, original_count, count, len(lossless), len(lossless), 'RGB+Zstd', None, adjusted_speed)
    best_size = None
    for quality in (100, 95, 85, 75, 65, 55, 45):
        jpegs = []
        for image in selected:
            out = io.BytesIO()
            image.save(out, 'JPEG', quality=quality, subsampling=0, optimize=True)
            jpegs.append(out.getvalue())
        # Include the standalone clip/frame overhead, matching the Debug units.
        maximum_frame = max(11+len(jpeg) for jpeg in jpegs)
        best_size = maximum_frame if best_size is None else min(best_size, maximum_frame)
        if maximum_frame > settings.budget_bytes:
            continue
        blob = bytes([0x23, count])+struct.pack('>H', adjusted_speed)+bytes([8, 10])
        blob += b''.join(b'\x01'+struct.pack('>I', len(jpeg))+jpeg for jpeg in jpegs)
        decoded = []
        for jpeg in jpegs:
            with Image.open(io.BytesIO(jpeg)) as image:
                decoded.append(image.convert('RGB'))
        assert maximum_frame <= settings.budget_bytes and count <= settings.max_frames
        return decoded, adjusted_speed, blob, metadata(settings, original_count, count, len(blob), maximum_frame, 'JPEG', quality, adjusted_speed)
    raise SizeLimitError(f'Не удалось сжать каждый кадр до {settings.budget_bytes/1024:g} КБ: требуется не менее {best_size/1024:.1f} КБ на кадр. Увеличьте лимит. На устройство ничего не отправлено.')


def metadata(settings, original, count, size, maximum_frame, codec, quality, speed):
    return {'bytes':size, 'max_frame_bytes':maximum_frame, 'budget_bytes':settings.budget_bytes,
            'budget_scope':'frame', 'colors':settings.colors,
            'frames':count, 'original_frames':original, 'codec':codec, 'quality':quality,
            'frame_ms':speed, 'reduced':count<original}
