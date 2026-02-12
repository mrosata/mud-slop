import json


class GMCPHandler:
    """Parses GMCP payloads and maintains merged state per package."""

    def __init__(self):
        self.state: dict[str, dict] = {}

    def handle(self, ts: float, raw: bytes) -> tuple[str, object]:
        """Parse 'package.name {json}' payload, merge into state.
        Returns (package, parsed_data)."""
        text = raw.decode("utf-8", errors="replace")
        # Split into package name and optional JSON body
        space = text.find(" ")
        if space == -1:
            package = text.strip().lower()
            data = {}
        else:
            package = text[:space].strip().lower()
            body = text[space + 1 :].strip()
            try:
                data = json.loads(body)
            except (json.JSONDecodeError, ValueError):
                data = body  # keep as raw string

        # Merge dict updates; replace for non-dict data
        if isinstance(data, dict):
            if package not in self.state:
                self.state[package] = {}
            self.state[package].update(data)
        else:
            self.state[package] = data

        return package, data

    @property
    def vitals(self) -> dict:
        return self.state.get("char.vitals", {})

    @property
    def status(self) -> dict:
        return self.state.get("char.status", {})

    @property
    def stats(self) -> dict:
        return self.state.get("char.stats", {})

    @property
    def maxstats(self) -> dict:
        return self.state.get("char.maxstats", {})
