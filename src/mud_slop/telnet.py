from mud_slop.constants import (
    IAC, DONT, DO, WONT, WILL, SB, SE, ECHO, GMCP,
    TELNET_OPT_NAMES, NEGOTIATION_CMDS,
)


class TelnetFilter:
    """
    Minimal Telnet negotiator:
    - Strips IAC sequences out of the display stream.
    - Accepts GMCP (option 201); refuses all other WILL/DO offers.
    - Captures GMCP subnegotiation payloads and returns them separately.
    """

    def __init__(self):
        self._sb_mode = False
        self._sb_opt = 0
        self._sb_buf = bytearray()
        self.echo_off = False  # True when server signals password mode (WILL ECHO)

    def feed(self, data: bytes):
        """
        Returns: (display_bytes, responses_bytes, proto_notes[], gmcp_payloads[])
        """
        out = bytearray()
        resp = bytearray()
        notes = []
        gmcp_payloads = []

        i = 0
        n = len(data)

        while i < n:
            byte = data[i]

            if self._sb_mode:
                if byte == IAC and i + 1 < n:
                    if data[i + 1] == SE:
                        # End subnegotiation
                        if self._sb_opt == GMCP:
                            gmcp_payloads.append(bytes(self._sb_buf))
                            opt_name = TELNET_OPT_NAMES.get(self._sb_opt, str(self._sb_opt))
                            notes.append(f"IAC SE (end {opt_name} subneg, {len(self._sb_buf)} bytes)".encode())
                        else:
                            notes.append(b"IAC SE (end subnegotiation)")
                        self._sb_mode = False
                        self._sb_buf.clear()
                        i += 2
                    elif data[i + 1] == IAC:
                        # Escaped 0xFF inside subnegotiation
                        self._sb_buf.append(IAC)
                        i += 2
                    else:
                        self._sb_buf.append(byte)
                        i += 1
                else:
                    self._sb_buf.append(byte)
                    i += 1
                continue

            if byte != IAC:
                out.append(byte)
                i += 1
                continue

            # byte == IAC
            if i + 1 >= n:
                break

            cmd = data[i + 1]

            if cmd == IAC:
                out.append(IAC)
                i += 2
                continue

            if cmd == SB:
                if i + 2 >= n:
                    break
                self._sb_opt = data[i + 2]
                self._sb_mode = True
                self._sb_buf.clear()
                opt_name = TELNET_OPT_NAMES.get(self._sb_opt, str(self._sb_opt))
                notes.append(f"IAC SB {opt_name} (begin subnegotiation)".encode())
                i += 3
                continue

            if cmd in NEGOTIATION_CMDS:
                if i + 2 >= n:
                    break
                opt = data[i + 2]

                if cmd == WILL:
                    if opt == GMCP:
                        resp += bytes([IAC, DO, opt])
                        notes.append(bytes([IAC, WILL, opt]) + b" -> IAC DO " + bytes([opt]) + b" (GMCP)")
                    else:
                        if opt == ECHO:
                            self.echo_off = True
                        resp += bytes([IAC, DONT, opt])
                        notes.append(bytes([IAC, WILL, opt]) + b" -> IAC DONT " + bytes([opt]))
                elif cmd == DO:
                    if opt == GMCP:
                        resp += bytes([IAC, WILL, opt])
                        notes.append(bytes([IAC, DO, opt]) + b" -> IAC WILL " + bytes([opt]) + b" (GMCP)")
                    else:
                        resp += bytes([IAC, WONT, opt])
                        notes.append(bytes([IAC, DO, opt]) + b" -> IAC WONT " + bytes([opt]))
                elif cmd == WONT:
                    if opt == ECHO:
                        self.echo_off = False
                    notes.append(bytes([IAC, WONT, opt]))
                elif cmd == DONT:
                    notes.append(bytes([IAC, DONT, opt]))

                i += 3
                continue

            notes.append(bytes([IAC, cmd]))
            i += 2

        return bytes(out), bytes(resp), notes, gmcp_payloads
