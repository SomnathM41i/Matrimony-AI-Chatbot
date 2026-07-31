import logging
import sys
import time


logger = logging.getLogger("myvivahai")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
))
if not logger.handlers:
    logger.addHandler(handler)
# Uvicorn configures the root logger; without this every line is emitted twice.
logger.propagate = False


class StepTimer:
    def __init__(self, request_id: str | None = None):
        self.steps = []
        self.request_id = request_id
        self._start = time.perf_counter()
        self._current_step = None
        self._current_start = None
        self._logged = False

    def begin(self, label: str):
        now = time.perf_counter()
        if self._current_step:
            elapsed = round((now - self._current_start) * 1000)
            self.steps.append((self._current_step, elapsed))
        self._current_step = label
        self._current_start = now
        elapsed_since_start = round(now - self._start, 2)
        return {"step": label, "elapsed": elapsed_since_start}

    def end(self):
        now = time.perf_counter()
        if self._current_step:
            elapsed = round((now - self._current_start) * 1000)
            self.steps.append((self._current_step, elapsed))
            self._current_step = None
        total = round((now - self._start) * 1000)
        return total

    def summary(self) -> str:
        parts = [f"{label}={ms}ms" for label, ms in self.steps]
        return " | ".join(parts) if parts else ""

    def log_summary(self, intent: str):
        # Guard so a summary logged in a finally block does not duplicate the
        # one already logged on the success path.
        if self._logged:
            return
        self._logged = True
        total = self.end()
        self.steps.append(("total", total))
        steps_str = self.summary()
        if self.request_id:
            logger.info("[%s] [req=%s] %s", intent, self.request_id[:8], steps_str)
        else:
            logger.info("[%s] %s", intent, steps_str)
