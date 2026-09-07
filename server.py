import asyncio

from websockets.asyncio.server import serve

HOST = "0.0.0.0"
PORT = 8765
WEBSOCKET_PATH = "/ws"
HELLO_REPLY = "hello"


async def handle_client(websocket):
    if websocket.request.path != WEBSOCKET_PATH:
        await websocket.close()
        return

    print("CLIENT_CONNECTED", flush=True)
    message = await websocket.recv()
    await websocket.send(HELLO_REPLY)
    print("Recive message: ", message, flush=True)


async def main():
    print("SERVER_STARTED", flush=True)
    async with serve(handle_client, HOST, PORT) as server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
