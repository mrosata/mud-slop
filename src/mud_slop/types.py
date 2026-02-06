import time
from dataclasses import dataclass


@dataclass
class ProtoEvent:
    direction: str  # "IN" or "OUT" or "SYS"
    ts: float
    raw: bytes
    text_preview: str


def ts_str(t: float) -> str:
    lt = time.localtime(t)
    return time.strftime("%H:%M:%S", lt)


def safe_text_preview(b: bytes, max_len: int = 120) -> str:
    # Replace unprintables; keep it readable
    s = b.decode("utf-8", errors="replace")
    s = s.replace("\r", "\\r").replace("\n", "\\n")
    if len(s) > max_len:
        s = s[:max_len] + "\u2026"
    return s


def hex_preview(b: bytes, max_len: int = 48) -> str:
    hb = b[:max_len].hex(" ")
    if len(b) > max_len:
        hb += " \u2026"
    return hb
