import json
import logging
import os
import socketserver
from datetime import datetime, timezone

import redis

LOG = logging.getLogger("redis-log-sink")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

LISTEN_HOST = os.getenv("LOG_SINK_HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("LOG_SINK_PORT", "6001"))
REDIS_LOG_URL = os.getenv("REDIS_LOG_URL", "redis://redis-log:6379/0")
REDIS_LOG_STREAM_KEY = os.getenv("REDIS_LOG_STREAM_KEY", "caddy:warn_error_logs")
REDIS_LOG_MAXLEN = int(os.getenv("REDIS_LOG_MAXLEN", "200"))
ALLOWED_LEVELS = {"warn", "error"}

redis_client = redis.from_url(REDIS_LOG_URL, decode_responses=True)


def _build_stream_entry(payload: dict, raw_line: str, level: str) -> dict[str, str]:
    ts = payload.get("ts")
    if not isinstance(ts, str):
        ts = datetime.now(timezone.utc).isoformat()

    msg = payload.get("msg")
    if not isinstance(msg, str):
        msg = raw_line

    logger_name = payload.get("logger")
    if not isinstance(logger_name, str):
        logger_name = "caddy"

    return {
        "ts": ts,
        "level": level,
        "logger": logger_name,
        "msg": msg,
        "payload": raw_line,
    }


class LogLineHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        peer = f"{self.client_address[0]}:{self.client_address[1]}"
        LOG.info("Accepted stream from %s", peer)
        while True:
            line = self.rfile.readline()
            if not line:
                break

            raw_line = line.decode("utf-8", errors="replace").strip()
            if not raw_line:
                continue

            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                payload = {"msg": raw_line}

            level = str(payload.get("level", "")).lower()
            if level not in ALLOWED_LEVELS:
                continue

            entry = _build_stream_entry(payload, raw_line, level)
            redis_client.xadd(
                REDIS_LOG_STREAM_KEY,
                entry,
                maxlen=REDIS_LOG_MAXLEN,
                approximate=False,
            )

        LOG.info("Stream closed from %s", peer)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


def main() -> None:
    LOG.info(
        "Starting sink on %s:%s -> %s stream=%s maxlen=%s",
        LISTEN_HOST,
        LISTEN_PORT,
        REDIS_LOG_URL,
        REDIS_LOG_STREAM_KEY,
        REDIS_LOG_MAXLEN,
    )
    with ThreadedTCPServer((LISTEN_HOST, LISTEN_PORT), LogLineHandler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
