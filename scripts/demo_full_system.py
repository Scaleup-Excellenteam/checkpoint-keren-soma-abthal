import argparse
import asyncio
import contextlib
import json
import time

import websockets


EXACT_DLP = "Add 7 grams of dry yeast and 10 grams of fine salt"

SEMANTIC_DLP = (
    "Use half a kilo of bread flour together with about "
    "325 ml of warm water"
)

SAFE_URL = "check https://example.com/test"
MALICIOUS_URL = "check http://malware.wicar.org/"


class DemoClient:
    def __init__(self, name, username, password, url):
        self.name = name
        self.username = username
        self.password = password
        self.url = url

        self.ws = None
        self.listener_task = None

        self.pending = {}
        self.events = asyncio.Queue()
        self.counter = 0

    async def connect(self):
        self.ws = await websockets.connect(self.url)
        self.listener_task = asyncio.create_task(self._listen())

        response = await self.request(
            "login",
            {
                "username": self.username,
                "password": self.password,
            },
        )

        if response.get("status") != "ok":
            raise RuntimeError(
                f"{self.name} login failed: "
                f"{response.get('code')}"
            )

        print(
            f"PASS  {self.name} connected and logged in "
            f"as {self.username}"
        )

    async def _listen(self):
        try:
            async for raw in self.ws:
                message = json.loads(raw)

                if message.get("type") == "response":
                    request_id = message.get("request_id")
                    future = self.pending.pop(request_id, None)

                    if future is not None and not future.done():
                        future.set_result(message)

                elif message.get("type") == "event":
                    await self.events.put(message)

        except Exception as exc:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(exc)

    async def request(self, action, payload):
        self.counter += 1
        request_id = f"{self.name}-{self.counter}"

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.pending[request_id] = future

        message = {
            "type": "request",
            "request_id": request_id,
            "action": action,
            "payload": payload,
        }

        await self.ws.send(json.dumps(message))

        return await asyncio.wait_for(future, timeout=30)

    async def join_room(self, room_id):
        response = await self.request(
            "join_room",
            {"room_id": room_id},
        )

        code = response.get("code")

        if code not in {"ROOM_JOINED", "ALREADY_ROOM_MEMBER"}:
            raise RuntimeError(
                f"{self.name} couldn't join room: {code}"
            )

        print(
            f"PASS  {self.name} is a member of room {room_id} "
            f"({code})"
        )

    async def send_message(self, room_id, text):
        return await self.request(
            "send_message",
            {
                "room_id": room_id,
                "message": text,
            },
        )

    async def wait_for_message(self, text, timeout=3):
        deadline = time.monotonic() + timeout

        while True:
            remaining = deadline - time.monotonic()

            if remaining <= 0:
                return False

            try:
                event = await asyncio.wait_for(
                    self.events.get(),
                    timeout=remaining,
                )
            except asyncio.TimeoutError:
                return False

            payload = event.get("payload", {})

            if payload.get("message") == text:
                return True

    async def close(self):
        if self.ws is not None:
            await self.ws.close()

        if self.listener_task is not None:
            with contextlib.suppress(Exception):
                await self.listener_task

        print(f"PASS  {self.name} disconnected")


def credentials(value):
    if ":" not in value:
        raise argparse.ArgumentTypeError(
            "Use username:password"
        )

    return value.split(":", 1)


def result(ok, description):
    print(
        f"{'PASS' if ok else 'FAIL'}  {description}"
    )
    return ok


