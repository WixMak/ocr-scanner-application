"""Generate a bilingual blank form and handwriting-style filled copies for trying the app.

Run from backend/:  uv run python -m scripts.make_sample_forms
Writes to data/samples/: blank_form.png, filled_01.jpg + filled_01.json, ...
The filled copies are rotated, scaled and noisy so alignment is exercised like a real scan.
"""

import json
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings
from app.imaging.page import NORMALISED_PAGE_WIDTH

PAGE_HEIGHT = 2339
INK = (20, 20, 20)
HANDWRITING_INK = (25, 45, 140)
PRINTED_FONT_SIZE = 34
TITLE_FONT_SIZE = 48
HANDWRITING_FONT_SIZE = 44
RANDOM_SEED = 7

PRINTED_FONT_NAMES = ("STHeiti Medium.ttc", "Hiragino Sans GB.ttc", "Songti.ttc")
HANDWRITING_FONT_NAMES = ("Hanzipen.ttc", "Hannotate.ttc", "Kaiti.ttc", "STHeiti Light.ttc")
FONT_SEARCH_DIRS = (
    Path("/System/Library/Fonts"),
    Path("/System/Library/Fonts/Supplemental"),
    Path("/Library/Fonts"),
    Path.home() / "Library/Fonts",
    Path("/System/Library/AssetsV2"),
)

UNDERLINE_FIELDS = (
    ("姓名 Full Name:", "full_name", 260),
    ("出生日期 Date of Birth:", "date_of_birth", 400),
    ("电话 Phone:", "phone", 520),
    ("地址 Address:", "address", 640),
)
TABLE_FIELDS = (
    ("雇主 Employer", "employer"),
    ("月薪 Monthly Salary", "monthly_salary"),
    ("供款金额 Contribution", "contribution"),
)
TABLE_TOP = 820
TABLE_ROW_HEIGHT = 110
TABLE_LEFT = 120
TABLE_SPLIT = 620
TABLE_RIGHT = 1530
SIGNED_DATE_LABEL = ("签署日期 Signed Date:", "signed_date", 1260)
LABEL_LEFT = 120
UNDERLINE_RIGHT = 1530

FILLED_SAMPLES = (
    {
        "full_name": "陈大文 Chan Tai Man",
        "date_of_birth": "1985-03-12",
        "phone": "9123 4567",
        "address": "香港九龙弥敦道88号",
        "employer": "东方贸易有限公司",
        "monthly_salary": "28500",
        "contribution": "1425",
        "signed_date": "2026-11-20",
    },
    {
        "full_name": "李小红 Lee Siu Hung",
        "date_of_birth": "1992-07-08",
        "phone": "6688 1234",
        "address": "上海市浦东新区世纪大道100号",
        "employer": "Harbour Logistics Ltd",
        "monthly_salary": "41000",
        "contribution": "1500",
        "signed_date": "2026-10-02",
    },
    {
        "full_name": "王建国 Wong Kin Kwok",
        "date_of_birth": "1978-12-30",
        "phone": "5432 9876",
        "address": "广州市天河区体育西路1号",
        "employer": "新城建筑工程",
        "monthly_salary": "19800",
        "contribution": "990",
        "signed_date": "",
    },
)


def find_font(names: tuple[str, ...]) -> Path:
    for name in names:
        for directory in FONT_SEARCH_DIRS:
            matches = list(directory.rglob(name)) if directory.exists() else []
            if matches:
                return matches[0]
    raise SystemExit(f"None of these fonts are installed: {', '.join(names)}")


