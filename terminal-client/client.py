import asyncio
import json
import os
import threading
from datetime import datetime

import websockets
import pyttsx3
from colorama import init, Fore, Style

init(autoreset=True)

SERVER_URL = "ws://localhost:3000"
MAX_VISIBLE_MESSAGES = 8

messages = []
speak_enabled = True
tts_lock = threading.Lock()


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def speak_text(text: str):
    """
    Text-to-Speech runs in a separate thread
    so it will not freeze the terminal chat.
    """
    def run():
        global speak_enabled

        if not speak_enabled:
            return

        try:
            with tts_lock:
                engine = pyttsx3.init()
                engine.setProperty("rate", 165)
                engine.setProperty("volume", 1.0)
                engine.say(text)
                engine.runAndWait()
                engine.stop()
        except Exception as error:
            print(Fore.RED + f"\n[TTS ERROR] {error}")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()


def add_message(kind: str, content: str):
    timestamp = datetime.now().strftime("%H:%M:%S")

    messages.append({
        "time": timestamp,
        "kind": kind,
        "content": content
    })

    while len(messages) > MAX_VISIBLE_MESSAGES:
        messages.pop(0)


def render_header(user_id: str, channel: str):
    print(Fore.CYAN + "╔════════════════════════════════════════════════════════════╗")
    print(Fore.CYAN + "║" + Fore.WHITE + "              SECURE PTT TERMINAL - TEXT TO TALK           " + Fore.CYAN + "║")
    print(Fore.CYAN + "╠════════════════════════════════════════════════════════════╣")
    print(
        Fore.CYAN + "║ " +
        Fore.WHITE + f"User: {user_id:<18}" +
        Fore.WHITE + f"Channel: {channel:<21}" +
        Fore.CYAN + "║"
    )
    print(
        Fore.CYAN + "║ " +
        Fore.WHITE + f"Server: {SERVER_URL:<49}" +
        Fore.CYAN + "║"
    )
    print(
        Fore.CYAN + "║ " +
        Fore.WHITE + f"TTS: {'ON' if speak_enabled else 'OFF':<52}" +
        Fore.CYAN + "║"
    )
    print(Fore.CYAN + "╚════════════════════════════════════════════════════════════╝")


def render_messages():
    print()
    print(Fore.BLUE + "┌──────────────────── Temporary Messages ───────────────────┐")

    if not messages:
        print(Fore.BLUE + "│" + Fore.WHITE + " No messages yet.                                      " + Fore.BLUE + "│")
    else:
        for msg in messages:
            line = f"[{msg['time']}] {msg['content']}"
            if len(line) > 56:
                line = line[:53] + "..."

            color = Fore.WHITE
            if msg["kind"] == "system":
                color = Fore.MAGENTA
            elif msg["kind"] == "incoming":
                color = Fore.GREEN
            elif msg["kind"] == "own":
                color = Fore.YELLOW
            elif msg["kind"] == "error":
                color = Fore.RED

            print(Fore.BLUE + "│ " + color + f"{line:<56}" + Fore.BLUE + "│")

    print(Fore.BLUE + "└────────────────────────────────────────────────────────────┘")
    print()
    print(Fore.LIGHTBLACK_EX + "Commands:")
    print(Fore.LIGHTBLACK_EX + "  /tts      toggle text-to-speech")
    print(Fore.LIGHTBLACK_EX + "  /clear    clear screen messages")
    print(Fore.LIGHTBLACK_EX + "  /exit     disconnect")
    print()


def render(user_id: str, channel: str):
    clear_screen()
    render_header(user_id, channel)
    render_messages()


async def receive_messages(websocket, user_id: str, channel: str):
    global speak_enabled

    async for raw_message in websocket:
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            add_message("error", "Received invalid message from server")
            render(user_id, channel)
            continue

        msg_type = data.get("type")

        if msg_type == "joined":
            add_message("system", f"Connected to channel: {data.get('channel')}")
            render(user_id, channel)

        elif msg_type == "system":
            add_message("system", data.get("message", "System event"))
            render(user_id, channel)

        elif msg_type == "text-message":
            sender = data.get("from", "unknown")
            text = data.get("text", "")

            add_message("incoming", f"{sender}: {text}")
            render(user_id, channel)

            if speak_enabled:
                speak_text(text)

        elif msg_type == "delivery-status":
            add_message("system", "Message delivered")
            render(user_id, channel)

        elif msg_type == "error":
            add_message("error", data.get("message", "Unknown error"))
            render(user_id, channel)


async def send_messages(websocket, user_id: str, channel: str):
    global speak_enabled

    while True:
        text = await asyncio.to_thread(input, Fore.WHITE + "> ")

        text = text.strip()

        if not text:
            continue

        if text.lower() == "/exit":
            await websocket.close()
            break

        if text.lower() == "/tts":
            speak_enabled = not speak_enabled
            add_message("system", f"TTS {'enabled' if speak_enabled else 'disabled'}")
            render(user_id, channel)
            continue

        if text.lower() == "/clear":
            messages.clear()
            render(user_id, channel)
            continue

        payload = {
            "type": "text-message",
            "text": text
        }

        await websocket.send(json.dumps(payload))

        add_message("own", f"{user_id}: {text}")
        render(user_id, channel)


async def main():
    clear_screen()

    print(Fore.CYAN + "SECURE PTT TERMINAL")
    print(Fore.WHITE + "Legitimate temporary text-to-talk communication client")
    print()

    user_id = input("Enter user name: ").strip()
    channel = input("Enter channel: ").strip()

    if not user_id or not channel:
        print(Fore.RED + "User name and channel are required.")
        return

    try:
        async with websockets.connect(SERVER_URL) as websocket:
            join_payload = {
                "type": "join",
                "userId": user_id,
                "channel": channel
            }

            await websocket.send(json.dumps(join_payload))

            render(user_id, channel)

            receive_task = asyncio.create_task(
                receive_messages(websocket, user_id, channel)
            )

            send_task = asyncio.create_task(
                send_messages(websocket, user_id, channel)
            )

            done, pending = await asyncio.wait(
                [receive_task, send_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

    except ConnectionRefusedError:
        print(Fore.RED + "Could not connect to server. Make sure server.js is running.")
    except websockets.exceptions.InvalidURI:
        print(Fore.RED + "Invalid server URL.")
    except websockets.exceptions.ConnectionClosed:
        print(Fore.YELLOW + "Connection closed.")
    except Exception as error:
        print(Fore.RED + f"Unexpected error: {error}")


if __name__ == "__main__":
    asyncio.run(main())