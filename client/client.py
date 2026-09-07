# import asyncio
# import sys
# from pathlib import Path

# from websockets.asyncio.client import connect
# from websockets.exceptions import ConnectionClosed

# sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
# from protocol import build_request, encode, parse_json

# SERVER_URL = "ws://localhost:8765/ws"
# PROMPT = "> "

# COMMAND_USAGE = (
#     "commands: login <username> | create <room> | join <id> | list | send <id> <message>"
# )


# def parse_command(line):
#     stripped = line.strip()
#     if not stripped:
#         return None

#     parts = stripped.split()
#     command = parts[0]

#     if command == "login" and len(parts) == 2:
#         return "login", {"username": parts[1]}
#     if command == "create" and len(parts) == 2:
#         return "create_room", {"name": parts[1]}
#     if command == "join" and len(parts) == 2:
#         return "join_room", {"room_id": parts[1]}
#     if command == "list" and len(parts) == 1:
#         return "list_rooms", {}
#     if command == "send" and len(parts) >= 3:
#         room_id = parts[1]
#         message = stripped.split(None, 2)[2]
#         return "send_message", {"room_id": room_id, "message": message}

#     return None


# def display_server_message(text):
#     data = parse_json(text)
#     if data is None:
#         print(text, flush=True)
#         return
#     if data.get("type") == "response":
#         status = data.get("status")
#         code = data.get("code")
#         message = data.get("message")
#         payload = data.get("payload") or {}
#         if message:
#             print(f"{status}: {code} ({message})", flush=True)
#         else:
#             print(f"{status}: {code}", flush=True)
#         if code == "LOGIN_SUCCESS":
#             print(f"  user_id={payload.get('user_id')} username={payload.get('username')}", flush=True)
#         elif code == "ROOM_CREATED" or code == "ROOM_JOINED":
#             print(f"  room_id={payload.get('room_id')} name={payload.get('name')}", flush=True)
#         elif code == "ROOM_LIST":
#             rooms = payload.get("rooms") or []
#             if not rooms:
#                 print("  (no rooms)", flush=True)
#             for room in rooms:
#                 membership = "member" if room.get("member") else "not member"
#                 print(
#                     f"  [{room.get('room_id')}] {room.get('name')} ({membership})",
#                     flush=True,
#                 )
#         return
#     if data.get("type") == "event":
#         payload = data.get("payload") or {}
#         username = payload.get("sender_username", "?")
#         room_name = payload.get("room_name", "?")
#         chat_text = payload.get("message", "")
#         print(f"[{username} @ {room_name}]: {chat_text}", flush=True)
#         return
#     print(text, flush=True)


# async def read_keyboard(websocket):
#     request_id = 1
#     while True:
#         try:
#             line = await asyncio.to_thread(input, PROMPT)
#         except EOFError:
#             break

#         parsed = parse_command(line)
#         if parsed is None:
#             if line.strip():
#                 print(COMMAND_USAGE, flush=True)
#             continue

#         action, payload = parsed
#         request = build_request(request_id, action, payload)
#         request_id += 1
#         await websocket.send(encode(request))


# async def read_server(websocket):
#     try:
#         async for message in websocket:
#             display_server_message(message)
#     except ConnectionClosed:
#         print("disconnected", flush=True)


# async def main():
#     async with connect(SERVER_URL) as websocket:
#         keyboard_task = asyncio.create_task(read_keyboard(websocket))
#         server_task = asyncio.create_task(read_server(websocket))
#         done, pending = await asyncio.wait(
#             {keyboard_task, server_task},
#             return_when=asyncio.FIRST_COMPLETED,
#         )
#         for task in pending:
#             task.cancel()
#         await asyncio.gather(*pending, return_exceptions=True)
#         for task in done:
#             task.result()


# if __name__ == "__main__":
#     asyncio.run(main())
import asyncio
import sys
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "server")
)

from protocol import build_request, encode, parse_json


SERVER_URL = "ws://localhost:8765/ws"

PROMPT = "> "

COMMAND_USAGE = (
    "commands:\n"
    "  signup <username> <password>\n"
    "  login <username> <password>\n"
    "  logout\n"
    "  create <room>\n"
    "  join <room_id>\n"
    "  leave <room_id>\n"
    "  list\n"
    "  send <room_id> <message>"
)


