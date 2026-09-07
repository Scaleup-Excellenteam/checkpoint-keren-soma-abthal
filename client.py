import asyncio

from websockets.asyncio.client import connect

SERVER_URL = "ws://localhost:8765/ws"
CLIENT_MESSAGE = "ping"


async def main():
    async with connect(SERVER_URL) as websocket:
        await websocket.send(CLIENT_MESSAGE)
        reply = await websocket.recv()
        print(reply)


if __name__ == "__main__":
    asyncio.run(main())
