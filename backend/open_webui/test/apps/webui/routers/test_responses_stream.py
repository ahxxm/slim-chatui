"""
Tests for Responses API stream processing.

Uses captured stream data from test/data/ as input tape — real API output,
replayed deterministically.

Capture new test data (with dev server running):
    curl -s http://localhost:8080/openai/chat/completions \
      -H 'Content-Type: application/json' \
      -H "Authorization: Bearer $TOKEN" \
      -d '{"model":"o3","stream":true,"messages":[{"role":"user","content":"..."}]}' \
      -o backend/open_webui/test/data/responses-api-stream-DESCRIPTION.txt
"""

import json
import time
from pathlib import Path

from open_webui.utils.middleware import (
    handle_responses_streaming_event,
    serialize_output,
)

TEST_DATA = Path(__file__).resolve().parents[3] / "data"
SIMULATED_REASONING_DELAY = 0.1


def parse_sse_events(path: Path) -> list[dict]:
    lines = path.read_text().splitlines()
    events = []
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


def replay_stream(events: list[dict]) -> tuple[list, dict]:
    # Simulate reasoning time: sleep after processing reasoning output_item.added,
    # so started_at is stamped first, then the delay represents the model thinking
    # before the next item arrives.
    output = []
    metadata = None
    for event in events:
        output, meta = handle_responses_streaming_event(event, output)
        if meta is not None:
            metadata = meta
        if (
            event.get("type") == "response.output_item.added"
            and event.get("item", {}).get("type") == "reasoning"
        ):
            time.sleep(SIMULATED_REASONING_DELAY)
    return output, metadata


class TestResponsesStream:
    def test_websearch_stream_serializes_reasoning_search_and_message(self):
        events = parse_sse_events(TEST_DATA / "responses-api-stream-o3-websearch.txt")
        output, metadata = replay_stream(events)
        html = serialize_output(output)

        assert metadata.get("done") is True, "stream should complete"
        assert '<details type="reasoning"' in html, "expect reasoning details"
        assert '<details type="web_search"' in html, "expect web search details"
        assert (
            html.rstrip().split("</details>")[-1].strip()
        ), "expect message text after details blocks"

    def test_reasoning_durations_are_per_block_not_cumulative(self):
        """
        Each reasoning block's duration should reflect only that block's time,
        not wall-clock from its start to end of entire response.

        Bug: all durations computed as (now - started_at) at response.completed,
        so they share the same end time and monotonically decrease. The first
        block's "duration" equals total response time.
        """
        events = parse_sse_events(TEST_DATA / "responses-api-stream-o3-websearch.txt")
        output, _ = replay_stream(events)

        reasoning_items = [i for i in output if i["type"] == "reasoning"]
        durations = [i.get("duration", 0) for i in reasoning_items]

        assert len(durations) > 1, "need multiple reasoning blocks to test"
        # replay_stream sleeps 0.1s before each reasoning block, so each
        # block's duration should be ~0.1s (time until next item arrives).
        # The bug computed all as (now - started_at) at response.completed,
        # making the first ~1.2s and the last ~0s.
        max_expected = SIMULATED_REASONING_DELAY * 2
        for i, d in enumerate(durations):
            assert d < max_expected, (
                f"reasoning block {i} duration {d:.3f}s > {max_expected}s — "
                "duration covers more than its own block"
            )
