# main.py

from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

MONTHS_RU = [
    "", "января", "февраля", "марта", "апреля", "мая",
    "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"
]

def get_russian_date_string():
    now = datetime.now()
    day = now.day
    month = MONTHS_RU[now.month]
    year = now.year
    time = now.strftime("%H:%M")
    return f"{day} {month} {year} г. | {time}"

def paste_checkmark(image, position, scale=2.5):
    check_img = Image.open("./otrisovka/check.png").convert("RGBA")
    new_size = (int(check_img.width * scale), int(check_img.height * scale))
    check_img = check_img.resize(new_size, Image.Resampling.LANCZOS)
    adjusted_position = (
        position[0] - new_size[0] // 2,
        position[1] - new_size[1] // 2
    )
    image.paste(check_img, adjusted_position, check_img)

def format_amount(amount_str):
    try:
        cleaned = ''.join(c for c in amount_str if c.isdigit() or c in [',', '.'])
        amount = float(cleaned.replace(",", "."))
        return f"- {amount:,.2f} ₽".replace(",", "X").replace(".", ",").replace("X", " ")
    except:
        return "- 0,00 ₽"

def draw_spaced_text(draw, position, text, font, fill, spacing):
    x, y = position
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        w = font.getlength(char)
        x += w + spacing

def generate_image_with_amounts(amounts):
    image = Image.open('./otrisovka/image.png').convert("RGBA")
    draw = ImageDraw.Draw(image)

    font_date = ImageFont.truetype("./otrisovka/SF-Pro-Display-Light.otf", size=34)
    font_amount = ImageFont.truetype("./otrisovka/SF-Pro-Display-Medium.otf", size=44)

    date_time = get_russian_date_string()

    date_coords = [(810, 560), (810, 810), (810, 1060)]
    amount_coords = [(935, 635), (935, 885), (935, 1135)]
    checkmark_coords = [(1230, 655), (1230, 910), (1230, 1160)]

    for i in range(3):
        spacing_date = 2.5
        text_width = sum(font_date.getlength(c) for c in date_time) + spacing_date * (len(date_time) - 1)
        x_right = checkmark_coords[i][0]
        y = date_coords[i][1]
        x_aligned = x_right - text_width - 5

        draw_spaced_text(draw, (x_aligned, y), date_time, font_date, (118, 130, 156), spacing=2.5)

        formatted_amount = format_amount(amounts[i])
        spacing_amount = 3
        amount_width = sum(font_amount.getlength(c) for c in formatted_amount) + spacing_amount * (len(formatted_amount) - 1)
        OFFSET = 40
        x_right_amount = checkmark_coords[i][0] - OFFSET
        y_amount = amount_coords[i][1]
        x_amount_aligned = x_right_amount - amount_width
        draw_spaced_text(draw, (x_amount_aligned, y_amount), formatted_amount, font_amount, (56, 193, 114), spacing=3)

        paste_checkmark(image, checkmark_coords[i], scale=2.5)

    image.save("./otrisovka/output.png")
