import asyncio
import logging

from websockets.asyncio.server import serve

from .client_session import ClientSession, handle_disconnect, handle_request
from .logging_config import configure_logging, connection_fields, log_event
from .protocol import (
    CODE_INVALID_JSON,
    CODE_UNKNOWN_ACTION,
    KNOWN_ACTIONS,
    build_error,
    encode,
    parse_json,
    validate_request,
)

HOST = "0.0.0.0"
PORT = 8765
WEBSOCKET_PATH = "/ws"

logger = logging.getLogger(__name__)


async def reply_for_message(session, text):
    data = parse_json(text)
    if data is None:
        log_event(
            logger,
            logging.WARNING,
            "VALIDATION_FAILED",
            username=session.username,
            user_id=session.user_id,
            reason_code=CODE_INVALID_JSON,
        )
        return build_error("", CODE_INVALID_JSON, "Invalid JSON")

    request, error_code = validate_request(data)
    request_id = data.get("request_id", "") if isinstance(data, dict) else ""
    if error_code:
        log_event(
            logger,
            logging.WARNING,
            "VALIDATION_FAILED",
            username=session.username,
            user_id=session.user_id,
            reason_code=error_code,
        )
        return build_error(request_id, error_code, "Invalid request")

    action = request["action"]
    log_event(
        logger,
        logging.INFO,
        "REQUEST_RECEIVED",
        username=session.username,
        user_id=session.user_id,
        action=action,
    )
    if action not in KNOWN_ACTIONS:
        log_event(
            logger,
            logging.WARNING,
            "INVALID_REQUEST",
            username=session.username,
            user_id=session.user_id,
            action=action,
            reason_code=CODE_UNKNOWN_ACTION,
        )
        return build_error(request["request_id"], CODE_UNKNOWN_ACTION, "Unknown action")

    return await handle_request(session, request)


async def handle_client(websocket):
    if websocket.request.path != WEBSOCKET_PATH:
        await websocket.close()
        return

    session = ClientSession(websocket)
    log_event(
        logger,
        logging.INFO,
        "CLIENT_CONNECTED",
        **connection_fields(websocket),
    )
    try:
        async for message in session.websocket:
            await session.websocket.send(encode(await reply_for_message(session, message)))
    except Exception:
        log_event(
            logger,
            logging.ERROR,
            "INTERNAL_ERROR",
            exc_info=True,
            username=session.username,
            user_id=session.user_id,
            reason_code="CLIENT_HANDLER_FAILED",
            **connection_fields(websocket),
        )
        raise
    finally:
        handle_disconnect(session)


async def main():
    configure_logging()
    async with serve(handle_client, HOST, PORT) as server:
        log_event(
            logger,
            logging.INFO,
            "SERVER_STARTED",
            host=HOST,
            port=PORT,
            path=WEBSOCKET_PATH,
        )
        try:
            await server.serve_forever()
        finally:
            log_event(logger, logging.INFO, "SERVER_STOPPED")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
