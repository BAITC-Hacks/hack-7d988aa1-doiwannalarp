"""One-command setup and run: venv, dependencies, pipeline, then the UI.

    python start.py

Creates .venv if missing, installs requirements.txt, runs the pipeline
once, then launches the Streamlit app. Safe to re-run: an existing venv
and already-satisfied requirements are left alone.
"""

import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
PYTHON = VENV_DIR / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def run(*cmd: str) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    if not PYTHON.exists():
        print(f"Создаю виртуальное окружение в {VENV_DIR}...")
        venv.create(VENV_DIR, with_pip=True)

    run(str(PYTHON), "-m", "pip", "install", "--quiet", "--upgrade", "pip")
    run(str(PYTHON), "-m", "pip", "install", "--quiet", "-r", "requirements.txt")
    run(str(PYTHON), "run_pipeline.py")
    run(str(PYTHON), "-m", "streamlit", "run", "app/main.py", "--server.headless", "true")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
