# OCR Form Scanner

Turn a blank form into a template, then read filled-in copies (handwriting, Chinese, English,
numbers) back as JSON. Everything runs locally: PaddleOCR on the CPU and Qwen3-VL through Ollama.

## How it works

1. **Template from a blank form.** PaddleOCR finds the printed labels. OpenCV finds the
   underlines, table cells and blank space after a `:`/`：`. Each label is paired with its answer
   area. You review and adjust the boxes in the browser, then save.
2. **Values from a filled form.** The scan is lined up with the blank template (ORB + homography),
   and each field area is cropped. A field with no new ink is returned as empty without calling OCR.
   PaddleOCR reads every other field first, and its reading decides which engine gives the value:
   - **English text:** PaddleOCR alone (about 0.3 s).
   - **Text with Chinese characters, or text PaddleOCR can't read:** **Qwen3-VL 4B** (about 3 s).
   - **Numbers and dates:** **Qwen3-VL 8B** (about 5 s). The value is *confirmed* only when
     PaddleOCR reads the same digits. This stops a believable but wrong VLM guess (for example a
     `1` read as `7`) from passing silently.

   A value whose engine is less confident than the threshold is flagged *needs review*.

Filled forms are never written to disk. Only templates (JSON + the blank form image) are stored, in
`backend/data/`.

## Requirements

- macOS (Apple Silicon) or Linux, Python 3.12 via [uv](https://docs.astral.sh/uv/), Node 20+
- [Ollama](https://ollama.com) with the models:
  ```sh
  ollama pull qwen3-vl:4b
  ollama pull qwen3-vl:8b
  ```

## Run it

```sh
# 1. Backend (http://127.0.0.1:8000). The first run downloads the PaddleOCR models (~100 MB).
cd backend
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2. Frontend (http://localhost:5173), in another terminal
cd frontend
npm install
npm run dev
```

### Try it with sample forms

```sh
cd backend
uv run python -m scripts.make_sample_forms   # writes data/samples/
```

This writes a bilingual blank form and three filled copies with handwriting-style fonts. The
copies are slightly rotated and noisy, like a real scan. Upload `blank_form.png` on **Templates →
New template**, save it, then upload a `filled_0N.jpg` on **Extract values**.

## Configuration

Set these as environment variables or in `backend/.env`:

| Variable | Default | Purpose |
|---|---|---|
| `OCR_OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `OCR_FAST_MODEL` | `qwen3-vl:4b` | Reads Chinese text |
| `OCR_ACCURATE_MODEL` | `qwen3-vl:8b` | Reads numbers and dates |
| `OCR_SKIP_MODEL_THINKING` | `true` | Skips Qwen's reasoning step (see note) |
| `OCR_CONFIDENCE_THRESHOLD` | `0.85` | Below this, a value is flagged for review |
| `OCR_DATA_DIR` | `backend/data` | Template storage |
| `OCR_MAX_UPLOAD_BYTES` | `20971520` | Upload size limit |

**Note on thinking models:** the `qwen3-vl:4b`/`8b` tags in Ollama are the *Thinking* builds,
and they ignore `think: false`. The backend pre-fills an empty reasoning block, so the model
answers directly. This cut reading time from about 6 s to about 0.4 s per field with the same
results. If you switch to an *Instruct* model tag, set `OCR_SKIP_MODEL_THINKING=false`.

## Compare engines on your own forms

The sample results are not a fair test: their "handwriting" is a font. To choose engines or
thresholds for real use, collect 20–50 real filled forms. Put a JSON file of the correct values
next to each one:

```
my-samples/form01.jpg
my-samples/form01.json   {"full_name": "陈大文", "phone": "91234567"}
```

```sh
cd backend
uv run python -m scripts.compare_engines --template-id <id> --samples my-samples
```

It prints exact-match rate, character error rate, digit-field accuracy and seconds per page for
PaddleOCR, 4B, 8B and the by-language reader the app uses. Every mismatch is listed in
`data/reports/`.

## Adding a new kind of form

Field detection on blank forms uses fixed OpenCV rules. Each saved template is the correct answer
for its blank form, so every template you save becomes a check the rules must keep passing.

1. Upload the blank form, fix the detected fields in the editor and save it as a template.
2. Score detection against every saved template:

   ```sh
   cd backend
   uv run python -m scripts.score_detection
   ```

   It prints, per template, how many saved fields detection found, missed and made up, plus
   choice fields found with the wrong number of options. Every difference is listed in
   `data/reports/`. A detected field counts as found when its box overlaps the saved one by at
   least half (intersection over union).
3. If the new form scores badly, change the rules in `app/services/field_detection.py` and score
   again. Keep a change only if no template scores worse than before.

## API

| Method | Path | |
|---|---|---|
| `POST` | `/api/templates/drafts` | Upload a blank form (`file`) → detected fields |
| `GET` | `/api/templates/drafts/{draftId}/image` | Normalised blank form image |
| `POST` / `GET` | `/api/templates` | Save a draft as a template / list templates |
| `GET` / `PUT` / `DELETE` | `/api/templates/{id}` | Read, update, delete |
| `GET` | `/api/templates/{id}/image` | Template image |
| `POST` | `/api/extractions` | Filled form (`file`, `templateId`) → values JSON |
| `GET` | `/api/health` | Ollama reachability and installed models |

Example extraction response (trimmed):

```json
{
  "templateId": "…",
  "isAligned": true,
  "values": { "full_name": "陈大文 Chan Tai Man", "phone": "9123 4567", "signed_date": "" },
  "fields": [
    {
      "key": "phone", "value": "9123 4567", "status": "confirmed", "confidence": 0.99,
      "readings": [
        { "engine": "paddleocr", "text": "9123 4567", "confidence": 0.98 },
        { "engine": "qwen-fast", "text": "9123 4567", "confidence": 0.99 }
      ]
    }
  ]
}
```

## Development

```sh
# backend
uv run pytest                  # unit tests (fakes at the OCR boundary)
uv run pytest -m integration   # real PaddleOCR + Ollama
uv run ruff check . && uv run ruff format --check .

# frontend
npm run type-check && npm run lint && npm test
```

## Limitations

- PDFs: only the first page is used.
- Field detection relies on rules (underlines, table cells, `label:` + blank space). Unusual
  layouts may need boxes added by hand in the editor.
- Values are returned as strings exactly as read. Dates and amounts are not parsed or reformatted.
