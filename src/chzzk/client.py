
import json
import threading
import time
import requests
import socketio

from pydantic import BaseModel
from typing import Dict, List, Literal, Any, Optional
from loguru import logger

from . import message_queue as MessageQueue
from .auth import ChzzkAuth, CHZZK_API_URL


class ChatEventDataProfile(BaseModel):
    nickname: str
    verifiedMark: bool
    badges: List[Dict[str, Any]]
    userRoleCode: str


class ChatEventData(BaseModel):
    channelId: str
    senderChannelId: str
    content: str
    profile: Optional[ChatEventDataProfile]
    emojis: Dict[str, Any]
    messageTime: int
    eventSentAt: str


class ChzzkClient:
    def __init__(self, auth: ChzzkAuth, code: str, state: str):
        self.auth = auth
        self.code = code
        self.state = state

    async def start(self):
        auth: ChzzkAuth = self.auth
        headers = {
            "Client-Id": auth.client_id,
            "Client-Secret": auth.client_secret,
            "Content-Type": "application/json",
        }

        response = requests.get(
            f"{CHZZK_API_URL}/open/v1/sessions/auth/client", headers=headers)
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
                elif type == 'subscribed' or type == 'unsubscribed':
                    eventType, channelId = data['eventType'], data['channelId']
                    is_subscribe = (type == 'subscribed')
                    self.on_subsribe_event(eventType, channelId, is_subscribe)
            except Exception as e:
                self.on_error(e)
                return

            self.on_system_received(type, data)

        @sio.on('CHAT')
        def on_chat(data: str):
            logger.info(f"Received CHAT event: {data}")
            self.on_chat_received(ChatEventData(**json.loads(data)))

        # call interval polling in a separate thread
        polling_thread = threading.Thread(
            target=self.interval_polling, daemon=True)
        polling_thread.start()

        # hold the connection
        try:
            await sio.wait()
        finally:
            polling_thread.join()
            sio.disconnect()

    # =================== Callback Handlers ===================

    def on_connected(self, session_key: str):
        MessageQueue.create_queue()
        # Subscribe to events
        logger.info(f"Connected to session: {session_key}")
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

    def on_subsribe_event(
            self,
            eventType: Literal["CHAT", "DONATION"],
            channelId: str,
            is_subscribe: bool
    ):
        if is_subscribe:
            logger.info(f"Subscribed {eventType} to channelId={channelId}")
        else:
            logger.info(f"Unsubscribed {eventType} from channelId={channelId}")

    def on_chat_received(self, data: ChatEventData):
        logger.info(f"Chat received callback: {data}")
        message = data.content
        sender = data.profile.nickname if data.profile else ""
        if sender and message:
            MessageQueue.push({"sender": sender, "message": message})

    def on_system_received(self, type: str, data: Any):
        logger.info(f"System received callback: type={type}, data={data}")

    def on_error(self, error: Exception):
        logger.error(f"Error callback: {error}")

    def interval_polling(self):
        """Polling to fetch messages from the queue."""
        while True:
            logger.info(f"Polling")
            if not MessageQueue.is_empty():
                messages = MessageQueue.poll()
                logger.info(f"Polled message: {messages}")
            time.sleep(30)  # Poll every 30 seconds
