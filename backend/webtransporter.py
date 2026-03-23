#!/usr/bin/env -S BACKEND_ENV=config.env python3
import json
import asyncio
import logging
import base64
import datetime
import ipaddress
from typing import Any, Dict, List, cast, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Body, status, WebSocket, WebSocketDisconnect
from fastapi.logger import logger
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pywebtransport import ServerApp, WebTransportSession, ServerConfig  # type: ignore
from pywebtransport.server.middleware import create_logging_middleware  # type: ignore
from pywebtransport.events import Event  # type: ignore
from hypercorn.config import Config
from hypercorn.asyncio import serve
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend

from utils.jwt import decode_jwt
from utils.settings import settings
from utils.access_control import access_control
from models.enums import ActionType, ResourceType, Status as ResponseStatus
from utils.logger import logging_schema


all_MKW = "__ALL__"

class WebTransportConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Dict[str, List[Any]] = {}
        self.channels: Dict[str, List[str]] = {}

    async def connect(self, stream, user_shortname: str):
        if user_shortname not in self.active_connections:
            self.active_connections[user_shortname] = []
        if stream not in self.active_connections[user_shortname]:
            self.active_connections[user_shortname].append(stream)

    def disconnect(self, user_shortname: str, stream_to_remove=None):
        if user_shortname in self.active_connections:
            if stream_to_remove is None:
                del self.active_connections[user_shortname]
            else:
                if stream_to_remove in self.active_connections[user_shortname]:
                    self.active_connections[user_shortname].remove(stream_to_remove)
                if not self.active_connections[user_shortname]:
                    del self.active_connections[user_shortname]
        
        if user_shortname not in self.active_connections:
            self.remove_all_subscriptions(user_shortname)

    async def send_message(self, message: str, user_shortname: str):
        if user_shortname in self.active_connections:
            streams = self.active_connections[user_shortname].copy()
            results = []
            for stream in streams:
                try:
                    if hasattr(stream, "send_text"):
                        await stream.send_text(message)
                    else:
                        data = (message + '\n').encode()
                        await stream.write(data, end_stream=False)
                    results.append(True)
                except Exception as e:
                    print(f"Failed to send message to {user_shortname}: {e}")
                    results.append(False)
                    self.disconnect(user_shortname, stream)
            return any(results)
        return False

    async def broadcast_message(self, message: str, channel_name: str):
        if channel_name not in self.channels:
            return False
            
        results = []
        for user_shortname in self.channels[channel_name]:
            results.append(await self.send_message(message, user_shortname))

        return any(results)

    def remove_all_subscriptions(self, username: str):
        for channel_name in list(self.channels.keys()):
            if username in self.channels[channel_name]:
                self.channels[channel_name].remove(username)
            if not self.channels[channel_name]:
                del self.channels[channel_name]

    def generate_channel_name(self, msg: dict):
        if not {"space_name", "subpath"}.issubset(msg):
            return None
        space_name = msg["space_name"]
        subpath = msg["subpath"]
        schema_shortname = msg.get("schema_shortname", all_MKW)
        action_type = msg.get("action_type", all_MKW)
        ticket_state = msg.get("ticket_state", all_MKW)
        return f"{space_name}:{subpath}:{schema_shortname}:{action_type}:{ticket_state}"

    async def check_eligibility(self, user_shortname: str, space_name: str, subpath: str) -> bool:
        try:
            result = await access_control.check_access(
                user_shortname=user_shortname,
                space_name=space_name,
                subpath=subpath,
                resource_type=ResourceType.notification,
                action_type=ActionType.query,
            )
            return bool(result)
        except Exception as e:
            print(f"Eligibility check failed for {user_shortname}: {e}")
            return False

    async def channel_subscribe(self, user_shortname: str, msg_json: dict):
        space_name = msg_json.get("space_name")
        subpath = msg_json.get("subpath")
        
        if not space_name or not subpath:
            return False, "space_name and subpath are required"

        is_eligible = await self.check_eligibility(user_shortname, space_name, subpath)
        if not is_eligible:
            return False, f"User {user_shortname} is not eligible to access {space_name}/{subpath}"

        channel_name = self.generate_channel_name(msg_json)
        if not channel_name:
            return False, "Failed to generate channel name"

        self.channels.setdefault(channel_name, [])
        if user_shortname not in self.channels[channel_name]:
            self.channels[channel_name].append(user_shortname)
        
        subscribed_message = json.dumps({
            "type": "notification_subscription",
            "message": {
                "status": "success",
                "channel": channel_name
            }
        })
        await self.send_message(subscribed_message, user_shortname)
        return True, "Subscribed successfully"

    async def channel_unsubscribe(self, user_shortname: str, msg_json: Optional[dict] = None):
        if msg_json and {"space_name", "subpath"}.issubset(msg_json):
            channel_name = self.generate_channel_name(msg_json)
            if channel_name in self.channels and user_shortname in self.channels[channel_name]:
                self.channels[channel_name].remove(user_shortname)
                if not self.channels[channel_name]:
                    del self.channels[channel_name]
        else:
            self.remove_all_subscriptions(user_shortname)
            
        unsubscribed_message = json.dumps({
            "type": "notification_unsubscribe",
            "message": {
                "status": "success"
            }
        })
        await self.send_message(unsubscribed_message, user_shortname)
        return True, "Unsubscribed successfully"

