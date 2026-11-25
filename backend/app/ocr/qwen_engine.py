import base64
import math
import re

import httpx
import numpy as np
from pydantic import BaseModel

from app.errors import OcrEngineUnavailableError
from app.imaging.page import encode_png
from app.ocr.types import Reading

TRANSCRIPTION_PROMPT = (
    "Transcribe the handwritten or printed text in this image exactly as written. "
    "Keep the original language and characters (Chinese, English, digits). "
    "Do not translate, correct spelling, reformat, or guess unclear characters. "
    "Ignore printed underlines and box borders. "
    "Output only the transcribed text. If nothing is written, output nothing."
)
# Ollama's Qwen3-VL "thinking" builds ignore think=false; pre-filling an empty think block makes
# the model answer directly (about 0.4s instead of 6s per field, with the same transcription).
EMPTY_THINKING_PREFILL = "<think>\n\n</think>\n\n"
MAX_OUTPUT_TOKENS = 128
# Shown a nearly empty crop, the model sometimes describes the image instead of transcribing it
# ("The field appears to be a blank space…"). Such a reply is not a value.
IMAGE_DESCRIPTION_PATTERN = re.compile(
    r"\b(appears? to be|(the|this) image|blank (space|field|area|box)|"
    r"is (mostly |completely |entirely )?(blank|empty)|"
    r"no ((visible|legible|handwritten|handwriting) )*(text|writing)|nothing (is )?written)\b",
    re.IGNORECASE,
)


class OllamaMessage(BaseModel):
    content: str = ""


class OllamaTokenLogprob(BaseModel):
    token: str
    logprob: float


class OllamaChatResponse(BaseModel):
    message: OllamaMessage
    logprobs: list[OllamaTokenLogprob] | None = None


class OllamaModelTag(BaseModel):
    name: str


class OllamaTagsResponse(BaseModel):
    models: list[OllamaModelTag]


class QwenVlEngine:
    def __init__(
        self,
        *,
        name: str,
        model: str,
        client: httpx.Client,
        keep_alive: str,
        should_skip_thinking: bool,
    ) -> None:
        self.name = name
        self._model = model
        self._client = client
        self._keep_alive = keep_alive
        self._should_skip_thinking = should_skip_thinking

    def read(self, crop: np.ndarray) -> Reading:
        try:
            response = self._client.post("/api/chat", json=self._build_request(crop))
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise OcrEngineUnavailableError(self._model) from error
        chat_response = OllamaChatResponse.model_validate(response.json())
        text = _drop_image_description(chat_response.message.content.strip())
        confidence = estimate_confidence(chat_response.logprobs, has_text=bool(text))
        return Reading(engine=self.name, text=text, confidence=confidence)

    def _build_request(self, crop: np.ndarray) -> dict[str, object]:
        encoded_image = base64.b64encode(encode_png(crop)).decode("ascii")
        messages: list[dict[str, object]] = [
            {"role": "user", "content": TRANSCRIPTION_PROMPT, "images": [encoded_image]}
        ]
        if self._should_skip_thinking:
            messages.append({"role": "assistant", "content": EMPTY_THINKING_PREFILL})
        return {
            "model": self._model,
            "stream": False,
            "think": False,
            "logprobs": True,
            "keep_alive": self._keep_alive,
            "options": {"temperature": 0, "num_predict": MAX_OUTPUT_TOKENS},
            "messages": messages,
        }


def _drop_image_description(text: str) -> str:
    return "" if IMAGE_DESCRIPTION_PATTERN.search(text) else text


def estimate_confidence(logprobs: list[OllamaTokenLogprob] | None, *, has_text: bool) -> float:
    """Use the least certain token as the field's confidence: one doubtful digit is enough."""
    if not has_text or not logprobs:
        return 0.0
    return math.exp(min(token.logprob for token in logprobs))


def list_available_models(client: httpx.Client) -> set[str] | None:
    try:
        response = client.get("/api/tags")
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    payload = OllamaTagsResponse.model_validate(response.json())
    return {model.name for model in payload.models}
