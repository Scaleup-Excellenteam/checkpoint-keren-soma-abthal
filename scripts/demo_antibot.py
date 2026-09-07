import argparse
import asyncio
import json

import websockets


async def wait_for_response(ws, request_id):
    """Read messages until we get the response for request_id."""
    while True:
        raw = await ws.recv()
        message = json.loads(raw)

        if message.get("type") == "event":
            payload = message.get("payload", {})
            print(
                f"  EVENT: {message.get('event')} "
                f"message={payload.get('message')!r}"
            )
            continue

        if (
            message.get("type") == "response"
            and message.get("request_id") == request_id
        ):
            return message

        print("  OTHER:", message)


async def main():
    parser = argparse.ArgumentParser(
        description="Demo the Day 2 Anti-Bot rate limiter"
    )
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("room_id", type=int)
    parser.add_argument(
        "--url",
        default="ws://127.0.0.1:8765/ws",
        help="WebSocket server URL",
    )
    args = parser.parse_args()

    print(f"Connecting to {args.url}")

    async with websockets.connect(args.url) as ws:
        # -----------------------------------------------------
        # 1. LOGIN
        # -----------------------------------------------------
        login_request = {
            "type": "request",
            "request_id": "login-1",
            "action": "login",
            "payload": {
                "username": args.username,
                "password": args.password,
            },
        }

        await ws.send(json.dumps(login_request))

        login_response = await wait_for_response(ws, "login-1")

        print(
            "LOGIN:",
            login_response.get("status"),
            login_response.get("code"),
        )

        if login_response.get("status") != "ok":
            print("Login failed. Stopping demo.")
            return

        # -----------------------------------------------------
        # 2. SEND SIX MESSAGES IMMEDIATELY
        # -----------------------------------------------------
        print()
        print("Sending 6 messages as fast as possible...")
        print()

        request_ids = []

        for i in range(1, 7):
            request_id = f"burst-{i}"
            request_ids.append(request_id)

            request = {
                "type": "request",
                "request_id": request_id,
                "action": "send_message",
                "payload": {
                    "room_id": args.room_id,
                    "message": f"burst-message-{i}",
                },
            }

            await ws.send(json.dumps(request))
            print(f"SENT message {i}")

        # -----------------------------------------------------
        # 3. RECEIVE ALL RESULTS
        # -----------------------------------------------------
        results = {}

        while len(results) < 6:
            raw = await ws.recv()
            message = json.loads(raw)

            if message.get("type") == "event":
                payload = message.get("payload", {})
                print(
                    f"  BROADCAST EVENT: "
                    f"{payload.get('message')!r}"
                )
                continue

            if message.get("type") != "response":
                print("  OTHER:", message)
                continue

            request_id = message.get("request_id")

            if request_id not in request_ids:
                print("  OTHER RESPONSE:", message)
                continue

            results[request_id] = message

            print(
                f"{request_id}: "
                f"status={message.get('status')} "
                f"code={message.get('code')}"
            )

        # -----------------------------------------------------
        # 4. SUMMARY
        # -----------------------------------------------------
        allowed = [
            r for r in results.values()
            if r.get("code") == "MESSAGE_ACCEPTED"
        ]

        blocked = [
            r for r in results.values()
            if r.get("code") == "ANTIBOT_RATE_LIMIT"
        ]

        print()
        print("===== ANTI-BOT DEMO SUMMARY =====")
        print(f"Allowed messages: {len(allowed)}")
        print(f"Blocked messages: {len(blocked)}")

        if len(allowed) == 5 and len(blocked) == 1:
            print("PASS: Anti-Bot rate limiting worked.")
        else:
            print("CHECK: Results differed from expected 5 ALLOW + 1 BLOCK.")


if __name__ == "__main__":
    asyncio.run(main())
