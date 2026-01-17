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

from src.chzzk.Auth import ChzzkAuth

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.chzzk.env'))

OPENAPI_URL = "https://openapi.chzzk.naver.com"

APP_CODE = os.getenv("APP_CODE")
APP_STATE = os.getenv("APP_STATE")

print("APP_CODE:", APP_CODE)
print("APP_STATE:", APP_STATE)


class CallbackHandler(BaseHTTPRequestHandler):
    response_queue = None

    def do_GET(self):
        if self.path.startswith("/callback"):
            query_params = parse_qs(urlparse(self.path).query)
            code = query_params.get("code", [None])[0]
            state = query_params.get("state", [None])[0]

            print(f"✓ Callback received: code={code}, state={state}")

            # Put the code and state into the queue
            if self.response_queue:
                self.response_queue.put((code, state))

            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<html><body>"
                             b"<h1>Authorization successful!</h1>"
                             b"<p>You can close this window.</p>"
                             b"</body></html>")

            # Stop the server
            threading.Thread(target=self.server.shutdown,
                             daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()


# Example usage
async def main():
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    REDIRECT_URI = "http://localhost:8080/callback"
    STATE = secrets.token_urlsafe(16)  # 보안을 위한 랜덤 문자열 생성

    auth = ChzzkAuth(CLIENT_ID, CLIENT_SECRET)

    q = queue.Queue()
    server = HTTPServer(("localhost", 8080), CallbackHandler)
    CallbackHandler.response_queue = q  # 큐 설정
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    logger.info("Callback server started on http://localhost:8080")

    def open_browser():
        time.sleep(1)
        auth_url = auth.get_auth_url(REDIRECT_URI, STATE)
        webbrowser.open(auth_url)

    logger.info("Opening web browser for user authentication in 1 second...")
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # 메인 스레드에서 큐를 체크하여 code와 state를 받음
    received_code = None
    received_state = None
    while server_thread.is_alive() or not q.empty():
        try:
            # Check queue without blocking for a long time (timeout=0.1s)
            received_code, received_state = q.get_nowait()
            logger.info(
                f"Received code={received_code}, state={received_state}")
            break  # 데이터를 받았으므로 루프 종료
        except queue.Empty:
            # No item in queue yet, continue looping/doing other main thread work
            time.sleep(0.1)

    server_thread.join()

    # 받은 code와 state를 사용
    if received_code and received_state:
        APP_CODE = received_code
        APP_STATE = received_state
        print("Got authorization code and state from callback.")
        print("APP_CODE:", APP_CODE)
        print("APP_STATE:", APP_STATE)

    # tokens = auth.get_access_token(APP_CODE, APP_STATE, REDIRECT_URI)
    # print(tokens)
    # content = tokens["content"]
    # access_token = content.get("accessToken")
    # refresh_token = content.get("refreshToken")
    # print("token:", tokens)

    # headers = {
    #     "Authorization": f"Bearer {access_token}",
    #     "User-Agent": "Mozilla/5.0"
    # }

    # responses = requests.get(f"{OPENAPI_URL}/open/v1/sessions", headers=headers)
    # print("responses:", responses.json())


if __name__ == "__main__":
    asyncio.run(main())
