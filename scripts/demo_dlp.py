import argparse
import asyncio
import json

import websockets


CASES = [
    {
        "name": "Safe unrelated message",
        "message": "Hello everyone, how are you today?",
        "expected": "MESSAGE_ACCEPTED",
    },
    {
        "name": "Exact protected fragment",
        "message": "Add 7 grams of dry yeast and 10 grams of fine salt",
        "expected": "DLP_PROTECTED_CONTENT",
    },
    {
        "name": "Different uppercase/lowercase",
        "message": "ADD 7 GRAMS OF DRY YEAST AND 10 GRAMS OF FINE SALT",
        "expected": "DLP_PROTECTED_CONTENT",
    },
    {
        "name": "Extra whitespace",
        "message": "Add    7 grams   of dry yeast    and 10 grams of fine salt",
        "expected": "DLP_PROTECTED_CONTENT",
    },
    {
        "name": "Punctuation spacing variation",
        "message": "Knead the dough for 10 minutes , then let it rise for 90 minutes",
        "expected": "DLP_PROTECTED_CONTENT",
    },
    {
        "name": "Exact temperature fragment",
        "message": "Preheat the oven to 250 degrees Celsius",
        "expected": "DLP_PROTECTED_CONTENT",
    },

    # Current known limitations:
    {
        "name": "Paraphrase - current DLP limitation",
        "message": "Use half a kilo of bread flour together with about 325 ml of warm water",
        "expected": "MESSAGE_ACCEPTED",
    },
    {
        "name": "Changed protected quantity",
        "message": "Add 8 grams of dry yeast and 10 grams of fine salt",
        "expected": "MESSAGE_ACCEPTED",
    },
    {
        "name": "Only a small protected phrase",
        "message": "dry yeast",
        "expected": "MESSAGE_ACCEPTED",
    },
    {
        "name": "Obfuscated / leetspeak",
        "message": "Add 7 gr4ms of dry y.e.a.s.t and 10 grams of fine salt",
        "expected": "MESSAGE_ACCEPTED",
    },
    {
        "name": "Split leakage part 1 - current context limitation",
        "message": "Add 7 grams of dry yeast",
        "expected": "MESSAGE_ACCEPTED",
    },
    {
        "name": "Split leakage part 2 - current context limitation",
        "message": "and 10 grams of fine salt",
        "expected": "MESSAGE_ACCEPTED",
    },
]


async def receive_until_response(ws, request_id, sent_message):
    broadcast_seen = False

    while True:
        raw = await ws.recv()
        incoming = json.loads(raw)

        if incoming.get("type") == "event":
            payload = incoming.get("payload", {})

            if payload.get("message") == sent_message:
                broadcast_seen = True

            continue

        if (
            incoming.get("type") == "response"
            and incoming.get("request_id") == request_id
        ):
            return incoming, broadcast_seen


async def main():
    parser = argparse.ArgumentParser(
        description="Real end-to-end DLP demo against the running chat server"
    )
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("room_id", type=int)

    parser.add_argument(
        "--url",
        default="ws://127.0.0.1:8765/ws",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=1.3,
        help="Delay between messages so Anti-Bot doesn't interfere",
    )

    args = parser.parse_args()

    print(f"\nConnecting to {args.url}")

    async with websockets.connect(args.url) as ws:

        # ------------------------------------
        # LOGIN
        # ------------------------------------
        login_id = "dlp-login"

        login_request = {
            "type": "request",
            "request_id": login_id,
            "action": "login",
            "payload": {
                "username": args.username,
                "password": args.password,
            },
        }

        await ws.send(json.dumps(login_request))

        login_response, _ = await receive_until_response(
            ws,
            login_id,
            "",
        )

        print(
            "LOGIN:",
            login_response.get("status"),
            login_response.get("code"),
        )

        if login_response.get("status") != "ok":
            print("Login failed. Stop.")
            return

        # Clear any old Anti-Bot timestamps.
        print("Waiting for Anti-Bot window to clear...")
        await asyncio.sleep(5.5)

        print("\n===== REAL DLP INTEGRATION DEMO =====\n")

        passed = 0

        for index, case in enumerate(CASES, start=1):

            request_id = f"dlp-{index}"

            request = {
                "type": "request",
                "request_id": request_id,
                "action": "send_message",
                "payload": {
                    "room_id": args.room_id,
                    "message": case["message"],
                },
            }

            print(f"[{index}] {case['name']}")
            print(f"    SEND: {case['message']}")

            await ws.send(json.dumps(request))

            response, broadcast_seen = await receive_until_response(
                ws,
                request_id,
                case["message"],
            )

            actual = response.get("code")
            expected = case["expected"]

            success = actual == expected

            if success:
                passed += 1

            print(f"    EXPECTED: {expected}")
            print(f"    ACTUAL:   {actual}")

            if actual == "DLP_PROTECTED_CONTENT":
                print(f"    BROADCAST: {'ERROR - seen' if broadcast_seen else 'NO ✓'}")
            else:
                print(f"    BROADCAST: {'YES ✓' if broadcast_seen else 'NOT SEEN'}")

            print(f"    RESULT: {'PASS ✓' if success else 'CHECK ✗'}")
            print()

            # Keep Anti-Bot out of this DLP test.
            await asyncio.sleep(args.delay)

        print("====================================")
        print(f"Passed expected behavior: {passed}/{len(CASES)}")

        if passed == len(CASES):
            print("PASS: Current DLP behavior matches expectations.")
        else:
            print("Some results differ. Inspect them before changing code.")


if __name__ == "__main__":
    asyncio.run(main())
