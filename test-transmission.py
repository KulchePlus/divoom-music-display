"""Payload budget, frame cap, decoded preview and configuration validation."""
import io
import random
from PIL import Image
import now_playing as core
import transmission as tx

track = {'App':'','Title':'Длинное название для проверки ограничений передачи с прокруткой текста и кириллицей',
         'Artist':'Исполнитель','Status':'Playing'}
frames, speed = core.animation(track)
for colors in (128, 256):
    for maximum in (1, 4, 16, 64):
        settings = tx.Settings(20480, colors, maximum)
        output, timing, blob, metadata = tx.prepare(frames, speed, settings)
        assert metadata['max_frame_bytes'] <= settings.budget_bytes
        assert metadata['budget_scope'] == 'frame'
        assert len(output) == blob[1] == metadata['frames'] <= maximum
        assert len(output) == min(len(frames), maximum)
        assert metadata['colors'] == colors
        if blob[0] == 0x23:
            pos = 6
            for image in output:
                size = int.from_bytes(blob[pos+1:pos+5], 'big')
                assert size+11 <= settings.budget_bytes
                with Image.open(io.BytesIO(blob[pos+5:pos+5+size])) as decoded:
                    assert decoded.convert('RGB').tobytes() == image.tobytes()
                pos += size+5
            assert pos == len(blob)
        else:
            assert len(output[0].getcolors(256)) <= colors
        print(colors, maximum, len(blob), len(output), metadata['codec'])
noise = Image.frombytes('RGB', (160,128), random.Random(1).randbytes(160*128*3))
try:
    tx.prepare([noise], 1000, tx.Settings(1024, 256, 1))
except tx.SizeLimitError:
    pass
else:
    raise AssertionError('An impossible budget was silently exceeded')
for values in (('0',256,'4'), ('20',7,'4'), ('20',128,'0'), ('20',128,'65'), ('20',128,'1.5')):
    try:
        tx.Settings.parse(*values)
    except ValueError:
        continue
    raise AssertionError(values)
assert tx.Settings.parse('20,5',128,'8').budget_bytes == 20992
for colors in tx.COLOR_CHOICES:
    settings = tx.Settings.parse('24', colors, '1')
    output, timing, blob, metadata = tx.prepare([frames[0]], speed, settings)
    assert metadata['max_frame_bytes'] <= 24576
    if metadata['codec'] == 'RGB+Zstd':
        assert len(output[0].getcolors(256)) <= colors
assert tx.Settings().budget_bytes == 24576
print('Per-frame budget, preserved frame count, all palettes, preview and validation: OK')
