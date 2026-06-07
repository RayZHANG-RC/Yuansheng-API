# -*- coding: utf-8 -*-
"""
合作方试调 API（薄封装 main.py 管线）

启动:
  pip install -r requirements-api.txt
  set REAL_TOC_PARTNER_API_KEY=dev-partner-change-me
  python api_server.py

文档: API_QUICKSTART.md
"""
from __future__ import annotations

import hashlib
import os
import sys
import json
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pipeline_core import ensure_dir, load_json, save_json, log_message

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")
MAIN_SCRIPT = os.path.join(PROJECT_ROOT, "main.py")

_executor: Optional[ThreadPoolExecutor] = None
_jobs_lock = threading.Lock()
_quota_lock = threading.Lock()
_active_sessions: set[str] = set()


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class AnalyzeRequest(BaseModel):
    """合作方仅需提交 user_id 与 session_input；user_settings 由服务端按 config 生成。"""
    user_id: str = Field(..., min_length=1, description="合作方用户唯一标识")
    session_input: Dict[str, Any]


def _load_app_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        raise RuntimeError("缺少 config.json")
    return load_json(CONFIG_PATH)


def _partner_settings(cfg: dict) -> dict:
    defaults = {
        "enabled": True,
        "api_keys": [],
        "data_root": "data/partner_trials",
        "max_concurrent_jobs": 2,
        "host": "0.0.0.0",
        "port": 8765,
        "require_api_key": True,
        "model_set": "gpt-4.1",
        "default_user_sensitivity_setting": {
            "tone": "温和",
            "tone_MBTI": "ENFJ",
            "sensitivity": "低",
        },
        "default_api_key_success_quota": {
            "enabled": False,
            "max_successful_requests": 0,
            "period": "lifetime",
        },
    }
    partner_api = cfg.get("partner_api", {}) or {}
    merged = {**defaults, **partner_api}
    base_quota = defaults["default_api_key_success_quota"]
    quota_src = partner_api.get("default_api_key_success_quota")
    if not quota_src and partner_api.get("user_success_quota"):
        quota_src = partner_api["user_success_quota"]
    merged["default_api_key_success_quota"] = {**base_quota, **(quota_src or {})}
    env_keys = os.environ.get("REAL_TOC_PARTNER_API_KEY", "").strip()
    if env_keys:
        merged["api_keys"] = [k.strip() for k in env_keys.split(",") if k.strip()]
    merged["data_root"] = os.environ.get(
        "REAL_TOC_DATA_ROOT", merged["data_root"]
    )
    if not os.path.isabs(merged["data_root"]):
        merged["data_root"] = os.path.join(PROJECT_ROOT, merged["data_root"])
    return merged


def _normalize_api_key_entries(partner: dict) -> List[dict]:
    entries: List[dict] = []
    for item in partner.get("api_keys") or []:
        if isinstance(item, str):
            key = item.strip()
            if key:
                entries.append({"key": key, "name": None, "success_quota": None})
        elif isinstance(item, dict):
            key = str(item.get("key") or "").strip()
            if key:
                entries.append(
                    {
                        "key": key,
                        "name": item.get("name"),
                        "success_quota": item.get("success_quota"),
                    }
                )
    return entries


def _allowed_api_key_tokens(partner: dict) -> List[str]:
    tokens = [e["key"] for e in _normalize_api_key_entries(partner)]
    if not tokens and not partner.get("require_api_key", True):
        return []
    if not tokens:
        tokens = ["dev-partner-change-me"]
    return tokens


