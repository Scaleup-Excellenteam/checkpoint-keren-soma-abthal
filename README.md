# Check Point Secure Chat

## 1. Project Overview

This project is a real-time, authenticated chat server with persistent users and rooms, WebSocket communication, and server-side security controls that evaluate every outgoing room message before broadcast.

The implementation was built in two milestones:

- **Day 1 – Infrastructure:** WebSocket communication, an HTTP health endpoint, signup/login, authenticated users, rooms, access checks, request validation, JSON persistence, structured logging, and multi-client communication.
- **Day 2 – Security:** per-user Anti-Bot rate limiting, VirusTotal domain reputation checking, rule-based DLP, semantic DLP with local embeddings, common ALLOW/BLOCK decisions and reason codes, security logs, and automated tests.

## 2. High-Level Architecture

```text
Client
  ↓ WebSocket
Server
  ↓
Authentication / Authorization
  ↓
Anti-Bot
  ↓
URL / Domain Reputation
  ↓
Rule-Based DLP
  ↓
Semantic DLP
  ↓
ALLOW / BLOCK
  ↓
Room Broadcast
```

Authentication and room membership are checked first. All security controls run before the message is broadcast; a blocked message is returned only as an error response to its sender, and the connection remains open.

## 3. Security Controls

### Anti-Bot

The Anti-Bot control applies an in-memory sliding-window rate limit per authenticated `user_id`, independent of the WebSocket connection. The default demo policy allows 5 messages in 5 seconds. A sixth message inside that window is blocked with `ANTIBOT_RATE_LIMIT`; the user is not disconnected or banned.

Both the message limit and window are configurable. These defaults are a demonstration policy, not universal security values.

### URL / Domain Reputation

The URL control detects HTTP/HTTPS URLs and bare domains, extracts and normalizes each hostname, and queries the existing VirusTotal API v3 domain report. It never opens the user-provided website and does not submit it for scanning. VirusTotal supplies reputation signals; this server applies the policy:

| VirusTotal signal | Decision | Reason code |
|---|---|---|
| `malicious >= 3` | Block | `URL_MALICIOUS` |
| `malicious >= 1` and `suspicious >= 2` | Block | `URL_HIGH_RISK` |
| Otherwise | Allow | `URL_REPUTATION_OK` |
| No domain report | Allow | `URL_REPUTATION_UNKNOWN` |
| Missing key, timeout, quota/rate limit, or service failure | Allow | `URL_CHECK_UNAVAILABLE` |

Results are cached in memory per normalized domain for 10 minutes by default; unavailable checks are not cached. The TTL is configurable. This version evaluates **domain reputation**, not full URL reputation.

### DLP – Rule Based

Demo protected data is kept separately in [`data/protected_recipe.json`](data/protected_recipe.json) as identified recipe fragments. The DLP normalizer lowercases text, normalizes Unicode, removes simple punctuation differences, and collapses whitespace. Direct matches against normalized protected fragments are blocked before broadcast with `DLP_PROTECTED_CONTENT`.

### DLP – Semantic Embeddings

Messages that pass direct matching are compared semantically with every protected fragment using the local Sentence Transformers model `sentence-transformers/all-MiniLM-L6-v2` and cosine similarity. Protected fragment embeddings are computed once and reused, and the model is loaded once on first use.

The configured demo threshold is `0.80`. A score at or above the threshold blocks the message with `DLP_SEMANTIC_MATCH`; lower scores produce `DLP_OK`. Similarity is a signal, and `0.80` is a tunable policy that should be validated against representative data. Embedding work runs through `asyncio.to_thread()` so inference does not block the WebSocket event loop.

## 4. Security Decision Format

Every control returns the common `SecurityDecision` fields:

- `allowed`: whether processing may continue
- `control`: the control that made the decision, such as `ANTI_BOT`, `URL`, or `DLP`
- `action`: `ALLOW` or `BLOCK_MESSAGE`
- `reason_code`: a stable machine-readable explanation

```python
SecurityDecision(
    allowed=True,
    control="ANTI_BOT",
    action="ALLOW",
    reason_code="ANTIBOT_OK",
)

SecurityDecision(
    allowed=False,
    control="URL",
    action="BLOCK_MESSAGE",
    reason_code="URL_MALICIOUS",
)
```

## 5. Structured Logging

Application logs use Python's standard `logging` module and include timestamps, levels, event names, usernames/user IDs when known, room names/IDs when relevant, decisions, actions, reason codes, and message lengths. DLP decisions can also include the matched fragment ID and a rounded similarity score.

Application events remain visible at INFO level. Noisy ML and HTTP dependency loggers are limited to WARNING and above, so genuine third-party warnings and errors remain visible.

Logs do **not** contain passwords, password hashes, API keys, authentication tokens, full message contents, or protected recipe contents.

## 6. Repository Structure

```text
server/                    WebSocket server, protocol/session handling, logging
client/client.py           Interactive WebSocket CLI client
security/                  SecurityDecision, Anti-Bot, URL reputation, and DLP
data/protected_recipe.json Demo protected fragments
data/users.json            Persistent users
data/rooms.json            Persistent rooms and memberships
scripts/                   End-to-end Anti-Bot and DLP demo clients
tests/                     Unit and integration-level tests
auth_service.py            Signup/login service
room_service.py            Room operations and authorization
storage.py                 JSON persistence
requirements.txt           Python dependencies
```

