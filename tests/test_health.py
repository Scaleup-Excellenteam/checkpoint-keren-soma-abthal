import asyncio
import json
from urllib.request import urlopen

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from server.server import handle_client, process_http_request


async def run_test_server(test):
    async with serve(
        handle_client,
        "127.0.0.1",
        0,
        process_request=process_http_request,
    ) as server:
        port = server.sockets[0].getsockname()[1]
        return await test(port)


def test_health_endpoint_returns_json_ok():
    async def exercise(port):
        def request_health():
            with urlopen(
                f"http://127.0.0.1:{port}/health",
                timeout=2,
            ) as response:
                return (
                    response.status,
                    response.headers.get_content_type(),
                    response.read(),
                )

        return await asyncio.to_thread(request_health)

    status, content_type, body = asyncio.run(run_test_server(exercise))

    assert status == 200
    assert content_type == "application/json"
    assert json.loads(body) == {"status": "ok"}


def test_websocket_endpoint_still_accepts_requests():
    async def exercise(port):
        async with connect(f"ws://127.0.0.1:{port}/ws") as websocket:
            await websocket.send(
                json.dumps(
                    {
                        "type": "request",
                        "request_id": "health-ws-test",
                        "action": "list_rooms",
                        "payload": {},
                    }
                )
            )
            return json.loads(await websocket.recv())

    response = asyncio.run(run_test_server(exercise))

    assert response == {
        "type": "response",
        "request_id": "health-ws-test",
        "status": "error",
        "code": "NOT_AUTHENTICATED",
        "payload": {},
        "message": "Login required",
    }
