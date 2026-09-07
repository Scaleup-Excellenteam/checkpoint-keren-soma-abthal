import asyncio

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from protocol import build_request, encode, parse_json

SERVER_URL = "ws://localhost:8765/ws"
PROMPT = "> "

COMMAND_USAGE = (
    "commands: login <username> | create <room> | join <id> | list | send <id> <message>"
)


def parse_command(line):
    stripped = line.strip()
    if not stripped:
        return None

    parts = stripped.split()
    command = parts[0]

    if command == "login" and len(parts) == 2:
        return "login", {"username": parts[1]}
    if command == "create" and len(parts) == 2:
        return "create_room", {"name": parts[1]}
    if command == "join" and len(parts) == 2:
        return "join_room", {"room_id": parts[1]}
    if command == "list" and len(parts) == 1:
        return "list_rooms", {}
    if command == "send" and len(parts) >= 3:
        room_id = parts[1]
        message = stripped.split(None, 2)[2]
        return "send_message", {"room_id": room_id, "message": message}

    return None


def display_server_message(text):
    data = parse_json(text)
    if data is None:
        print(text, flush=True)
        return
    if data.get("type") == "response":
        status = data.get("status")
        code = data.get("code")
        message = data.get("message")
        if message:
            print(f"{status}: {code} ({message})", flush=True)
        else:
            print(f"{status}: {code}", flush=True)
        return
    if data.get("type") == "event":
        payload = data.get("payload") or {}
        print(payload.get("message", text), flush=True)
        return
    print(text, flush=True)


async def read_keyboard(websocket):
    request_id = 1
    while True:
        try:
            line = await asyncio.to_thread(input, PROMPT)
        except EOFError:
            break

        parsed = parse_command(line)
        if parsed is None:
            if line.strip():
                print(COMMAND_USAGE, flush=True)
            continue

        action, payload = parsed
        request = build_request(request_id, action, payload)
        request_id += 1
        await websocket.send(encode(request))


async def read_server(websocket):
    try:
        async for message in websocket:
            display_server_message(message)
    except ConnectionClosed:
        print("disconnected", flush=True)


async def main():
    async with connect(SERVER_URL) as websocket:
        keyboard_task = asyncio.create_task(read_keyboard(websocket))
        server_task = asyncio.create_task(read_server(websocket))
        done, pending = await asyncio.wait(
            {keyboard_task, server_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()


if __name__ == "__main__":
    asyncio.run(main())
