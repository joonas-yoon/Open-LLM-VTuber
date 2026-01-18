
import json
import requests
import socketio

from loguru import logger

from .auth import ChzzkAuth, CHZZK_API_URL


class ChzzkClient:
    def __init__(self, auth: ChzzkAuth, code: str, state: str):
        self.auth = auth
        self.code = code
        self.state = state

    async def connect(self):
        auth: ChzzkAuth = self.auth
        headers = {
            "Client-Id": auth.client_id,
            "Client-Secret": auth.client_secret,
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
            logger.info(f"Received SYSTEM event: {json_data}")

            type, data = json_data['type'], json_data['data']

            try:
                if type == 'connected':
                    session_key = data['sessionKey']
                    self.on_connected(session_key)
                elif type == 'subscribed':
                    # eventType: "CHAT"|"DONATION"
                    eventType, channelId = data['eventType'], data['channelId']
                    logger.info(
                        f"Subscribed to session: eventType={eventType}, channelId={channelId}")
                elif type == 'unsubscribed':
                    # eventType: "CHAT"|"DONATION"
                    eventType, channelId = data['eventType'], data['channelId']
                    logger.info(
                        f"Unsubscribed from session: eventType={eventType}, channelId={channelId}")
            except Exception as e:
                self.on_error(e)
                return

            self.on_system_received(type, data)

        @sio.on('CHAT')
        def on_chat(data):
            logger.info(f"Received CHAT event: {data}")
            self.on_chat_received(data)

        # hold the connection
        await sio.wait()

    def on_connected(self, session_key):
        logger.info(f"Connected to session: {session_key}")
        # Subscribe to events
        access_token = self.auth.get_access_token(self.code, self.state)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            f"{CHZZK_API_URL}/open/v1/sessions/events/subscribe/chat",
            headers=headers,
            params={
                "sessionKey": session_key,
            },
        )
        logger.info(
            f"Subscribed to chat events: {response.status_code}, {response.text}")

    def on_chat_received(self, data):
        logger.info(f"Chat received callback: {data}")

    def on_system_received(self, type, data):
        logger.info(f"System received callback: type={type}, data={data}")
    
    def on_error(self, error):
        logger.error(f"Error callback: {error}")

