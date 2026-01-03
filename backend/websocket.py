#!/usr/bin/env -S BACKEND_ENV=config.env python3
import json
from contextlib import asynccontextmanager

from typing import Any, cast
from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect, status
from utils.jwt import decode_jwt
import asyncio
from hypercorn.config import Config
from utils.logger import changeLogFile, logging_schema
from utils.settings import settings
from hypercorn.asyncio import serve
from models.enums import Status as ResponseStatus
from fastapi.responses import JSONResponse
from fastapi.logger import logger


all_MKW = "__ALL__"
class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        # item => channel_name: list_of_subscribed_clients
        self.channels: dict[str, list[str]] = {}

    async def connect(self, websocket: WebSocket, user_shortname: str):
        await websocket.accept()
        self.active_connections[user_shortname] = websocket


    def disconnect(self, user_shortname: str):
        del self.active_connections[user_shortname]


    async def send_message(self, message: str, user_shortname: str):
        if user_shortname in self.active_connections:
            await self.active_connections[user_shortname].send_text(message)
            return True

        return False

    
    async def broadcast_message(self, message: str, channel_name: str):
        if channel_name not in self.channels:
            return False
            
        for user_shortname in self.channels[channel_name]:
            await self.send_message(message, user_shortname)

        return True
            

    def remove_all_subscriptions(self, username: str):
        updated_channels: dict[str, list[str]] = {}
        for channel_name, users in self.channels.items():
            if username in users:
                users.remove(username)
            updated_channels[channel_name] = users
        self.channels = updated_channels


    async def channel_unsubscribe(self, websocket: WebSocket):
        connections_usernames = list(self.active_connections.keys())
        connections = list(self.active_connections.values())
        username = connections_usernames[connections.index(websocket)]
        self.remove_all_subscriptions(username)
        subscribed_message = json.dumps({
            "type": "notification_unsubscribe",
            "message": {
                "status": "success"
            }
        })
        await self.send_message(subscribed_message, username)

    
    def generate_channel_name(self, msg: dict):
        if not {"space_name", "subpath"}.issubset(msg):
            return False
        space_name = msg["space_name"]
        subpath = msg["subpath"]
        schema_shortname = msg.get("schema_shortname", all_MKW)
        action_type = msg.get("action_type", all_MKW)
        ticket_state = msg.get("ticket_state", all_MKW)
        return f"{space_name}:{subpath}:{schema_shortname}:{action_type}:{ticket_state}"
            

    async def channel_subscribe(
        self,
        websocket: WebSocket,
        msg_json: dict
    ):
        channel_name = self.generate_channel_name(msg_json)
        if not channel_name:
            return False

        self.channels.setdefault(channel_name, [])

        connections_usernames = list(self.active_connections.keys())
        connections = list(self.active_connections.values())
        username = connections_usernames[connections.index(websocket)]
        self.remove_all_subscriptions(username)
        self.channels[channel_name].append(username)

        subscribed_message = json.dumps({
            "type": "notification_subscription",
            "message": {
                "status": "success"
            }
        })
        await self.send_message(subscribed_message, username)



websocket_manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up")
    print('{"stage":"starting up"}')

    yield

    logger.info("Application shutting down")
    print('{"stage":"shutting down"}')


app = FastAPI(
    lifespan=lifespan,
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    try:
        decoded_token = decode_jwt(token)
    except Exception:
        return status.HTTP_401_UNAUTHORIZED, [], b"Invalid token\n"

    user_shortname = decoded_token["shortname"]
    try:
        await websocket_manager.connect(websocket, user_shortname)
    except Exception as e:
        return status.HTTP_500_INTERNAL_SERVER_ERROR, [], str(e.__str__()).encode()

    success_connection_message = json.dumps({
        "type": "connection_response",
        "message": {
            "status": "success"
        }
    })

    try:
        await websocket_manager.send_message(success_connection_message, user_shortname)
    except Exception as e:
        return status.HTTP_500_INTERNAL_SERVER_ERROR, [], str(e.__str__()).encode()

    try:
        while True:
            try:
                msg = await websocket.receive_text()
                msg_json = json.loads(msg)
                if "type" in msg_json and msg_json["type"] == "notification_subscription":
                    await websocket_manager.channel_subscribe(websocket, msg_json)
                if "type" in msg_json and msg_json["type"] == "notification_unsubscribe":
                    await websocket_manager.channel_unsubscribe(websocket)
            except Exception as e:
                logger.error(f"Error while processing message: {e.__str__()}", extra={"user_shortname": user_shortname})
                break
    except WebSocketDisconnect:
        logger.info("WebSocket connection closed", extra={"user_shortname": user_shortname})
        websocket_manager.disconnect(user_shortname)


@app.api_route(path="/send-message/{user_shortname}", methods=["post"])
async def send_message(user_shortname: str, data: dict = Body(...)):
    formatted_message = json.dumps({
        "type": data["type"],
        "message": data["message"]
    })
    is_sent = await websocket_manager.send_message(formatted_message, user_shortname)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": ResponseStatus.success, "message_sent": is_sent}
    )


@app.api_route(path="/broadcast-to-channels", methods=["post"])
async def broadcast(data: dict = Body(...)):
    formatted_message = json.dumps({
        "type": data["type"],
        "message": data["message"]
    })

    is_sent = False
    for channel_name in data["channels"]:
        is_sent = await websocket_manager.broadcast_message(formatted_message, channel_name) or is_sent

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": ResponseStatus.success, "message_sent": is_sent}
    )


@app.api_route(path="/info", methods=["get"])
async def service_info():
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": ResponseStatus.success, 
            "data": {
                "connected_clients": str(websocket_manager.active_connections),
                "channels": str(websocket_manager.channels)
            } 
        }
    )


async def main():
    config = Config()
    config.bind = [f"{settings.listening_host}:{settings.websocket_port}"]
    config.backlog = 200

    changeLogFile(settings.ws_log_file)
    config.logconfig_dict = logging_schema
    config.errorlog = logger
    config.accesslog = logger
    await serve(cast(Any, app), config)

if __name__ == "__main__":

    asyncio.run(main())
