import os
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUTPUT_DIR = "tests/bills"
os.makedirs(OUTPUT_DIR, exist_ok=True)

FONTS_DIR = "C:/Windows/Fonts"
font_printed = ImageFont.truetype(os.path.join(FONTS_DIR, "consola.ttf"), 24)
font_printed_bold = ImageFont.truetype(os.path.join(FONTS_DIR, "consolab.ttf"), 28)
font_printed_sm = ImageFont.truetype(os.path.join(FONTS_DIR, "consola.ttf"), 18)

try:
    font_hw = ImageFont.truetype(os.path.join(FONTS_DIR, "segoepr.ttf"), 26)
    font_hw_lg = ImageFont.truetype(os.path.join(FONTS_DIR, "segoeprb.ttf"), 30)
except Exception:
    font_hw = font_printed
    font_hw_lg = font_printed_bold

try:
    font_kannada = ImageFont.truetype(os.path.join(FONTS_DIR, "Nirmala.ttc"), 26)
    font_kannada_bold = ImageFont.truetype(os.path.join(FONTS_DIR, "Nirmala.ttc"), 30)
except Exception:
    font_kannada = font_printed
    font_kannada_bold = font_printed_bold

def create_printed_bill():
    w, h = 800, 1000
    img = Image.new("RGB", (w, h), (248, 248, 245))
    draw = ImageDraw.Draw(img)

    # Header
    draw.text((220, 40), "SRI LAKSHMI WHOLESALE TRADERS", fill=(20, 20, 20), font=font_printed_bold)
    draw.text((260, 80), "APMC Yard, Yeshwanthpur, Bengaluru", fill=(60, 60, 60), font=font_printed_sm)
    draw.text((310, 110), "TAX INVOICE / CASH MEMO", fill=(30, 30, 30), font=font_printed)
    draw.line([(50, 150), (750, 150)], fill=(40, 40, 40), width=2)

    # Metadata
    draw.text((60, 165), "Inv No: SLT-2026/894", fill=(40, 40, 40), font=font_printed_sm)
    draw.text((520, 165), "Date: 09-10-2026", fill=(40, 40, 40), font=font_printed_sm)
    draw.text((60, 195), "Customer: Sri Ganesha Provision Store", fill=(40, 40, 40), font=font_printed_sm)
    draw.line([(50, 230), (750, 230)], fill=(40, 40, 40), width=2)

    # Table Header
    draw.text((60, 245), "ITEM DESCRIPTION", fill=(20, 20, 20), font=font_printed)
    draw.text((450, 245), "QTY", fill=(20, 20, 20), font=font_printed)
    draw.text((560, 245), "RATE", fill=(20, 20, 20), font=font_printed)
    draw.text((660, 245), "AMOUNT", fill=(20, 20, 20), font=font_printed)
    draw.line([(50, 280), (750, 280)], fill=(40, 40, 40), width=1)

    items = [
        ("Parle-G Biscuit 250g", "20 pkt", "24.00", "480.00"),
        ("Maggi 2-Min Noodles 70g", "2 dzn", "120.00", "240.00"),
        ("Aashirvaad Shudh Chakki Atta 10kg", "5 bag", "920.00", "4600.00"),
        ("Tata Salt Vacuum Evaporated 1kg", "10 pkt", "28.00", "280.00"),
        ("Amul Butter 500g", "5 pc", "270.00", "1350.00"),
        ("Fortune Sunlite Refined Oil 1L", "12 pouch", "140.00", "1680.00"),
    ]

    y = 300
    for desc, qty, rate, amt in items:
        draw.text((60, y), desc, fill=(30, 30, 30), font=font_printed)
        draw.text((450, y), qty, fill=(30, 30, 30), font=font_printed)
        draw.text((560, y), rate, fill=(30, 30, 30), font=font_printed)
        draw.text((660, y), amt, fill=(30, 30, 30), font=font_printed)
        y += 45

    draw.line([(50, y + 20), (750, y + 20)], fill=(40, 40, 40), width=2)
    draw.text((450, y + 35), "TOTAL AMOUNT:", fill=(20, 20, 20), font=font_printed_bold)
    draw.text((650, y + 35), "Rs 8630.00", fill=(20, 20, 20), font=font_printed_bold)
    draw.line([(50, y + 80), (750, y + 80)], fill=(40, 40, 40), width=1)

    draw.text((250, y + 110), "** THANK YOU VISIT AGAIN **", fill=(80, 80, 80), font=font_printed_sm)

    img.save(os.path.join(OUTPUT_DIR, "printed-01.jpg"), quality=92)
    print("Saved printed-01.jpg")
    return img

def create_handwritten_bill():
    w, h = 800, 1000
    img = Image.new("RGB", (w, h), (252, 250, 240)) # lined pad off-white
    draw = ImageDraw.Draw(img)

    # Draw faint ruled lines
    for line_y in range(120, h - 50, 40):
        draw.line([(40, line_y), (760, line_y)], fill=(215, 225, 235), width=1)
    # Red margin line
    draw.line([(100, 40), (100, h - 30)], fill=(240, 180, 180), width=2)

    # Pad header
    draw.text((260, 45), "KIRANA BILL ESTIMATE", fill=(10, 30, 120), font=font_hw_lg)
    draw.text((600, 65), "09/10", fill=(10, 30, 120), font=font_hw)

    hw_lines = [
        "20 pkt parle g 480",
        "2 dzn maggi 240",
        "5 bori aata 4600",
        "10 nos tata salt 280",
        "1 ctn amul milk 720",
    ]

    y = 125
    for line in hw_lines:
        # slight ink color variation
        ink = (15 + random.randint(-5, 5), 25 + random.randint(-5, 5), 110 + random.randint(-10, 10))
        draw.text((120, y), line, fill=ink, font=font_hw)
        y += 80

    draw.text((120, y + 40), "Total = 6320/-", fill=(15, 25, 110), font=font_hw_lg)

    img.save(os.path.join(OUTPUT_DIR, "handwritten-01.jpg"), quality=90)
    print("Saved handwritten-01.jpg")
    return img

