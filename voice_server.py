"""
Start the free VieNeu-TTS voice server (Apache-2.0, runs on CPU or GPU) in its own environment.

  python voice_server.py            # creates venv_voice on first run (needs internet), then serves http://127.0.0.1:8000
  python voice_server.py --port 8010

Then choose "VieNeu-TTS" as the speech synthesis type (Voice tab). If the server is not running, the app falls back
to edge-tts automatically.
"""
import argparse
import os
import subprocess
import sys

from utils import setup_wizard


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--backend", default="auto", choices=["auto", "onnx", "pytorch"])
    a = ap.parse_args()
    py = setup_wizard.ensure_voice_env()
    env = dict(os.environ, HOST="127.0.0.1", PORT=str(a.port), VIENEU_BACKEND=a.backend)
    print(f"VieNeu-TTS server on http://127.0.0.1:{a.port}  (first start downloads the model, then it is cached)")
    sys.exit(subprocess.call(setup_wizard.voice_command(py), env=env))


if __name__ == "__main__":
    main()
