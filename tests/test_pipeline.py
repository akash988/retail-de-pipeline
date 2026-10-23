import sys

from pipeline.run_pipeline import run_step


def test_run_step_success():
    r = run_step("ok", [sys.executable, "-c", "print(1)"], retries=0, backoff=0)
    assert r["status"] == "success" and r["attempts"] == 1


def test_run_step_retries_then_fails():
    r = run_step("bad", [sys.executable, "-c", "import sys; sys.exit(3)"],
                 retries=1, backoff=0)
    assert r["status"] == "failed" and r["attempts"] == 2