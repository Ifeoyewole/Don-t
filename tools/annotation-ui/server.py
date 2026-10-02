"""Internal Human Annotation and Review Tool Server.

Provides a lightweight, audit-compliant interface for human engineers
to review joint candidates, verify or adjust bounding boxes and segmentation masks,
confirm physical condition classes, and log immutable review events.
"""

import argparse
import base64
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

from .review_store import ReviewStore, AnnotationEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("annotation_server")

app = FastAPI(title="JointInspect Human Annotation & Review System", version="1.0.0")
review_store = ReviewStore()


class ReviewSubmission(BaseModel):
    asset_id: str
    reviewer_id: str
    action: str  # ACCEPT, REJECT, SKIP, UPDATE_ANNOTATION, FLAG_AMBIGUOUS, REQUEST_SECOND_REVIEW
    condition_class: str
    is_joint_visible: bool
    visibility_status: str  # FULL_VISIBILITY, PARTIAL_VISIBILITY, OBSCURED, UNUSABLE
    bbox_xyxy: Optional[List[float]] = None
    polygon_points: Optional[List[List[float]]] = None
    ground_truth_gap_mm: Optional[float] = None
    measurement_method: Optional[str] = None
    instrument_name: Optional[str] = None
    review_notes: str = ""


@app.get("/api/health")
def health():
    return {"status": "ok", "system": "JointInspect Annotation UI"}


@app.get("/api/stats")
def get_stats():
    """Returns counts of reviewed and pending assets."""
    return {
        "status_summary": review_store.get_status_summary(),
        "total_events": len(review_store.events),
    }


@app.get("/api/events")
def get_events(limit: int = 50):
    """Returns recent audit events."""
    return [e.dict() for e in review_store.events[-limit:]]


@app.post("/api/review")
def submit_review(sub: ReviewSubmission):
    """Logs an immutable review action to the audit ledger."""
    new_val = {
        "condition_class": sub.condition_class,
        "is_joint_visible": sub.is_joint_visible,
        "visibility_status": sub.visibility_status,
        "bbox_xyxy": sub.bbox_xyxy,
        "polygon_points": sub.polygon_points,
        "ground_truth_gap_mm": sub.ground_truth_gap_mm,
        "measurement_method": sub.measurement_method,
        "instrument_name": sub.instrument_name,
    }

    event = review_store.record_event(
        asset_id=sub.asset_id,
        reviewer_id=sub.reviewer_id,
        action=sub.action,
        new_value=new_val,
        review_notes=sub.review_notes,
    )
    return {"status": "success", "event_id": event.event_id, "review_status": event.review_status}


