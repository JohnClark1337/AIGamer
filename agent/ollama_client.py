import base64
import io
import json
import logging
import requests
from PIL import Image
from typing import Any

log = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, config: dict[str, Any]):
        self._host = config.get("ollama", {}).get("host", "http://localhost:11434")
        self._model = config.get("ollama", {}).get("model", "llama3.2-vision:11b")
        self._temperature = config.get("ollama", {}).get("temperature", 0.2)
        self._num_predict = config.get("ollama", {}).get("num_predict", 128)
        self._generate_url = f"{self._host.rstrip('/')}/api/generate"
        self._chat_url = f"{self._host.rstrip('/')}/api/chat"

    @property
    def model(self) -> str:
        return self._model

    def _encode_image(self, img: Image.Image) -> str:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def generate(self, prompt: str, image: Image.Image | None = None) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "temperature": self._temperature,
            "num_predict": self._num_predict,
            "stream": False,
        }

        if image is not None:
            payload["images"] = [self._encode_image(image)]

        log.debug("Sending to Ollama: model=%s prompt_len=%d image=%s",
                   self._model, len(prompt), image is not None)

        resp = requests.post(self._generate_url, json=payload, timeout=600)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()

    def chat(
        self,
        messages: list[dict[str, Any]],
        image: Image.Image | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "num_predict": self._num_predict,
            "stream": False,
        }

        if image is not None:
            encoded = self._encode_image(image)
            last = messages[-1]
            content = last.get("content", "")
            last["content"] = content
            last["images"] = [encoded]

        log.debug("Ollama chat: %d messages, image=%s",
                   len(messages), image is not None)

        resp = requests.post(self._chat_url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "").strip()

    def list_models(self) -> list[dict[str, Any]]:
        resp = requests.get(f"{self._host.rstrip('/')}/api/tags", timeout=10)
        resp.raise_for_status()
        return resp.json().get("models", [])

    def is_available(self) -> bool:
        try:
            resp = requests.get(f"{self._host.rstrip('/')}", timeout=5)
            return resp.status_code < 500
        except requests.RequestException:
            return False

    def pull_model(self, model: str) -> None:
        payload = {"name": model, "stream": False}
        resp = requests.post(f"{self._host.rstrip('/')}/api/pull", json=payload, timeout=600)
        resp.raise_for_status()
