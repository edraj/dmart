#!/usr/bin/env -S BACKEND_ENV=config.env python3
import asyncio
import base64
import datetime
import ipaddress
import json
import logging
import re
from contextlib import asynccontextmanager
from typing import Any, cast

from aioquic.asyncio import QuicConnectionProtocol
from aioquic.asyncio import serve as quic_serve
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import HeadersReceived, WebTransportStreamDataReceived
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import ProtocolNegotiated, QuicEvent
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from fastapi import Body, FastAPI, status
from fastapi.logger import logger
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from hypercorn.asyncio import serve
from hypercorn.config import Config

from models.enums import ActionType, ResourceType
from models.enums import Status as ResponseStatus
from utils.access_control import access_control
from utils.jwt import decode_jwt
from utils.logger import logging_schema
from utils.settings import settings

all_MKW = "__ALL__"


# ---------------------------------------------------------------------------
# Stream wrapper — lets the manager send data without holding a direct
# reference to the H3Connection or QuicConnectionProtocol internals.
# ---------------------------------------------------------------------------

class WebTransportStream:
    def __init__(self, protocol: "WebTransportProtocol", stream_id: int):
        self.protocol = protocol
        self.stream_id = stream_id

    async def send(self, data: bytes) -> None:
        try:
            self.protocol._quic.send_stream_data(self.stream_id, data, end_stream=False)
            self.protocol.transmit()
        except Exception as e:
            raise RuntimeError(f"send failed on stream {self.stream_id}: {e}") from e


# ---------------------------------------------------------------------------
# Connection manager (same public interface as before)
# ---------------------------------------------------------------------------

class WebTransportConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebTransportStream]] = {}
        self.channels: dict[str, list[str]] = {}

    async def connect(self, stream: WebTransportStream, user_shortname: str) -> None:
        if user_shortname not in self.active_connections:
            self.active_connections[user_shortname] = []
        if stream not in self.active_connections[user_shortname]:
            self.active_connections[user_shortname].append(stream)

    def disconnect(self, user_shortname: str, stream_to_remove: WebTransportStream | None = None) -> None:
        if user_shortname in self.active_connections:
            if stream_to_remove is None:
                del self.active_connections[user_shortname]
            else:
                try:
                    self.active_connections[user_shortname].remove(stream_to_remove)
                except ValueError:
                    pass
                if not self.active_connections[user_shortname]:
                    del self.active_connections[user_shortname]

        if user_shortname not in self.active_connections:
            self.remove_all_subscriptions(user_shortname)

    async def send_message(self, message: str, user_shortname: str) -> bool:
        if user_shortname not in self.active_connections:
            return False
        streams = self.active_connections[user_shortname].copy()
        results = []
        for stream in streams:
            try:
                await stream.send((message + "\n").encode())
                results.append(True)
            except Exception:
                results.append(False)
                self.disconnect(user_shortname, stream)
        return any(results)

    async def broadcast_message(self, message: str, channel_name: str) -> bool:
        if channel_name not in self.channels:
            return False
        results = [
            await self.send_message(message, u)
            for u in self.channels[channel_name]
        ]
        return any(results)

    def remove_all_subscriptions(self, username: str) -> None:
        for channel_name in list(self.channels.keys()):
            if username in self.channels[channel_name]:
                self.channels[channel_name].remove(username)
            if not self.channels[channel_name]:
                del self.channels[channel_name]

    def generate_channel_name(self, msg: dict) -> str | None:
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
        except Exception:
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

        await self.send_message(
            json.dumps({
                "type": "notification_subscription",
                "message": {"status": "success", "channel": channel_name},
            }),
            user_shortname,
        )
        return True, "Subscribed successfully"

    async def channel_unsubscribe(self, user_shortname: str, msg_json: dict | None = None):
        if msg_json and {"space_name", "subpath"}.issubset(msg_json):
            channel_name = self.generate_channel_name(msg_json)
            if channel_name in self.channels and user_shortname in self.channels[channel_name]:
                self.channels[channel_name].remove(user_shortname)
                if not self.channels[channel_name]:
                    del self.channels[channel_name]
        else:
            self.remove_all_subscriptions(user_shortname)

        await self.send_message(
            json.dumps({"type": "notification_unsubscribe", "message": {"status": "success"}}),
            user_shortname,
        )
        return True, "Unsubscribed successfully"


manager = WebTransportConnectionManager()


# ---------------------------------------------------------------------------
# aioquic WebTransport protocol
# ---------------------------------------------------------------------------

class WebTransportProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._http: H3Connection | None = None
        # session_stream_id (CONNECT stream) -> user_shortname
        self._sessions: dict[int, str] = {}
        # data_stream_id -> WebTransportStream (registered with manager)
        self._streams: dict[int, WebTransportStream] = {}
        # per-stream read buffers
        self._buffers: dict[int, bytearray] = {}

    # ------------------------------------------------------------------
    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, ProtocolNegotiated):
            self._http = H3Connection(self._quic, enable_webtransport=True)

        if self._http is not None:
            for h3_event in self._http.handle_event(event):
                self._handle_h3_event(h3_event)

    # ------------------------------------------------------------------
    # Must be synchronous — aioquic requires the 200 response to the
    # WebTransport CONNECT to be sent within the same quic_event_received
    # call, not deferred via ensure_future / next event loop tick.
    def _handle_h3_event(self, event) -> None:
        if isinstance(event, HeadersReceived):
            headers = dict(event.headers)
            method   = headers.get(b":method", b"")
            protocol = headers.get(b":protocol", b"")

            if method == b"CONNECT" and protocol == b"webtransport":
                path = headers.get(b":path", b"").decode()
                m = re.match(r"/wt/(.+)", path)
                if m:
                    self._accept_session(event.stream_id, m.group(1))
                else:
                    self._reject(event.stream_id, b"404")

        elif isinstance(event, WebTransportStreamDataReceived):
            asyncio.ensure_future(self._handle_stream_data(event))

    # ------------------------------------------------------------------
    def _reject(self, stream_id: int, code: bytes) -> None:
        self._http.send_headers(
            stream_id=stream_id,
            headers=[(b":status", code)],
            end_stream=True,
        )
        self.transmit()

    # ------------------------------------------------------------------
    def _accept_session(self, session_stream_id: int, token: str) -> None:
        try:
            decoded = decode_jwt(token)
            user_shortname = decoded["shortname"]
        except Exception as e:
            err = getattr(e, "error", None)
            msg = err.message if (err and hasattr(err, "message")) else str(e)
            self._reject(session_stream_id, b"401")
            return

        self._http.send_headers(
            stream_id=session_stream_id,
            headers=[(b":status", b"200")],
            end_stream=False,
        )
        self.transmit()

        self._sessions[session_stream_id] = user_shortname

    # ------------------------------------------------------------------
    async def _handle_stream_data(self, event: WebTransportStreamDataReceived) -> None:
        session_id = event.session_id
        stream_id  = event.stream_id
        data       = event.data

        user_shortname = self._sessions.get(session_id)
        if not user_shortname:
            return

        # First data on this stream — register with manager
        if stream_id not in self._streams:
            wt_stream = WebTransportStream(self, stream_id)
            self._streams[stream_id] = wt_stream
            self._buffers[stream_id] = bytearray()
            await manager.connect(wt_stream, user_shortname)

        buf = self._buffers[stream_id]
        buf.extend(data)

        if len(buf) > 1024 * 1024:
            manager.disconnect(user_shortname, self._streams.get(stream_id))
            return

        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            self._buffers[stream_id] = buf
            if not line.strip():
                continue
            try:
                msg_json = json.loads(line.decode())
                await self._dispatch(user_shortname, msg_json)
            except Exception as e:
                logger.error(f"Error processing message from {user_shortname}: {e}")

        if event.stream_ended:
            manager.disconnect(user_shortname, self._streams.pop(stream_id, None))
            self._buffers.pop(stream_id, None)

    # ------------------------------------------------------------------
    async def _dispatch(self, user_shortname: str, msg_json: dict) -> None:
        msg_type = msg_json.get("type")

        if msg_type == "notification_subscription":
            await manager.channel_subscribe(user_shortname, msg_json)

        elif msg_type == "notification_unsubscribe":
            await manager.channel_unsubscribe(user_shortname, msg_json)

        elif msg_type == "message":
            receiver_id = msg_json.get("receiverId")
            group_id    = msg_json.get("groupId")
            raw         = json.dumps(msg_json)
            if receiver_id:
                await manager.send_message(raw, receiver_id)
            elif group_id:
                for p in msg_json.get("participants", []):
                    if p != user_shortname:
                        await manager.send_message(raw, p)

        elif msg_type == "chat_message":
            channel_name = manager.generate_channel_name(msg_json)
            if channel_name:
                eligible   = await manager.check_eligibility(user_shortname, msg_json.get("space_name"), msg_json.get("subpath"))
                subscribed = channel_name in manager.channels and user_shortname in manager.channels[channel_name]
                if eligible and subscribed:
                    await manager.broadcast_message(
                        json.dumps({
                            "type": "chat_message",
                            "message": msg_json.get("message"),
                            "from": user_shortname,
                            "timestamp": msg_json.get("timestamp"),
                        }),
                        channel_name,
                    )
                else:
                    logger.error(f"Unauthorized chat from {user_shortname} to {channel_name}")

    # ------------------------------------------------------------------
    def connection_lost(self, exc) -> None:
        # Clean up every user whose stream lived on this connection
        for stream_id, wt_stream in list(self._streams.items()):
            for session_id, user_shortname in self._sessions.items():
                manager.disconnect(user_shortname, wt_stream)
        super().connection_lost(exc)