def parse_command(line):
    stripped = line.strip()

    if not stripped:
        return None

    parts = stripped.split()
    command = parts[0].lower()

    # signup username password
    if command == "signup" and len(parts) == 3:
        return (
            "signup",
            {
                "username": parts[1],
                "password": parts[2],
            },
        )

    # login username password
    if command == "login" and len(parts) == 3:
        return (
            "login",
            {
                "username": parts[1],
                "password": parts[2],
            },
        )

    if command == "logout" and len(parts) == 1:
        return "logout", {}

    if command == "create" and len(parts) >= 2:
        room_name = stripped.split(None, 1)[1]

        return (
            "create_room",
            {
                "name": room_name,
            },
        )

    if command == "join" and len(parts) == 2:
        return (
            "join_room",
            {
                "room_id": parts[1],
            },
        )

    if command == "leave" and len(parts) == 2:
        return (
            "leave_room",
            {
                "room_id": parts[1],
            },
        )

    if command == "list" and len(parts) == 1:
        return "list_rooms", {}

    if command == "send" and len(parts) >= 3:
        room_id = parts[1]

        message = stripped.split(
            None,
            2
        )[2]

        return (
            "send_message",
            {
                "room_id": room_id,
                "message": message,
            },
        )

    return None


def display_server_message(text):
    data = parse_json(text)

    if data is None:
        print(text, flush=True)
        return

    # ---------------------------------------
    # Normal response
    # ---------------------------------------

    if data.get("type") == "response":

        status = data.get("status")
        code = data.get("code")
        message = data.get("message")
        payload = data.get("payload") or {}

        if message:
            print(
                f"{status}: {code} ({message})",
                flush=True,
            )
        else:
            print(
                f"{status}: {code}",
                flush=True,
            )

        if code in {
            "SIGNUP_SUCCESS",
            "LOGIN_SUCCESS",
        }:
            print(
                f"  user_id={payload.get('user_id')} "
                f"username={payload.get('username')}",
                flush=True,
            )

        elif code in {
            "ROOM_CREATED",
            "ROOM_JOINED",
            "ROOM_LEFT",
        }:
            print(
                f"  room_id={payload.get('room_id')} "
                f"name={payload.get('name')}",
                flush=True,
            )

        elif code == "ROOM_LIST":

            rooms = payload.get("rooms") or []

            if not rooms:
                print(
                    "  (no rooms)",
                    flush=True,
                )

            for room in rooms:

                membership = (
                    "member"
                    if room.get("member")
                    else "not member"
                )

                print(
                    f"  [{room.get('room_id')}] "
                    f"{room.get('name')} "
                    f"({membership})",
                    flush=True,
                )

        return

    # ---------------------------------------
    # Real-time room event
    # ---------------------------------------

    if data.get("type") == "event":

        payload = data.get("payload") or {}

        username = payload.get(
            "sender_username",
            "?",
        )

        room_name = payload.get(
            "room_name",
            "?",
        )

        chat_text = payload.get(
            "message",
            "",
        )

        print(
            f"[{username} @ {room_name}]: "
            f"{chat_text}",
            flush=True,
        )

        return

    print(
        text,
        flush=True,
    )


async def read_keyboard(websocket):
    request_id = 1

    print(COMMAND_USAGE)

    while True:

        try:
            line = await asyncio.to_thread(
                input,
                PROMPT,
            )

        except EOFError:
            break

        parsed = parse_command(line)

        if parsed is None:

            if line.strip():
                print(
                    COMMAND_USAGE,
                    flush=True,
                )

            continue

        action, payload = parsed

        request = build_request(
            request_id,
            action,
            payload,
        )

        request_id += 1

        await websocket.send(
            encode(request)
        )


async def read_server(websocket):
    try:

        async for message in websocket:

            display_server_message(
                message
            )

    except ConnectionClosed:

        print(
            "disconnected",
            flush=True,
        )


async def main():

    print(
        f"Connecting to {SERVER_URL}..."
    )

    async with connect(
        SERVER_URL
    ) as websocket:

        print("Connected.")

        keyboard_task = asyncio.create_task(
            read_keyboard(websocket)
        )

        server_task = asyncio.create_task(
            read_server(websocket)
        )

        done, pending = await asyncio.wait(
            {
                keyboard_task,
                server_task,
            },
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        await asyncio.gather(
            *pending,
            return_exceptions=True,
        )

        for task in done:
            task.result()


if __name__ == "__main__":
    asyncio.run(main())