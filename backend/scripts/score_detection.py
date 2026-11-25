"""Score blank-form field detection against your saved templates.

Each saved template is the correct answer for its blank form, once you have fixed its fields in
the editor. This runs detection on every saved blank form again and reports, per template, which
saved fields it found, which it missed and which it made up. Run it before and after changing the
detection rules: a change is only an improvement if no template gets worse.

Run from backend/:
    uv run python -m scripts.score_detection                     # every saved template
    uv run python -m scripts.score_detection --template-id <id>  # just one
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.api.dependencies import get_blank_form_field_detector, get_template_store
from app.config import get_settings
from app.schemas import TemplateField
from app.services.evaluation import DetectionScore, score_detection
from app.services.form_processing import detect_template_fields

PERCENT = 100


def score_templates(template_ids: list[str]) -> list[DetectionScore]:
    store = get_template_store()
    detector = get_blank_form_field_detector()
    ids = template_ids or [summary.id for summary in store.list_summaries()]
    if not ids:
        raise SystemExit("No saved templates yet. Save one from the app first.")

    scores = []
    for template_id in ids:
        template = store.get(template_id)
        detected = detect_template_fields(store.load_blank_pages(template), detector=detector)
        scores.append(score_detection(template.name, expected=template.fields, detected=detected))
        print(f"  scored {template.name}")
    return scores


def print_report(scores: list[DetectionScore]) -> None:
    header = (
        f"{'Template':<28}{'Saved':>7}{'Found':>7}{'Matched':>9}{'Missed':>8}"
        f"{'Made up':>9}{'Wrong kind':>12}{'Recall':>9}{'Precision':>11}"
    )
    print("\n" + header)
    print("-" * len(header))
    for score in scores:
        print(
            f"{score.template_name[:27]:<28}{score.expected_count:>7}{score.detected_count:>7}"
            f"{len(score.matches):>9}{len(score.missed):>8}{len(score.made_up):>9}"
            f"{len(score.different_kind):>12}"
            f"{score.recall * PERCENT:>8.1f}%{score.precision * PERCENT:>10.1f}%"
        )
    for score in scores:
        _print_differences(score)


def _print_differences(score: DetectionScore) -> None:
    if not (score.missed or score.made_up or score.different_kind):
        return
    print(f"\n{score.template_name}")
    for field in score.missed:
        print(f"  missed      {_describe(field)}")
    for field in score.made_up:
        print(f"  made up     {_describe(field)}")
    for match in score.different_kind:
        detected_kind = _describe_kind(match.detected)
        print(f"  wrong kind  {_describe(match.expected)}  detected as {detected_kind}")


def _describe(field: TemplateField) -> str:
    box = field.box
    position = f"({box.x}, {box.y}, {box.width}x{box.height})"
    return f"page {field.page_index + 1} {position:<24} {_describe_kind(field)} {field.label!r}"


def _describe_kind(field: TemplateField) -> str:
    if field.options:
        return f"{field.field_type.value}[{len(field.options)}]"
    return field.field_type.value


def write_report(scores: list[DetectionScore], reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = reports_dir / f"detection-{timestamp}.json"
    report = [
        {
            "template": score.template_name,
            "recall": score.recall,
            "precision": score.precision,
            "missed": [_to_report_field(field) for field in score.missed],
            "madeUp": [_to_report_field(field) for field in score.made_up],
            "wrongKind": [
                {
                    "saved": _to_report_field(match.expected),
                    "detected": _to_report_field(match.detected),
                }
                for match in score.different_kind
            ],
        }
        for score in scores
    ]
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def _to_report_field(field: TemplateField) -> dict[str, object]:
    return field.model_dump(
        mode="json", by_alias=True, include={"key", "label", "field_type", "page_index", "box"}
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--template-id", action="append", default=[], dest="template_ids")
    arguments = parser.parse_args()

    scores = score_templates(arguments.template_ids)
    print_report(scores)
    report_path = write_report(scores, get_settings().data_dir / "reports")
    print(f"\nEvery difference is listed in {report_path}")


if __name__ == "__main__":
    main()
