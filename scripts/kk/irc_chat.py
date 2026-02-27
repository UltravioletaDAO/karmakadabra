"""IRC chat script for KK agent conversations on MeshRelay.

Features:
  - Auto-extends timeout when conversation is active
  - Graceful disconnect with reason
  - PING/PONG keep-alive handling
  - Nick collision recovery with timestamp suffix
"""
import asyncio
import sys
import time

IRC_SERVER = "irc.meshrelay.xyz"
IRC_PORT = 6667
NICK = "kk-claude"
CHANNELS = ["#Agents"]

# Timeout config
IDLE_TIMEOUT = 300       # Disconnect after 5 min of silence (no messages)
MAX_SESSION = 1800       # Hard cap: 30 min max session
ACTIVITY_EXTENSION = 120 # Each message resets idle timer by 2 min


async def irc_session(
    messages: list[str],
    listen_seconds: int = IDLE_TIMEOUT,
    max_seconds: int = MAX_SESSION,
):
    """Connect to IRC, send messages, listen for replies.

    The session stays alive as long as there is conversation activity,
    up to max_seconds. Disconnects gracefully after idle_timeout of silence.
    """
    reader, writer = await asyncio.open_connection(IRC_SERVER, IRC_PORT)
    current_nick = NICK

    async def send(msg: str):
        writer.write(f"{msg}\r\n".encode("utf-8"))
        await writer.drain()

    async def recv(timeout: float = 10.0) -> str:
        try:
            data = await asyncio.wait_for(reader.readline(), timeout=timeout)
            return data.decode("utf-8", errors="replace").strip()
        except asyncio.TimeoutError:
            return ""

    # Register
    await send(f"NICK {current_nick}")
    await send(f"USER {current_nick} 0 * :KK Agent (Karmacadabra - Ultravioleta DAO)")

    # Wait for welcome
    attempts = 0
    while attempts < 10:
        line = await recv(15)
        if not line:
            attempts += 1
            continue
        if " 001 " in line:
            print(f"[CONNECTED] as {current_nick}")
            break
        if " 433 " in line:
            current_nick = f"{NICK}-{int(time.time()) % 10000}"
            print(f"[NICK IN USE] retrying as {current_nick}")
            await send(f"NICK {current_nick}")
        if line.startswith("PING"):
            token = line.split("PING ")[-1]
            await send(f"PONG {token}")
    else:
        print("[ERROR] Failed to connect after 10 attempts")
        writer.close()
        return []

    # Join channels
    for ch in CHANNELS:
        await send(f"JOIN {ch}")
        print(f"[JOINED] {ch}")

    await asyncio.sleep(2)

    # Send messages
    for msg in messages:
        for ch in CHANNELS:
            await send(f"PRIVMSG {ch} :{msg}")
            print(f"[SENT -> {ch}] {msg}")
        await asyncio.sleep(1)

    # Listen with adaptive timeout
    session_start = time.time()
    last_activity = time.time()
    conversation = []

    print(f"\n[LISTENING] idle timeout={listen_seconds}s, max session={max_seconds}s")

    while True:
        now = time.time()

        # Hard session limit
        if now - session_start >= max_seconds:
            print(f"\n[MAX SESSION] {max_seconds}s reached, disconnecting")
            break

        # Idle timeout (no messages received)
        if now - last_activity >= listen_seconds:
            print(f"\n[IDLE TIMEOUT] No activity for {listen_seconds}s, disconnecting")
            break

        line = await recv(5.0)
        if not line:
            continue

        # PING keep-alive
        if line.startswith("PING"):
            token = line.split("PING ")[-1]
            await send(f"PONG {token}")
            continue

        # Chat messages
        if "PRIVMSG" in line:
            try:
                prefix, _, rest = line.partition(" PRIVMSG ")
                sender = prefix.split("!")[0].lstrip(":")
                channel, _, message = rest.partition(" :")
                ts = time.strftime("%H:%M:%S")
                entry = f"[{ts}] {sender} @ {channel}: {message}"
                print(entry)
                conversation.append(entry)

                # Reset idle timer on real messages (not our own)
                if sender != current_nick:
                    last_activity = time.time()
            except Exception:
                pass

        # Show JOIN/PART/QUIT
        if " JOIN " in line or " PART " in line or " QUIT " in line:
            print(f"[NOTICE] {line[:200]}")

    # Graceful disconnect
    elapsed = int(time.time() - session_start)
    await send(f"QUIT :Session ended after {elapsed}s — {len(conversation)} messages. See you on EM!")
    writer.close()
    print(f"\n[DISCONNECTED] {len(conversation)} messages in {elapsed}s")
    return conversation


if __name__ == "__main__":
    messages = sys.argv[1:] if len(sys.argv) > 1 else [
        "Hey! I'm from KK (Karmacadabra). Quick question about the EM API auth.",
    ]
    asyncio.run(irc_session(messages, listen_seconds=IDLE_TIMEOUT, max_seconds=MAX_SESSION))
