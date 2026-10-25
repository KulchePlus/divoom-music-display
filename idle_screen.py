"""Three-frame standby scene with live clock and date for the 160x128 display."""
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter

MONTHS = ('ЯНВАРЯ', 'ФЕВРАЛЯ', 'МАРТА', 'АПРЕЛЯ', 'МАЯ', 'ИЮНЯ',
          'ИЮЛЯ', 'АВГУСТА', 'СЕНТЯБРЯ', 'ОКТЯБРЯ', 'НОЯБРЯ', 'ДЕКАБРЯ')


@lru_cache(maxsize=1)
def background(path):
    with Image.open(path) as image:
        return image.convert('RGB').resize((160, 128), Image.Resampling.NEAREST)


def frames(resource_root, now):
    base = background(str(resource_root/'resources'/'idle-night.png'))
    clock_font = ImageFont.truetype('C:/Windows/Fonts/consolab.ttf', 32)
    date_font = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 10)
    small_font = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 9)
    result = []
    for index, intensity in enumerate((0, 30, 12)):
        image = base.copy().convert('RGBA')
        light = Image.new('RGBA', image.size)
        glow = ImageDraw.Draw(light)
        glow.ellipse((129, 87, 149, 109), fill=(255, 164, 74, intensity))
        image = Image.alpha_composite(image, light.filter(ImageFilter.GaussianBlur(2)))
        draw = ImageDraw.Draw(image)
        for number, (x, y) in enumerate(((16, 5), (34, 4), (70, 3), (94, 11), (150, 5))):
            brightness = (number+index) % 3
            color = ((99, 80, 145), (157, 119, 184), (239, 173, 169))[brightness]
            draw.point((x, y), fill=color)
            if brightness == 2:
                draw.point((x+1, y), fill=color)
        draw.text((80, 23), now.strftime('%H:%M'), font=clock_font, fill='#fff2d9', anchor='mt')
        draw.text((80, 53), f'{now.day} {MONTHS[now.month-1]}', font=date_font,
                  fill='#d5a6cc', anchor='mt')
        draw.text((80, 115), 'ЖДУ МУЗЫКУ', font=small_font, fill='#f3ae8c', anchor='mt')
        result.append(image.convert('RGB'))
    return result, 900
