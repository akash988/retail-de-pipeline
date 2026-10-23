"""Orchestrator: run the whole pipeline with retries, stop-on-failure and run logging.

Run:  python -m pipeline.run_pipeline
      python -m pipeline.run_pipeline --skip-weather --retries 2
"""
import argparse
import json
import logging
import subprocess
import sys
import time
import uuid
from datetime import datetime

import duckdb

from ingestion import config

log = logging.getLogger("pipeline")


def build_steps(skip_weather: bool) -> list[tuple[str, list[str]]]:
    ingest = [sys.executable, "-m", "ingestion.ingest"]
    if skip_weather:
        ingest.append("--skip-weather")
    return [
        ("ingest", ingest),
        ("silver", [sys.executable, "-m", "transform.silver"]),
        ("gold", [sys.executable, "-m", "transform.gold"]),
        ("warehouse", [sys.executable, "-m", "warehouse.load"]),
    ]


def run_step(name: str, cmd: list[str], retries: int = 1, backoff: float = 5) -> dict:
    started = datetime.now()
    t0 = time.time()
    status, message, attempts = "failed", "", 0
    for attempt in range(1, retries + 2):
        attempts = attempt
        log.info("Step '%s' attempt %d", name, attempt)
        proc = subprocess.run(cmd, cwd=config.ROOT, capture_output=True,
                              text=True, errors="replace")
        if proc.returncode == 0:
            status, message = "success", ""
            break
        message = (proc.stderr or proc.stdout).strip()[-500:]
        log.warning("Step '%s' failed (attempt %d): %s", name, attempt, message[-200:])
        if attempt <= retries:
            time.sleep(backoff * attempt)
    return {"step": name, "status": status, "started_at": started,
            "duration_s": round(time.time() - t0, 1),
            "attempts": attempts, "message": message}


def record_runs(run_id: str, results: list[dict]) -> None:
    config.LOG_DIR.mkdir(exist_ok=True)
    with open(config.LOG_DIR / "pipeline_runs.jsonl", "a", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps({"run_id": run_id, **r}, default=str) + "\n")
    try:
        config.SERVING_DB.parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(str(config.SERVING_DB))
        con.execute("""CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id VARCHAR, step VARCHAR, status VARCHAR, started_at TIMESTAMP,
            duration_s DOUBLE, attempts INTEGER, message VARCHAR)""")
        for r in results:
            con.execute("INSERT INTO pipeline_runs VALUES (?,?,?,?,?,?,?)",
                        [run_id, r["step"], r["status"], r["started_at"],
                         r["duration_s"], r["attempts"], r["message"]])
        con.close()
    except Exception as e:
        log.warning("Could not write run history to warehouse: %s", e)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--skip-weather", action="store_true")
    p.add_argument("--retries", type=int, default=1, help="extra attempts per step")
    a = p.parse_args()

    config.LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(config.LOG_DIR / "pipeline.log"),
                  logging.StreamHandler()],
    )
    run_id = uuid.uuid4().hex[:8]
    log.info("=== Pipeline run %s started ===", run_id)

    results, failed = [], False
    for name, cmd in build_steps(a.skip_weather):
        if failed:
            results.append({"step": name, "status": "skipped", "started_at": datetime.now(),
                            "duration_s": 0.0, "attempts": 0, "message": "earlier step failed"})
            continue
        r = run_step(name, cmd, retries=a.retries)
        results.append(r)
        failed = r["status"] != "success"

    record_runs(run_id, results)

    print(f"\nRun {run_id}")
    print(f"{'step':<12}{'status':<10}{'seconds':>9}{'attempts':>10}")
    for r in results:
        print(f"{r['step']:<12}{r['status']:<10}{r['duration_s']:>9}{r['attempts']:>10}")
    if failed:
        bad = next(r for r in results if r["status"] == "failed")
        print(f"\nFAILED at '{bad['step']}':\n{bad['message']}")
        log.error("=== Pipeline run %s FAILED ===", run_id)
        sys.exit(1)
    log.info("=== Pipeline run %s finished OK ===", run_id)


if __name__ == "__main__":
    main()