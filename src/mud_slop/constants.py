# Telnet constants (RFC 854-ish)
IAC = 255  # Interpret As Command
DONT = 254
DO = 253
WONT = 252
WILL = 251
SB = 250  # Subnegotiation Begin
SE = 240  # Subnegotiation End
ECHO = 1  # Telnet ECHO option (RFC 857)
GMCP = 201  # Generic MUD Communication Protocol

TELNET_CMD_NAMES = {
    IAC: "IAC",
    DONT: "DONT",
    DO: "DO",
    WONT: "WONT",
    WILL: "WILL",
    SB: "SB",
    SE: "SE",
}

NEGOTIATION_CMDS = {DO, DONT, WILL, WONT}

TELNET_OPT_NAMES = {
    GMCP: "GMCP",
}
