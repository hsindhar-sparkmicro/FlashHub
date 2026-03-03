"""
Flash job manager: runs blocking pyocd operations in a thread pool and
exposes per-job asyncio Queues for WebSocket progress streaming.
"""

import asyncio
import uuid
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Literal

from src.backend.pyocd_wrapper import PyOCDWrapper
from src.utils.config_manager import ConfigManager

log = logging.getLogger("flashhub.manager")

JobStatus = Literal["queued", "running", "done", "failed"]

_SENTINEL = None  # signals WebSocket that the stream is finished


@dataclass
class FlashJob:
    job_id: str
    alias: str
    probe_uid: str
    target: str
    firmware: str
    project_name: str
    packs: list[str] = field(default_factory=list)
    status: JobStatus = "queued"
    progress: int = 0
    message: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    # Every subscriber gets its own queue so multiple WS clients work
    _queues: list[asyncio.Queue] = field(default_factory=list)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.append(q)
        return q

    def _push(self, event: dict):
        for q in self._queues:
            q.put_nowait(event)

    def _close(self):
        for q in self._queues:
            q.put_nowait(_SENTINEL)


class FlashManager:
    _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="flash")

    def __init__(self, config_path: str = "config.json"):
        self.cfg = ConfigManager(config_path=config_path)
        self._jobs: dict[str, FlashJob] = {}

    # ------------------------------------------------------------------
    # Config helpers (called from API routes synchronously)
    # ------------------------------------------------------------------

    def get_projects(self) -> list[dict]:
        projects = []
        active_idx = self.cfg.config.get("current_project_index", 0)
        for i, p in enumerate(self.cfg.get_projects()):
            probes = [
                {
                    "uid": uid,
                    "alias": cfg.get("alias", uid),
                    "firmware": cfg.get("firmware", ""),
                }
                for uid, cfg in p.get("probes_config", {}).items()
            ]
            projects.append(
                {
                    "index": i,
                    "name": p["name"],
                    "target_device": p.get("target_device", ""),
                    "active": i == active_idx,
                    "probes": probes,
                }
            )
        return projects

    def use_project(self, name: str) -> dict:
        for i, p in enumerate(self.cfg.get_projects()):
            if p["name"].lower() == name.lower():
                self.cfg.select_project(i)
                return {"ok": True, "active": p["name"]}
        return {"ok": False, "error": f"Project '{name}' not found"}

    def list_connected_probes(self, project_name: str | None = None) -> list[dict]:
        proj = self._get_project(project_name)
        probes_config = proj.get("probes_config", {}) if proj else {}
        connected = PyOCDWrapper.list_probes()
        result = []
        for p in connected:
            uid = p["unique_id"].upper()
            alias = next(
                (c.get("alias", "") for k, c in probes_config.items() if k.upper() == uid),
                None,
            )
            firmware = next(
                (c.get("firmware", "") for k, c in probes_config.items() if k.upper() == uid),
                None,
            )
            result.append(
                {
                    "uid": uid,
                    "alias": alias,
                    "vendor": p.get("vendor_name", ""),
                    "product": p.get("product_name", ""),
                    "firmware": firmware,
                    "registered": alias is not None,
                }
            )
        return result

    def get_job(self, job_id: str) -> FlashJob | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        return [self._job_summary(j) for j in self._jobs.values()]

    # ------------------------------------------------------------------
    # Job creation & execution
    # ------------------------------------------------------------------

    def _get_project(self, project_name: str | None) -> dict | None:
        if project_name:
            for p in self.cfg.get_projects():
                if p["name"].lower() == project_name.lower():
                    return p
            return None
        return self.cfg.get_current_project()

    def _resolve_alias(self, proj: dict, alias: str) -> tuple[str, dict] | tuple[None, None]:
        for uid, cfg in proj.get("probes_config", {}).items():
            if cfg.get("alias", "").lower() == alias.lower():
                return uid, cfg
        return None, None

    def create_flash_job(
        self,
        alias: str,
        project_name: str | None = None,
        firmware_override: str | None = None,
    ) -> tuple[FlashJob | None, str]:
        proj = self._get_project(project_name)
        if not proj:
            return None, f"Project '{project_name}' not found"

        uid, probe_cfg = self._resolve_alias(proj, alias)
        if not uid:
            known = [c.get("alias", k) for k, c in proj.get("probes_config", {}).items()]
            return None, f"Alias '{alias}' not found. Known: {', '.join(known)}"

        target = proj.get("target_device", "")
        firmware = firmware_override or (probe_cfg or {}).get("firmware", "")

        if not target:
            return None, "No target_device configured for project"
        if not firmware:
            return None, f"No firmware configured for alias '{alias}'"

        job = FlashJob(
            job_id=str(uuid.uuid4())[:8],
            alias=alias,
            probe_uid=uid,
            target=target,
            firmware=firmware,
            project_name=proj["name"],
            packs=proj.get("packs") or [],
        )
        self._jobs[job.job_id] = job
        return job, ""

    def create_flash_all_jobs(
        self, project_name: str | None = None
    ) -> tuple[list[FlashJob], list[str]]:
        proj = self._get_project(project_name)
        if not proj:
            return [], [f"Project not found"]

        connected_uids = {p["unique_id"].upper() for p in PyOCDWrapper.list_probes()}
        target = proj.get("target_device", "")
        jobs, skipped = [], []

        for uid, pcfg in proj.get("probes_config", {}).items():
            alias = pcfg.get("alias", uid)
            firmware = pcfg.get("firmware", "")
            if uid.upper() not in connected_uids:
                skipped.append(f"'{alias}' not connected")
                continue
            if not firmware:
                skipped.append(f"'{alias}' has no firmware")
                continue
            job = FlashJob(
                job_id=str(uuid.uuid4())[:8],
                alias=alias,
                probe_uid=uid,
                target=target,
                firmware=firmware,
                project_name=proj["name"],
                packs=proj.get("packs") or [],
            )
            self._jobs[job.job_id] = job
            jobs.append(job)

        return jobs, skipped

    async def run_job(self, job: FlashJob):
        """Submit the blocking flash operation to the thread pool."""
        loop = asyncio.get_event_loop()
        job.status = "running"
        job._push({"type": "status", "status": "running", "progress": 0})

        def _do_flash():
            def _progress(pct: int):
                job.progress = pct
                job._push({"type": "progress", "progress": pct})

            PyOCDWrapper.flash_firmware(
                job.probe_uid, job.target, job.firmware,
                progress_callback=_progress,
                packs=job.packs or None,
            )

        try:
            await loop.run_in_executor(self._executor, _do_flash)
            job.status = "done"
            job.progress = 100
            job.message = "Flash complete"
            job.finished_at = time.time()
            job._push({"type": "done", "progress": 100, "message": job.message})
        except Exception as e:
            job.status = "failed"
            job.message = str(e)
            job.finished_at = time.time()
            log.error("Flash failed for %s: %s", job.alias, e)
            job._push({"type": "failed", "message": job.message})
        finally:
            job._close()

    async def run_reset(
        self, alias: str, project_name: str | None = None
    ) -> dict:
        proj = self._get_project(project_name)
        if not proj:
            return {"ok": False, "error": "Project not found"}
        uid, _ = self._resolve_alias(proj, alias)
        if not uid:
            return {"ok": False, "error": f"Alias '{alias}' not found"}
        target = proj.get("target_device", "")
        packs = proj.get("packs") or None
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                self._executor,
                lambda: PyOCDWrapper.reset_target(uid, target, packs=packs),
            )
            return {"ok": True, "message": f"Reset complete for '{alias}'"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def run_detect_target(
        self, alias: str, project_name: str | None = None
    ) -> dict:
        proj = self._get_project(project_name)
        if not proj:
            return {"ok": False, "error": "Project not found"}
        uid, _ = self._resolve_alias(proj, alias)
        if not uid:
            return {"ok": False, "error": f"Alias '{alias}' not found"}
        loop = asyncio.get_event_loop()
        try:
            detected = await loop.run_in_executor(
                self._executor, PyOCDWrapper.detect_target, uid
            )
            return {"ok": True, "target": detected or "unknown"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update_probe_firmware(self, alias: str, firmware: str, project_name: str | None = None) -> dict:
        """Persist a new firmware path for the given alias to config.json."""
        proj = self._get_project(project_name)
        if not proj:
            return {"ok": False, "error": f"Project '{project_name}' not found"}
        uid, _ = self._resolve_alias(proj, alias)
        if not uid:
            known = [c.get("alias", k) for k, c in proj.get("probes_config", {}).items()]
            return {"ok": False, "error": f"Alias '{alias}' not found. Known: {', '.join(known)}"}
        success = self.cfg.update_probe_firmware(
            probe_uid=uid,
            firmware=firmware,
            project_name=proj.get("name"),
        )
        if not success:
            return {"ok": False, "error": "Failed to update config"}
        return {"ok": True, "alias": alias, "firmware": firmware}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _job_summary(j: FlashJob) -> dict:
        return {
            "job_id": j.job_id,
            "alias": j.alias,
            "probe_uid": j.probe_uid,
            "target": j.target,
            "firmware": j.firmware,
            "project": j.project_name,
            "status": j.status,
            "progress": j.progress,
            "message": j.message,
            "started_at": j.started_at,
            "finished_at": j.finished_at,
        }
