# TSPO — Day 1 Implementation Specification

**Version:** Day 1 MVP  
**Team size:** 2  
**Goal:** להגיע במהירות למערכת עובדת שממלאת את כל דרישות Day 1 לפני תחילת DLP / Anti-Bot.

---

# 1. Day 1 Goal

בסוף Day 1 חייב להיות אפשר לבצע את התרחיש הבא:

```text
Laptop A                  Server                  Laptop B
   |                         |                         |
   |---- WebSocket --------->|<------ WebSocket ------|
   |                         |                         |
 Signup/Login                |                  Signup/Login
   |                         |                         |
 Authenticated               |                  Authenticated
   |                         |                         |
 Create Room --------------->|                         |
   |                         |<------------ Join Room |
   |                         |                         |
 Send "hello" -------------> | ---------------------> |
   |                         |                receives message
   |                         |                         |
   | <---------------------- | <---- Send "hi" ------ |
 receives message            |                         |
```

בנוסף:

```text
GET /health
→ server healthy

invalid request
→ rejected

unauthorized action
→ rejected

important actions
→ visible in logs
```

---

# 2. Scope

## חובה ב-Day 1

```text
WebSocket server
WebSocket client
Multiple concurrent clients
Signup
Login
Logout
Authenticated session
Users persistence
Rooms persistence
Create room
List rooms
Join room
Leave room
Send room message
Room membership access checks
Request validation
Response/error codes
Server events
Logging
/health
Multi-laptop demo
```

## לא עושים עכשיו

```text
DLP
Anti-Bot
Private messages
Message history
Offline delivery
Database
GUI
JWT
Microservices
Docker
Kubernetes
Advanced reconnect
Custom heartbeat implementation
Advanced administration
Delete room
Transfer room ownership
Message encryption
```

אלה מחוץ ל-MVP הנוכחי.

---

# 3. Technology Decisions

## Language

```text
Python 3.12+
```

## Communication

```text
WebSocket
```

library:

```text
websockets
```

## Concurrency model

```text
asyncio
```

**לא thread לכל client.**

יהיה:

```text
One Python process
       |
One asyncio event loop
       |
       +---- Client A task
       |
       +---- Client B task
       |
       +---- Client C task
```

כל WebSocket connection מטופל כ-coroutine/task.

---

# 4. Runtime Architecture

```text
                         SERVER
                           |
              +------------+------------+
              |                         |
        Communication                 Domain
         Partner A                   Partner B
              |                         |
     WebSocket connection            Users
     Protocol                        Authentication
     Session                         Rooms
     Dispatcher                      Membership
     online_users                    Authorization
     MessageRouter                   Persistence
              |                         |
              +------------+------------+
                           |
                      Shared interface
```

כלל מרכזי:

```text
Partner A handles HOW data moves.

Partner B handles WHAT the operation means
and WHETHER it is allowed.
```

---

# 5. Project Structure

נשמור את מספר הקבצים קטן כדי להתקדם מהר:

```text
check-point/
│
├── server.py
├── client.py
│
├── protocol.py
├── runtime.py
├── errors.py
│
├── models.py
├── auth_service.py
├── room_service.py
├── storage.py
├── password_utils.py
│
├── logging_config.py
│
├── data/
│   ├── users.json
│   └── rooms.json
│
├── tests/
│   └── test_day1.py
│
├── requirements.txt
└── README.md
```

---

# 6. File Ownership

## Partner A

```text
server.py
client.py
protocol.py
runtime.py
logging integration for runtime
```

Responsible for:

```text
WebSocket client
WebSocket server
Connections
asyncio
ClientSession
Protocol
Dispatcher
online_users
MessageRouter
Network send
Disconnect cleanup
Multi-laptop integration
```

---

## Partner B

```text
models.py
auth_service.py
room_service.py
storage.py
password_utils.py
business logging
```

Responsible for:

```text
Users
Signup
Login
Password hashing
Persistence
Rooms
Membership
Authorization
Business validation
```

---

## Shared

```text
errors.py
tests/
requirements.txt
README.md
protocol decisions
integration
demo
```

---

# 7. Network Configuration

Server listens on:

```text
0.0.0.0:8765
```