def draw_blank_form(printed_font_path: Path) -> Image.Image:
    page = Image.new("RGB", (NORMALISED_PAGE_WIDTH, PAGE_HEIGHT), "white")
    draw = ImageDraw.Draw(page)
    label_font = ImageFont.truetype(str(printed_font_path), PRINTED_FONT_SIZE)
    title_font = ImageFont.truetype(str(printed_font_path), TITLE_FONT_SIZE)
    draw.text(
        (LABEL_LEFT, 110), "强积金成员登记表 MPF Member Enrolment Form", font=title_font, fill=INK
    )

    for label, _key, top in UNDERLINE_FIELDS:
        draw.text((LABEL_LEFT, top), label, font=label_font, fill=INK)
        label_right = int(draw.textlength(label, font=label_font)) + LABEL_LEFT + 16
        draw.line((label_right, top + 46, UNDERLINE_RIGHT, top + 46), fill=INK, width=3)

    for row, (label, _key) in enumerate(TABLE_FIELDS):
        row_top = TABLE_TOP + row * TABLE_ROW_HEIGHT
        draw.rectangle(
            (TABLE_LEFT, row_top, TABLE_SPLIT, row_top + TABLE_ROW_HEIGHT), outline=INK, width=3
        )
        draw.rectangle(
            (TABLE_SPLIT, row_top, TABLE_RIGHT, row_top + TABLE_ROW_HEIGHT), outline=INK, width=3
        )
        draw.text((TABLE_LEFT + 20, row_top + 34), label, font=label_font, fill=INK)

    signed_label, _signed_key, signed_top = SIGNED_DATE_LABEL
    draw.text((LABEL_LEFT, signed_top), signed_label, font=label_font, fill=INK)
    return page


def field_anchor(
    key: str, draw: ImageDraw.ImageDraw, label_font: ImageFont.FreeTypeFont
) -> tuple[int, int]:
    for label, field_key, top in (*UNDERLINE_FIELDS, SIGNED_DATE_LABEL):
        if field_key == key:
            return int(draw.textlength(label, font=label_font)) + LABEL_LEFT + 40, top - 8
    for row, (_label, field_key) in enumerate(TABLE_FIELDS):
        if field_key == key:
            return TABLE_SPLIT + 30, TABLE_TOP + row * TABLE_ROW_HEIGHT + 26
    raise KeyError(key)


def fill_form(
    blank: Image.Image, values: dict[str, str], fonts: tuple[Path, Path], rng: random.Random
) -> Image.Image:
    printed_font_path, handwriting_font_path = fonts
    page = blank.copy()
    draw = ImageDraw.Draw(page)
    label_font = ImageFont.truetype(str(printed_font_path), PRINTED_FONT_SIZE)
    for key, value in values.items():
        if not value:
            continue
        size = HANDWRITING_FONT_SIZE + rng.randint(-4, 4)
        handwriting_font = ImageFont.truetype(str(handwriting_font_path), size)
        anchor_x, anchor_y = field_anchor(key, draw, label_font)
        draw.text(
            (anchor_x + rng.randint(0, 30), anchor_y + rng.randint(-4, 4)),
            value,
            font=handwriting_font,
            fill=HANDWRITING_INK,
        )
    return page


def simulate_scan(page: Image.Image, rng: random.Random) -> np.ndarray:
    image = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)
    height, width = image.shape[:2]
    rotation = cv2.getRotationMatrix2D(
        (width / 2, height / 2), rng.uniform(-2.0, 2.0), rng.uniform(0.9, 0.97)
    )
    rotation[:, 2] += (rng.uniform(-30, 30), rng.uniform(-30, 30))
    scanned = cv2.warpAffine(image, rotation, (width, height), borderValue=(250, 250, 250))
    noise = np.random.default_rng(rng.randint(0, 10_000)).normal(0, 6, scanned.shape)
    noisy = np.clip(scanned.astype(np.float64) + noise, 0, 255).astype(np.uint8)
    return cv2.GaussianBlur(noisy, (3, 3), 0)


def main() -> None:
    output_dir = get_settings().data_dir / "samples"
    output_dir.mkdir(parents=True, exist_ok=True)
    fonts = (find_font(PRINTED_FONT_NAMES), find_font(HANDWRITING_FONT_NAMES))
    rng = random.Random(RANDOM_SEED)

    blank = draw_blank_form(fonts[0])
    blank.save(output_dir / "blank_form.png")
    for number, values in enumerate(FILLED_SAMPLES, start=1):
        filled = simulate_scan(fill_form(blank, values, fonts, rng), rng)
        cv2.imwrite(str(output_dir / f"filled_{number:02d}.jpg"), filled)
        (output_dir / f"filled_{number:02d}.json").write_text(
            json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(f"Wrote blank_form.png and {len(FILLED_SAMPLES)} filled samples to {output_dir}")


if __name__ == "__main__":
    main()
