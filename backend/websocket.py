#!/usr/bin/env -S BACKEND_ENV=config.env python3
import json
from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect, status, Request
from utils.jwt import decode_jwt
import asyncio
from hypercorn.config import Config
from utils.settings import settings
from hypercorn.asyncio import serve
from models.enums import Status as ResponseStatus
from fastapi.responses import JSONResponse
from fastapi.logger import logger

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

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

websocket_manager = ConnectionManager()


app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):

    try:
        decoded_token = decode_jwt(token)
    except :
        return status.HTTP_401_UNAUTHORIZED, [], b"Invalid token\n"

    user_shortname = decoded_token["username"]
    await websocket_manager.connect(websocket, user_shortname)

    success_connection_message = json.dumps({
        "type": "connection_response",
        "message": {
            "status": "success"
        }
    })
    await websocket_manager.send_message(success_connection_message, user_shortname)

    try:
        # Waiting for connection close message
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WebSocket connection closed", extra={"user_shortname": user_shortname})
        websocket_manager.disconnect(user_shortname)


@app.api_route(path="/send-message/{user_shortname}", methods=["post"])
async def send_message(user_shortname: str, message: dict = Body(...)):
    formatted_message = json.dumps({
        "type": "message",
        "message": message
    })
    is_sent = await websocket_manager.send_message(formatted_message, user_shortname)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": ResponseStatus.success, "message_sent": is_sent}
    )


if __name__ == "__main__":
    config = Config()
    config.bind = [f"{settings.listening_host}:{settings.websocket_port}"]
    config.errorlog = logger
    config.backlog = 200
    config.logconfig = "./json_log.ini"
    asyncio.run(serve(app, config))  # type: ignore
