import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Launch the Streamlit app (`uv run nepal-security-incident-map`)."""
    app = Path(__file__).with_name("app.py")
    cmd = [sys.executable, "-m", "streamlit", "run", str(app), *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd))
