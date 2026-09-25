"""Small local HTTP transport for Kaapi's public analysis facade."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import Body, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from . import ConfigError, PolicyError, analyze_text


MAX_REQUEST_BYTES = 1024 * 1024
_REQUEST_FIELDS = {"runtime", "config", "policy", "source"}
_ERROR_MESSAGES = {
    "invalid_request": "The request body is invalid.",
    "invalid_configuration": "The configuration input is invalid.",
    "invalid_policy": "The policy input is invalid.",
    "request_too_large": "The request body exceeds the maximum allowed size.",
    "internal_error": "The analysis service could not complete the request.",
}


def _error_response(status_code: int, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": _ERROR_MESSAGES[code]}},
    )


async def _send_error(
    scope: Scope,
    receive: Receive,
    send: Send,
    status_code: int,
    code: str,
) -> None:
    await _error_response(status_code, code)(scope, receive, send)


class RequestSizeLimitMiddleware:
    """Reject oversized bodies before FastAPI parses attacker-controlled JSON."""

    def __init__(self, app: Callable[..., Awaitable[None]], max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = next(
            (
                value
                for key, value in scope.get("headers", [])
                if key.lower() == b"content-length"
            ),
            None,
        )
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                await _send_error(scope, receive, send, 400, "invalid_request")
                return
            if declared_length < 0:
                await _send_error(scope, receive, send, 400, "invalid_request")
                return
            if declared_length > self.max_bytes:
                await _send_error(scope, receive, send, 413, "request_too_large")
                return

        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body = message.get("body", b"")
            total += len(body)
            if total > self.max_bytes:
                await _send_error(scope, receive, send, 413, "request_too_large")
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        replayed = False

        async def replay() -> dict[str, Any]:
            nonlocal replayed
            if replayed:
                return {"type": "http.disconnect"}
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)


app = FastAPI(
    title="Kaapi local analysis API",
    version="v1",
    docs_url=None,
    redoc_url=None,
)
app.add_middleware(RequestSizeLimitMiddleware, max_bytes=MAX_REQUEST_BYTES)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(_, __) -> JSONResponse:
    return _error_response(400, "invalid_request")


@app.exception_handler(Exception)
async def internal_error_handler(_, __) -> JSONResponse:
    return _error_response(500, "internal_error")


def _valid_policy_shape(value: Any) -> bool:
    if value is None or isinstance(value, (str, dict)):
        return True
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, (str, dict)) for item in value
    )


@app.post("/v1/analyze")
def analyze_endpoint(payload: Any = Body(...)) -> JSONResponse:
    """Analyze one supported configuration and return Kaapi's document unchanged."""
    if not isinstance(payload, dict) or set(payload) - _REQUEST_FIELDS:
        return _error_response(400, "invalid_request")

    runtime = payload.get("runtime")
    config = payload.get("config")
    policy = payload.get("policy")
    source = payload.get("source")
    if runtime not in {"claude-code", "codex"}:
        return _error_response(400, "invalid_request")
    if not isinstance(config, str) or not config.strip():
        return _error_response(400, "invalid_request")
    if source is not None and (
        not isinstance(source, str) or not source or len(source) > 256
    ):
        return _error_response(400, "invalid_request")
    if not _valid_policy_shape(policy):
        return _error_response(400, "invalid_request")

    try:
        document = analyze_text(
            config,
            runtime=runtime,
            source=source,
            policy=policy,
        )
    except ConfigError:
        return _error_response(400, "invalid_configuration")
    except PolicyError:
        return _error_response(400, "invalid_policy")
    except (TypeError, ValueError):
        return _error_response(400, "invalid_request")
    return JSONResponse(status_code=200, content=document)


def main() -> None:
    import uvicorn

    uvicorn.run("kaapi.http_api:app", host="127.0.0.1", port=8000)


__all__ = ["MAX_REQUEST_BYTES", "app", "main"]
