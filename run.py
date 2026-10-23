"""Start the A3 Tracker.

Single user:   python run.py                      -> http://127.0.0.1:8080
Team (one host serves, others browse to http://<host>:8080):
               python run.py --host 0.0.0.0 --data-dir \\\\server\\share\\A3
Stop:          Ctrl+C in this terminal.
"""
import argparse
import os


def main():
    p = argparse.ArgumentParser(description="A3 Problem Solving tracker")
    p.add_argument("--host", default="127.0.0.1", help="Bind address (0.0.0.0 to serve the team)")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--data-dir", help="Folder holding a3.sqlite3 and optional a3config.toml (default: ./instance)")
    args = p.parse_args()
    if args.data_dir:
        os.environ["A3_DATA_DIR"] = args.data_dir

    from waitress import serve

    from a3app import create_app
    app = create_app()
    print(f"A3 Tracker on http://{args.host}:{args.port}")
    print(f"  database: {app.config['DATABASE']}")
    print(f"  config:   {app.config['A3']['_path']}")
    print("  stop with Ctrl+C")
    serve(app, host=args.host, port=args.port, threads=8)


if __name__ == "__main__":
    main()
