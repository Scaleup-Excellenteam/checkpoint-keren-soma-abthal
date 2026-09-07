# from .protocol import (
#     CODE_ALREADY_AUTHENTICATED,
#     CODE_ALREADY_ROOM_MEMBER,
#     CODE_INVALID_PAYLOAD,
#     CODE_LOGIN_SUCCESS,
#     CODE_MESSAGE_ACCEPTED,
#     CODE_NOT_AUTHENTICATED,
#     CODE_NOT_ROOM_MEMBER,
#     CODE_ROOM_CREATED,
#     CODE_ROOM_JOINED,
#     CODE_ROOM_LIST,
#     CODE_ROOM_NAME_TAKEN,
#     CODE_ROOM_NOT_FOUND,
#     CODE_USER_ALREADY_ONLINE,
#     build_error,
#     build_event,
#     build_ok,
#     encode,
# )


# class ClientSession:
#     def __init__(self, websocket):
#         self.websocket = websocket
#         self.user_id = None
#         self.username = None


# class AppStore:
#     def __init__(self):
#         self.online_users = {}
#         self.registered_users = {}
#         self.rooms = {}
#         self.next_user_id = 1
#         self.next_room_id = 1


# store = AppStore()

# ACTIONS_NEEDING_LOGIN = frozenset(
#     {
#         "create_room",
#         "join_room",
#         "list_rooms",
#         "send_message",
#     }
# )


# def handle_disconnect(session):
#     if session.user_id is not None:
#         store.online_users.pop(session.user_id, None)
#     print("CLIENT_DISCONNECTED", flush=True)


# def parse_room_id(value):
#     if isinstance(value, int):
#         return value
#     if isinstance(value, str) and value.isdigit():
#         return int(value)
#     return None


# async def handle_request(session, request):
#     action = request["action"]
#     request_id = request["request_id"]
#     payload = request["payload"]

#     if action in ACTIONS_NEEDING_LOGIN and session.user_id is None:
#         return build_error(request_id, CODE_NOT_AUTHENTICATED, "Login required")

#     if action == "login":
#         return handle_login(session, request_id, payload)
#     if action == "create_room":
#         return handle_create_room(session, request_id, payload)
#     if action == "join_room":
#         return handle_join_room(session, request_id, payload)
#     if action == "list_rooms":
#         return handle_list_rooms(session, request_id)
#     if action == "send_message":
#         return await handle_send_message(session, request_id, payload)

#     return None


# def handle_login(session, request_id, payload):
#     username = payload.get("username")
#     if not isinstance(username, str) or username.strip() == "":
#         return build_error(request_id, CODE_INVALID_PAYLOAD, "username is required")
#     username = username.strip()

#     if session.user_id is not None:
#         return build_error(
#             request_id, CODE_ALREADY_AUTHENTICATED, "Already logged in"
#         )

#     if username in store.registered_users:
#         user_id = store.registered_users[username]
#     else:
#         user_id = store.next_user_id
#         store.next_user_id += 1
#         store.registered_users[username] = user_id

#     if user_id in store.online_users:
#         return build_error(
#             request_id, CODE_USER_ALREADY_ONLINE, "User is already online"
#         )

#     session.user_id = user_id
#     session.username = username
#     store.online_users[user_id] = session
#     return build_ok(
#         request_id,
#         CODE_LOGIN_SUCCESS,
#         {"user_id": user_id, "username": username},
#     )


# def handle_create_room(session, request_id, payload):
#     name = payload.get("name")
#     if not isinstance(name, str) or name.strip() == "":
#         return build_error(request_id, CODE_INVALID_PAYLOAD, "name is required")
#     name = name.strip()

#     for room in store.rooms.values():
#         if room["name"] == name:
#             return build_error(
#                 request_id, CODE_ROOM_NAME_TAKEN, "Room name already exists"
#             )