## 7. Setup

Python 3.10 or newer is required by the current type syntax. The current test run uses Python 3.12.3.

```bash
git clone https://github.com/Scaleup-Excellenteam/checkpoint-keren-soma-abthal.git check-point
cd check-point

python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate the environment with:

```powershell
venv\Scripts\Activate.ps1
```

The public Sentence Transformers model may be downloaded on the first message that reaches semantic DLP and is cached by the model tooling afterward. A Hugging Face token is not required by this application.

## 8. Environment Variables

Set a VirusTotal API key to enable live domain reputation reports:

```bash
export VIRUSTOTAL_API_KEY="YOUR_API_KEY"
```

Never commit the key. If the key or VirusTotal service is unavailable, domain checks fail open with `URL_CHECK_UNAVAILABLE`; the remaining controls and chat continue to operate.

## 9. Run the Server

From the repository root with the virtual environment active:

```bash
python -m server.server
```

The server listens on:

- Host: `0.0.0.0`
- Port: `8765`
- WebSocket path: `/ws`
- Local URL: `ws://localhost:8765/ws`
- Health URL: `http://localhost:8765/health`

Verify the server from another terminal:

```bash
curl -i http://127.0.0.1:8765/health
```

The response is HTTP 200 with `Content-Type: application/json` and body `{"status":"ok"}`.

## 10. Run a Client

In another terminal:

```bash
source venv/bin/activate
python client/client.py
```

The interactive commands are:

```text
signup <username> <password>
login <username> <password>
logout
create <room name>
list
join <room_id>
leave <room_id>
send <room_id> <message>
```

Signup creates an account; log in afterward before using room operations. Creating a room also makes its creator a member.

## 11. Two-Laptop Demo

1. Connect both laptops to a network where they can reach each other.
2. On the server laptop, complete setup and run `python -m server.server`.
3. Find the server laptop's LAN/Wi-Fi IP address and ensure inbound TCP port `8765` is reachable through its firewall/network configuration.
4. On the second laptop, set `SERVER_URL` in `client/client.py` to `ws://<SERVER_LAN_IP>:8765/ws`.
5. Run `python client/client.py` on both laptops, authenticate separate users, and join the same room.

No Windows/WSL `portproxy` configuration is included in the current repository; use only what the actual lab network requires.

## 12. Demo Scripts

The scripts connect to an already-running server. The supplied user must be registered and a member of the supplied room.

### Anti-Bot

```bash
python scripts/demo_antibot.py <username> <password> <room_id>
```

With the default policy, the first five immediate messages are accepted and the sixth is blocked with `ANTIBOT_RATE_LIMIT`.

### DLP

```bash
python scripts/demo_dlp.py <username> <password> <room_id>
```

This sends real messages through the running WebSocket server and spaces them out to avoid the Anti-Bot limit. Its expected-result labels were written for rule-based DLP Step 1: some paraphrases are still marked as expected `MESSAGE_ACCEPTED`, and its broadcast display recognizes only `DLP_PROTECTED_CONTENT` as a block. With semantic DLP enabled, a correct `DLP_SEMANTIC_MATCH` may therefore appear as `CHECK` or `NOT SEEN`; inspect the server reason code and security log for the current result.

Both scripts accept `--url ws://<host>:8765/ws`; the DLP script also accepts `--delay <seconds>`.

## 13. Tests

```bash
python -m pytest -q
```

Current verified result on 2026-09-08 with Python 3.12.3: **55 passed**.

Automated tests use fake embedding and VirusTotal backends where needed, so they do not require a live API call or model download.

## 14. Known Limitations

- Anti-Bot currently focuses on per-user message rate limiting and keeps state only in memory.
- VirusTotal checks domain reputation rather than full URL reputation, depends on an external service with API quotas, and fails open when unavailable.
- Embedding similarity can produce false positives and false negatives; the semantic threshold requires production-specific tuning.
- DLP has no cross-message, user-history, or cross-room context and no LLM-based reasoning.
- Sophisticated obfuscation can bypass the current conservative normalization and similarity policy.
- The protected pizza recipe is demo data, not a production secrets store or secrets-management design.
- In-memory security caches and rate-limit state are local to one server process.

## 15. Final Demo Flow

1. Start the server and keep its structured logs visible.
2. Connect and authenticate two clients.
3. Create a room and have both users join it.
4. Send a safe message and confirm both clients receive it.
5. Trigger Anti-Bot and confirm the violating message is blocked with `ANTIBOT_RATE_LIMIT`.
6. Send a safe URL/domain and confirm it is allowed.
7. Send a malicious test domain whose VirusTotal report meets the policy and confirm `URL_MALICIOUS` or `URL_HIGH_RISK`.
8. Send an exact protected recipe fragment and confirm `DLP_PROTECTED_CONTENT` without broadcast.
9. Send a paraphrase that exceeds the configured similarity threshold and confirm `DLP_SEMANTIC_MATCH` without broadcast.
10. Show the structured `SECURITY_DECISION` logs and reason codes.
11. Run `python -m pytest -q`.
