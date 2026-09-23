"""One-command setup and run: venv, dependencies, pipeline, then the UI.

    python start.py

Creates .venv if missing, installs requirements.txt, runs the pipeline
once, builds the frontend (npm install + build on first run only), then
serves the built UI and its API from one process on http://127.0.0.1:8080.
Safe to re-run: an existing venv, node_modules, and already-satisfied
requirements are left alone.
"""

import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
PYTHON = VENV_DIR / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
FRONTEND_DIR = ROOT / "frontend"
NPM = shutil.which("npm.cmd") or shutil.which("npm")


def run(*cmd: str, cwd: Path = ROOT) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> None:
    if not PYTHON.exists():
        print(f"Создаю виртуальное окружение в {VENV_DIR}...")
        venv.create(VENV_DIR, with_pip=True)

    run(str(PYTHON), "-m", "pip", "install", "--quiet", "--upgrade", "pip")
    run(str(PYTHON), "-m", "pip", "install", "--quiet", "-r", "requirements.txt")
    run(str(PYTHON), "run_pipeline.py")

    if NPM is None:
        sys.exit("npm не найден в PATH. Установите Node.js (https://nodejs.org/), затем запустите python start.py снова.")

    if not (FRONTEND_DIR / "node_modules").exists():
        run(NPM, "install", cwd=FRONTEND_DIR)
    if not (FRONTEND_DIR / "dist" / "index.html").exists():
        run(NPM, "run", "build", cwd=FRONTEND_DIR)

    run(str(PYTHON), "run_fingraph.py")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
