#!/usr/bin/env python3
"""
Paperly Administrative CLI Tool
Allows administrator to securely provision accounts, list users, disable accounts,
and reset passwords on the self-hosted backend.
"""
import sys
import argparse
import secrets
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import SessionLocal, migrate
from app.core.security import get_password_hash
from app.models.user import User
import app.models  # ensure models registered


def init_db():
    migrate()


def create_user(username: str, password: str, full_name: str | None = None, role: str = "teacher"):
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"Error: User '{username}' already exists.")
            sys.exit(1)

        hashed = get_password_hash(password)
        user = User(
            username=username,
            hashed_password=hashed,
            full_name=full_name,
            role=role,
            is_active=True
        )
        db.add(user)
        db.commit()
        print(f"Successfully created user '{username}' (Role: {role}).")
    finally:
        db.close()


def list_users():
    init_db()
    db = SessionLocal()
    try:
        users = db.query(User).all()
        if not users:
            print("No users found in database.")
            return

        print(f"{'ID':<38} {'Username':<20} {'Role':<10} {'Status':<10} {'Full Name'}")
        print("-" * 90)
        for u in users:
            status = "Active" if u.is_active else "Disabled"
            print(f"{u.id:<38} {u.username:<20} {u.role:<10} {status:<10} {u.full_name or ''}")
    finally:
        db.close()


def reset_password(username: str, new_password: str):
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"Error: User '{username}' not found.")
            sys.exit(1)

        user.hashed_password = get_password_hash(new_password)
        db.commit()
        print(f"Password reset successfully for user '{username}'.")
    finally:
        db.close()


def toggle_user_status(username: str, enable: bool):
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"Error: User '{username}' not found.")
            sys.exit(1)

        user.is_active = enable
        db.commit()
        state = "enabled" if enable else "disabled"
        print(f"User '{username}' is now {state}.")
    finally:
        db.close()


_WORDS = [
    "Maple", "River", "Cobalt", "Falcon", "Cedar", "Orbit", "Lotus", "Amber", "Tiger", "Coral",
    "Nova", "Pixel", "Harbor", "Summit", "Willow", "Comet", "Atlas", "Ember", "Quartz", "Jasmine",
]


def _readable_password() -> str:
    """Easy to type on a phone, still ~40 bits of entropy: Word-1234-Word."""
    return f"{secrets.choice(_WORDS)}-{secrets.randbelow(9000) + 1000}-{secrets.choice(_WORDS)}"


def seed_accounts(count: int, reset: bool):
    """Create teacher01..teacherNN plus an admin account and write credentials.txt."""
    init_db()
    db = SessionLocal()
    lines = []
    try:
        wanted = [("admin", "Administrator", "admin")] + [
            (f"teacher{i:02d}", f"Teacher {i:02d}", "teacher") for i in range(1, count + 1)
        ]
        for username, full_name, role in wanted:
            user = db.query(User).filter(User.username == username).first()
            if user and not reset:
                print(f"  skip  {username} (already exists; use --reset to give it a new password)")
                continue
            password = _readable_password()
            if user:
                user.hashed_password = get_password_hash(password)
                user.is_active = True
            else:
                db.add(User(username=username, hashed_password=get_password_hash(password),
                            full_name=full_name, role=role, is_active=True))
            lines.append(f"{username:<12} {password:<24} {role}")
            print(f"  ready {username}")
        db.commit()
    finally:
        db.close()

    if lines:
        out = backend_dir / "credentials.txt"
        with out.open("a") as f:
            f.write("USERNAME     PASSWORD                 ROLE\n")
            f.write("\n".join(lines) + "\n\n")
        out.chmod(0o600)
        print(f"\nSaved {len(lines)} login(s) to {out}")
        print("Show them with:  cat credentials.txt")


def check_gemini():
    """Verify GEMINI_API_KEY and GEMINI_MODEL with one tiny request."""
    from app.core.config import settings
    if not settings.ai_enabled:
        print("GEMINI_API_KEY is not set in .env, so the server runs in offline demo mode.")
        print("Get a key at https://aistudio.google.com/apikey and put it in backend/.env")
        sys.exit(1)
    from google import genai
    print(f"Testing model '{settings.GEMINI_MODEL}' ...")
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        reply = client.models.generate_content(model=settings.GEMINI_MODEL, contents="Reply with just: OK")
        print(f"Success! Gemini replied: {(reply.text or '').strip()}")
    except Exception as e:
        print(f"FAILED: {e}")
        print("Check the key, the model name in .env, and that the phone has internet.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Paperly Administrative CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-user
    parser_create = subparsers.add_parser("create-user", help="Create a new teacher or admin account")
    parser_create.add_argument("--username", required=True, help="Username for login")
    parser_create.add_argument("--password", required=True, help="Password")
    parser_create.add_argument("--full-name", default=None, help="Teacher's full name")
    parser_create.add_argument("--role", default="teacher", choices=["teacher", "admin"], help="User role")

    # list-users
    subparsers.add_parser("list-users", help="List all registered user accounts")

    # reset-password
    parser_reset = subparsers.add_parser("reset-password", help="Reset a user's password")
    parser_reset.add_argument("--username", required=True, help="Username to update")
    parser_reset.add_argument("--new-password", required=True, help="New password")

    # disable-user
    parser_disable = subparsers.add_parser("disable-user", help="Disable a user account")
    parser_disable.add_argument("--username", required=True, help="Username to disable")

    # enable-user
    parser_enable = subparsers.add_parser("enable-user", help="Enable a user account")
    parser_enable.add_argument("--username", required=True, help="Username to enable")

    # seed-accounts
    parser_seed = subparsers.add_parser("seed-accounts", help="Create admin + teacher01..teacherNN with random passwords")
    parser_seed.add_argument("--count", type=int, default=10, help="Number of teacher accounts (default 10)")
    parser_seed.add_argument("--reset", action="store_true", help="Give existing accounts new passwords")

    # check-gemini
    subparsers.add_parser("check-gemini", help="Test the Gemini API key and model")

    args = parser.parse_args()

    if args.command == "create-user":
        create_user(args.username, args.password, args.full_name, args.role)
    elif args.command == "list-users":
        list_users()
    elif args.command == "reset-password":
        reset_password(args.username, args.new_password)
    elif args.command == "disable-user":
        toggle_user_status(args.username, enable=False)
    elif args.command == "enable-user":
        toggle_user_status(args.username, enable=True)
    elif args.command == "seed-accounts":
        seed_accounts(args.count, args.reset)
    elif args.command == "check-gemini":
        check_gemini()


if __name__ == "__main__":
    main()
