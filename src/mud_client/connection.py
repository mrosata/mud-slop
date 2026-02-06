from __future__ import annotations

import json
import queue
import selectors
import socket
import time
from typing import TYPE_CHECKING

from mud_client.constants import (
    IAC, DO, GMCP, SB, SE,
    TELNET_CMD_NAMES, TELNET_OPT_NAMES, NEGOTIATION_CMDS,
)
from mud_client.types import ProtoEvent, safe_text_preview, hex_preview
from mud_client.telnet import TelnetFilter

if TYPE_CHECKING:
    from mud_client.config import GMCPConfig


class MudConnection:
    def __init__(self, host: str, port: int, proto_q: "queue.Queue[ProtoEvent]",
                 text_q: "queue.Queue[str]", gmcp_q: "queue.Queue[tuple[float, bytes]]",
                 gmcp_config: "GMCPConfig | None" = None):
        self.host = host
        self.port = port
        self.proto_q = proto_q
        self.text_q = text_q
        self.gmcp_q = gmcp_q
        self.gmcp_config = gmcp_config

        self.sock = None
        self.sel = selectors.DefaultSelector()
        self.telnet = TelnetFilter()

        self._rx_buf = bytearray()
        self._gmcp_negotiated = False

    @property
    def echo_off(self) -> bool:
        """True when server has signaled password mode (WILL ECHO)."""
        return self.telnet.echo_off

    def connect(self, timeout: float = 10.0):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((self.host, self.port))
        s.setblocking(False)
        self.sock = s
        self.sel.register(self.sock, selectors.EVENT_READ)

        self._proto("SYS", b"", f"Connected to {self.host}:{self.port}")

    def close(self):
        try:
            if self.sock:
                self.sel.unregister(self.sock)
                self.sock.close()
        except Exception:
            pass
        self.sock = None
        self._proto("SYS", b"", "Disconnected")

    def _proto(self, direction: str, raw: bytes, preview: str = ""):
        if not preview:
            preview = safe_text_preview(raw)
        self.proto_q.put(ProtoEvent(direction=direction, ts=time.time(), raw=raw, text_preview=preview))

    def send_line(self, line: str):
        if not self.sock:
            return
        # MUDs typically want \r\n
        data = (line + "\r\n").encode("utf-8", errors="replace")
        try:
            self.sock.sendall(data)
            self._proto("OUT", data, f"{safe_text_preview(data)}  |  {hex_preview(data)}")
        except Exception as e:
            self._proto("SYS", b"", f"Send failed: {e}")
            self.close()

    def poll(self):
        """
        Called from UI loop. Non-blocking read.
        """
        if not self.sock:
            return

        events = self.sel.select(timeout=0)
        for key, mask in events:
            if mask & selectors.EVENT_READ:
                try:
                    chunk = self.sock.recv(4096)
                except BlockingIOError:
                    continue
                except Exception as e:
                    self._proto("SYS", b"", f"Recv failed: {e}")
                    self.close()
                    return

                if not chunk:
                    self._proto("SYS", b"", "Server closed connection")
                    self.close()
                    return

                self._proto("IN", chunk, f"{safe_text_preview(chunk)}  |  {hex_preview(chunk)}")

                display, responses, notes, gmcp_payloads = self.telnet.feed(chunk)

                # Log telnet notes as SYS proto events
                for nte in notes:
                    txt = self._pretty_telnet_note(nte)
                    self._proto("SYS", nte, txt)

                if responses:
                    try:
                        self.sock.sendall(responses)
                        self._proto("OUT", responses, f"(telnet) {hex_preview(responses)}")
                    except Exception as e:
                        self._proto("SYS", b"", f"Send(telnet) failed: {e}")
                        self.close()
                        return

                    # Check if we just agreed to GMCP — send handshake
                    if not self._gmcp_negotiated and bytes([IAC, DO, GMCP]) in responses:
                        self._gmcp_negotiated = True
                        self._send_gmcp_handshake()

                # Queue GMCP payloads
                now = time.time()
                for payload in gmcp_payloads:
                    self.gmcp_q.put((now, payload))

                if display:
                    text = display.decode("utf-8", errors="replace")
                    text = text.replace("\r\n", "\n").replace("\r", "")
                    self.text_q.put(text)

    def send_gmcp(self, package: str, data: str = ""):
        """Send a GMCP message: IAC SB 201 <payload> IAC SE"""
        if not self.sock:
            return
        if data:
            payload = f"{package} {data}".encode("utf-8")
        else:
            payload = package.encode("utf-8")
        # Escape any 0xFF in payload
        payload = payload.replace(bytes([IAC]), bytes([IAC, IAC]))
        frame = bytes([IAC, SB, GMCP]) + payload + bytes([IAC, SE])
        try:
            self.sock.sendall(frame)
            self._proto("OUT", frame, f"GMCP send: {package} {data[:80]}")
        except Exception as e:
            self._proto("SYS", b"", f"GMCP send failed: {e}")

    def _send_gmcp_handshake(self):
        self.send_gmcp("Core.Hello", json.dumps({"client": "PyMudClient", "version": "0.1.0"}))
        # Use subscriptions from config if available, otherwise use defaults
        if self.gmcp_config and self.gmcp_config.subscriptions:
            subscriptions = self.gmcp_config.subscriptions
        else:
            subscriptions = [
                "char 1", "char.vitals 1", "char.stats 1", "char.status 1",
                "char.maxstats 1",
            ]
        self.send_gmcp("Core.Supports.Set", json.dumps(subscriptions))

    def _pretty_telnet_note(self, b: bytes) -> str:
        # b may be 2 bytes (IAC cmd) or 3 bytes (IAC cmd opt) or our annotations
        if len(b) >= 2 and b[0] == IAC:
            cmd = b[1]
            cmd_name = TELNET_CMD_NAMES.get(cmd, f"CMD({cmd})")
            if len(b) >= 3 and cmd in NEGOTIATION_CMDS:
                opt = b[2]
                opt_name = TELNET_OPT_NAMES.get(opt, str(opt))
                return f"TELNET {cmd_name} opt={opt_name}"
            return f"TELNET {cmd_name}"
        return f"TELNET {hex_preview(b)}"
