class ClientSession:
    def __init__(self, websocket):
        self.websocket = websocket
        self.user_id = None


def handle_disconnect(session):
    print("CLIENT_DISCONNECTED", flush=True)
