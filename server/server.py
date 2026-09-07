import asyncio

from websockets.asyncio.server import serve

from client_session import ClientSession, handle_disconnect, handle_request
from protocol import (
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


async def reply_for_message(session, text):
    data = parse_json(text)
    if data is None:
        print("VALIDATION_FAILED", CODE_INVALID_JSON, flush=True)
        return build_error("", CODE_INVALID_JSON, "Invalid JSON")

    request, error_code = validate_request(data)
    request_id = data.get("request_id", "") if isinstance(data, dict) else ""
    if error_code:
        print("VALIDATION_FAILED", error_code, flush=True)
        return build_error(request_id, error_code, "Invalid request")

    action = request["action"]
    print("REQUEST_RECEIVED", action, flush=True)
    if action not in KNOWN_ACTIONS:
        return build_error(request["request_id"], CODE_UNKNOWN_ACTION, "Unknown action")

    return await handle_request(session, request)


async def handle_client(websocket):
    if websocket.request.path != WEBSOCKET_PATH:
        await websocket.close()
        return

    session = ClientSession(websocket)
    print("CLIENT_CONNECTED", flush=True)
    try:
        async for message in session.websocket:
            await session.websocket.send(encode(await reply_for_message(session, message)))
    finally:
        handle_disconnect(session)


async def main():
    print("SERVER_STARTED", flush=True)
    async with serve(handle_client, HOST, PORT) as server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
