"""
FastAPI router — REST endpoints + WebSocket flash-progress stream.
All routes are prefixed under /api except the WebSocket at /ws and static files.
"""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.flash_manager import FlashManager

router = APIRouter()

# Single shared manager instance (attached in web_server.py)
_manager: FlashManager | None = None


def init_manager(config_path: str = "config.json"):
    global _manager
    _manager = FlashManager(config_path=config_path)


def get_manager() -> FlashManager:
    if _manager is None:
        raise RuntimeError("FlashManager not initialised")
    return _manager


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class UseProjectRequest(BaseModel):
    name: str

class FlashRequest(BaseModel):
    alias: str
    project: Optional[str] = None
    firmware: Optional[str] = None

class FlashAllRequest(BaseModel):
    project: Optional[str] = None

class ResetRequest(BaseModel):
    alias: str
    project: Optional[str] = None

class DetectRequest(BaseModel):
    alias: str
    project: Optional[str] = None

class UpdateFirmwareRequest(BaseModel):
    alias: str
    firmware: str
    project: Optional[str] = None


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@router.get("/api/projects")
def list_projects():
    return get_manager().get_projects()


@router.post("/api/projects/use")
def use_project(req: UseProjectRequest):
    result = get_manager().use_project(req.name)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------

@router.get("/api/probes")
def list_probes(project: Optional[str] = None):
    return get_manager().list_connected_probes(project_name=project)


@router.patch("/api/probes/firmware")
def update_firmware(req: UpdateFirmwareRequest):
    result = get_manager().update_probe_firmware(
        alias=req.alias,
        firmware=req.firmware,
        project_name=req.project,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Flash
# ---------------------------------------------------------------------------

@router.post("/api/flash")
async def flash(req: FlashRequest):
    mgr = get_manager()
    job, err = mgr.create_flash_job(
        alias=req.alias,
        project_name=req.project,
        firmware_override=req.firmware,
    )
    if not job:
        raise HTTPException(status_code=400, detail=err)
    # Fire off the job without blocking the response
    asyncio.create_task(mgr.run_job(job))
    return {"job_id": job.job_id, "alias": job.alias, "status": "queued"}


@router.post("/api/flash-all")
async def flash_all(req: FlashAllRequest):
    mgr = get_manager()
    jobs, skipped = mgr.create_flash_all_jobs(project_name=req.project)
    if not jobs and skipped:
        raise HTTPException(status_code=400, detail={"skipped": skipped})
    for job in jobs:
        asyncio.create_task(mgr.run_job(job))
    return {
        "jobs": [{"job_id": j.job_id, "alias": j.alias} for j in jobs],
        "skipped": skipped,
    }


# ---------------------------------------------------------------------------
# Reset / detect
# ---------------------------------------------------------------------------

@router.post("/api/reset")
async def reset(req: ResetRequest):
    result = await get_manager().run_reset(req.alias, req.project)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/api/detect-target")
async def detect_target(req: DetectRequest):
    result = await get_manager().run_detect_target(req.alias, req.project)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Job status
# ---------------------------------------------------------------------------

@router.get("/api/jobs")
def list_jobs():
    return get_manager().list_jobs()


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = get_manager().get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return FlashManager._job_summary(job)


# ---------------------------------------------------------------------------
# WebSocket: stream flash progress for a job
# ---------------------------------------------------------------------------

@router.websocket("/ws/job/{job_id}")
async def ws_job_progress(websocket: WebSocket, job_id: str):
    await websocket.accept()
    mgr = get_manager()
    job = mgr.get_job(job_id)

    if not job:
        await websocket.send_json({"type": "error", "message": "Job not found"})
        await websocket.close()
        return

    # If already done, just send final state immediately
    if job.status in ("done", "failed"):
        await websocket.send_json({"type": job.status, "progress": job.progress, "message": job.message})
        await websocket.close()
        return

    queue = job.subscribe()
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send a keepalive ping
                await websocket.send_json({"type": "ping"})
                continue

            if event is None:  # sentinel — job stream closed
                break

            await websocket.send_json(event)

            if event.get("type") in ("done", "failed"):
                break

    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()