manager = WebTransportConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("WebTransporter starting up")
    yield
    print("WebTransporter shutting down")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def generate_wt_cert(certfile, keyfile, hostname="localhost"):
    key = ec.generate_private_key(
        ec.SECP256R1(),
        backend=default_backend()
    )
    
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])
    
    san = [
        x509.DNSName(hostname),
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv6Address("::1")),
    ]
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    ).not_valid_after(
        # WebTransport requires validity period < 14 days for self-signed certs
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=12)
    ).add_extension(
        x509.SubjectAlternativeName(san),
        critical=False,
    ).sign(key, hashes.SHA256(), default_backend())
    
    with open(keyfile, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        
    with open(certfile, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

generate_wt_cert("localhost.crt", "localhost.key")

async def handle_session(session: WebTransportSession, token: str):
    try:
        decoded_token = decode_jwt(token)
        user_shortname = decoded_token["shortname"]
    except Exception as e:
        error_msg = str(e)
        err_obj = getattr(e, 'error', None)
        if err_obj is not None and hasattr(err_obj, 'message'):
            error_msg = getattr(err_obj, 'message')
        print(f"WebTransport authentication failed for token {token[:10]}...: {error_msg}")
        await session.reject(status_code=401)
        return

    main_stream = None
    print(f"Waiting for bidirectional stream from {user_shortname}...")
    try:
        async for stream in session.incoming_bidirectional_streams():
            main_stream = stream
            print(f"Bidirectional stream established for {user_shortname}")
            break
    except Exception as e:
        print(f"Error getting stream for {user_shortname}: {e}")
        return
        
    if not main_stream:
        print(f"No bidirectional stream established for {user_shortname} before session end/timeout")
        return

    await manager.connect(main_stream, user_shortname)
    
    try:
        buffer = bytearray()
        while True:
            data = await main_stream.read()
            if not data:
                break
            
            buffer.extend(data)
            if len(buffer) > 1024 * 1024:
                print(f"Buffer overflow for {user_shortname}")
                break
                
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                if not line.strip():
                    continue
                
                try:
                    msg_json = json.loads(line.decode())
                    msg_type = msg_json.get("type")
                    
                    if msg_type == "notification_subscription":
                        await manager.channel_subscribe(user_shortname, msg_json)
                    elif msg_type == "notification_unsubscribe":
                        await manager.channel_unsubscribe(user_shortname, msg_json)
                    elif msg_type == "message":
                        receiver_id = msg_json.get("receiverId")
                        group_id = msg_json.get("groupId")
                        message_str = line.decode()
                        if receiver_id:
                            await manager.send_message(message_str, receiver_id)
                        elif group_id:
                            participants = msg_json.get("participants", [])
                            for p in participants:
                                if p != user_shortname:
                                    await manager.send_message(message_str, p)
                    elif msg_type == "chat_message":
                        channel_name = manager.generate_channel_name(msg_json)
                        if channel_name:
                            is_eligible = await manager.check_eligibility(user_shortname, msg_json.get("space_name"), msg_json.get("subpath"))
                            is_subscribed = channel_name in manager.channels and user_shortname in manager.channels[channel_name]
                            
                            if is_eligible and is_subscribed:
                                chat_message = json.dumps({
                                    "type": "chat_message",
                                    "message": msg_json.get("message"),
                                    "from": user_shortname,
                                    "timestamp": msg_json.get("timestamp")
                                })
                                await manager.broadcast_message(chat_message, channel_name)
                            else:
                                logger.error(f"Unauthorized chat message from {user_shortname} to {channel_name} (eligible={is_eligible}, subscribed={is_subscribed})")
                except Exception as e:
                    logger.error(f"Error processing message from {user_shortname}: {e}")
                
    except Exception as e:
        logger.error(f"Connection error for {user_shortname}: {e}")
    finally:
        manager.disconnect(user_shortname, main_stream)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    try:
        decoded_token = decode_jwt(token)
        user_shortname = decoded_token["shortname"]
    except Exception as e:
        logger.error(f"WebSocket authentication failed for token {e}")
        error_msg = str(e)
        err_obj = getattr(e, 'error', None)
        if err_obj is not None and hasattr(err_obj, 'message'):
            error_msg = getattr(err_obj, 'message')
        logger.error(f"WebSocket authentication failed for token {token[:10]}...: {error_msg}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    await manager.connect(websocket, user_shortname)

    try:
        while True:
            try:
                line = await websocket.receive_text()
                if not line.strip():
                    continue
                msg_json = json.loads(line)
                msg_type = msg_json.get("type")
                
                if msg_type == "notification_subscription":
                    await manager.channel_subscribe(user_shortname, msg_json)
                elif msg_type == "notification_unsubscribe":
                    await manager.channel_unsubscribe(user_shortname, msg_json)
                elif msg_type == "message":
                    receiver_id = msg_json.get("receiverId")
                    group_id = msg_json.get("groupId")
                    if receiver_id:
                        await manager.send_message(line, receiver_id)
                    elif group_id:
                        participants = msg_json.get("participants", [])
                        for p in participants:
                            if p != user_shortname:
                                await manager.send_message(line, p)
                elif msg_type == "chat_message":
                    channel_name = manager.generate_channel_name(msg_json)
                    if channel_name:
                        is_eligible = await manager.check_eligibility(user_shortname, msg_json.get("space_name"), msg_json.get("subpath"))
                        is_subscribed = channel_name in manager.channels and user_shortname in manager.channels[channel_name]
                        if is_eligible and is_subscribed:
                            chat_message = json.dumps({
                                "type": "chat_message",
                                "message": msg_json.get("message"),
                                "from": user_shortname,
                                "timestamp": msg_json.get("timestamp")
                            })
                            await manager.broadcast_message(chat_message, channel_name)
                        else:
                            print(f"Unauthorized ws chat message from {user_shortname} to {channel_name}")
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"Error processing ws message from {user_shortname}: {e}")
    finally:
        manager.disconnect(user_shortname, websocket)

fingerprint_cache = None

@app.api_route(path="/wt-fingerprint", methods=["get"])
async def get_fingerprint():
    global fingerprint_cache
    if not fingerprint_cache:
        fingerprint_cache = get_certificate_fingerprint("localhost.crt")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": ResponseStatus.success, "fingerprint": fingerprint_cache}
    )

@app.api_route(path="/send-message/{user_shortname}", methods=["post"])
async def send_message(user_shortname: str, data: dict = Body(...)):
    formatted_message = json.dumps({
        "type": data["type"],
        "message": data["message"]
    })
    is_sent = await manager.send_message(formatted_message, user_shortname)
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
        is_sent = await manager.broadcast_message(formatted_message, channel_name) or is_sent

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
                "connected_clients": list(manager.active_connections.keys()),
                "channels": manager.channels
            } 
        }
    )