WebSocket path:

```text
/ws
```

Example client:

```text
ws://SERVER_IP:8765/ws
```

Health:

```text
http://SERVER_IP:8765/health
```

Important:

```text
localhost
```

משמש רק כאשר client וה-server על אותו מחשב.

ב-demo בין laptops משתמשים ב-IP של מחשב השרת.

---

# 8. HTTP /health

לא נוסיף Flask/FastAPI רק בשביל health.

ה-WebSocket server יטפל גם ב:

```text
GET /health
```

דרך ה-HTTP request hook של `websockets`.

Response:

```json
{
  "status": "ok"
}
```

HTTP Status:

```text
200 OK
```

לא צריך authentication ל-health.

---

# 9. User Model

```python
User:
    user_id: int
    username: str
    password_hash: str
```

Example:

```json
{
  "user_id": 1,
  "username": "soma",
  "password_hash": "$2b$..."
}
```

אנחנו לא שומרים plaintext password.

---

# 10. Room Model

```python
Room:
    room_id: int
    name: str
    admin_user_id: int
    members: set[int]
```

Example:

```json
{
  "room_id": 1,
  "name": "general",
  "admin_user_id": 1,
  "members": [1, 2]
}
```

---

# 11. Room Decisions

### Room names

Room name חייב להיות unique.

```text
general
developers
random
```

לא יכולים להיות שני:

```text
general
general
```

---

### Creator

מי שיוצר room:

```text
becomes room admin
+
automatically becomes member
```

---

### Join

כל authenticated user יכול להצטרף ל-room קיים.

אין invites ב-Day 1.

---

### Leave

member רגיל יכול לעזוב.

Room admin לא יכול לעזוב ב-Day 1.

Response:

```text
ADMIN_CANNOT_LEAVE_ROOM
```

לא נבנה כרגע transfer ownership.

---

# 12. Persistence

נשתמש בשני קבצים בלבד:

```text
data/users.json
data/rooms.json
```

---

## users.json

```json
{
  "users": [
    {
      "user_id": 1,
      "username": "soma",
      "password_hash": "..."
    }
  ]
}
```

---

## rooms.json

```json
{
  "rooms": [
    {
      "room_id": 1,
      "name": "general",
      "admin_user_id": 1,
      "members": [1, 2]
    }
  ]
}
```

---

# 13. ID Generation

לא צריך UUID.

בעת startup:

```text
next_user_id =
max(existing user_ids) + 1

next_room_id =
max(existing room_ids) + 1
```

אם אין records:

```text
first ID = 1
```

---

# 14. StorageManager

`storage.py` אחראי **לבדו** לקריאה וכתיבה לקבצים.

Interface:

```python
load_users()
save_users(users)

load_rooms()
save_rooms(rooms)
```

אסור ל:

```text
server.py
runtime.py
protocol.py
```

לפתוח ישירות `users.json` או `rooms.json`.

---

# 15. Password Handling

נשתמש ב:

```text
bcrypt
```

Signup:

```text
password
   ↓
bcrypt hash
   ↓
password_hash
   ↓
users.json
```

Login:

```text
entered password
      +
stored hash
      ↓
bcrypt verification
```

לעולם לא log password.

לעולם לא נשמור plaintext password.

---

# 16. Authentication Model

לא משתמשים ב:

```text
JWT
cookies
access tokens
```

ב-Day 1.

ה-WebSocket עצמו מחזיק session.

---

# 17. ClientSession

לכל connection:

```python
ClientSession:
    websocket
    user_id
```

בהתחלה:

```text
user_id = None
```

כלומר:

```text
connected
but
not authenticated
```

אחרי Login:

```text
user_id = 5
```

כלומר השרת יודע:

```text
this WebSocket belongs to user 5
```

---

# 18. online_users

Runtime-only structure:

```python
online_users = {
    user_id: websocket
}
```

Example:

```text
1 → WebSocket A
2 → WebSocket B
```

זה **לא נשמר בדיסק**.

כאשר server נכבה:

```text
online_users disappears
```

וזה תקין.

---

# 19. One Active Connection Per User

ב-Day 1 משתמש יכול להיות מחובר ממקום אחד בלבד.