def _api_key_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def _extract_api_key_token(
    authorization: Optional[str],
    x_api_key: Optional[str],
) -> Optional[str]:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _resolve_api_key(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> str:
    cfg = _load_app_config()
    partner = _partner_settings(cfg)
    if not partner.get("enabled", True):
        raise HTTPException(status_code=503, detail="partner API 未启用")
    if not partner.get("require_api_key", True):
        return ""
    allowed = _allowed_api_key_tokens(partner)
    token = _extract_api_key_token(authorization, x_api_key)
    if not token or token not in allowed:
        raise HTTPException(status_code=401, detail="无效或缺少 API Key")
    return token


def _resolve_session_dir(
    session_input: dict, user_id: str, data_root: str
) -> tuple[str, str, str, str]:
    sm = session_input.get("session_metadata") or {}
    session_id = (sm.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("session_input.session_metadata.session_id 必填")

    qp = session_input.get("question_parameters") or {}
    qmeta = qp.get("question_metadata") or {}
    question_id = (qmeta.get("question_id") or "").strip()
    if not question_id:
        raise ValueError(
            "session_input.question_parameters.question_metadata.question_id 必填"
        )

    user_id = str(user_id).strip()
    if not user_id:
        raise ValueError("user_id 不能为空")

    session_dir = os.path.join(data_root, user_id, question_id, session_id)
    return session_id, session_dir, question_id, user_id


def _default_sensitivity(partner: dict) -> dict:
    return {
        **{
            "tone": "温和",
            "tone_MBTI": "ENFJ",
            "sensitivity": "低",
        },
        **(partner.get("default_user_sensitivity_setting") or {}),
    }


def _build_user_settings(session_id: str, user_id: str, partner: dict) -> dict:
    return {
        "user_metadata": {
            "user_id": user_id,
            "session_id": session_id,
        },
        "user_sensitivity_setting": _default_sensitivity(partner),
    }


def _server_model_set(partner: dict) -> str:
    model_set = (partner.get("model_set") or "gpt-4.1").strip()
    if model_set not in ("gpt-4.1", "gpt-5"):
        return "gpt-4.1"
    return model_set


def _api_key_quota_settings(partner: dict, token: str) -> dict:
    q = None
    for entry in _normalize_api_key_entries(partner):
        if entry["key"] == token and entry.get("success_quota"):
            q = entry["success_quota"]
            break
    if q is None:
        q = partner.get("default_api_key_success_quota") or {}
    period = str(q.get("period") or "lifetime").strip().lower()
    if period not in ("lifetime", "daily", "monthly"):
        period = "lifetime"
    return {
        "enabled": bool(q.get("enabled", False)),
        "max": int(q.get("max_successful_requests") or 0),
        "period": period,
    }


def _quota_period_key(period: str) -> str:
    now = datetime.now()
    if period == "daily":
        return now.strftime("%Y-%m-%d")
    if period == "monthly":
        return now.strftime("%Y-%m")
    return "lifetime"


def _quota_store_path(data_root: str) -> str:
    return os.path.join(data_root, "_quota", "success_counts.json")


def _load_quota_store(data_root: str) -> dict:
    path = _quota_store_path(data_root)
    if os.path.exists(path):
        return load_json(path)
    return {"users": {}}


def _save_quota_store(data_root: str, store: dict) -> None:
    ensure_dir(os.path.dirname(_quota_store_path(data_root)))
    save_json(_quota_store_path(data_root), store)


def _api_key_quota_record(store: dict, key_id: str, period_key: str) -> dict:
    api_keys = store.setdefault("api_keys", {})
    rec = api_keys.setdefault(
        key_id,
        {"period_key": period_key, "success_session_ids": []},
    )
    if rec.get("period_key") != period_key:
        rec["period_key"] = period_key
        rec["success_session_ids"] = []
    if "success_session_ids" not in rec:
        rec["success_session_ids"] = []
    return rec


def get_api_key_quota_status(token: str, partner: dict) -> dict:
    """返回当前 API Key 的配额使用情况（供接口与校验复用）。"""
    cfg = _api_key_quota_settings(partner, token)
    key_id = _api_key_id(token)
    if not cfg["enabled"] or cfg["max"] <= 0:
        return {
            "enabled": False,
            "max_successful_requests": None,
            "used": 0,
            "remaining": None,
            "period": cfg["period"],
        }
    period_key = _quota_period_key(cfg["period"])
    with _quota_lock:
        store = _load_quota_store(partner["data_root"])
        rec = _api_key_quota_record(store, key_id, period_key)
        used = len(rec["success_session_ids"])
    remaining = max(0, cfg["max"] - used)
    return {
        "enabled": True,
        "max_successful_requests": cfg["max"],
        "used": used,
        "remaining": remaining,
        "period": cfg["period"],
        "period_key": period_key,
    }


def _enforce_api_key_quota(token: str, partner: dict) -> None:
    status = get_api_key_quota_status(token, partner)
    if not status["enabled"]:
        return
    if status["remaining"] <= 0:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "api_key_success_quota_exceeded",
                "message": "当前 API Key 已达到成功调用上限",
                "quota": status,
            },
        )


def _record_api_key_success(token: str, session_id: str, partner: dict) -> None:
    cfg = _api_key_quota_settings(partner, token)
    if not cfg["enabled"] or cfg["max"] <= 0:
        return
    key_id = _api_key_id(token)
    period_key = _quota_period_key(cfg["period"])
    with _quota_lock:
        store = _load_quota_store(partner["data_root"])
        rec = _api_key_quota_record(store, key_id, period_key)
        ids: List[str] = rec["success_session_ids"]
        if session_id not in ids:
            ids.append(session_id)
            rec["success_session_ids"] = ids
            _save_quota_store(partner["data_root"], store)


