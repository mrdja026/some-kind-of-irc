import json
import logging
import os
import signal
import socketserver
import threading
from datetime import datetime, timezone

import redis

from session_dump_lib import (
    DEFAULT_AI_STREAM_KEY,
    build_session_dump_document,
    write_session_dump_json,
)

LOG = logging.getLogger("redis-log-sink")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

LISTEN_HOST = os.getenv("LOG_SINK_HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("LOG_SINK_PORT", "6001"))
REDIS_LOG_URL = os.getenv("REDIS_LOG_URL", "redis://redis-log:6379/0")
REDIS_LOG_STREAM_KEY = os.getenv("REDIS_LOG_STREAM_KEY", "caddy:warn_error_logs")
AI_SESSION_STREAM_KEY = os.getenv("AI_SESSION_STREAM_KEY", DEFAULT_AI_STREAM_KEY)
REDIS_LOG_MAXLEN = int(os.getenv("REDIS_LOG_MAXLEN", "200"))
ALLOWED_LEVELS = {"warn", "error"}

redis_client = redis.from_url(REDIS_LOG_URL, decode_responses=True)

_session_dump_written = False


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


def _write_merged_session_dump() -> None:
    global _session_dump_written
    if _session_dump_written:
        return
    dump_dir = os.getenv("SESSION_DUMP_DIR", "").strip()
    if not dump_dir:
        LOG.error(
            "SESSION_DUMP_DIR is not set; skipping merged session dump on shutdown. "
            "Set SESSION_DUMP_DIR to a writable directory or run scripts/dump-ai-data-session.py."
        )
        return
    sync = redis.from_url(REDIS_LOG_URL, decode_responses=False)
    try:
        doc = build_session_dump_document(
            sync,
            caddy_stream_key=REDIS_LOG_STREAM_KEY,
            ai_stream_key=AI_SESSION_STREAM_KEY,
        )
        path = write_session_dump_json(doc, dump_dir)
        LOG.info("Wrote merged AI session dump to %s", path)
        _session_dump_written = True
    except OSError as exc:
        LOG.error("Failed to write session dump under %s: %s", dump_dir, exc)
    except redis.RedisError as exc:
        LOG.error("Redis error while building session dump: %s", exc)
    except Exception:
        LOG.exception("Unexpected error while writing session dump")
    finally:
        sync.close()


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

            if not isinstance(payload, dict):
                payload = {"msg": raw_line}

            level = str(payload.get("level", "")).lower()
            if level not in ALLOWED_LEVELS:
                continue

            entry = _build_stream_entry(payload, raw_line, level)
            try:
                redis_client.xadd(
                    REDIS_LOG_STREAM_KEY,
                    entry,
                    maxlen=REDIS_LOG_MAXLEN,
                    approximate=False,
                )
            except redis.RedisError as exc:
                LOG.error(
                    "Redis error writing to stream %s: %s (entry: %r)",
                    REDIS_LOG_STREAM_KEY,
                    exc,
                    entry,
                )
            except Exception as exc:
                LOG.exception(
                    "Unexpected error writing to stream %s: %s",
                    REDIS_LOG_STREAM_KEY,
                    exc,
                )

        LOG.info("Stream closed from %s", peer)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    # Allow process to exit after shutdown so SIGTERM finally{} runs the dump writer.
    daemon_threads = True


def main() -> None:
    dump_dir_status = os.getenv("SESSION_DUMP_DIR", "").strip() or "(unset)"
    LOG.info(
        "Starting sink on %s:%s -> %s stream=%s maxlen=%s ai_stream=%s dump_dir=%s",
        LISTEN_HOST,
        LISTEN_PORT,
        REDIS_LOG_URL,
        REDIS_LOG_STREAM_KEY,
        REDIS_LOG_MAXLEN,
        AI_SESSION_STREAM_KEY,
        dump_dir_status,
    )
    server = ThreadedTCPServer((LISTEN_HOST, LISTEN_PORT), LogLineHandler)

    def handle_sig(signum: int, _frame: object) -> None:
        LOG.info("Received signal %s, shutting down TCP server", signum)
        # Shutdown must run in a separate thread: calling server.shutdown() from
        # the signal handler (which runs in the main thread blocked in
        # serve_forever()) would deadlock because shutdown() waits for
        # serve_forever() to exit. The dump is written in the finally block
        # after all worker threads have drained.
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, handle_sig)
    signal.signal(signal.SIGINT, handle_sig)

    try:
        server.serve_forever()
    finally:
        LOG.info("Sink TCP server stopped; writing merged session dump if configured")
        server.server_close()
        _write_merged_session_dump()


if __name__ == "__main__":
    main()
