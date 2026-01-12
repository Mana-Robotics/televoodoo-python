# Specification: Wi‑Fi Pose Streaming (UDP + mDNS/Bonjour) as an Alternative to BLE

## Goal

Extend the existing Python package (macOS + Ubuntu), which currently creates a BLE peripheral for receiving a pose data stream from an iPhone app, with a second transport option: **Wi‑Fi**.

- **Discovery**: the iPhone automatically finds the PC on the same Wi‑Fi via mDNS/Bonjour
- **Streaming**: the iPhone streams pose data to the PC via UDP with minimal latency
- **Data format**: a small binary packet (struct)
- **Robustness**: sequence number + timestamp; **latest-wins** in the app (iOS side)
- **Security**: simple pairing/token (pre-shared token) optional, but planned

The BLE shall also incorporate the new Data format (binary) but other than that the BLE backend remains unchanged.

## Non-goals

- No WAN/Internet/NAT traversal
- No guaranteed delivery (UDP) — drops are acceptable
- No TLS/DTLS (optional later)

## API / Configuration (Python)

### New transport backend

- **Name**: `wifi_udp`

### Selection via CLI and/or config

- `--transport ble|wifi`
- `--wifi-port <int>`
  - Default: `50000`
  - Note: UDP receive port on the **PC**. Poses are streamed **iPhone → PC**. **One port is used for everything** (handshake, keepalive, BYE, and pose packets).
- `--service-name <string>`
  - Default: `PoseStream`
- `--pairing-token <string>`
  - Default: random at startup; print in logs

## Lifecycle

- **Start**: announce service + start handshake listener + provide streaming loop
- **Stop**: unregister service + close sockets

## Network discovery (mDNS/Bonjour)

### Service type

- `_televoodoo._udp.local.`
- **Recommendation**: `_televoodoo._udp.local.` (makes it explicit UDP is used)

### Service instance name

- `${service_name} (${hostname})` or e.g. `PoseStream._televoodoo._udp.local.`

### TXT records (properties)

| Key | Example | Meaning |
| --- | --- | --- |
| `v` | `1` | Protocol version |
| `transport` | `udp` | Transport |
| `format` | `struct_v1` | Payload format |
| `handshake_port` | `50000` | Port on the PC to which the iPhone sends `HELLO` |
| `token_required` (optional) | `0` / `1` | Token validation enabled |

### IP/interface

The PC announces the IPv4 address of the active Wi‑Fi interface (or all matching interfaces). Minimal requirement: best-effort “default route” IP.

### Python lib

- Use `zeroconf`.

## Handshake / Session setup

UDP pose streaming is **iPhone → PC**. The PC must know which client is allowed to send poses (single-client safety) and which source it should accept packets from. Solution: **the iPhone sends `HELLO` to the PC**, and the PC locks the session to `(src_ip, src_port)` (UDP source address/port).

### Single-client safety mode (required)

For safety, the service must be **exclusive**:

- Once a client session is active, the server **must not** accept a different client.
- While a session is active, only `HELLO` from the **same** `(src_ip, src_port)` is accepted (keepalive / refresh).
- `HELLO` from a **different** client must be rejected/ignored (recommended: respond with `ACK` status `busy`).
- A new client may only connect after the previous session is considered **closed** (see **Session timeout** and **BYE_v1**).

### Ports

- The PC opens **one** UDP socket on `handshake_port` (default e.g. `50000`) and listens.
- The iPhone should bind its UDP socket to a fixed local port (referred to as `client_port`) so that the source port is stable, and optionally listen on the same port for any PC → iPhone datagrams.
- The iPhone sends **all** WIFI datagrams to the PC’s `handshake_port`:
  - `HELLO_v1` (keepalive / session lock)
  - `BYE_v1` (explicit close, recommended)
  - `POSE_v1` (pose stream)

### Handshake packet format

Handshake packets can be binary or very small JSON. Recommendation: **binary** (handshakes are rare; minimal overhead). For simplicity: binary struct.

#### HELLO_v1 (Client → PC)

