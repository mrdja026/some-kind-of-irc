#!/usr/bin/env python3
"""Manual export of merged Caddy + AI session streams (same JSON as redis-log-sink on SIGTERM).

Environment:
  REDIS_LOG_URL           — required (e.g. redis://redis-log:6379/0)
  REDIS_LOG_STREAM_KEY    — default caddy:warn_error_logs
  AI_SESSION_STREAM_KEY   — default ai:session_events
  SESSION_DUMP_DIR        — if set, write {utc}-data-session.json here
  SESSION_ID              — optional opaque id for the dump document
  DUMP_TO_STDOUT          — if "1" or "true", print JSON to stdout (no file)
"""

from __future__ import annotations

import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import redis  # noqa: E402

from ai_session_dump_lib import (  # noqa: E402
    DEFAULT_AI_STREAM_KEY,
    DEFAULT_CADDY_STREAM_KEY,
    build_session_dump_document,
    write_session_dump_json,
)


def main() -> int:
    url = os.getenv("REDIS_LOG_URL", "").strip()
    if not url:
        print("REDIS_LOG_URL is required", file=sys.stderr)
        return 1

    caddy_key = os.getenv("REDIS_LOG_STREAM_KEY", DEFAULT_CADDY_STREAM_KEY).strip()
    ai_key = os.getenv("AI_SESSION_STREAM_KEY", DEFAULT_AI_STREAM_KEY).strip()
    session_id = os.getenv("SESSION_ID", "").strip() or None
    stdout = os.getenv("DUMP_TO_STDOUT", "").lower() in ("1", "true", "yes")
    dump_dir = os.getenv("SESSION_DUMP_DIR", "").strip()
    if not stdout and not dump_dir:
        print(
            "Set SESSION_DUMP_DIR to write a file, or DUMP_TO_STDOUT=1 for stdout",
            file=sys.stderr,
        )
        return 1

    client = redis.from_url(url, decode_responses=False)
    try:
        doc = build_session_dump_document(
            client,
            caddy_stream_key=caddy_key,
            ai_stream_key=ai_key,
            session_id=session_id,
        )
    finally:
        client.close()

    if stdout:
        json.dump(doc, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    path = write_session_dump_json(doc, dump_dir)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
