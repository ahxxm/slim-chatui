import json
import logging
import sys
from typing import TYPE_CHECKING

from loguru import logger
from open_webui.env import (
    GLOBAL_LOG_LEVEL,
    LOG_FORMAT,
    _LEVEL_MAP,
)

if TYPE_CHECKING:
    from loguru import Message, Record


def stdout_format(record: "Record") -> str:
    """
    Generates a formatted string for log records that are output to the console. This format includes a timestamp, log level, source location (module, function, and line), the log message, and any extra data (serialized as JSON).

    Parameters:
    record (Record): A Loguru record that contains logging details including time, level, name, function, line, message, and any extra context.
    Returns:
    str: A formatted log string intended for stdout.
    """
    if record["extra"]:
        record["extra"]["extra_json"] = json.dumps(record["extra"])
        extra_format = " - {extra[extra_json]}"
    else:
        extra_format = ""
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>" + extra_format + "\n{exception}"
    )


def _json_sink(message: "Message") -> None:
    """Write log records as single-line JSON to stdout.

    Used as a Loguru sink when LOG_FORMAT is set to "json".
    """
    record = message.record
    log_entry = {
        "ts": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "level": _LEVEL_MAP.get(record["level"].name, record["level"].name.lower()),
        "msg": record["message"],
        "caller": f"{record['name']}:{record['function']}:{record['line']}",
    }

    if record["extra"]:
        log_entry["extra"] = record["extra"]

    if record["exception"] is not None:
        log_entry["error"] = "".join(record["exception"].format_exception()).rstrip()

    sys.stdout.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


class InterceptHandler(logging.Handler):
    """
    Intercepts log records from Python's standard logging module
    and redirects them to Loguru's logger.
    """

    def emit(self, record):
        """
        Called by the standard logging module for each log event.
        It transforms the standard `LogRecord` into a format compatible with Loguru
        and passes it to Loguru's logger.
        """
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def configure_logging():
    """Routes all stdlib and uvicorn logging through loguru."""
    logger.remove()

    if LOG_FORMAT == "json":
        logger.add(
            _json_sink,
            level=GLOBAL_LOG_LEVEL,
        )
    else:
        logger.add(
            sys.stdout,
            level=GLOBAL_LOG_LEVEL,
            format=stdout_format,
        )

    logging.basicConfig(
        handlers=[InterceptHandler()], level=GLOBAL_LOG_LEVEL, force=True
    )

    for uvicorn_logger_name in ["uvicorn", "uvicorn.error"]:
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        uvicorn_logger.setLevel(GLOBAL_LOG_LEVEL)
        uvicorn_logger.handlers = []

    logger.info(f"GLOBAL_LOG_LEVEL: {GLOBAL_LOG_LEVEL}")