אם Soma כבר authenticated ו-login נוסף נעשה לאותו account:

```text
USER_ALREADY_ONLINE
```

לא ננהל multi-device sessions כרגע.

---

# 20. Disconnect

כאשר connection נסגר:

```text
WebSocket disconnected
        ↓
find session.user_id
        ↓
remove user from online_users
        ↓
log CLIENT_DISCONNECTED
```

Disconnect **לא** מסיר משתמש מה-room.

Room membership הוא persistent.

---

# 21. Reconnect

אין reconnect אוטומטי.

אם connection נפל:

```text
client reconnects
        ↓
new WebSocket
        ↓
login again
        ↓
new ClientSession
```

זה מספיק ל-Day 1.

---

# 22. WebSocket Ping/Pong

נשתמש ב-heartbeat המובנה של ספריית `websockets`.

לא נכתוב custom Ping/Pong.

מטרתו:

```text
detect dead connections
```

ולא לזהות מי המשתמש.

זהות המשתמש נמצאת ב:

```text
ClientSession.user_id
```

---

# 23. Protocol

יש רק 3 message envelopes:

```text
REQUEST
RESPONSE
EVENT
```

---

# 24. Request Format

כל בקשה מה-client:

```json
{
  "type": "request",
  "request_id": "1",
  "action": "login",
  "payload": {}
}
```

חובה:

```text
type
request_id
action
payload
```

---

# 25. Response Format — Success

```json
{
  "type": "response",
  "request_id": "1",
  "status": "ok",
  "code": "LOGIN_SUCCESS",
  "payload": {}
}
```

---

# 26. Response Format — Error

```json
{
  "type": "response",
  "request_id": "1",
  "status": "error",
  "code": "AUTHENTICATION_FAILED",
  "message": "Invalid username or password",
  "payload": {}
}
```

`request_id` תמיד מוחזר כמו שהגיע.

---

# 27. Event Format

אירוע server → client:

```json
{
  "type": "event",
  "event": "room_message",
  "payload": {
    "room_id": 1,
    "room_name": "general",
    "sender_id": 1,
    "sender_username": "soma",
    "message": "hello"
  }
}
```

Event אינו response ולכן אין לו `request_id`.

---

# 28. Supported Actions

Day 1 מכיל בדיוק:

```text
signup
login
logout
create_room
list_rooms
join_room
leave_room
send_message
```

לא מוסיפים actions נוספים עד שה-demo עובד.

---

# 29. SIGNUP

Request:

```json
{
  "type": "request",
  "request_id": "1",
  "action": "signup",
  "payload": {
    "username": "soma",
    "password": "password123"
  }
}
```

Success:

```text
SIGNUP_SUCCESS
```

Signup **לא עושה login אוטומטי**.

אחריו client צריך לשלוח `login`.

---

# 30. LOGIN

Request:

```json
{
  "type": "request",
  "request_id": "2",
  "action": "login",
  "payload": {
    "username": "soma",
    "password": "password123"
  }
}
```

Partner B:

```text
find user
↓
verify password
↓
return User
```

Partner A:

```text
session.user_id = user.user_id

online_users[user.user_id] = websocket
```

Response:

```json
{
  "type": "response",
  "request_id": "2",
  "status": "ok",
  "code": "LOGIN_SUCCESS",
  "payload": {
    "user_id": 1,
    "username": "soma"
  }
}
```

---

# 31. LOGOUT

Request:

```json
{
  "type": "request",
  "request_id": "3",
  "action": "logout",
  "payload": {}
}
```

Server:

```text
remove from online_users
↓
session.user_id = None
```

WebSocket יכול להישאר פתוח.

Response:

```text
LOGOUT_SUCCESS
```

---

# 32. CREATE_ROOM

Authentication required.

Request:

```json
{
  "type": "request",
  "request_id": "4",
  "action": "create_room",
  "payload": {
    "name": "general"
  }
}
```

Server:

```text
authenticated?
↓
room name already exists?
↓
create room
↓
admin = current user
↓
members = {current user}
↓
persist
```

Response:

```text
ROOM_CREATED
```

---

# 33. LIST_ROOMS

Authentication required.

Request:

