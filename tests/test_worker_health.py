import runpy

import pytest


def test_worker_health_sqlite(tmp_path, monkeypatch, capsys):
    db = tmp_path / "queue.sqlite3"
    monkeypatch.setenv("CONTROL_QUEUE_BACKEND", "sqlite")
    monkeypatch.setenv("CONTROL_QUEUE_DB", str(db))
    with pytest.raises(SystemExit) as exc:
        runpy.run_path("worker/worker_health.py", run_name="__main__")
    assert exc.value.code == 0
    assert "worker healthy" in capsys.readouterr().out


def test_worker_health_postgres_requires_dsn(monkeypatch):
    monkeypatch.setenv("CONTROL_QUEUE_BACKEND", "postgres")
    monkeypatch.delenv("CONTROL_POSTGRES_DSN", raising=False)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path("worker/worker_health.py", run_name="__main__")
    assert exc.value.code == 1


def test_worker_health_rejects_unknown_backend(monkeypatch):
    monkeypatch.setenv("CONTROL_QUEUE_BACKEND", "unknown")
    with pytest.raises(SystemExit) as exc:
        runpy.run_path("worker/worker_health.py", run_name="__main__")
    assert exc.value.code == 1
