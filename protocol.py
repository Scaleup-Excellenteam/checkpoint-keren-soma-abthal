import json

TYPE_REQUEST = "request"
TYPE_RESPONSE = "response"
TYPE_EVENT = "event"

STATUS_OK = "ok"
STATUS_ERROR = "error"

CODE_INVALID_JSON = "INVALID_JSON"
CODE_INVALID_REQUEST = "INVALID_REQUEST"
CODE_UNKNOWN_ACTION = "UNKNOWN_ACTION"
CODE_OK = "OK"

KNOWN_ACTIONS = frozenset(
    {
        "login",
        "create_room",
        "join_room",
        "list_rooms",
        "send_message",
    }
)


def encode(message):
    return json.dumps(message)


def parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def build_request(request_id, action, payload=None):
    return {
        "type": TYPE_REQUEST,
        "request_id": str(request_id),
        "action": action,
        "payload": payload or {},
    }


def build_response(request_id, status, code, message=None, payload=None):
    response = {
        "type": TYPE_RESPONSE,
        "request_id": "" if request_id is None else request_id,
        "status": status,
        "code": code,
        "payload": payload or {},
    }
    if message is not None:
        response["message"] = message
    return response


def build_ok(request_id, code=CODE_OK, payload=None):
    return build_response(request_id, STATUS_OK, code, payload=payload)


def build_error(request_id, code, message):
    return build_response(request_id, STATUS_ERROR, code, message=message)


def build_event(event, payload):
    return {
        "type": TYPE_EVENT,
        "event": event,
        "payload": payload,
    }


def validate_request(data):
    if not isinstance(data, dict):
        return None, CODE_INVALID_REQUEST
    if data.get("type") != TYPE_REQUEST:
        return None, CODE_INVALID_REQUEST
    if "request_id" not in data or "action" not in data or "payload" not in data:
        return None, CODE_INVALID_REQUEST
    if not isinstance(data["action"], str) or data["action"] == "":
        return None, CODE_INVALID_REQUEST
    if not isinstance(data["payload"], dict):
        return None, CODE_INVALID_REQUEST
    return data, None
