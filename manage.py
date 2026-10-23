"""User administration from the command line.

python manage.py create-user <username> --name "Display Name" --role admin
python manage.py set-password <username>
python manage.py set-role <username> admin
python manage.py list-users
Add --data-dir PATH when the server uses one.
"""
import argparse
import getpass
import os
import sys

ROLES = ["viewer", "member", "team_leader", "champion", "admin"]


def _password():
    pw = getpass.getpass("Password (min. 10 characters): ")
    if len(pw) < 10 or pw != getpass.getpass("Repeat password: "):
        sys.exit("Password too short or not matching.")
    return pw


def main():
    p = argparse.ArgumentParser(description="A3 Tracker user administration")
    p.add_argument("--data-dir")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-user")
    c.add_argument("username")
    c.add_argument("--name", required=True)
    c.add_argument("--role", choices=ROLES, default="member")
    s = sub.add_parser("set-password")
    s.add_argument("username")
    r = sub.add_parser("set-role")
    r.add_argument("username")
    r.add_argument("role", choices=ROLES)
    sub.add_parser("list-users")
    args = p.parse_args()
    if args.data_dir:
        os.environ["A3_DATA_DIR"] = args.data_dir

    from werkzeug.security import generate_password_hash

    from a3app import create_app, db
    app = create_app()
    with app.app_context():
        if args.cmd == "create-user":
            if db.get_user_by_username(args.username):
                sys.exit("User already exists.")
            db.create_user(args.username, args.name, generate_password_hash(_password()), args.role)
            print(f"Created {args.username} ({args.role}).")
        elif args.cmd == "set-password":
            u = db.get_user_by_username(args.username)
            if not u:
                sys.exit("No such user.")
            db.update_user(u["id"], password_hash=generate_password_hash(_password()), active=1)
            print("Password set and account activated.")
        elif args.cmd == "set-role":
            u = db.get_user_by_username(args.username)
            if not u:
                sys.exit("No such user.")
            db.update_user(u["id"], role=args.role, active=1)
            print(f"{args.username} is now {args.role} (active).")
        else:
            for u in db.list_users():
                print(f"{u['username']:20} {u['role']:12} {'active' if u['active'] else 'inactive':9} {u['display_name']}")


if __name__ == "__main__":
    main()
