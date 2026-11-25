"""Compare OCR engines on your own filled forms.

Put filled forms in a folder, each with a JSON file of the correct values next to it:
    samples/form01.jpg + samples/form01.json   ({"full_name": "陈大文", "phone": "91234567"})

Run from backend/:
    uv run python -m scripts.compare_engines --template-id <id> --samples data/samples
"""

import argparse
import json
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from app.api.dependencies import (
    ACCURATE_ENGINE_NAME,
    FAST_ENGINE_NAME,
    create_qwen_engine,
    get_field_value_reader,
    get_paddle_engine,
    get_template_store,
)
from app.config import get_settings
from app.imaging.page import load_page_images
from app.ocr.field_readers import SingleEngineFieldReader
from app.ocr.types import FieldValueReader
from app.services.evaluation import EngineScore, record_page
from app.services.form_processing import extract_form_values

SAMPLE_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".pdf", ".tif", ".tiff", ".webp")
LANGUAGE_ROUTED_READER_NAME = "by-language"
PERCENT = 100


def build_readers() -> dict[str, FieldValueReader]:
    settings = get_settings()
    threshold = settings.confidence_threshold
    return {
        "paddleocr": SingleEngineFieldReader(get_paddle_engine(), confidence_threshold=threshold),
        f"{FAST_ENGINE_NAME} ({settings.fast_model})": SingleEngineFieldReader(
            create_qwen_engine(name=FAST_ENGINE_NAME, model=settings.fast_model),
            confidence_threshold=threshold,
        ),
        f"{ACCURATE_ENGINE_NAME} ({settings.accurate_model})": SingleEngineFieldReader(
            create_qwen_engine(name=ACCURATE_ENGINE_NAME, model=settings.accurate_model),
            confidence_threshold=threshold,
        ),
        LANGUAGE_ROUTED_READER_NAME: get_field_value_reader(),
    }


def find_samples(samples_dir: Path) -> list[tuple[Path, dict[str, str]]]:
    samples = []
    for image_path in sorted(samples_dir.iterdir()):
        expected_path = image_path.with_suffix(".json")
        if image_path.suffix.lower() in SAMPLE_IMAGE_SUFFIXES and expected_path.exists():
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
            samples.append((image_path, {key: str(value) for key, value in expected.items()}))
    return samples


def compare(template_id: str, samples_dir: Path) -> list[EngineScore]:
    store = get_template_store()
    template = store.get(template_id)
    blank_pages = store.load_blank_pages(template)
    samples = find_samples(samples_dir)
    if not samples:
        raise SystemExit(f"No image + .json pairs found in {samples_dir}")

    scores = []
    for reader_name, reader in build_readers().items():
        score = EngineScore(engine=reader_name)
        for image_path, expected_values in samples:
            page_images = load_page_images(image_path.read_bytes())
            started = time.perf_counter()
            result = extract_form_values(
                page_images, template=template, blank_pages=blank_pages, reader=reader
            )
            record_page(
                score,
                sample=image_path.name,
                fields=result.fields,
                expected_values=expected_values,
                seconds=time.perf_counter() - started,
            )
        scores.append(score)
        print(f"  finished {reader_name}")
    return scores


def print_report(scores: list[EngineScore]) -> None:
    header = (
        f"{'Engine':<32}{'Exact match':>13}{'Char error':>12}{'Digits exact':>14}{'Sec/page':>10}"
    )
    print("\n" + header)
    print("-" * len(header))
    for score in scores:
        print(
            f"{score.engine:<32}"
            f"{score.exact_match_rate * PERCENT:>12.1f}%"
            f"{score.character_error_rate * PERCENT:>11.1f}%"
            f"{score.digit_exact_rate * PERCENT:>13.1f}%"
            f"{score.seconds_per_page:>10.1f}"
        )


def write_report(scores: list[EngineScore], reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = reports_dir / f"comparison-{timestamp}.json"
    report = [
        {
            "engine": score.engine,
            "exactMatchRate": score.exact_match_rate,
            "characterErrorRate": score.character_error_rate,
            "digitExactRate": score.digit_exact_rate,
            "secondsPerPage": score.seconds_per_page,
            "mismatches": [asdict(mismatch) for mismatch in score.mismatches],
        }
        for score in scores
    ]
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--template-id", required=True)
    parser.add_argument("--samples", type=Path, required=True)
    arguments = parser.parse_args()

    scores = compare(arguments.template_id, arguments.samples)
    print_report(scores)
    report_path = write_report(scores, get_settings().data_dir / "reports")
    print(f"\nEvery mismatch is listed in {report_path}")


if __name__ == "__main__":
    main()
