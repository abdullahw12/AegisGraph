import logging
import os
from typing import Optional

import ddtrace

logger = logging.getLogger(__name__)


class MiniMaxClient:
    """Optional TTS client. No-ops gracefully when MINIMAX_API_KEY is absent."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("MINIMAX_API_KEY")
        self._enabled = bool(self._api_key)
        if not self._enabled:
            logger.info("MiniMaxClient: MINIMAX_API_KEY not set — TTS disabled.")

    def speak_alert(self, text: str) -> None:
        """Speak an incident alert via MiniMax TTS. No-ops if not configured."""
        with ddtrace.tracer.trace("minimax.tts_alert") as span:
            span.set_tag("alert_text", text[:200])
            if not self._enabled:
                logger.debug("MiniMaxClient: TTS skipped (no API key).")
                return
            try:
                self._call_tts_api(text)
            except Exception as exc:
                logger.warning("MiniMaxClient: TTS call failed: %s", exc)
                # Do not re-raise — pipeline must not fail due to TTS errors

    def _call_tts_api(self, text: str) -> None:
        """Stub for the actual MiniMax TTS REST call."""
        import urllib.request
        import json

        payload = json.dumps({"text": text, "model": "speech-01"}).encode()
        req = urllib.request.Request(
            "https://api.minimax.chat/v1/text_to_speech",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