```json
{
  "type": "request",
  "request_id": "5",
  "action": "list_rooms",
  "payload": {}
}
```

Response example:

```json
{
  "type": "response",
  "request_id": "5",
  "status": "ok",
  "code": "ROOM_LIST",
  "payload": {
    "rooms": [
      {
        "room_id": 1,
        "name": "general",
        "member": true
      }
    ]
  }
}
```

---

# 34. JOIN_ROOM

Authentication required.

Request:

```json
{
  "type": "request",
  "request_id": "6",
  "action": "join_room",
  "payload": {
    "room_id": 1
  }
}
```

Checks:

```text
authenticated?
room exists?
already member?
```

Then:

```text
add member
↓
persist
```

Success:

```text
ROOM_JOINED
```

---

# 35. LEAVE_ROOM

Authentication required.

Checks:

```text
room exists?
user member?
user admin?
```

If normal member:

```text
remove
↓
persist
```

Success:

```text
ROOM_LEFT
```

---

# 36. SEND_MESSAGE

Authentication required.

Request:

```json
{
  "type": "request",
  "request_id": "7",
  "action": "send_message",
  "payload": {
    "room_id": 1,
    "message": "hello everyone"
  }
}
```

Business checks:

```text
authenticated?
↓
room exists?
↓
sender is room member?
```

If valid:

```text
RoomService returns room members
```

Then Partner A:

```text
room members
      ∩
online_users
      ↓
online recipients
```

Server sends `room_message` event to every online member of the room.

---

# 37. Sender Receives the Event Too

Decision:

```text
Server broadcasts the message
to ALL online room members,
including the sender.
```

The client therefore should **not locally print a sent message**.

It prints it only when it receives the server event.

Benefits:

```text
one source of truth
no duplicate messages
same behavior for every client
```

---

# 38. Offline Users

If user belongs to the room but isn't online:

```text
skip
```

No queue.

No offline delivery.

No message history.

---

# 39. AuthService Interface

Partner A may only interact with authentication through:

```python
AuthService.signup(username, password) -> User

AuthService.login(username, password) -> User
```

Domain errors are raised as `AppError`.

Partner A never directly reads `users.json`.

---

# 40. RoomService Interface

```python
RoomService.create_room(user_id, name) -> Room

RoomService.list_rooms(user_id) -> list

RoomService.join_room(user_id, room_id) -> Room

RoomService.leave_room(user_id, room_id) -> Room

RoomService.get_room(room_id) -> Room

RoomService.authorize_message(
    user_id,
    room_id
) -> Room
```

Partner A never directly modifies room membership.

---

# 41. AppError

Shared error:

```python
AppError:
    code
    message
```

Example:

```text
raise AppError(
    "ROOM_NOT_FOUND",
    "Room does not exist"
)
```

Dispatcher catches it and converts it into standard protocol response.

---

# 42. Protocol Validation — Partner A

Before dispatch:

```text
valid JSON?
↓
top-level object?
↓
type == "request"?
↓
request_id exists?
↓
action exists?
↓
payload is object?
↓
action known?
↓
required fields exist?
↓
correct field types?
```

---

# 43. Business Validation — Partner B

Examples:

```text
username already exists?
password correct?
room exists?
room name already exists?
already member?
is member?
permission allowed?
```

---

# 44. Input Validation Rules

Username:

```text
3–32 characters
letters
numbers
underscore
```

Password:

```text
8–128 characters
```

Room name:

```text
1–40 characters
non-empty after strip
```

Message:

```text
1–1000 characters
non-empty after strip
```

---

# 45. Error Codes

Protocol:

```text
INVALID_JSON
INVALID_REQUEST
INVALID_PAYLOAD
UNKNOWN_ACTION
```

Authentication:

```text
USERNAME_TAKEN
SIGNUP_SUCCESS
AUTHENTICATION_FAILED
LOGIN_SUCCESS
ALREADY_AUTHENTICATED
USER_ALREADY_ONLINE
NOT_AUTHENTICATED
LOGOUT_SUCCESS
```

Rooms:

