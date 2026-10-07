"""
One-command launcher.

  python launcher.py            # start the app, open the web UI (Setup tab) in your browser
  python launcher.py --no-browser

It starts main.py (the AI streamer + HTTP API) and webui.py (the control panel), waits for both, opens the browser,
and stops everything when you press Ctrl+C. The TikTok bridge and product tour are started from the Setup tab.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for(port: int, timeout: float) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if port_open(port):
            return True
        time.sleep(1)
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    os.chdir(ROOT)
    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    web_port = cfg.get("webui", {}).get("port", 8081)
    api_port = cfg.get("api_port", 8082)

    procs = []
    try:
        for script in ("main.py", "webui.py"):
            print(f"Starting {script} ...")
            procs.append(subprocess.Popen([sys.executable, script]))
            time.sleep(2)
        if wait_for(web_port, 90):
            url = f"http://127.0.0.1:{web_port}/"
            print(f"\nControl panel: {url}  (open the Setup tab)\nAPI: http://127.0.0.1:{api_port}/send\nPress Ctrl+C to stop.\n")
            if not a.no_browser:
                webbrowser.open(url)
        else:
            print("The web UI did not come up in 90 s; check the console output above.")
        while all(p.poll() is None for p in procs):
            time.sleep(1)
        print("A process exited; shutting down.")
    except KeyboardInterrupt:
        print("\nStopping ...")
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