@app.get("/", response_class=HTMLResponse)
def index_view():
    """Serves the internal review single-page interface."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JointInspect — Human Annotation & Review</title>
    <style>
        :root {
            --bg: #0f172a;
            --surface: #1e293b;
            --border: #334155;
            --primary: #38bdf8;
            --text: #f8fafc;
            --text-dim: #94a3b8;
            --success: #22c55e;
            --danger: #ef4444;
            --warning: #f59e0b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background: var(--bg); color: var(--text); display: flex; flex-direction: column; height: 100vh; }
        header { background: var(--surface); padding: 12px 24px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 1.15rem; font-weight: 700; color: var(--primary); display: flex; align-items: center; gap: 8px; }
        .badge { background: #0369a1; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; }
        main { display: flex; flex: 1; overflow: hidden; }
        .viewport { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; position: relative; background: #090d16; padding: 20px; }
        .canvas-container { position: relative; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
        canvas { display: block; max-width: 100%; max-height: 75vh; }
        .sidebar { width: 380px; background: var(--surface); border-left: 1px solid var(--border); padding: 20px; display: flex; flex-direction: column; gap: 16px; overflow-y: auto; }
        .card { background: #182234; border: 1px solid var(--border); border-radius: 6px; padding: 14px; }
        .card-title { font-size: 0.85rem; font-weight: 600; text-transform: uppercase; color: var(--text-dim); margin-bottom: 10px; }
        label { display: block; font-size: 0.82rem; color: var(--text-dim); margin-bottom: 4px; }
        select, input, textarea { width: 100%; background: #0f172a; border: 1px solid var(--border); color: var(--text); padding: 8px 10px; border-radius: 4px; margin-bottom: 10px; font-size: 0.9rem; }
        .row { display: flex; gap: 8px; }
        .btn { flex: 1; padding: 10px; border: none; border-radius: 5px; font-weight: 600; cursor: pointer; transition: 0.15s; font-size: 0.85rem; }
        .btn-success { background: var(--success); color: #fff; }
        .btn-danger { background: var(--danger); color: #fff; }
        .btn-warning { background: var(--warning); color: #000; }
        .btn-secondary { background: var(--border); color: var(--text); }
        .audit-list { font-size: 0.75rem; color: var(--text-dim); display: flex; flex-direction: column; gap: 6px; }
        .audit-item { padding: 6px; background: #0f172a; border-radius: 4px; border-left: 3px solid var(--primary); }
    </style>
</head>
<body>
    <header>
        <div class="logo">
            <span>JOINTINSPECT</span>
            <span class="badge">AUDIT-COMPLIANT REVIEW SYSTEM</span>
        </div>
        <div id="statsBanner" style="font-size: 0.85rem; color: var(--text-dim);">
            Verified: <span id="statVerified" style="color:var(--success); font-weight:600;">0</span> | 
            Pending: <span id="statPending" style="color:var(--warning); font-weight:600;">0</span> | 
            Rejected: <span id="statRejected" style="color:var(--danger); font-weight:600;">0</span>
        </div>
    </header>
    <main>
        <div class="viewport">
            <div class="canvas-container">
                <canvas id="reviewCanvas" width="960" height="540"></canvas>
            </div>
            <div style="margin-top: 10px; font-size: 0.8rem; color: var(--text-dim);">
                Asset ID: <strong id="lblAssetId" style="color:var(--text);">JI-SYN-A00001</strong> | 
                Source: <span id="lblSource">SRC-SYN-001 (JointInspect Synthetic v1)</span>
            </div>
        </div>
        <div class="sidebar">
            <div class="card">
                <div class="card-title">1. Joint Verification</div>
                <label>Joint Boundary Visible?</label>
                <select id="selVisible">
                    <option value="true">YES — Joint Clearly Identified</option>
                    <option value="false">NO — No Joint Present</option>
                </select>
                <label>Visibility Status</label>
                <select id="selVisibilityStatus">
                    <option value="FULL_VISIBILITY">FULL_VISIBILITY (Clear Circumference)</option>
                    <option value="PARTIAL_VISIBILITY">PARTIAL_VISIBILITY (Partially Obscured)</option>
                    <option value="OBSCURED">OBSCURED (Debris/Silt Cover)</option>
                    <option value="UNUSABLE">UNUSABLE (Severe Glare/Blur)</option>
                </select>
            </div>
            <div class="card">
                <div class="card-title">2. Condition Classification</div>
                <label>Assigned Condition Class</label>
                <select id="selClass">
                    <option value="NORMAL_JOINT">NORMAL_JOINT (Intact Alignment)</option>
                    <option value="DISPLACED_JOINT">DISPLACED_JOINT (Deflection / Offset)</option>
                    <option value="DAMAGED_JOINT">DAMAGED_JOINT (Spalling / Crack / Break)</option>
                    <option value="INTRUDING_SEAL">INTRUDING_SEAL (Gasket Extrusion)</option>
                    <option value="DEPOSITS_OBSTACLES">DEPOSITS_OBSTACLES (Invert Silt / Roots)</option>
                    <option value="DIFFICULT_CONDITION">DIFFICULT_CONDITION (Turbid Water / Complex)</option>
                </select>
                <label>Physical Ground-Truth Gap (mm) [Optional]</label>
                <input type="number" id="txtGapMm" step="0.1" placeholder="e.g. 2.5">
                <label>Measurement Instrument</label>
                <input type="text" id="txtInstrument" placeholder="e.g. Feeler Gauge, Caliper, Synthetic Exact">
            </div>
            <div class="card">
                <div class="card-title">3. Audit Action & Notes</div>
                <label>Review Notes / Discrepancy Rationale</label>
                <textarea id="txtNotes" rows="2" placeholder="Document review rationale..."></textarea>
                <div class="row">
                    <button class="btn btn-success" onclick="submitAction('ACCEPT')">ACCEPT</button>
                    <button class="btn btn-danger" onclick="submitAction('REJECT')">REJECT</button>
                    <button class="btn btn-warning" onclick="submitAction('FLAG_AMBIGUOUS')">AMBIGUOUS</button>
                    <button class="btn btn-secondary" onclick="submitAction('SKIP')">SKIP</button>
                </div>
            </div>
            <div class="card" style="flex:1;">
                <div class="card-title">Immutable Audit Trail</div>
                <div class="audit-list" id="auditList">
                    <div class="audit-item">Loading audit history...</div>
                </div>
            </div>
        </div>
    </main>
    <script>
        let currentAsset = "JI-SYN-A00001";
        const canvas = document.getElementById('reviewCanvas');
        const ctx = canvas.getContext('2d');

        function drawDemoCanvas() {
            ctx.fillStyle = "#1e293b";
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.strokeStyle = "#38bdf8";
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(canvas.width / 2, canvas.height / 2, 160, 0, Math.PI * 2);
            ctx.stroke();
            ctx.strokeStyle = "#22c55e";
            ctx.beginPath();
            ctx.arc(canvas.width / 2, canvas.height / 2, 185, 0, Math.PI * 2);
            ctx.stroke();
            ctx.fillStyle = "#94a3b8";
            ctx.font = "14px sans-serif";
            ctx.fillText("Pipe Joint Circumferential Inspection Canvas", 30, 40);
        }

        async function loadAuditLog() {
            try {
                const res = await fetch('/api/events');
                const data = await res.json();
                const list = document.getElementById('auditList');
                if (data.length === 0) {
                    list.innerHTML = "<div class='audit-item'>No review events recorded yet.</div>";
                    return;
                }
                list.innerHTML = data.slice(-5).reverse().map(e => `
                    <div class="audit-item">
                        <strong>${e.action}</strong>: ${e.asset_id} [${e.review_status}]<br>
                        <span style="font-size:0.68rem; color:#64748b;">${e.timestamp.slice(0, 19)} by ${e.reviewer_id}</span>
                    </div>
                `).join('');
            } catch(e) {
                console.error(e);
            }
        }

        async function submitAction(action) {
            const payload = {
                asset_id: currentAsset,
                reviewer_id: "ENGINEER-LEAD-01",
                action: action,
                condition_class: document.getElementById('selClass').value,
                is_joint_visible: document.getElementById('selVisible').value === "true",
                visibility_status: document.getElementById('selVisibilityStatus').value,
                ground_truth_gap_mm: parseFloat(document.getElementById('txtGapMm').value) || null,
                instrument_name: document.getElementById('txtInstrument').value || null,
                review_notes: document.getElementById('txtNotes').value || ""
            };
            const res = await fetch('/api/review', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            const out = await res.json();
            alert(`Review event ${out.event_id} logged. Status: ${out.review_status}`);
            loadAuditLog();
        }

        drawDemoCanvas();
        loadAuditLog();
    </script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="JointInspect Human Annotation Tool")
    parser.add_argument("--port", default=8088, type=int, help="Port to serve review UI")
    parser.add_argument("--host", default="127.0.0.1", type=str, help="Host to bind review UI")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
