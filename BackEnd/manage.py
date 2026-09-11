"""Owner CLI, run from the Render service shell or a local checkout:

    python manage.py enroll <username> [--reps-user Aviv2026] [--display-name "Aviv"]
    python manage.py list-devices
    python manage.py approve-device <device-id>
    python manage.py revoke-device <device-id>
    python manage.py revoke-sessions [--user <username>]

`enroll` prints a one-time enrollment link (15 minutes). Open it on the device
to enrol; the passkey created there is the login from then on.
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

import bootstrap  # noqa: E402
from db import SessionLocal, engine  # noqa: E402
from BL.auth import register as register_bl  # noqa: E402
from BL.auth import session as sessions  # noqa: E402
from BL.auth.common import settings  # noqa: E402
from DAL.crud import auth as crud  # noqa: E402


def app_origin() -> str:
    return (os.getenv("AUTH_APP_ORIGIN") or settings.allowed_origins()[0]).rstrip("/")


def cmd_enroll(args) -> int:
    with SessionLocal() as db:
        user = crud.get_user_by_username(db, args.username)
        if user is None:
            user = crud.add_user(
                db,
                username=args.username,
                display_name=args.display_name or args.username,
                reps_user=args.reps_user,
            )
        elif args.reps_user or args.display_name:
            user.reps_user = args.reps_user or user.reps_user
            user.display_name = args.display_name or user.display_name
        token = register_bl.issue_enrollment_token(db, user=user, created_by=None)
        db.commit()
    print(f"{app_origin()}/enroll?token={token}")
    print(f"(valid for {settings.enroll_minutes()} minutes, single use)", file=sys.stderr)
    return 0


def cmd_list_devices(args) -> int:
    with SessionLocal() as db:
        for d in crud.list_devices(db):
            user = crud.get_user(db, d.user_id)
            print(f"{d.id}  {d.status:8}  {d.kind:8}  {user.username if user else '?':16}  {d.label}  last seen {d.last_seen_at:%Y-%m-%d %H:%M} from {d.last_ip or '?'}")
    return 0


def _set_device_status(device_id: str, status: str) -> int:
    from uuid import UUID

    with SessionLocal() as db:
        device = crud.get_device(db, UUID(device_id))
        if device is None:
            print("device not found", file=sys.stderr)
            return 1
        device.status = status
        if status == "trusted":
            device.approved_at = crud.now()
            for s in crud.sessions_for_device(db, device.id):
                if s.status == "pending":
                    s.status = "trusted"
        else:
            device.revoked_at = crud.now()
            sessions.revoke_device_sessions(db, device.id)
        db.commit()
    print(f"device {device_id} is now {status}")
    return 0


def cmd_approve_device(args) -> int:
    return _set_device_status(args.device_id, "trusted")


def cmd_revoke_device(args) -> int:
    return _set_device_status(args.device_id, "revoked")


def cmd_revoke_sessions(args) -> int:
    with SessionLocal() as db:
        if args.user:
            user = crud.get_user_by_username(db, args.user)
            rows = crud.sessions_for_user(db, user.id) if user else []
        else:
            from DAL.data_models.auth.models import Session

            rows = db.query(Session).all()
        n = 0
        for s in rows:
            if s.status != "revoked":
                sessions.revoke(s)
                n += 1
        db.commit()
    print(f"revoked {n} session(s)")
    return 0


def main(argv=None) -> int:
    bootstrap.run(engine, SessionLocal)
    parser = argparse.ArgumentParser(prog="manage.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("enroll"); p.add_argument("username"); p.add_argument("--reps-user"); p.add_argument("--display-name"); p.set_defaults(fn=cmd_enroll)
    p = sub.add_parser("list-devices"); p.set_defaults(fn=cmd_list_devices)
    p = sub.add_parser("approve-device"); p.add_argument("device_id"); p.set_defaults(fn=cmd_approve_device)
    p = sub.add_parser("revoke-device"); p.add_argument("device_id"); p.set_defaults(fn=cmd_revoke_device)
    p = sub.add_parser("revoke-sessions"); p.add_argument("--user"); p.set_defaults(fn=cmd_revoke_sessions)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