async def main():
    parser = argparse.ArgumentParser(
        description="Full live multi-client system demo"
    )

    parser.add_argument("room_id", type=int)

    parser.add_argument(
        "--a",
        required=True,
        type=credentials,
        help="Client A username:password",
    )
    parser.add_argument(
        "--b",
        required=True,
        type=credentials,
        help="Client B username:password",
    )
    parser.add_argument(
        "--c",
        required=True,
        type=credentials,
        help="Client C username:password",
    )
    parser.add_argument(
        "--d",
        required=True,
        type=credentials,
        help="Client D username:password",
    )

    parser.add_argument(
        "--url",
        default="ws://127.0.0.1:8765/ws",
    )

    args = parser.parse_args()

    a = DemoClient("A", *args.a, args.url)
    b = DemoClient("B", *args.b, args.url)
    c = DemoClient("C", *args.c, args.url)
    d = DemoClient("D", *args.d, args.url)

    checks = []

    try:
        print("\n===== CONNECT A / B / C =====")

        await asyncio.gather(
            a.connect(),
            b.connect(),
            c.connect(),
        )

        await asyncio.gather(
            a.join_room(args.room_id),
            b.join_room(args.room_id),
            c.join_room(args.room_id),
        )

        # --------------------------------------------------
        # TEST 1: A + B send almost simultaneously
        # --------------------------------------------------

        print("\n===== TEST 1: CONCURRENT SEND =====")

        msg_a = "concurrent-message-from-A"
        msg_b = "concurrent-message-from-B"

        response_a, response_b = await asyncio.gather(
            a.send_message(args.room_id, msg_a),
            b.send_message(args.room_id, msg_b),
        )

        checks.append(
            result(
                response_a.get("code") == "MESSAGE_ACCEPTED"
                and response_b.get("code") == "MESSAGE_ACCEPTED",
                "A and B sent concurrently",
            )
        )

        a_saw_b, b_saw_a, c_saw_a, c_saw_b = await asyncio.gather(
            a.wait_for_message(msg_b),
            b.wait_for_message(msg_a),
            c.wait_for_message(msg_a),
            c.wait_for_message(msg_b),
        )

        checks.append(
            result(
                a_saw_b and b_saw_a and c_saw_a and c_saw_b,
                "Concurrent broadcasts reached active clients",
            )
        )

        # --------------------------------------------------
        # TEST 2: C disconnects, A/B continue
        # --------------------------------------------------

        print("\n===== TEST 2: DISCONNECT DURING USE =====")

        await c.close()

        after_c_a = "A-still-working-after-C-disconnect"
        after_c_b = "B-still-working-after-C-disconnect"

        ra, rb = await asyncio.gather(
            a.send_message(args.room_id, after_c_a),
            b.send_message(args.room_id, after_c_b),
        )

        checks.append(
            result(
                ra.get("code") == "MESSAGE_ACCEPTED"
                and rb.get("code") == "MESSAGE_ACCEPTED",
                "A and B continued after C disconnected",
            )
        )

        # --------------------------------------------------
        # TEST 3: D joins while system remains active
        # --------------------------------------------------

        print("\n===== TEST 3: CLIENT D ENTERS =====")

        await d.connect()
        await d.join_room(args.room_id)

        safe = "normal-message-after-D-joined"

        safe_response = await a.send_message(
            args.room_id,
            safe,
        )

        b_received, d_received = await asyncio.gather(
            b.wait_for_message(safe),
            d.wait_for_message(safe),
        )

        checks.append(
            result(
                safe_response.get("code") == "MESSAGE_ACCEPTED"
                and b_received
                and d_received,
                "Normal message reached B and newly joined D",
            )
        )

        # Let A's Anti-Bot window clear before security tests.
        print("\nWaiting for Anti-Bot window to clear...")
        await asyncio.sleep(5.5)

        # --------------------------------------------------
        # TEST 4: Safe URL
        # --------------------------------------------------

        print("\n===== TEST 4: SAFE URL =====")

        safe_url_response = await a.send_message(
            args.room_id,
            SAFE_URL,
        )

        checks.append(
            result(
                safe_url_response.get("code") == "MESSAGE_ACCEPTED",
                "Safe URL/domain was allowed",
            )
        )

        # --------------------------------------------------
        # TEST 5: Exact DLP
        # --------------------------------------------------

        print("\n===== TEST 5: EXACT DLP BLOCK =====")

        exact_response = await a.send_message(
            args.room_id,
            EXACT_DLP,
        )

        exact_seen_b, exact_seen_d = await asyncio.gather(
            b.wait_for_message(EXACT_DLP, timeout=1),
            d.wait_for_message(EXACT_DLP, timeout=1),
        )

        checks.append(
            result(
                exact_response.get("code")
                == "DLP_PROTECTED_CONTENT"
                and not exact_seen_b
                and not exact_seen_d,
                "Exact protected recipe blocked before broadcast",
            )
        )

        # --------------------------------------------------
        # TEST 6: Semantic DLP
        # --------------------------------------------------

        print("\n===== TEST 6: EMBEDDING DLP BLOCK =====")

        semantic_response = await a.send_message(
            args.room_id,
            SEMANTIC_DLP,
        )

        semantic_seen_b, semantic_seen_d = await asyncio.gather(
            b.wait_for_message(SEMANTIC_DLP, timeout=1),
            d.wait_for_message(SEMANTIC_DLP, timeout=1),
        )

        checks.append(
            result(
                semantic_response.get("code")
                == "DLP_SEMANTIC_MATCH"
                and not semantic_seen_b
                and not semantic_seen_d,
                "Paraphrased recipe blocked by semantic DLP",
            )
        )

        # --------------------------------------------------
        # TEST 7: Malicious URL
        # --------------------------------------------------

        print("\n===== TEST 7: MALICIOUS DOMAIN BLOCK =====")

        malicious_response = await a.send_message(
            args.room_id,
            MALICIOUS_URL,
        )

        malicious_seen_b, malicious_seen_d = await asyncio.gather(
            b.wait_for_message(MALICIOUS_URL, timeout=1),
            d.wait_for_message(MALICIOUS_URL, timeout=1),
        )

        url_block_codes = {
            "URL_MALICIOUS",
            "URL_HIGH_RISK",
        }

        checks.append(
            result(
                malicious_response.get("code")
                in url_block_codes
                and not malicious_seen_b
                and not malicious_seen_d,
                "Malicious domain blocked before broadcast",
            )
        )

        # --------------------------------------------------
        # TEST 8: Anti-Bot burst
        # --------------------------------------------------

        print("\n===== TEST 8: ANTI-BOT BURST =====")

        # Clear B's earlier rate-limit history.
        await asyncio.sleep(5.5)

        burst_messages = [
            f"burst-neutral-message-{i}"
            for i in range(1, 7)
        ]

        burst_responses = await asyncio.gather(
            *[
                b.send_message(args.room_id, message)
                for message in burst_messages
            ]
        )

        accepted = sum(
            r.get("code") == "MESSAGE_ACCEPTED"
            for r in burst_responses
        )

        blocked = sum(
            r.get("code") == "ANTIBOT_RATE_LIMIT"
            for r in burst_responses
        )

        checks.append(
            result(
                accepted == 5 and blocked == 1,
                f"Anti-Bot burst: accepted={accepted}, blocked={blocked}",
            )
        )

        # --------------------------------------------------
        # TEST 9: Nobody got stuck
        # --------------------------------------------------

        print("\n===== TEST 9: FINAL RESPONSIVENESS =====")

        final_message = "FINAL-SYSTEM-STILL-RESPONSIVE"

        final_response = await a.send_message(
            args.room_id,
            final_message,
        )

        final_b, final_d = await asyncio.gather(
            b.wait_for_message(final_message, timeout=3),
            d.wait_for_message(final_message, timeout=3),
        )

        checks.append(
            result(
                final_response.get("code") == "MESSAGE_ACCEPTED"
                and final_b
                and final_d,
                "Server still responsive after all security/concurrency tests",
            )
        )

    finally:
        for client in (a, b, c, d):
            with contextlib.suppress(Exception):
                if client.ws is not None and not client.ws.closed:
                    await client.close()

    print("\n======================================")
    print("       FULL SYSTEM DEMO SUMMARY")
    print("======================================")

    passed = sum(checks)
    total = len(checks)

    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("OVERALL RESULT: PASS ✓")
    else:
        print("OVERALL RESULT: CHECK FAILURES ✗")


if __name__ == "__main__":
    asyncio.run(main())
