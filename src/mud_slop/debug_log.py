import json
import time

from mud_slop.types import ProtoEvent, ts_str, hex_preview


class DebugLogger:
    """Manages optional debug log files for output, protocol, and GMCP streams."""

    def __init__(self):
        self.enabled = False
        self._output_fh = None
        self._proto_fh = None
        self._gmcp_fh = None

    def start(self):
        self._output_fh = open("mud_output.log", "a", encoding="utf-8")
        self._proto_fh = open("mud_proto.log", "a", encoding="utf-8")
        self._gmcp_fh = open("mud_gmcp.log", "a", encoding="utf-8")
        self.enabled = True
        sep = f"\n{'='*60}\n  Session started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n{'='*60}\n"
        for fh in (self._output_fh, self._proto_fh, self._gmcp_fh):
            fh.write(sep)
            fh.flush()

    def stop(self):
        self.enabled = False
        for fh in (self._output_fh, self._proto_fh, self._gmcp_fh):
            if fh:
                try:
                    fh.close()
                except Exception:
                    pass
        self._output_fh = self._proto_fh = self._gmcp_fh = None

    def toggle(self) -> bool:
        if self.enabled:
            self.stop()
        else:
            self.start()
        return self.enabled

    def log_output(self, text: str):
        if not self.enabled or not self._output_fh:
            return
        for line in text.split("\n"):
            self._output_fh.write(f"{ts_str(time.time())} | {line}\n")
        self._output_fh.flush()

    def log_proto(self, ev: ProtoEvent):
        if not self.enabled or not self._proto_fh:
            return
        hex_str = hex_preview(ev.raw) if ev.raw else ""
        self._proto_fh.write(
            f"{ts_str(ev.ts)} {ev.direction:>3} | {ev.text_preview}"
            + (f"  | hex: {hex_str}" if hex_str else "")
            + "\n"
        )
        self._proto_fh.flush()

    def log_gmcp(self, package: str, data):
        if not self.enabled or not self._gmcp_fh:
            return
        self._gmcp_fh.write(f"{ts_str(time.time())} | {package}: {json.dumps(data, default=str)}\n")
        self._gmcp_fh.flush()
