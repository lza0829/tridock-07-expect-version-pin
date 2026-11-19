from __future__ import annotations
from fastapi import APIRouter
from app.db import connect
from app.services.batch_evidence import batch_view
from app.services.gate import is_sealed

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard():
    conn = connect()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key='dock_day'").fetchone()
        day = row["value"] if row else None
        expect_n = receive_n = confirm_n = 0
        batch = None
        pending = 0
        sealed = False
        if day:
            expect_n = conn.execute(
                "SELECT COUNT(*) c FROM expect_lines WHERE dock_day=?", (day,)
            ).fetchone()["c"]
            receive_n = conn.execute(
                "SELECT COUNT(*) c FROM receive_lines WHERE dock_day=?", (day,)
            ).fetchone()["c"]
            confirm_n = conn.execute(
                "SELECT COUNT(*) c FROM confirm_lines WHERE dock_day=?", (day,)
            ).fetchone()["c"]
            sealed_row = conn.execute(
                "SELECT * FROM reconcile_batches WHERE dock_day=? AND status='sealed' LIMIT 1",
                (day,),
            ).fetchone()
            sealed = sealed_row is not None
            # 已结案时总览锁定封印批；否则展示当前可用于结案的 open 批。
            batch = sealed_row or conn.execute(
                "SELECT * FROM reconcile_batches WHERE dock_day=? AND status='open' "
                "ORDER BY id DESC LIMIT 1",
                (day,),
            ).fetchone()
            if batch is not None:
                pending = conn.execute(
                    "SELECT COUNT(*) c FROM variance_rows WHERE batch_id=? AND fate='pending'",
                    (batch["id"],),
                ).fetchone()["c"]

        latest = batch_view(conn, batch) if batch is not None else None
        return {
            "dock_day": day,
            "sealed": sealed,
            "seal_evidence": (
                {
                    "batch_id": latest["id"],
                    "batch_no": latest["batch_no"],
                    "fingerprint": latest["sealed_fingerprint"],
                    "matched_count": latest["sealed_match_count"],
                    "variance_count": latest["sealed_variance_count"],
                    "sealed_at": latest["sealed_at"],
                    "sealed_by": latest["sealed_by"],
                }
                if sealed and latest is not None
                else None
            ),
            "expect_count": expect_n,
            "receive_count": receive_n,
            "confirm_count": confirm_n,
            "latest_batch": latest,
            "pending_variance": pending,
            "can_seal": (not sealed) and latest is not None
            and latest["status"] == "open"
            and not latest["expired"],
        }
    finally:
        conn.close()
