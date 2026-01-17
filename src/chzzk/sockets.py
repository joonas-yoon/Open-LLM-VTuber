
import json
import requests
import socketio

from loguru import logger

from ..chzzk import CLIENT_ID, CLIENT_SECRET
from .auth import CHZZK_API_URL


async def connect_socket():
    headers = {
        "Client-Id": CLIENT_ID,
        "Client-Secret": CLIENT_SECRET,
        "Content-Type": "application/json",
    }

    response = requests.get(
        f"{CHZZK_API_URL}/open/v1/sessions/auth/client", headers=headers)
    print(response.status_code)
    response_json = response.json()

    try:
        url = response_json['content']['url']
        logger.info(f"Socket URL: {url}")
    except Exception as e:
        logger.error(f"Failed to get socket URL: {e}")
        logger.error(f"Response JSON: {response_json}")
        return

    sio = socketio.Client(reconnection=False,
                          reconnection_attempts=2,
                          logger=True,
                          engineio_logger=True)
    sio.connect(url, transports=['websocket'])

    @sio.event
    def connect():
        logger.info("Socket connected.")
        sio.send('Hello, server!')

    @sio.on('SYSTEM')
    def on_system(raw_data):
        json_data = json.loads(raw_data)
        type, data = json_data['type'], json_data['data']
        session_key = data['sessionKey']
        logger.info(f"Received SYSTEM event: {json_data}, sessionKey={session_key}")

    @sio.on('CHAT')
    def on_chat(data):
        logger.info(f"Received CHAT event: {data}")

    # hold the connection
    sio.wait()
