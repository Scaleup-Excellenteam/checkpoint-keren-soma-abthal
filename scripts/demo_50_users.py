import asyncio
import json
import time

import websockets


SERVER_URL = "ws://127.0.0.1:8765/ws"

NUM_USERS = 50

# Unique prefix so the script can be run again
RUN_ID = int(time.time())

PASSWORD = "DemoLoad123!"


async def request(ws, request_id, action, payload=None):
    message = {
        "type": "request",
        "request_id": request_id,
        "action": action,
        "payload": payload or {},
    }

    await ws.send(json.dumps(message))

    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=20)
        response = json.loads(raw)

        # Ignore unrelated events
        if (
            response.get("type") == "response"
            and response.get("request_id") == request_id
        ):
            return response


async def run_user(index):
    username = f"load_{RUN_ID}_{index:02d}"

    result = {
        "username": username,
        "connected": False,
        "signup": False,
        "login": False,
        "authenticated_request": False,
        "error": None,
    }

    try:
        async with websockets.connect(
            SERVER_URL,
            open_timeout=10,
        ) as ws:

            result["connected"] = True

            # -------------------------
            # SIGNUP
            # -------------------------
            signup_response = await request(
                ws,
                f"{username}-signup",
                "signup",
                {
                    "username": username,
                    "password": PASSWORD,
                },
            )

            if signup_response.get("status") != "ok":
                result["error"] = (
                    "signup failed: "
                    + str(signup_response.get("code"))
                )
                return result

            result["signup"] = True

            # -------------------------
            # LOGIN
            # -------------------------
            login_response = await request(
                ws,
                f"{username}-login",
                "login",
                {
                    "username": username,
                    "password": PASSWORD,
                },
            )

            if login_response.get("status") != "ok":
                result["error"] = (
                    "login failed: "
                    + str(login_response.get("code"))
                )
                return result

            result["login"] = True

            # -------------------------
            # AUTHENTICATED REQUEST
            # -------------------------
            rooms_response = await request(
                ws,
                f"{username}-rooms",
                "list_rooms",
                {},
            )

            if rooms_response.get("status") == "ok":
                result["authenticated_request"] = True
            else:
                result["error"] = (
                    "list_rooms failed: "
                    + str(rooms_response.get("code"))
                )

            # Keep all connections alive briefly
            await asyncio.sleep(2)

    except Exception as exc:
        result["error"] = str(exc)

    return result


async def main():
    print("=" * 55)
    print(f"50 USER CONCURRENCY TEST")
    print(f"Users: {NUM_USERS}")
    print(f"Server: {SERVER_URL}")
    print("=" * 55)

    start = time.perf_counter()

    # This starts all 50 clients concurrently.
    results = await asyncio.gather(
        *[
            run_user(i)
            for i in range(1, NUM_USERS + 1)
        ]
    )

    duration = time.perf_counter() - start

    connected = sum(
        r["connected"]
        for r in results
    )

    signed_up = sum(
        r["signup"]
        for r in results
    )

    logged_in = sum(
        r["login"]
        for r in results
    )

    authenticated = sum(
        r["authenticated_request"]
        for r in results
    )

    failures = [
        r
        for r in results
        if r["error"] is not None
    ]

    print()
    print("=" * 55)
    print("RESULTS")
    print("=" * 55)

    print(f"Connected:              {connected}/{NUM_USERS}")
    print(f"Signup succeeded:       {signed_up}/{NUM_USERS}")
    print(f"Login succeeded:        {logged_in}/{NUM_USERS}")
    print(f"Authenticated requests: {authenticated}/{NUM_USERS}")
    print(f"Duration:               {duration:.2f} seconds")
    print(f"Failures:               {len(failures)}")

    if failures:
        print()
        print("FAILURES:")
        for failure in failures:
            print(
                f"- {failure['username']}: "
                f"{failure['error']}"
            )

    print()

    if (
        connected == NUM_USERS
        and signed_up == NUM_USERS
        and logged_in == NUM_USERS
        and authenticated == NUM_USERS
    ):
        print("OVERALL RESULT: PASS ✓")
    else:
        print("OVERALL RESULT: CHECK FAILURES ✗")


if __name__ == "__main__":
    asyncio.run(main())