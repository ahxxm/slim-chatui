import inspect
import logging
from functools import wraps

from fastapi import HTTPException

log = logging.getLogger(__name__)


def route_error_handler(
    *, detail: str = "Something went wrong", status_code: int = 400
):
    """Decorator that catches non-HTTP exceptions, logs them, and raises HTTPException.

    HTTPException passes through untouched so intentional error responses are preserved.
    Handles both sync and async route handlers.
    """

    def decorator(fn):
        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def wrapper(*args, **kwargs):
                try:
                    return await fn(*args, **kwargs)
                except HTTPException:
                    raise
                except Exception as e:
                    log.exception(e)
                    raise HTTPException(status_code=status_code, detail=detail)

            return wrapper
        else:

            @wraps(fn)
            def wrapper(*args, **kwargs):
                try:
                    return fn(*args, **kwargs)
                except HTTPException:
                    raise
                except Exception as e:
                    log.exception(e)
                    raise HTTPException(status_code=status_code, detail=detail)

            return wrapper

    return decorator