#     room_id = store.next_room_id
#     store.next_room_id += 1
#     store.rooms[room_id] = {"name": name, "members": {session.user_id}}
#     return build_ok(
#         request_id,
#         CODE_ROOM_CREATED,
#         {"room_id": room_id, "name": name},
#     )


# def handle_join_room(session, request_id, payload):
#     room_id = parse_room_id(payload.get("room_id"))
#     if room_id is None:
#         return build_error(request_id, CODE_INVALID_PAYLOAD, "room_id is required")

#     room = store.rooms.get(room_id)
#     if room is None:
#         return build_error(request_id, CODE_ROOM_NOT_FOUND, "Room does not exist")

#     if session.user_id in room["members"]:
#         return build_error(
#             request_id, CODE_ALREADY_ROOM_MEMBER, "Already a member of this room"
#         )

#     room["members"].add(session.user_id)
#     return build_ok(
#         request_id,
#         CODE_ROOM_JOINED,
#         {"room_id": room_id, "name": room["name"]},
#     )


# def handle_list_rooms(session, request_id):
#     rooms = []
#     for room_id, room in store.rooms.items():
#         rooms.append(
#             {
#                 "room_id": room_id,
#                 "name": room["name"],
#                 "member": session.user_id in room["members"],
#             }
#         )
#     return build_ok(request_id, CODE_ROOM_LIST, {"rooms": rooms})


# async def handle_send_message(session, request_id, payload):
#     room_id = parse_room_id(payload.get("room_id"))
#     if room_id is None:
#         return build_error(request_id, CODE_INVALID_PAYLOAD, "room_id is required")

#     message = payload.get("message")
#     if not isinstance(message, str) or message.strip() == "":
#         return build_error(request_id, CODE_INVALID_PAYLOAD, "message is required")
#     message = message.strip()

#     room = store.rooms.get(room_id)
#     if room is None:
#         return build_error(request_id, CODE_ROOM_NOT_FOUND, "Room does not exist")
#     if session.user_id not in room["members"]:
#         return build_error(
#             request_id, CODE_NOT_ROOM_MEMBER, "Not a member of this room"
#         )

#     event = build_event(
#         "room_message",
#         {
#             "room_id": room_id,
#             "room_name": room["name"],
#             "sender_id": session.user_id,
#             "sender_username": session.username,
#             "message": message,
#         },
#     )
#     encoded_event = encode(event)
#     print("MESSAGE_ACCEPTED", "length", len(message), flush=True)

#     for member_id in room["members"]:
#         member_session = store.online_users.get(member_id)
#         if member_session is None:
#             continue
#         try:
#             await member_session.websocket.send(encoded_event)
#         except Exception:
#             print("SEND_FAILED", flush=True)

#     return build_ok(request_id, CODE_MESSAGE_ACCEPTED)


from auth_service import AuthService
from errors import AppError
from room_service import RoomService
from storage import StorageManager

from .protocol import (
    CODE_ALREADY_AUTHENTICATED,
    CODE_INVALID_PAYLOAD,
    CODE_LOGIN_SUCCESS,
    CODE_MESSAGE_ACCEPTED,
    CODE_NOT_AUTHENTICATED,
    CODE_ROOM_CREATED,
    CODE_ROOM_JOINED,
    CODE_ROOM_LIST,
    CODE_USER_ALREADY_ONLINE,
    CODE_SIGNUP_SUCCESS,
    CODE_LOGOUT_SUCCESS,
    CODE_ROOM_LEFT,
    build_error,
    build_event,
    build_ok,
    encode,
)


# =========================================================
# Real Day 1 services
# =========================================================

storage = StorageManager()
auth_service = AuthService(storage)
room_service = RoomService(storage)


class ClientSession:
    def __init__(self, websocket):
        self.websocket = websocket
        self.user_id = None
        self.username = None


# =========================================================
# Runtime-only state
# =========================================================

class AppStore:
    def __init__(self):
        # user_id -> ClientSession
        #
        # This is intentionally NOT persistent.
        # A WebSocket connection only exists while the server is running.
        self.online_users = {}


