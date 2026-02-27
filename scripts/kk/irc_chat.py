"""Quick IRC chat script for debugging — connect, send, listen."""
import asyncio
import sys
import time

IRC_SERVER = "irc.meshrelay.xyz"
IRC_PORT = 6667
NICK = "kk-claude"
CHANNELS = ["#Agents"]


async def irc_session(messages: list[str], listen_seconds: int = 120):
    """Connect to IRC, send messages, listen for replies."""
    reader, writer = await asyncio.open_connection(IRC_SERVER, IRC_PORT)

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
    await send(f"NICK {NICK}")
    await send(f"USER {NICK} 0 * :KK Debug Agent (Claude)")

    # Wait for welcome
    while True:
        line = await recv(15)
        if not line:
            continue
        if " 001 " in line:
            print(f"[CONNECTED] as {NICK}")
            break
        if " 433 " in line:
            NICK_NEW = NICK + "_"
            print(f"[NICK IN USE] retrying as {NICK_NEW}")
            await send(f"NICK {NICK_NEW}")
        if line.startswith("PING"):
            token = line.split("PING ")[-1]
            await send(f"PONG {token}")

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

    # Listen for replies
    print(f"\n[LISTENING] for {listen_seconds}s...")
    deadline = time.time() + listen_seconds
    conversation = []

    while time.time() < deadline:
        line = await recv(5.0)
        if not line:
            continue

        if line.startswith("PING"):
            token = line.split("PING ")[-1]
            await send(f"PONG {token}")
            continue

        if "PRIVMSG" in line:
            try:
                prefix, _, rest = line.partition(" PRIVMSG ")
                sender = prefix.split("!")[0].lstrip(":")
                channel, _, message = rest.partition(" :")
                ts = time.strftime("%H:%M:%S")
                entry = f"[{ts}] {sender} @ {channel}: {message}"
                print(entry)
                conversation.append(entry)
            except Exception:
                pass

        # Also show JOIN/PART/other useful lines
        if " JOIN " in line or " PART " in line or " QUIT " in line:
            print(f"[NOTICE] {line[:200]}")

    # Disconnect
    await send("QUIT :Thanks, see you on EM!")
    writer.close()
    print(f"\n[DISCONNECTED] Got {len(conversation)} messages")
    return conversation


if __name__ == "__main__":
    messages = sys.argv[1:] if len(sys.argv) > 1 else [
        "Hey! I'm from KK (Karmacadabra). Quick question about the EM API auth.",
    ]
    asyncio.run(irc_session(messages, listen_seconds=120))