def _write_job_status(session_dir: str, payload: dict) -> None:
    ensure_dir(session_dir)
    save_json(os.path.join(session_dir, "api_job.json"), payload)


def _read_job_status(session_dir: str) -> Optional[dict]:
    path = os.path.join(session_dir, "api_job.json")
    if os.path.exists(path):
        return load_json(path)
    return None


def _find_session_dir_by_id(session_id: str, data_root: str) -> Optional[str]:
    job_path = os.path.join(data_root, "_index", f"{session_id}.json")
    if os.path.exists(job_path):
        meta = load_json(job_path)
        d = meta.get("session_dir")
        if d and os.path.isdir(d):
            return d
    for root, dirs, files in os.walk(data_root):
        if root.endswith(os.path.join("", session_id)) and "api_job.json" in files:
            return root
        if os.path.basename(root) == session_id and "input.json" in files:
            return root
    return None


def _index_session(session_id: str, session_dir: str, data_root: str) -> None:
    idx_dir = os.path.join(data_root, "_index")
    ensure_dir(idx_dir)
    save_json(
        os.path.join(idx_dir, f"{session_id}.json"),
        {"session_id": session_id, "session_dir": session_dir},
    )


def _run_pipeline(
    session_dir: str,
    session_id: str,
    user_id: str,
    model_set: str,
    partner: dict,
    api_key_token: str,
) -> None:
    input_path = os.path.join(session_dir, "input.json")
    settings_path = os.path.join(session_dir, "setting.json")
    started = datetime.now().isoformat()
    _write_job_status(
        session_dir,
        {
            "session_id": session_id,
            "status": JobStatus.running.value,
            "started_at": started,
            "session_dir": session_dir,
        },
    )
    cmd = [
        sys.executable,
        MAIN_SCRIPT,
        "--user-settings",
        settings_path,
        "--session-input",
        input_path,
        "--config-path",
        CONFIG_PATH,
        "--model-set",
        model_set,
    ]
    log_message("INFO", f"启动管线: {' '.join(cmd)}", "API")
    try:
        proc = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        log_path = os.path.join(session_dir, "api_pipeline.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(proc.stdout or "")
            if proc.stderr:
                f.write("\n--- stderr ---\n")
                f.write(proc.stderr)

        output_path = os.path.join(session_dir, "output.json")
        if proc.returncode != 0:
            _write_job_status(
                session_dir,
                {
                    "session_id": session_id,
                    "status": JobStatus.failed.value,
                    "started_at": started,
                    "finished_at": datetime.now().isoformat(),
                    "exit_code": proc.returncode,
                    "error": "管线执行失败，详见 api_pipeline.log",
                    "session_dir": session_dir,
                },
            )
            return

        if not os.path.exists(output_path):
            legacy = os.path.join(session_dir, "session_output.json")
            if os.path.exists(legacy):
                output_path = legacy
            else:
                _write_job_status(
                    session_dir,
                    {
                        "session_id": session_id,
                        "status": JobStatus.failed.value,
                        "started_at": started,
                        "finished_at": datetime.now().isoformat(),
                        "error": "未找到 output.json",
                        "session_dir": session_dir,
                    },
                )
                return

        result = load_json(output_path)
        _write_job_status(
            session_dir,
            {
                "session_id": session_id,
                "status": JobStatus.completed.value,
                "started_at": started,
                "finished_at": datetime.now().isoformat(),
                "session_dir": session_dir,
                "user_id": user_id,
                "result": result,
            },
        )
        if api_key_token:
            _record_api_key_success(api_key_token, session_id, partner)
    except Exception as e:
        _write_job_status(
            session_dir,
            {
                "session_id": session_id,
                "status": JobStatus.failed.value,
                "started_at": started,
                "finished_at": datetime.now().isoformat(),
                "error": str(e),
                "session_dir": session_dir,
            },
        )
    finally:
        with _jobs_lock:
            _active_sessions.discard(session_id)


def _submit_job(
    session_dir: str,
    session_id: str,
    user_id: str,
    model_set: str,
    partner: dict,
    api_key_token: str,
) -> None:
    global _executor
    if _executor is None:
        workers = int(partner.get("max_concurrent_jobs") or 2)
        _executor = ThreadPoolExecutor(max_workers=max(1, workers))

    _write_job_status(
        session_dir,
        {
            "session_id": session_id,
            "status": JobStatus.queued.value,
            "queued_at": datetime.now().isoformat(),
            "session_dir": session_dir,
        },
    )
    _executor.submit(
        _run_pipeline,
        session_dir,
        session_id,
        user_id,
        model_set,
        partner,
        api_key_token,
    )


def create_app() -> FastAPI:
    cfg = _load_app_config()
    partner = _partner_settings(cfg)
    origins = cfg.get("security", {}).get("allowed_origins") or ["*"]

    app = FastAPI(
        title="real_toc Partner Trial API",
        version="0.1.0",
        description="合作方试调接口：仅需 user_id + session_input；见 API_QUICKSTART.md",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "real_toc_partner_api",
            "project_root": PROJECT_ROOT,
        }

    @app.get("/v1/questions", dependencies=[Depends(_resolve_api_key)])
    def list_questions():
        qdir = os.path.join(PROJECT_ROOT, "question_config")
        ids = sorted(
            f[:-5]
            for f in os.listdir(qdir)
            if f.endswith(".jsonc") and not f.startswith("_")
        )
        return {"question_ids": ids, "count": len(ids)}

    @app.post("/v1/analyze", status_code=202)
    def analyze(body: AnalyzeRequest, api_key_token: str = Depends(_resolve_api_key)):
        cfg = _load_app_config()
        partner = _partner_settings(cfg)
        try:
            session_id, session_dir, question_id, user_id = _resolve_session_dir(
                body.session_input, body.user_id, partner["data_root"]
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        if api_key_token:
            _enforce_api_key_quota(api_key_token, partner)

        with _jobs_lock:
            if session_id in _active_sessions:
                raise HTTPException(
                    status_code=409,
                    detail=f"会话 {session_id} 正在处理中",
                )
            existing = _read_job_status(session_dir)
            if existing and existing.get("status") in (
                JobStatus.queued.value,
                JobStatus.running.value,
            ):
                raise HTTPException(
                    status_code=409,
                    detail=f"会话 {session_id} 已在队列或运行中",
                )
            _active_sessions.add(session_id)

        ensure_dir(session_dir)
        us = _build_user_settings(session_id, user_id, partner)
        save_json(os.path.join(session_dir, "input.json"), body.session_input)
        save_json(os.path.join(session_dir, "setting.json"), us)
        _index_session(session_id, session_dir, partner["data_root"])

        model_set = _server_model_set(partner)
        _submit_job(
            session_dir, session_id, user_id, model_set, partner, api_key_token
        )

        quota = (
            get_api_key_quota_status(api_key_token, partner)
            if api_key_token
            else {"enabled": False}
        )

        return {
            "session_id": session_id,
            "status": JobStatus.queued.value,
            "question_id": question_id,
            "user_id": user_id,
            "poll_url": f"/v1/jobs/{session_id}",
            "quota": quota,
            "message": "任务已入队，请轮询 poll_url 获取结果（通常需 1～5 分钟）",
        }

    @app.get("/v1/quota")
    def get_quota(api_key_token: str = Depends(_resolve_api_key)):
        partner = _partner_settings(_load_app_config())
        if not api_key_token:
            return {"enabled": False}
        return get_api_key_quota_status(api_key_token, partner)

    @app.get("/v1/jobs/{session_id}", dependencies=[Depends(_resolve_api_key)])
    def get_job(session_id: str):
        cfg = _load_app_config()
        partner = _partner_settings(cfg)
        session_dir = _find_session_dir_by_id(session_id, partner["data_root"])
        if not session_dir:
            raise HTTPException(status_code=404, detail="未找到该 session_id")

        job = _read_job_status(session_dir)
        if not job:
            if os.path.exists(os.path.join(session_dir, "output.json")):
                job = {
                    "session_id": session_id,
                    "status": JobStatus.completed.value,
                    "result": load_json(os.path.join(session_dir, "output.json")),
                    "session_dir": session_dir,
                }
            else:
                raise HTTPException(status_code=404, detail="任务状态未知")

        out = {
            "session_id": session_id,
            "status": job.get("status"),
            "session_dir": session_dir,
            "queued_at": job.get("queued_at"),
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
        }
        if job.get("status") == JobStatus.completed.value:
            out["result"] = job.get("result")
        if job.get("status") == JobStatus.failed.value:
            out["error"] = job.get("error")
            out["exit_code"] = job.get("exit_code")
            log_file = os.path.join(session_dir, "api_pipeline.log")
            if os.path.exists(log_file):
                out["log_hint"] = "详见会话目录下 api_pipeline.log"
        return out

    return app


app = create_app()


def main():
    cfg = _load_app_config()
    partner = _partner_settings(cfg)
    host = os.environ.get("REAL_TOC_API_HOST", partner.get("host", "0.0.0.0"))
    port = int(os.environ.get("REAL_TOC_API_PORT", partner.get("port", 8765)))
    import uvicorn

    log_message(
        "INFO",
        f"Partner API 监听 http://{host}:{port}  文档 http://{host}:{port}/docs",
        "API",
    )
    uvicorn.run("api_server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