- `magic`: 4 bytes ASCII `"POSE"`
- `msg_type`: `uint8 = 1`
- `version`: `uint8 = 1`
- `client_port`: `uint16` (UDP port bound on the iPhone; should match the UDP source port; can be used as the return port for optional PC → iPhone datagrams)
- `token_len`: `uint8` (`0..32`)
- `token`: `bytes[token_len]`

**PC validation:**

- validate `magic`/`version`
- if `token_required`: match token
- session handling:
  - if no active session: set `current_client = (src_ip, src_port)` and `last_hello_ts = now`
  - if active session and `(src_ip, src_port)` matches `current_client`: update `last_hello_ts = now`
  - if active session and client differs: reject (recommended: `ACK` with status `busy`)

#### ACK_v1 (PC → Client, optional)

- `magic`: `"POSE"`
- `msg_type`: `uint8 = 2`
- `version`: `uint8 = 1`
- `server_time_ms`: `uint32` (optional)
- `stream_port`: `uint16` (optional; if present, typically equals `handshake_port`)
- `status`: `uint8`
  - `0 = ok`
  - `1 = bad_token`
  - `2 = unsupported_version`
  - `3 = busy` (another client is currently connected)

#### BYE_v1 (Client → PC, recommended)

Because UDP is connectionless, “closing” a session should be explicit when possible. The active client should send `BYE` when it intentionally stops.

- `magic`: 4 bytes ASCII `"POSE"`
- `msg_type`: `uint8 = 4`
- `version`: `uint8 = 1`

**Server behavior:**

- If `BYE` comes from `current_client`: close session immediately (`current_client = None`)
- If `BYE` comes from a different client: ignore

### Session timeout

- If `now - last_hello_ts > 5s`: stop streaming / invalidate client
- The iPhone sends `HELLO` every `1s` (keepalive) or on reconnect

### Keepalive efficiency / latency impact (requirements)

Keepalive must **not** measurably impact pose streaming latency.

- **Do not put keepalive on the hot path**: pose sending must never block on handshake/keepalive handling.
- **Server-side design**:
  - Run the handshake/keepalive receiver on a dedicated thread/task (or non-blocking socket + `select`/poll).
  - On each valid keepalive, do only \(O(1)\) work: validate header and update `last_hello_ts` (and optionally re-send `ACK`).
  - Avoid allocations/log spam per keepalive; rate-limit logs.
- **Client-side design (iOS)**:
  - Keepalive rate `1 Hz` is sufficient for a `5s` timeout.
  - Keepalive should reuse `HELLO_v1` (small fixed-size binary), not JSON.
  - Send keepalive from a timer/dispatch source separate from render / pose receiver loops.

### Using other client traffic as liveness (recommended)

If the iPhone is already sending other packets to the server during control (e.g. “incoming poses” / control updates), those packets can serve as a keepalive signal.

- **Rule**: while a session is active, *any* valid datagram received from `current_client` may refresh liveness (i.e. update a `last_seen_ts` timestamp), not only `HELLO_v1`.
- **Safety**: liveness must be based on **incoming** packets from the active client (iPhone → PC).
- **Adaptive keepalive**: the client may send `HELLO_v1` at `1 Hz` **only when** it has not sent any other control packets within the last ~1s; otherwise it can skip dedicated keepalives.

## Multi-client behavior

Define explicitly:

- **Exactly one active client at a time**: the server accepts packets from a single `(src_ip, src_port)` only.
- **No replacement**: `HELLO` from other clients must be rejected while a session is active (safety requirement).
- **No multi-client support**: no broadcast, no parallel sessions.

## Optional reverse messages (PC → iPhone)

Secondary features that send data from the PC back to the iPhone do **not** require an additional PC port.

- The PC can send UDP datagrams back to the active client’s `(src_ip, src_port)` learned from `HELLO` (or to `client_port` if you choose to explicitly use that as the return port).
- This requires the iPhone to have a UDP socket bound/listening (typically the same socket/port it uses to send).

### Latency considerations

