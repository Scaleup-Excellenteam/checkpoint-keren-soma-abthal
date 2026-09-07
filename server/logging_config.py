import json
import logging
import os
import re


LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_SIMPLE_VALUE = re.compile(r"^[A-Za-z0-9_.:@/+-]+$")

THIRD_PARTY_LOGGERS = (
    "httpx",
    "httpcore",
    "huggingface_hub",
    "transformers",
    "sentence_transformers",
    "urllib3",
    "websockets",
)


def configure_logging(level=logging.INFO):
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )
    for logger_name in THIRD_PARTY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def log_event(logger, level, event, *, exc_info=False, **fields):
    parts = [f"event={event}"]
    for key, value in fields.items():
        if value is not None:
            parts.append(f"{key}={_format_value(value)}")

    logger.log(level, " ".join(parts), exc_info=exc_info)


def connection_fields(websocket):
    remote_address = getattr(websocket, "remote_address", None)
    if not remote_address:
        return {}

    if isinstance(remote_address, tuple):
        fields = {"remote_host": remote_address[0]}
        if len(remote_address) > 1:
            fields["remote_port"] = remote_address[1]
        return fields

    return {"remote_address": remote_address}


def _format_value(value):
    if isinstance(value, bool):
        return str(value).lower()

    text = str(value)
    if _SIMPLE_VALUE.fullmatch(text):
        return text

    return json.dumps(text, ensure_ascii=True)
