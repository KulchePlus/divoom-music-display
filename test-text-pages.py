"""Page order, strict prefix cap and constant page duration."""
from PIL import Image, ImageFont
import now_playing as core
import transmission as tx

track = {'App':'','Title':'Очень длинное название песни с большим количеством текста: первая часть, вторая часть, третья часть и четвёртая часть',
         'Artist':'Исполнитель','Status':'Playing'}
frames, speed = core.animation(track)
font = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf',15)
assert len(frames) == (len(core.wrap(track['Title'],font))+1)//2
assert speed == 3000 and len(frames) >= 3
for page, frame in enumerate(frames):
    # The independent static page renderer already defines two-line boundaries.
    assert frame.crop((0,86,160,128)).tobytes() == core.render(track,page).crop((0,86,160,128)).tobytes()
assert len({frame.crop((0,0,160,85)).tobytes() for frame in frames}) == 1
distinct = [Image.new('RGB',(160,128),color) for color in ('red','green','blue','yellow')]
for maximum in (1,2):
    selected, delay, blob, meta = tx.prepare(distinct,3000,tx.Settings(24576,256,maximum))
    assert len(selected) == maximum
    assert selected[0].getpixel((0,0))[0] > 200
    if maximum == 2:
        red, green, blue = selected[1].getpixel((0,0))
        assert green > 90 and red < 20 and blue < 20, 'Second page was replaced by a later frame'
        assert delay == 3000
print('Whole two-line pages, fixed header, first-N truncation and 3-second pages: OK')
