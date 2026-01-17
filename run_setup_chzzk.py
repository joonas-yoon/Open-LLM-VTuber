import webbrowser
import secrets
import asyncio
import os
import queue
import time

from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from urllib.parse import urlparse, parse_qs
from loguru import logger

from src.chzzk.Auth import ChzzkAuth, CallbackHandler

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.chzzk.env'))


def authenticate_chzzk():
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    RECV_HOST = "localhost"
    RECV_PORT = 8080
    RECV_URL = f"http://{RECV_HOST}:{RECV_PORT}"
    REDIRECT_URI = f"{RECV_URL}/callback"
    logger.info(f"Expected REDIRECT_URI: {REDIRECT_URI}")
    temporal_state = secrets.token_urlsafe(16)

    auth = ChzzkAuth(CLIENT_ID, CLIENT_SECRET)

    q = queue.Queue()
    server = HTTPServer((RECV_HOST, RECV_PORT), CallbackHandler)
    CallbackHandler.response_queue = q  # 큐 설정
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    logger.info(f"Callback server started on {RECV_URL}")

    def open_browser():
        time.sleep(1)
        auth_url = auth.get_auth_url(REDIRECT_URI, temporal_state)
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


async def main():
    code, state = authenticate_chzzk()
    logger.info(f"{code} {state}")
    pass

if __name__ == "__main__":
    asyncio.run(main())
