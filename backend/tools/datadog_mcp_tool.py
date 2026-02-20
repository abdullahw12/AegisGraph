import time
from collections import deque
from typing import Deque


class DatadogMCPTool:
    """
    In-memory event store for detecting attack spikes and triggering self-healing.

    Maintains two deque-based ring buffers (auth denies and safety blocks).
    When either buffer accumulates >= threshold events within window_seconds,
    should_escalate() returns True.  After escalation, a cooldown_seconds
    period must elapse before escalation can fire again.
    """

    def __init__(
        self,
        window_seconds: int = 60,
        threshold: int = 3,
        cooldown_seconds: int = 600,
    ):
        self._window = window_seconds
        self._threshold = threshold
        self._cooldown = cooldown_seconds

        # Each deque stores float timestamps (time.monotonic())
        self._auth_denies: Deque[float] = deque()
        self._safety_blocks: Deque[float] = deque()

        # Timestamp of the last escalation (None = never escalated)
        self._last_escalation: float | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_auth_deny(self) -> None:
        """Record a single auth-deny event with the current timestamp."""
        self._auth_denies.append(time.monotonic())

    def record_safety_block(self) -> None:
        """Record a single safety-block event with the current timestamp."""
        self._safety_blocks.append(time.monotonic())

    def should_escalate(self) -> bool:
        """
        Return True iff either buffer has >= threshold events within the
        rolling window AND the cooldown period since the last escalation
        has elapsed.
        """
        now = time.monotonic()

        # Respect cooldown
        if self._last_escalation is not None:
            if now - self._last_escalation < self._cooldown:
                return False

        if self._count_recent(self._auth_denies, now) >= self._threshold:
            self._last_escalation = now
            return True

        if self._count_recent(self._safety_blocks, now) >= self._threshold:
            self._last_escalation = now
            return True

        return False

    def reset_window(self) -> None:
        """Clear both ring buffers and reset the escalation timestamp."""
        self._auth_denies.clear()
        self._safety_blocks.clear()
        self._last_escalation = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _count_recent(self, buf: Deque[float], now: float) -> int:
        """Count events in buf that fall within the rolling window."""
        cutoff = now - self._window
        # Prune stale entries from the left
        while buf and buf[0] < cutoff:
            buf.popleft()
        return len(buf)
