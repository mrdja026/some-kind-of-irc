import logging
import sys
from typing import Dict, Optional, Any

_logger = logging.getLogger("irc")
if not _logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)


class IrcStateStore:
    def __init__(self) -> None:
        self._state: Dict[int, Dict[str, Optional[str]]] = {}

    def set_nick(self, user_id: int, nick: str) -> None:
        self._state.setdefault(user_id, {})
        self._state[user_id]["nick"] = nick

    def set_current_channel(self, user_id: int, channel_id: int, channel_name: str) -> None:
        self._state.setdefault(user_id, {})
        self._state[user_id]["channel_id"] = str(channel_id)
        self._state[user_id]["channel_name"] = channel_name

    def get_nick(self, user_id: int) -> str:
        nick = self._state.get(user_id, {}).get("nick")
        return nick if nick else f"user{user_id}"

    def get_channel_name(self, user_id: int, channel_id: int) -> Optional[str]:
        state = self._state.get(user_id, {})
        if state.get("channel_id") == str(channel_id):
            return state.get("channel_name")
        return None


state_store = IrcStateStore()


def _prefix(nick: str) -> str:
    return f":{nick}!user@host"


def _target_for_channel(channel_id: int, channel_name: Optional[str]) -> str:
    if channel_name:
        return channel_name
    return f"#channel-{channel_id}"


def log_nick_user(user_id: int | Any, nick: str | Any) -> None:
    state_store.set_nick(user_id, nick)
    _logger.info(f"{_prefix(nick)} NICK {nick}")
    _logger.info(f"{_prefix(nick)} USER {nick} 0 * :{nick}")


def log_join(user_id: int | Any, channel_id: int | Any, channel_name: str | Any) -> None:
    nick = state_store.get_nick(user_id)
    state_store.set_current_channel(user_id, channel_id, channel_name)
    _logger.info(f"{_prefix(nick)} JOIN {channel_name}")


def log_part(user_id: int | Any, channel_id: int | Any, channel_name: Optional[str] = None) -> None:
    nick = state_store.get_nick(user_id)
    target = _target_for_channel(channel_id, channel_name or state_store.get_channel_name(user_id, channel_id))
    _logger.info(f"{_prefix(nick)} PART {target}")


def log_privmsg(
    user_id: int | Any,
    channel_id: Optional[int | Any],
    message: str,
    channel_name: Optional[str] = None,
) -> None:
    if channel_id is None:
        return
    nick = state_store.get_nick(user_id)
    target = _target_for_channel(channel_id, channel_name or state_store.get_channel_name(user_id, channel_id))
    _logger.info(f"{_prefix(nick)} PRIVMSG {target} :{message}")
