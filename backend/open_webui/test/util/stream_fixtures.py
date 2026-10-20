import json
from pathlib import Path

TEST_DATA = Path(__file__).resolve().parents[1] / "data"


def parse_sse_events(path: Path) -> list[dict]:
    events = []
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith("event: "):
            event_type = lines[i][len("event: ") :]
            i += 1
            if i < len(lines) and lines[i].startswith("data: "):
                data = json.loads(lines[i][len("data: ") :])
                data["type"] = event_type
                events.append(data)
        i += 1
    return events