# ---------------------------------------------------------------------------
# TLS certificate (self-signed, valid < 14 days for WebTransport)
# ---------------------------------------------------------------------------

def generate_wt_cert(certfile: str, keyfile: str, hostname: str = "localhost") -> None:
    key = ec.generate_private_key(ec.SECP256R1(), backend=default_backend())

    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    san = [
        x509.DNSName(hostname),
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv6Address("::1")),
    ]

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=12))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .sign(key, hashes.SHA256(), default_backend())
    )

    with open(keyfile, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
    with open(certfile, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


generate_wt_cert("localhost.crt", "localhost.key")


def get_certificate_fingerprint(certfile: str) -> str | None:
    try:
        with open(certfile, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read(), default_backend())
        return base64.b64encode(cert.fingerprint(hashes.SHA256())).decode()
    except Exception:
        return None


fingerprint_cache: str | None = None


# ---------------------------------------------------------------------------
# FastAPI REST app (fingerprint + REST messaging endpoints)
# ---------------------------------------------------------------------------

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


@app.api_route("/wt-fingerprint", methods=["GET"])
async def get_fingerprint():
    global fingerprint_cache
    if not fingerprint_cache:
        fingerprint_cache = get_certificate_fingerprint("localhost.crt")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": ResponseStatus.success, "fingerprint": fingerprint_cache},
    )


@app.api_route("/send-message/{user_shortname}", methods=["POST"])
async def send_message(user_shortname: str, data: dict = Body(...)):
    formatted = json.dumps({"type": data["type"], "message": data["message"]})
    is_sent = await manager.send_message(formatted, user_shortname)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": ResponseStatus.success, "message_sent": is_sent},
    )


@app.api_route("/broadcast-to-channels", methods=["POST"])
async def broadcast(data: dict = Body(...)):
    formatted = json.dumps({"type": data["type"], "message": data["message"]})
    is_sent = False
    for channel_name in data["channels"]:
        is_sent = await manager.broadcast_message(formatted, channel_name) or is_sent
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": ResponseStatus.success, "message_sent": is_sent},
    )


@app.api_route("/info", methods=["GET"])
async def service_info():
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": ResponseStatus.success,
            "data": {
                "connected_clients": list(manager.active_connections.keys()),
                "channels": manager.channels,
            },
        },
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    # Hypercorn (plain HTTP, TCP only — must not use TLS/QUIC to avoid
    # conflicting with the aioquic QUIC server on the same UDP port)
    http_config = Config()
    http_config.bind = [f"{settings.listening_host}:{settings.webtransport_port}"]
    http_config.logconfig_dict = logging_schema
    http_config.errorlog = logger
    http_config.accesslog = logger

    if "loggers" not in logging_schema:
        logging_schema["loggers"] = {}
    for lib in ("aioquic",):
        logging_schema["loggers"][lib] = {
            "handlers": settings.log_handlers,
            "level": "DEBUG",
            "propagate": False,
        }
    logging.getLogger("aioquic").setLevel(logging.DEBUG)

    # aioquic QUIC/HTTP3 server (WebTransport)
    quic_config = QuicConfiguration(
        alpn_protocols=H3_ALPN,
        is_client=False,
        max_datagram_frame_size=65536,
    )
    quic_config.load_cert_chain("localhost.crt", "localhost.key")

    print(f"Listening on {settings.listening_host}:{settings.webtransport_port} "
          f"(HTTP/TCP + QUIC/UDP)")

    # Start the QUIC/WebTransport server — registers a UDP datagram endpoint
    # with the asyncio event loop and runs for the lifetime of the process.
    await quic_serve(
        settings.listening_host,
        int(settings.webtransport_port),
        configuration=quic_config,
        create_protocol=WebTransportProtocol,
    )

    # Hypercorn keeps the event loop alive; QUIC server runs alongside it.
    await serve(cast(Any, app), http_config)


if __name__ == "__main__":
    asyncio.run(main())