store = AppStore()


ACTIONS_NEEDING_LOGIN = frozenset(
    {
        "logout",
        "create_room",
        "join_room",
        "leave_room",
        "list_rooms",
        "send_message",
    }
)


def handle_disconnect(session):
    if session.user_id is not None:
        store.online_users.pop(
            session.user_id,
            None,
        )

    print(
        "CLIENT_DISCONNECTED",
        flush=True,
    )


def parse_room_id(value):
    if isinstance(value, int):
        return value

    if isinstance(value, str) and value.isdigit():
        return int(value)

    return None


async def handle_request(
    session,
    request,
):
    action = request["action"]
    request_id = request["request_id"]
    payload = request["payload"]

    if (
        action in ACTIONS_NEEDING_LOGIN
        and session.user_id is None
    ):
        return build_error(
            request_id,
            CODE_NOT_AUTHENTICATED,
            "Login required",
        )

    if action == "signup":
        return handle_signup(
            session,
            request_id,
            payload,
        )

    if action == "login":
        return handle_login(
            session,
            request_id,
            payload,
        )

    if action == "logout":
        return handle_logout(
            session,
            request_id,
        )

    if action == "create_room":
        return handle_create_room(
            session,
            request_id,
            payload,
        )

    if action == "join_room":
        return handle_join_room(
            session,
            request_id,
            payload,
        )

    if action == "leave_room":
        return handle_leave_room(
            session,
            request_id,
            payload,
        )

    if action == "list_rooms":
        return handle_list_rooms(
            session,
            request_id,
        )

    if action == "send_message":
        return await handle_send_message(
            session,
            request_id,
            payload,
        )

    return None


# =========================================================
# Signup
# =========================================================

def handle_signup(
    session,
    request_id,
    payload,
):
    if session.user_id is not None:
        return build_error(
            request_id,
            CODE_ALREADY_AUTHENTICATED,
            "Already logged in",
        )

    username = payload.get("username")
    password = payload.get("password")

    if (
        not isinstance(username, str)
        or not isinstance(password, str)
    ):
        return build_error(
            request_id,
            CODE_INVALID_PAYLOAD,
            "username and password are required",
        )

    try:
        user = auth_service.signup(
            username,
            password,
        )

    except AppError as error:
        return build_error(
            request_id,
            error.code,
            str(error),
        )

    return build_ok(
        request_id,
        CODE_SIGNUP_SUCCESS,
        {
            "user_id": user.user_id,
            "username": user.username,
        },
    )


# =========================================================
# Login
# =========================================================

def handle_login(
    session,
    request_id,
    payload,
):
    username = payload.get("username")
    password = payload.get("password")

    if (
        not isinstance(username, str)
        or not isinstance(password, str)
    ):
        return build_error(
            request_id,
            CODE_INVALID_PAYLOAD,
            "username and password are required",
        )

    if session.user_id is not None:
        return build_error(
            request_id,
            CODE_ALREADY_AUTHENTICATED,
            "Already logged in",
        )

    try:
        user = auth_service.login(
            username,
            password,
        )

    except AppError as error:
        return build_error(
            request_id,
            error.code,
            str(error),
        )

    if user.user_id in store.online_users:
        return build_error(
            request_id,
            CODE_USER_ALREADY_ONLINE,
            "User is already online",
        )

    session.user_id = user.user_id
    session.username = user.username

    store.online_users[
        user.user_id
    ] = session

    return build_ok(
        request_id,
        CODE_LOGIN_SUCCESS,
        {
            "user_id": user.user_id,
            "username": user.username,
        },
    )


# =========================================================
# Logout
# =========================================================

def handle_logout(
    session,
    request_id,
):
    if session.user_id is not None:
        store.online_users.pop(
            session.user_id,
            None,
        )

    session.user_id = None
    session.username = None

    return build_ok(
        request_id,
        CODE_LOGOUT_SUCCESS,
    )