def create_kannada_bill():
    w, h = 800, 1000
    img = Image.new("RGB", (w, h), (250, 248, 242))
    draw = ImageDraw.Draw(img)

    draw.text((240, 50), "ಶ್ರೀ ಮಂಜುನಾಥ ಪ್ರಾವಿಷನ್ ಸ್ಟೋರ್ಸ್", fill=(20, 20, 20), font=font_kannada_bold)
    draw.text((320, 95), "ಬಿಲ್ ರಸೀದಿ", fill=(40, 40, 40), font=font_kannada)
    draw.line([(50, 140), (750, 140)], fill=(40, 40, 40), width=2)

    kn_items = [
        "20 ಪ್ಯಾಕೆಟ್ ಪಾರ್ಲೆ-ಜಿ 480",
        "2 ಡಜನ್ ಮ್ಯಾಗಿ 240",
        "5 ಕೆಜಿ ಆಶೀರ್ವಾದ್ ಆಟಾ 4600",
        "10 ಪ್ಯಾಕೆಟ್ ಟಾಟಾ ಉಪ್ಪು 280",
        "5 ಬಾಕ್ಸ್ ಅಮೂಲ್ ಬೆಣ್ಣೆ 1350",
    ]

    y = 180
    for line in kn_items:
        draw.text((80, y), line, fill=(30, 30, 30), font=font_kannada)
        y += 65

    draw.line([(50, y + 20), (750, y + 20)], fill=(40, 40, 40), width=2)
    draw.text((80, y + 40), "ಒಟ್ಟು ಮೊತ್ತ: ರೂ 6950.00", fill=(20, 20, 20), font=font_kannada_bold)

    img.save(os.path.join(OUTPUT_DIR, "kannada-01.jpg"), quality=90)
    print("Saved kannada-01.jpg")

def create_angle_bill(base_img):
    # Rotate slightly and pad with desk background
    w, h = base_img.size
    desk = Image.new("RGB", (w + 200, h + 200), (160, 140, 120))
    rotated = base_img.rotate(14, expand=True, resample=Image.BICUBIC)
    rw, rh = rotated.size
    desk.paste(rotated, ((w + 200 - rw) // 2, (h + 200 - rh) // 2))
    desk = desk.resize((800, 1000), Image.LANCZOS)
    desk.save(os.path.join(OUTPUT_DIR, "angle-01.jpg"), quality=88)
    print("Saved angle-01.jpg")

def create_glare_bill(base_img):
    img = base_img.copy()
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    # Bright diagonal wash
    for r in range(200, 600, 10):
        alpha = int(140 * (1 - (r - 200) / 400))
        draw.ellipse([(600 - r, 100 - r // 2), (600 + r, 100 + r // 2)], fill=(255, 255, 255, alpha))
    overlay = overlay.filter(ImageFilter.GaussianBlur(30))
    img.paste(overlay, (0, 0), overlay)
    img.save(os.path.join(OUTPUT_DIR, "glare-01.jpg"), quality=90)
    print("Saved glare-01.jpg")

def create_crumpled_bill(base_img):
    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    # Fold crease lines with shadow and highlight
    creases = [
        ((0, 350), (800, 370)),
        ((0, 680), (800, 670)),
        ((380, 0), (410, 1000)),
    ]
    for start, end in creases:
        draw.line([start, end], fill=(160, 155, 145), width=3)
        draw.line([(start[0], start[1] + 2), (end[0], end[1] + 2)], fill=(255, 255, 255), width=2)
    img = img.filter(ImageFilter.SMOOTH)
    img.save(os.path.join(OUTPUT_DIR, "crumpled-01.jpg"), quality=88)
    print("Saved crumpled-01.jpg")

def create_not_a_bill():
    w, h = 800, 1000
    img = Image.new("RGB", (w, h), (85, 100, 115))
    draw = ImageDraw.Draw(img)
    # Draw desk table surface, coffee cup, notebook edge
    draw.rectangle([(0, 600), (800, 1000)], fill=(120, 85, 60)) # wooden desk
    # Coffee mug circle
    draw.ellipse([(300, 680), (480, 860)], fill=(230, 230, 235), outline=(180, 180, 180), width=4)
    draw.ellipse([(320, 700), (460, 840)], fill=(75, 45, 30)) # coffee
    # Laptop keyboard / monitor silhouette
    draw.rectangle([(150, 150), (650, 520)], fill=(30, 35, 40), outline=(70, 75, 80), width=6)
    draw.text((280, 300), "Workspace Monitor", fill=(100, 120, 140), font=font_printed)
    img.save(os.path.join(OUTPUT_DIR, "not-a-bill.jpg"), quality=90)
    print("Saved not-a-bill.jpg")

if __name__ == "__main__":
    p_img = create_printed_bill()
    hw_img = create_handwritten_bill()
    create_kannada_bill()
    create_angle_bill(p_img)
    create_glare_bill(p_img)
    create_crumpled_bill(p_img)
    create_not_a_bill()
    print("All bill corpus images generated successfully in tests/bills/")
