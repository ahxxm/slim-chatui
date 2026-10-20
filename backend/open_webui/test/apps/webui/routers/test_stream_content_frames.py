"""Replay captured SSE through the streaming handler and the real chat store."""

import asyncio
import json

from starlette.requests import Request

from open_webui.models.chats import Chats
from open_webui.utils.middleware import streaming_chat_response_handler
from test.util.abstract_integration_test import IntegrationTest
from test.util.stream_fixtures import TEST_DATA, parse_sse_events


class ReplayResponse:
    background = None

    def __init__(self, events: list[dict]):
        self.body_iterator = self._body(events)

    @staticmethod
    async def _body(events: list[dict]):
        for event in events:
            yield f"data: {json.dumps(event)}\n".encode()
        yield b"data: [DONE]\n"


def completion_frames(emitted: list[dict]) -> list[dict]:
    return [event["data"] for event in emitted if event["type"] == "chat:completion"]


def reassemble(frames: list[dict]) -> tuple[str, int]:
    content = ""
    snapshots = 0

    for frame in frames:
        if frame.get("done"):
            content = frame["content"]
        elif "content" in frame:
            content = frame["content"]
            snapshots += 1
        elif "content_delta" in frame:
            at = frame["offset"]
            content = content[:at] + frame["content_delta"] + content[at:]

    return content, snapshots


class TestStreamingHandler(IntegrationTest):
    def seed_assistant_message(self) -> tuple[str, str, dict]:
        user, headers = self.sign_up()
        chat = self.create_chat(
            headers,
            chat=self.chat_with_message("hi", msg_id="user-1", role="user"),
        )
        message_id = "msg-1"
        Chats.upsert_message_to_chat_by_id_and_message_id(
            chat["id"],
            message_id,
            {
                "id": message_id,
                "parentId": "user-1",
                "role": "assistant",
                "model": "test-model",
                "content": "",
                "childrenIds": [],
            },
        )
        return chat["id"], message_id, user

    def run_handler(
        self, chat_id: str, message_id: str, user: dict, events: list[dict]
    ):
        emitted: list[dict] = []

        async def event_emitter(event: dict) -> None:
            emitted.append(event)

        ctx = {
            "event_emitter": event_emitter,
            "metadata": {"chat_id": chat_id, "message_id": message_id},
            "form_data": {"messages": [{"role": "user", "content": "hi"}]},
            "request": Request(
                {"type": "http", "method": "POST", "path": "/", "headers": []}
            ),
            "user": user,
            "tasks": {},
        }

        asyncio.run(streaming_chat_response_handler(ReplayResponse(events), ctx))
        return emitted

    def test_responses_stream_emits_frames_and_persists(self):
        chat_id, message_id, user = self.seed_assistant_message()
        events = parse_sse_events(TEST_DATA / "responses-api-stream-o3-websearch.txt")

        frames = completion_frames(self.run_handler(chat_id, message_id, user, events))
        content, snapshots = reassemble(frames)
        done = frames[-1]

        assert done["done"] is True
        assert done["content"] == content
        assert done["output"]
        assert snapshots > 0, "rewrites in this capture must carry a snapshot"
        assert snapshots < len(frames) / 2, "most frames should be deltas"
        assert all("output" not in frame for frame in frames[:-1])
        assert any("usage" in frame for frame in frames)

        saved = Chats.get_message_by_id_and_message_id(chat_id, message_id)
        assert saved["content"] == content
        assert saved["output"] == done["output"]

    def test_interleaved_reasoning_search_and_updates_stream_incrementally(self):
        chat_id, message_id, user = self.seed_assistant_message()
        events = parse_sse_events(
            TEST_DATA / "responses-api-stream-deepseek-interleaved.txt"
        )

        frames = completion_frames(self.run_handler(chat_id, message_id, user, events))
        content, snapshots = reassemble(frames)
        done = frames[-1]
        deltas = "".join(frame.get("content_delta", "") for frame in frames)

        for text in (
            "We need to answer user in Chinese",
            "氣溫約 28–32°C，降雨機率約 62%",
            "已完成兩次搜尋",
        ):
            assert text in deltas, f"{text!r} must stream as a delta"

        ordered = (
            "We need to answer user in Chinese",
            "香港 天气 今天",
            "Now we need reply one sentence about HK weather",
            "氣溫約 28–32°C，降雨機率約 62%",
            "Texas weather today forecast",
            "Now final reply in Chinese, summarizing both",
            "已完成兩次搜尋",
        )
        positions = [content.index(text) for text in ordered]
        assert positions == sorted(positions), "blocks must keep output order"

        assert done["content"] == content
        assert snapshots < 10
        assert all("output" not in frame for frame in frames[:-1])

        saved = Chats.get_message_by_id_and_message_id(chat_id, message_id)
        assert saved["content"] == content

    def test_gpt6_stream_keeps_output_when_completed_is_empty(self):
        chat_id, message_id, user = self.seed_assistant_message()
        events = parse_sse_events(
            TEST_DATA / "responses-api-stream-gpt6-interleaved.txt"
        )

        frames = completion_frames(self.run_handler(chat_id, message_id, user, events))
        content, snapshots = reassemble(frames)
        done = frames[-1]
        deltas = "".join(frame.get("content_delta", "") for frame in frames)

        for text in ("香港天气。", "已完成：搜索香港天气"):
            assert text in deltas, f"{text!r} must stream as a delta"

        ordered = (
            "香港 天气 今天",
            "**Responding to weather request**",
            "香港天气。",
            "德州 天气 今天",
            "已完成：搜索香港天气",
        )
        positions = [content.index(text) for text in ordered]
        assert positions == sorted(positions), "blocks must keep output order"

        assert done["content"] == content
        assert snapshots < 10
        assert all("output" not in frame for frame in frames[:-1])

        saved = Chats.get_message_by_id_and_message_id(chat_id, message_id)
        assert saved["content"] == content

    def test_chat_completions_stream_emits_deltas_and_persists(self):
        chat_id, message_id, user = self.seed_assistant_message()
        events = [
            {"choices": [{"delta": {"role": "assistant"}}]},
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [{"delta": {"content": " world"}}]},
            {"choices": [{"delta": {"content": "!"}}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
            {"usage": {"prompt_tokens": 3, "completion_tokens": 3}},
        ]

        frames = completion_frames(self.run_handler(chat_id, message_id, user, events))
        content, snapshots = reassemble(frames)
        done = frames[-1]

        assert content == "Hello world!"
        assert done["done"] is True
        assert done["content"] == content
        assert snapshots == 0, "append-only content must not send snapshots"
        assert all("output" not in frame for frame in frames[:-1])
        assert any("usage" in frame for frame in frames)

        saved = Chats.get_message_by_id_and_message_id(chat_id, message_id)
        assert saved["content"] == content
        assert saved["output"] == done["output"]