# =========================================================
# Create room
# =========================================================

def handle_create_room(
    session,
    request_id,
    payload,
):
    name = payload.get("name")

    if not isinstance(name, str):
        return build_error(
            request_id,
            CODE_INVALID_PAYLOAD,
            "name is required",
        )

    try:
        room = room_service.create_room(
            session.user_id,
            name,
        )

    except AppError as error:
        return build_error(
            request_id,
            error.code,
            str(error),
        )

    return build_ok(
        request_id,
        CODE_ROOM_CREATED,
        {
            "room_id": room.room_id,
            "name": room.name,
        },
    )


# =========================================================
# Join room
# =========================================================

def handle_join_room(
    session,
    request_id,
    payload,
):
    room_id = parse_room_id(
        payload.get("room_id")
    )

    if room_id is None:
        return build_error(
            request_id,
            CODE_INVALID_PAYLOAD,
            "room_id is required",
        )

    try:
        room = room_service.join_room(
            session.user_id,
            room_id,
        )

    except AppError as error:
        return build_error(
            request_id,
            error.code,
            str(error),
        )

    return build_ok(
        request_id,
        CODE_ROOM_JOINED,
        {
            "room_id": room.room_id,
            "name": room.name,
        },
    )


# =========================================================
# Leave room
# =========================================================

def handle_leave_room(
    session,
    request_id,
    payload,
):
    room_id = parse_room_id(
        payload.get("room_id")
    )

    if room_id is None:
        return build_error(
            request_id,
            CODE_INVALID_PAYLOAD,
            "room_id is required",
        )

    try:
        room = room_service.leave_room(
            session.user_id,
            room_id,
        )

    except AppError as error:
        return build_error(
            request_id,
            error.code,
            str(error),
        )

    return build_ok(
        request_id,
        CODE_ROOM_LEFT,
        {
            "room_id": room.room_id,
            "name": room.name,
        },
    )


# =========================================================
# List rooms
# =========================================================

def handle_list_rooms(
    session,
    request_id,
):
    rooms = room_service.list_rooms(
        session.user_id
    )

    return build_ok(
        request_id,
        CODE_ROOM_LIST,
        {
            "rooms": rooms,
        },
    )


# =========================================================
# Send room message
# =========================================================

async def handle_send_message(
    session,
    request_id,
    payload,
):
    room_id = parse_room_id(
        payload.get("room_id")
    )

    if room_id is None:
        return build_error(
            request_id,
            CODE_INVALID_PAYLOAD,
            "room_id is required",
        )

    message = payload.get("message")

    if (
        not isinstance(message, str)
        or message.strip() == ""
    ):
        return build_error(
            request_id,
            CODE_INVALID_PAYLOAD,
            "message is required",
        )

    message = message.strip()

    # -----------------------------------------------------
    # Authorization comes from YOUR RoomService
    # -----------------------------------------------------

    try:
        room = room_service.authorize_message(
            session.user_id,
            room_id,
        )

    except AppError as error:
        return build_error(
            request_id,
            error.code,
            str(error),
        )

    # -----------------------------------------------------
    # Real-time delivery comes from Keren's WebSocket layer
    # -----------------------------------------------------

    event = build_event(
        "room_message",
        {
            "room_id": room.room_id,
            "room_name": room.name,
            "sender_id": session.user_id,
            "sender_username": session.username,
            "message": message,
        },
    )

    encoded_event = encode(event)

    print(
        "MESSAGE_ACCEPTED",
        "length",
        len(message),
        flush=True,
    )

    for member_id in room.members:

        member_session = (
            store.online_users.get(
                member_id
            )
        )

        if member_session is None:
            continue

        try:
            await member_session.websocket.send(
                encoded_event
            )

        except Exception:
            print(
                "SEND_FAILED",
                flush=True,
            )

    return build_ok(
        request_id,
        CODE_MESSAGE_ACCEPTED,
    )