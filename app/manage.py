"""Small local administration CLI. Run as `python -m app.manage ...`."""

import argparse
import asyncio
from getpass import getpass

from sqlalchemy import func, select

from app.auth import create_user
from app.db import SessionLocal
from app.models import User


async def bootstrap_owner(username: str, display_name: str | None) -> None:
    async with SessionLocal() as session:
        count = (await session.execute(select(func.count(User.id)))).scalar_one()
        if count:
            raise SystemExit("A user already exists; bootstrap is closed")
        password = getpass("Password (minimum 10 characters): ")
        confirmation = getpass("Repeat password: ")
        if password != confirmation:
            raise SystemExit("Passwords do not match")
        if len(password) < 10:
            raise SystemExit("Password must contain at least 10 characters")
        user = await create_user(
            session,
            username,
            password,
            display_name,
            claim_legacy_workspace=True,
        )
        print(f"Created owner {user.username} (id={user.id})")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.manage")
    commands = parser.add_subparsers(dest="command", required=True)
    bootstrap = commands.add_parser("bootstrap-owner")
    bootstrap.add_argument("username")
    bootstrap.add_argument("--display-name")
    args = parser.parse_args()
    if args.command == "bootstrap-owner":
        asyncio.run(bootstrap_owner(args.username, args.display_name))


if __name__ == "__main__":
    main()
