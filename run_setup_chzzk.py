import webbrowser
import secrets
import asyncio
import queue
import time

from http.server import HTTPServer
import threading
from loguru import logger

from src.chzzk import CLIENT_ID, CLIENT_SECRET
from src.chzzk.auth import ChzzkAuth, CallbackHandler
from src.chzzk.client import ChzzkClient

RECV_HOST = "localhost"
RECV_PORT = 8080
RECV_URL = f"http://{RECV_HOST}:{RECV_PORT}"
REDIRECT_URI = f"{RECV_URL}/callback"


def authenticate_chzzk(auth: ChzzkAuth):
    temporal_state = secrets.token_urlsafe(16)

    q = queue.Queue()
    server = HTTPServer((RECV_HOST, RECV_PORT), CallbackHandler)
    CallbackHandler.response_queue = q
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    logger.info(f"Callback server started on {RECV_URL}")

    def open_browser():
        time.sleep(1)
        auth_url = auth.get_auth_url(temporal_state)
        webbrowser.open(auth_url)

    logger.info("Opening web browser for user authentication in 1 second...")
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    received_code = None
    received_state = None
    while server_thread.is_alive() or not q.empty():
        try:
            # Check queue without blocking for a long time (timeout=0.1s)
            received_code, received_state = q.get_nowait()
            logger.info(
                f"Received code={received_code}, state={received_state}")
            break
        except queue.Empty:
            # No item in queue yet, continue looping/doing other main thread work
            time.sleep(0.1)

    server_thread.join()
    browser_thread.join()

    try:
        if not received_code or not received_state:
            logger.error("Failed to get authorization code and state")
        return (received_code, received_state)
    finally:
        server.shutdown()


async def start():
    auth = ChzzkAuth(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
    code, state = authenticate_chzzk(auth)
    client = ChzzkClient(auth, code, state)
    await client.start()


if __name__ == "__main__":
    asyncio.run(start())