def get_certificate_fingerprint(certfile):
    try:
        with open(certfile, "rb") as f:
            cert_data = f.read()
        cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        fingerprint = cert.fingerprint(hashes.SHA256())
        return base64.b64encode(fingerprint).decode()
    except Exception as e:
        print(f"Failed to calculate certificate fingerprint: {e}")
        return None

async def main():
    await access_control.load_permissions_and_roles()

    config = Config()
    config.bind = [f"{settings.listening_host}:{settings.webtransport_port}"]
    config.logconfig_dict = logging_schema
    config.errorlog = logger
    config.accesslog = logger

    if "loggers" not in logging_schema:
        logging_schema["loggers"] = {}
        
    logging_schema["loggers"]["pywebtransport"] = {
        "handlers": settings.log_handlers,
        "level": "DEBUG",
        "propagate": False,
    }
    logging_schema["loggers"]["aioquic"] = {
        "handlers": settings.log_handlers,
        "level": "DEBUG",
        "propagate": False,
    }

    logging.getLogger("pywebtransport").setLevel(logging.DEBUG)
    logging.getLogger("aioquic").setLevel(logging.DEBUG)

    wt_config = ServerConfig(
        bind_host=settings.listening_host,
        bind_port=int(settings.webtransport_port),
        certfile="localhost.crt",
        keyfile="localhost.key",
        max_sessions=100
    )
    wt_app = ServerApp(config=wt_config)

    def log_wt_event(event: Event):
        if event.type in ["stream_data_received", "datagram_received", "session_ready", "capsule_received"]:
            logger.info(f"WebTransport Event: {event.type}")
        else:
            msg = f"WebTransport Event: {event.type}"
            if hasattr(event, 'data') and event.data:
                msg += f" - {event.data}"

            if event.type == "session_request":
                try:
                    session = event.data.get("session") if isinstance(event.data, dict) else None
                    if session:
                        print(f"[*] Incoming session request: {session.path}")
                except Exception:
                    pass
            elif event.type == "connection_failed":
                print(f"[!] Connection failed: {event.data}")

    wt_app.server.on_any(handler=log_wt_event)

    wt_app.add_middleware(middleware=create_logging_middleware())
    wt_app.pattern_route(pattern=r"/wt/(?P<token>.+)")(handle_session)
    print(f"Listening {settings.listening_host}:{settings.webtransport_port}")
    # fingerprint = get_certificate_fingerprint("localhost.crt")


    async with wt_app:
        await asyncio.gather(
            serve(cast(Any, app), config),
            wt_app.serve()
        )

if __name__ == "__main__":
    asyncio.run(main())