```text
ROOM_CREATED
ROOM_NAME_TAKEN
ROOM_LIST
ROOM_NOT_FOUND
ROOM_JOINED
ALREADY_ROOM_MEMBER
ROOM_LEFT
NOT_ROOM_MEMBER
ADMIN_CANNOT_LEAVE_ROOM
```

Messages:

```text
MESSAGE_ACCEPTED
MESSAGE_EMPTY
```

Generic:

```text
INTERNAL_ERROR
```

---

# 46. Authentication Guard

These actions are allowed without login:

```text
signup
login
```

Everything else requires:

```text
session.user_id != None
```

So:

```text
create_room
list_rooms
join_room
leave_room
send_message
logout
```

require authentication.

If not:

```text
NOT_AUTHENTICATED
```

---

# 47. Dispatcher Flow

```text
WebSocket receives text
        ↓
protocol.parse()
        ↓
protocol.validate()
        ↓
identify action
        ↓
authentication guard
        ↓
call appropriate service
        ↓
build response
        ↓
WebSocket send
```

---

# 48. Full Signup/Login Flow

```text
CLIENT
 |
 | signup
 v
WebSocket
 |
 v
Server
 |
 v
Protocol Validation
 |
 v
AuthService.signup()
 |
 +--> username available?
 |
 +--> hash password
 |
 +--> create User
 |
 +--> Storage.save_users()
 |
 v
SIGNUP_SUCCESS
 |
 v
CLIENT


CLIENT
 |
 | login
 v
Server
 |
 v
AuthService.login()
 |
 +--> user exists?
 +--> password valid?
 |
 v
returns User
 |
 v
ClientSession.user_id = user.id
 |
 v
online_users[user.id] = websocket
 |
 v
LOGIN_SUCCESS
```

---

# 49. Full Room Flow

```text
Soma
 |
 | create_room("general")
 v
RoomService
 |
 +--> validate name
 +--> ensure unique
 +--> create Room #1
 +--> admin = Soma
 +--> members = {Soma}
 +--> save rooms
 |
 v
ROOM_CREATED


Maya
 |
 | join_room(1)
 v
RoomService
 |
 +--> room exists?
 +--> already member?
 +--> add Maya
 +--> save
 |
 v
ROOM_JOINED
```

---

# 50. Full Message Flow

```text
Soma Client
 |
 | send_message
 v
WebSocket
 |
 v
Connection Handler
 |
 v
Protocol Validation
 |
 v
Dispatcher
 |
 v
RoomService.authorize_message()
 |
 +--> authenticated?
 +--> room exists?
 +--> Soma member?
 |
 v
Room returned
 |
 v
MessageRouter
 |
 +--> room.members
 |
 +--> intersect online_users
 |
 v
active WebSockets
 |
 +----------+----------+
 |                     |
 v                     v
Soma                  Maya
event                 event
```

---

# 51. Client Design

CLI only.

Example:

```text
Connected to server.

> signup soma password123
SIGNUP_SUCCESS

> login soma password123
LOGIN_SUCCESS

> create general
ROOM_CREATED: room_id=1

> join 1
ALREADY_ROOM_MEMBER

> send 1 Hello!
[soma @ general]: Hello!
```

Another laptop:

```text
> login maya password123
LOGIN_SUCCESS

> join 1
ROOM_JOINED

[soma @ general]: Hello!

> send 1 Hi Soma!
[maya @ general]: Hi Soma!
```

---

# 52. Client Concurrency

Client needs two concurrent loops:

```text
             Client
               |
        +------+------+
        |             |
        v             v
   user input      server receive
        |             |
        v             v
      SEND          DISPLAY
```

Receiving messages must continue while user is typing.

---

# 53. Request IDs

Client maintains:

```python
next_request_id = 1
```

Each outgoing request:

```text
1
2
3
4
...
```

serialized as string.

Example:

```json
"request_id": "4"
```

Response must return the same ID.

---

# 54. Logging

Use Python standard `logging`.

Suggested format:

```text
2026-09-07 10:20:31 | INFO | LOGIN_SUCCESS user_id=1 username=soma
```

---

# 55. Partner A Logs

```text
SERVER_STARTED
CLIENT_CONNECTED
REQUEST_RECEIVED
VALIDATION_FAILED
MESSAGE_ACCEPTED
MESSAGE_DISTRIBUTED
SEND_FAILED
CLIENT_DISCONNECTED
```

