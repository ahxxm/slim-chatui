# Zstd HTTP compression using Python 3.14's built-in compression.zstd.
#
# Mirrors starlette.middleware.gzip: IdentityResponder handles all ASGI
# plumbing (deferred headers, Vary, Content-Length, minimum-size skip).
# ZstdResponder only provides the compression algorithm and content-encoding.

from compression.zstd import ZstdCompressor

from starlette.datastructures import Headers
from starlette.middleware.gzip import IdentityResponder
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class ZstdMiddleware:
    def __init__(self, app: ASGIApp, minimum_size: int = 500, level: int = 3) -> None:
        self.app = app
        self.minimum_size = minimum_size
        self.level = level

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        accept = Headers(scope=scope).get("Accept-Encoding", "")
        if "zstd" in accept:
            responder = ZstdResponder(self.app, self.minimum_size, level=self.level)
        else:
            responder = IdentityResponder(self.app, self.minimum_size)
        await responder(scope, receive, send)


class ZstdResponder(IdentityResponder):
    content_encoding = "zstd"

    def __init__(self, app: ASGIApp, minimum_size: int, level: int = 3) -> None:
        super().__init__(app, minimum_size)
        self.compressor = ZstdCompressor(level=level)
        self.below_minimum = False

    async def send_with_compression(self, message: Message) -> None:
        # Early-out for small responses: base class checks body size after
        # buffering the first chunk; this checks Content-Length before any
        # body arrives, bypassing compression setup entirely.
        if message["type"] == "http.response.start":
            cl = Headers(raw=message["headers"]).get("content-length")
            if cl is not None and int(cl) < self.minimum_size:
                self.below_minimum = True

        if self.below_minimum:
            await self.send(message)
        else:
            await super().send_with_compression(message)

    def apply_compression(self, body: bytes, *, more_body: bool) -> bytes:
        out = self.compressor.compress(body)
        # FLUSH_BLOCK: emit a decodable block so the client can decompress
        # incrementally (SSE / streaming chat). FLUSH_FRAME: close the
        # frame on the final chunk.
        if more_body:
            out += self.compressor.flush(ZstdCompressor.FLUSH_BLOCK)
        else:
            out += self.compressor.flush(ZstdCompressor.FLUSH_FRAME)
        return out