Using the same UDP port does **not** inherently add latency to the iPhone → PC pose stream. Latency issues only arise if reverse traffic competes for CPU time, socket buffers, or Wi‑Fi airtime.

- Keep PC → iPhone packets **small** and **infrequent** (status/force feedback at low rate).
- Ensure the PC’s pose receive loop is **not blocked** by reverse sends:
  - handle pose receive and reverse sends on separate threads/tasks, or use non-blocking I/O
  - avoid per-packet logging/allocations on the pose path
- If reverse traffic becomes **high-rate** (e.g. **30 Hz** force feedback), it can still be fine, but it must be designed as “latest-only”:
  - do not queue/backlog reverse messages; if the send loop is behind, **drop** and send only the newest values
  - keep packets **very small** (ideally << MTU; target <= ~64–128 bytes payload) to reduce Wi‑Fi airtime per message
  - rate-limit to the minimum required; prefer 10–30 Hz and only use higher rates if truly needed
- A second port is usually unnecessary (it does not change Wi‑Fi airtime), but it can help with implementation separation/observability if you want strict isolation.

## Pose streaming packet (binary)

### Goals

- small
- endianness defined
- stable / versioned
- fits into a single UDP datagram (<< MTU)

### Packet: POSE_v1 (iPhone → PC)

- `magic`: 4 bytes `"POSE"`
- `msg_type`: `uint8 = 3`
- `version`: `uint8 = 1`
- `seq`: `uint16` (rollover ok)
- `timestamp_us`: `uint64` (monotonic or unix; document which)
- `position`: 3 × `float32` (`x,y,z`)
- `orientation`: 4 × `float32` (`qx,qy,qz,qw`) (quaternion)

**Optional fields** (only if needed; otherwise omit):

- `flags`: `uint16` (bitfield)
- `confidence`: `float32`
- `frame_id`: `uint8`

**Total without optionals:**

- `4 + 1 + 1 + 2 + 8 + (7*4 = 28) = 44 bytes`

### Python packing

Network byte order / big-endian:

```python
struct.pack("!4sBBHQ7f", ...)
```

Note: `Q = uint64`.

### iOS parsing

- Fixed-size parse, validate `magic`/`type`/`version`/`len`
- Use `seq` for drop/ordering stats
- “latest wins” rendering: apply only the newest pose

## Performance / latency requirements

- Send rate: **60 Hz** nominal (16.666 ms)
- Sender may be “latest only” (no backlog)
- Latency goal: as low as possible; no additional buffering in the sender
- iOS may optionally use 0–1 frame of buffering for smoothing, but default: 0 buffer

## Python implementation details

### Threads / async

- Handshake receiver: dedicated thread or asyncio task
- Pose sender: timer loop (`sleep 1/60`) or event-driven (if the pose producer provides events)
- Pose data source: reuse the existing pose pipeline (same as BLE)

### Socket options

- `socket.AF_INET`, `socket.SOCK_DGRAM`
- optional: `SO_REUSEADDR` for the handshake socket
- optional: set send buffer (`SO_SNDBUF`) moderately
- not needed: Nagle etc. (UDP)

### Logging/telemetry

Print on startup:

- active IP
- `handshake_port`
- service name
- token (or token hint)

Stats (optional):

- sent fps
- dropped/late client (no `HELLO`)

### Packaging

- New dependency: `zeroconf`
- Keep macOS/Ubuntu compatibility

## iOS requirements (reference only)

(Agent primarily implements Python, but the protocol must match on iOS.)

- Bonjour browse `_televoodoo._udp`
- Resolve service → server IP + `handshake_port` (from TXT)
- UDP listener on `client_port`
- Send `HELLO` every `1s`
- Parse `POSE` packets

## Test plan

- Unit test: struct pack/unpack roundtrip (Python)
- Local test: two processes on one machine (simulate client via UDP)
- LAN test: macOS/Ubuntu → iPhone

Verify:

- discovery works
- `HELLO` establishes session
- streaming stable at 60 Hz
- session timeout stops streaming
- a second client is rejected while the first session is active (ACK status `busy`)