---

# 56. Partner B Logs

```text
SIGNUP_SUCCESS
SIGNUP_FAILED
LOGIN_SUCCESS
LOGIN_FAILED
ROOM_CREATED
ROOM_JOINED
ROOM_LEFT
ACCESS_DENIED
```

---

# 57. Never Log

```text
password
password hash
raw authentication payload
```

For messages, log metadata rather than full content:

```text
MESSAGE_ACCEPTED
sender=1
room=3
length=42
```

not:

```text
message="secret text..."
```

This also prepares the project for Day 2 DLP.

---

# 58. Concurrency and Shared State

For Day 1:

```text
one process
one asyncio event loop
```

`users`, `rooms`, and `online_users` live in the same process.

Room/Auth service state-changing methods remain synchronous and contain no `await`.

Therefore an operation such as:

```text
check membership
+
modify membership
+
save
```

runs without another asyncio task interrupting it halfway through.

We do not add locks unless these service methods become asynchronous.

This is a deliberate Day 1 simplification.

---

# 59. Git

Branches:

```text
main

feature/communication-runtime

feature/identity-rooms
```

Partner A:

```text
feature/communication-runtime
```

Partner B:

```text
feature/identity-rooms
```

---

# 60. Git Rules

```text
main must remain runnable.

Do not change shared protocol without telling partner.

Commit small working milestones.

Pull/rebase before integration.

Merge frequently.

Do not wait until everything is finished to integrate.
```

---

# 61. Development Order

## Milestone 0 — Connectivity

Partner A:

```text
server starts
client A connects
client B connects
```

Do this before anything complicated.

PASS when:

```text
two clients can connect simultaneously
```

---

## Milestone 1 — Partner B Domain

In parallel Partner B completes:

```text
User model
Room model
Storage
Password utilities
AuthService
RoomService
```

These should work without WebSocket.

---

## Milestone 2 — Signup/Login Integration

Connect:

```text
WebSocket
→ Dispatcher
→ AuthService
```

PASS:

```text
signup through client
login through client
session.user_id assigned
online_users updated
```

---

## Milestone 3 — Rooms

Integrate:

```text
create_room
list_rooms
join_room
leave_room
```

PASS:

```text
two authenticated users belong to same room
```

---

## Milestone 4 — Messaging

Integrate:

```text
send_message
RoomService authorization
MessageRouter
server events
```

PASS:

```text
Client A sends
Client B receives

Client B sends
Client A receives
```

---

## Milestone 5 — Access Checks

Verify:

```text
unauthenticated create room → denied

non-member send message → denied

unknown room → denied

duplicate join → denied
```

---

## Milestone 6 — Validation

Verify:

```text
invalid JSON
missing action
wrong payload type
unknown action
empty message
```

None may crash the server.

---

## Milestone 7 — Logs + Health

PASS:

```text
GET /health → 200

important actions visible in terminal logs
```

---

## Milestone 8 — Multi-Laptop

Only after local test works.

Setup:

```text
Laptop Server
    |
    +---- Laptop A
    |
    +---- Laptop B
```

Both clients connect to:

```text
ws://SERVER_IP:8765/ws
```

PASS when they can exchange messages.

---

# 62. Minimum Automated Tests

Create:

```text
tests/test_day1.py
```

Minimum cases:

```text
signup creates user

duplicate username rejected

correct login succeeds

incorrect login rejected

create room adds creator

join room adds member

non-member cannot send

member can authorize message

invalid room rejected

leave room removes member
```

Do not spend hours building testing infrastructure.

---

# 63. Manual Demo Script

Before presenting, clear or prepare predictable data.

Start server:

```text
python server.py
```

Health:

```text
GET /health
→ 200 OK
```

Laptop A:

```text
signup soma password123
login soma password123
create general
```

Expected:

```text
ROOM_CREATED room_id=1
```

Laptop B:

```text
signup maya password123
login maya password123
join 1
```

Expected:

```text
ROOM_JOINED
```

Laptop A:

```text
send 1 Hello from Laptop A
```

Laptop B must display:

```text
[soma @ general]: Hello from Laptop A
```

