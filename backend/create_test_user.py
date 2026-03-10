import argparse
import json
from pathlib import Path
from typing import Iterable, Sequence, Tuple

from src.core.database import Base, SessionLocal, engine
from src.models.user import User
from src.api.endpoints.auth import get_password_hash

DEFAULT_SEED_FILE = Path(__file__).resolve().with_name("seed_users.json")

def load_users_from_file(file_path: Path) -> list[Tuple[str, str, str]]:
    """Load seed users from JSON file.

    Expected format:
    {
      "users": [
        {"username": "...", "password": "...", "display_name": "..."}
      ]
    }
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to read seed file '{file_path}': {exc}") from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in seed file '{file_path}': {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"Seed file '{file_path}' must contain a JSON object.")

    users = payload.get("users")
    if not isinstance(users, list):
        raise RuntimeError(f"Seed file '{file_path}' must contain a 'users' array.")

    parsed: list[Tuple[str, str, str]] = []
    for idx, item in enumerate(users, start=1):
        if not isinstance(item, dict):
            raise RuntimeError(f"Seed user at index {idx} in '{file_path}' must be an object.")

        username = item.get("username")
        password = item.get("password")
        display_name = item.get("display_name")

        if not isinstance(username, str) or not username.strip():
            raise RuntimeError(f"Seed user at index {idx} in '{file_path}' has invalid 'username'.")

        if not isinstance(password, str) or not password:
            raise RuntimeError(f"Seed user at index {idx} in '{file_path}' has invalid 'password'.")

        if display_name is None:
            display_name = username
        if not isinstance(display_name, str) or not display_name.strip():
            raise RuntimeError(f"Seed user at index {idx} in '{file_path}' has invalid 'display_name'.")

        parsed.append((username, password, display_name))

    if not parsed:
        raise RuntimeError(f"Seed file '{file_path}' contains no users.")

    return parsed


def create_users(users: Iterable[Tuple[str, str, str]]) -> None:
    """Create the given users if they do not already exist."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for username, password, display_name in users:
            existing_user = db.query(User).filter(User.username == username).first()
            if existing_user:
                print(f"User '{username}' already exists (id={existing_user.id})")
                continue

            new_user = User(
                username=username,
                display_name=display_name,
                password_hash=get_password_hash(password),
                hash_type="bcrypt",
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            print(f"User '{username}' created successfully (id={new_user.id})")
    finally:
        db.close()


def parse_users_from_args(args: argparse.Namespace) -> Sequence[Tuple[str, str, str]]:
    if args.user:
        parsed: list[Tuple[str, str, str]] = []
        for entry in args.user:
            if ":" not in entry:
                print(f"Skipping malformed --user '{entry}', expected username:password")
                continue
            username, password = entry.split(":", 1)
            parsed.append((username, password, username))
        return parsed

    return load_users_from_file(args.file)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed test users into the configured application database.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_SEED_FILE,
        help="Path to seed JSON file (default: backend/seed_users.json).",
    )
    parser.add_argument(
        "--user",
        action="append",
        help="User in 'username:password' format (can be provided multiple times).",
    )
    args = parser.parse_args()

    try:
        users = parse_users_from_args(args)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)

    if not users:
        print("No users provided; nothing to create.")
        return

    create_users(users)


if __name__ == "__main__":
    main()
