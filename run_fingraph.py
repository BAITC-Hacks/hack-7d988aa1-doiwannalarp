"""Local-only HTTP adapter for the existing MoneyGraph pipeline and MoneyGraph UI.

No role logic lives here. Identifiers are converted to strings before JSON encoding.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from pandas.api.types import is_integer_dtype

ROOT = Path(__file__).resolve().parent
EXPORTS = ("nodes_roles.csv", "clusters.csv", "top_nodes.csv")
SCHEMAS = {
    "nodes": ["gid", "depth", "is_seed"],
    "edges": ["src", "dst", "sum_kzt", "n_tx", "depth"],
    "transactions": ["src", "dst", "date", "sum_kzt"],
}


def read_frames(directory: Path) -> dict[str, pd.DataFrame]:
    frames = {}
    for name, columns in SCHEMAS.items():
        frame = pd.read_parquet(directory / f"{name}.parquet")
        missing = set(columns) - set(frame.columns)
        if missing:
            raise ValueError(f"{name}: отсутствуют колонки {', '.join(sorted(missing))}")
        if frame.empty:
            raise ValueError(f"{name}: пустой файл")
        for col in ("gid", "src", "dst"):
            if col not in frame:
                continue
            if frame[col].isna().any() or not is_integer_dtype(frame[col].dtype):
                raise ValueError(f"{name}.{col}: ожидается int64 без пропусков; числовые ID с плавающей точкой небезопасны")
            frame[col] = frame[col].astype(str)
        frames[name] = frame
    nodes, edges, tx = (frames[k] for k in SCHEMAS)
    if nodes.gid.duplicated().any():
        raise ValueError("nodes: дубликаты GID")
    if not nodes.depth.isin(range(5)).all() or not nodes.is_seed.isin([True, False]).all():
        raise ValueError("nodes: недопустимые depth или is_seed")
    ids = set(nodes.gid)
    for name in ("edges", "transactions"):
        frame = frames[name]
        if not (set(frame.src) | set(frame.dst)) <= ids:
            raise ValueError(f"{name}: идентификаторы отсутствуют в nodes")
        if not pd.to_numeric(frame.sum_kzt, errors="coerce").map(lambda x: pd.notna(x) and math.isfinite(x) and x >= 0).all():
            raise ValueError(f"{name}: недопустимая сумма")
    if edges.duplicated(["src", "dst"]).any():
        raise ValueError("edges: повторяются агрегированные пары src/dst")
    dates = pd.to_datetime(tx.date, errors="coerce")
    if dates.isna().any():
        raise ValueError("transactions: некорректная дата")
    tx["date"] = dates
    grouped = tx.groupby(["src", "dst"]).sum_kzt.agg(["sum", "size"])
    aligned = edges.set_index(["src", "dst"])[["sum_kzt", "n_tx"]].join(grouped, how="outer")
    if aligned.isna().any().any() or not ((aligned.sum_kzt - aligned["sum"]).abs() < .01).all() or not (aligned.n_tx == aligned["size"]).all():
        raise ValueError("Агрегаты edges не совпадают с transactions: проверьте суммы и количество по каждой паре")
    return frames


def records(frame: pd.DataFrame) -> list[dict]:
    # Never use iterrows: mixed numeric rows can round int64 identifiers to floats.
    frame = frame.copy()
    for col in ("gid", "src", "dst"):
        if col in frame:
            frame[col] = frame[col].astype(str)
    return json.loads(frame.to_json(orient="records", date_format="iso", double_precision=15))


def dataset(data_dir: Path, out_dir: Path) -> dict:
    from moneygraph import thresholds
    frames = read_frames(data_dir)
    nodes, edges, tx = (frames[k] for k in SCHEMAS)
    available = [name for name in EXPORTS if (out_dir / name).exists()]
    if (out_dir / "node_features.parquet").exists():
        enriched = pd.read_parquet(out_dir / "node_features.parquet")
        enriched["gid"] = enriched.gid.astype(str)
        if enriched.gid.duplicated().any() or set(enriched.gid) != set(nodes.gid):
            raise ValueError("Результаты анализа не соответствуют GID текущего набора")
        nodes = nodes.merge(enriched.drop(columns=["depth", "is_seed"], errors="ignore"), on="gid", validate="one_to_one")
    elif (out_dir / "nodes_roles.csv").exists():
        result = pd.read_csv(out_dir / "nodes_roles.csv", dtype={"gid": str})
        if set(result.gid) != set(nodes.gid):
            raise ValueError("nodes_roles.csv не соответствует текущему набору")
        nodes = nodes.merge(result, on="gid", validate="one_to_one")
    for field, group, operation in (("in_sum", "dst", "sum"), ("out_sum", "src", "sum"), ("in_deg", "dst", "size"), ("out_deg", "src", "size")):
        if field not in nodes:
            nodes[field] = nodes.gid.map(edges.groupby(group).sum_kzt.agg(operation)).fillna(0)
    for field, group in (("in_tx", "dst"), ("out_tx", "src")):
        if field not in nodes:
            nodes[field] = nodes.gid.map(tx.groupby(group).size()).fillna(0)
    clusters = pd.read_csv(out_dir / "clusters.csv", dtype={"top_gids": str}) if "clusters.csv" in available else pd.DataFrame()
    for field in ("role_score", "priority_score"):
        if field in nodes and not nodes[field].dropna().between(0, 1).all():
            raise ValueError(f"Результат {field} вне диапазона 0–1")
    if "evidence" in nodes and nodes.evidence.fillna("").str.len().max() > 200:
        raise ValueError("evidence превышает 200 символов")
    has_time = bool((tx.date != tx.date.dt.normalize()).any())
    tx["date"] = tx.date.dt.strftime("%Y-%m-%dT%H:%M:%S" if has_time else "%Y-%m-%d")
    hashes = hashlib.sha256()
    for path in sorted(data_dir.glob("*.parquet")):
        hashes.update(path.read_bytes())
    methodology = ROOT / "docs/METHODOLOGY.md"
    return {
        "meta": {"id": hashes.hexdigest()[:12], "name": "Транзакционная сеть", "mode": "real",
                 "period": [tx.date.min(), tx.date.max()], "has_time": has_time,
                 "analyzed": "role" in nodes, "total_sum": float(tx.sum_kzt.sum()),
                 "files": [{"name": f"{k}.parquet", "rows": len(v)} for k, v in frames.items()],
                 "validation": ["Обязательные колонки присутствуют", "GID уникальны и сохранены без округления", "Все участники переводов найдены в nodes", "Суммы и число транзакций согласованы по каждой паре", "Повторяющиеся транзакции не удалялись"],
                 "computed_at": datetime.fromtimestamp((out_dir / "nodes_roles.csv").stat().st_mtime).isoformat() if "nodes_roles.csv" in available else None,
                 "methodology_version": hashlib.sha256(methodology.read_bytes()).hexdigest()[:10] if methodology.exists() else None},
        "nodes": records(nodes), "edges": records(edges), "transactions": records(tx),
        "clusters": records(clusters), "exports": available,
        "methodology": {"text": methodology.read_text(encoding="utf-8") if methodology.exists() else None,
                        "thresholds": {k: v for k, v in vars(thresholds).items() if k.isupper()}},
    }


class State:
    def __init__(self, data_dir: Path, out_dir: Path):
        self.data_dir, self.out_dir = data_dir, out_dir
        self.lock = threading.RLock()
        self.status = {"state": "idle", "message": "Расчёт не запущен"}
        self.cache = None

    def load(self):
        with self.lock:
            if self.cache is None:
                self.cache = dataset(self.data_dir, self.out_dir)
            return self.cache

    def analyze(self):
        with self.lock:
            if self.status["state"] == "running":
                raise ValueError("Расчёт уже выполняется")
            # Existing outputs and documentation are kept intact: each calculation is isolated.
            work = ROOT / ".fingraph" / uuid.uuid4().hex
            work.mkdir(parents=True)
            target = work / "outputs"
            data_dir = self.data_dir
            self.status = {"state": "running", "message": "Выполняется аналитический pipeline"}

        def job():
            try:
                result = subprocess.run([sys.executable, str(ROOT / "run_pipeline.py"), "--data", str(data_dir), "--out", str(target)], cwd=work, capture_output=True, text=True, timeout=600)
                if result.returncode:
                    raise ValueError(result.stderr[-4000:])
                payload = dataset(data_dir, target)
                with self.lock:
                    self.out_dir, self.cache = target, payload
                    self.status = {"state": "done", "message": "Анализ завершён; результаты доступны"}
            except Exception as exc:
                with self.lock:
                    self.status = {"state": "error", "message": str(exc)}
        threading.Thread(target=job, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    server_version = "MoneyGraphLocal/1.0"

    def send(self, status, body, content_type="application/json; charset=utf-8", filename=None):
        encoded = json.dumps(body, ensure_ascii=False, allow_nan=False).encode() if not isinstance(body, bytes) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        import mimetypes
        path = urlparse(self.path).path
        state = self.server.state
        try:
            if path == "/api/dataset":
                return self.send(200, state.load())
            if path == "/api/status":
                return self.send(200, state.status)
            if path.startswith("/api/exports/"):
                name = path.rsplit("/", 1)[-1]
                if name not in EXPORTS or name not in state.load()["exports"]:
                    return self.send(404, {"error": "Выгрузка ещё не сформирована"})
                return self.send(200, (state.out_dir / name).read_bytes(), "text/csv; charset=utf-8", name)
            if path.startswith("/api/"):
                return self.send(404, {"error": "Маршрут не найден"})
            dist = ROOT / "frontend/dist"
            target = (dist / path.lstrip("/")).resolve()
            if not target.is_relative_to(dist.resolve()):
                return self.send(403, {"error": "Недопустимый путь"})
            if not target.is_file():
                target = dist / "index.html"
            if not target.exists():
                return self.send(503, {"error": "Сначала выполните npm --prefix frontend run build"})
            return self.send(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        except Exception as exc:
            return self.send(422, {"error": str(exc)})

    def do_POST(self):
        # No cross-origin writes; bound to loopback only. JSON requests also require a custom header.
        origin = self.headers.get("Origin")
        if self.headers.get("X-FinGraph") != "local" or (origin and urlparse(origin).netloc != self.headers.get("Host")):
            return self.send(403, {"error": "Разрешены только локальные запросы интерфейса"})
        state = self.server.state
        try:
            path = urlparse(self.path).path
            if path == "/api/analyze":
                state.analyze()
                return self.send(202, state.status)
            if path != "/api/upload":
                return self.send(404, {"error": "Маршрут не найден"})
            with state.lock:
                if state.status["state"] == "running":
                    raise ValueError("Дождитесь завершения расчёта перед заменой набора")
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 100_000_000:
                    raise ValueError("Размер запроса должен быть от 1 байта до 100 МБ")
                body = json.loads(self.rfile.read(size))
                target = ROOT / ".fingraph" / uuid.uuid4().hex
                directory = target / "data"
                directory.mkdir(parents=True)
                for name in SCHEMAS:
                    (directory / f"{name}.parquet").write_bytes(base64.b64decode(body[f"{name}.parquet"], validate=True))
                payload = dataset(directory, target / "outputs")
                state.data_dir, state.out_dir, state.cache = directory, target / "outputs", payload
                state.status = {"state": "idle", "message": "Набор загружен. Анализ не выполнен"}
                return self.send(200, payload)
        except Exception as exc:
            return self.send(422, {"error": str(exc)})


def main():
    parser = argparse.ArgumentParser(description="MoneyGraph: локальный интерфейс транзакционной сети")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.state = State(args.data.resolve(), args.out.resolve())
    print(f"MoneyGraph: http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