Laptop B:

```text
send 1 Hello from Laptop B
```

Laptop A must display:

```text
[maya @ general]: Hello from Laptop B
```

---

# 64. Access-Control Demo

Create/login another user that isn't a member.

Attempt:

```text
send 1 I'm not a member
```

Expected:

```text
NOT_ROOM_MEMBER
```

And server log:

```text
ACCESS_DENIED
reason=NOT_ROOM_MEMBER
```

This explicitly demonstrates the required access checks.

---

# 65. Validation Demo

Send malformed/invalid request.

Expected:

```text
INVALID_REQUEST
```

or:

```text
INVALID_PAYLOAD
```

Server continues running.

Then perform a valid request to prove it did not crash.

---

# 66. Persistence Demo

Before final demo verify:

```text
create users
create room
stop server
start server
list rooms
```

Users and rooms must still exist.

Online status does not persist.

---

# 67. Day 1 Definition of Done

Day 1 is complete only when ALL are true:

```text
[ ] Git branches exist

[ ] Message format agreed and implemented

[ ] Room model implemented

[ ] asyncio concurrency model implemented

[ ] Task ownership agreed

[ ] WebSocket server runs

[ ] Multiple WebSocket clients connect concurrently

[ ] Signup works

[ ] Passwords are hashed

[ ] Login works

[ ] Authenticated session is connected to WebSocket

[ ] users persist

[ ] rooms persist

[ ] Create room works

[ ] List rooms works

[ ] Join room works

[ ] Leave room works

[ ] Membership access check works

[ ] Room messages work

[ ] Both laptops can send and receive

[ ] Invalid protocol requests are rejected

[ ] Invalid business actions are rejected

[ ] Server does not crash on bad input

[ ] Logs clearly show important actions

[ ] /health returns healthy response

[ ] Server works with clients on different laptops
```

If every checkbox passes:

```text
DAY 1 DONE
```

Stop adding functionality and move to Day 2.

---

# 68. Exact Responsibility Boundary

## Partner A asks Partner B:

```text
Can this user do this?
Who belongs to this room?
Did authentication succeed?
```

## Partner B answers.

Then Partner A handles:

```text
Which socket belongs to the recipient?
Is the recipient online?
How do I send the event?
```

Partner B never does:

```python
websocket.send(...)
```

Partner A never does:

```python
open("rooms.json")
```

This boundary must remain throughout implementation.

---

# 69. Day 2 Preparation

Day 1 message path is intentionally designed as:

```text
Client
  ↓
Protocol
  ↓
Authentication
  ↓
Room authorization
  ↓

[ SECURITY PIPELINE GOES HERE ON DAY 2 ]

  ↓
MessageRouter
  ↓
Recipients
```

Today:

```text
Room authorization
      ↓
MessageRouter
```

Tomorrow:

```text
Room authorization
      ↓
SecurityPipeline
      ↓
DLP
      ↓
Anti-Bot
      ↓
MessageRouter
```

Therefore Day 2 should not require rewriting the WebSocket, rooms, authentication or routing architecture.

---

# 70. Final Architecture

```text
                     CLIENT
                       |
                  WebSocket
                       |
                       v
              +----------------+
              |     SERVER     |
              +----------------+
                       |
                       v
                Protocol Layer
                       |
                       v
                  Dispatcher
                       |
              +--------+--------+
              |                 |
              v                 v
        AuthService        RoomService
              |                 |
              v                 v
           Users              Rooms
              |                 |
              +--------+--------+
                       |
                  Persistence
                       |
              users.json / rooms.json


SEND MESSAGE:

Client
  |
  v
WebSocket
  |
  v
Protocol Validation
  |
  v
Authentication Guard
  |
  v
Room Authorization
  |
  v
[Day 2 Security Pipeline]
  |
  v
MessageRouter
  |
  v
online_users
  |
  v
WebSocket Events
  |
  v
Clients
```

---

# 71. Core Rule for the Team

Until the Day 1 Definition of Done passes:

```text
DO NOT ADD FEATURES.
```

When something isn't required for:

```text
Signup
Login
Rooms
Access checks
Messaging
Validation
Logs
Health
Multi-laptop demo
```

it waits.