"""One paid analysis per owner, persisted stages and explicit delivery approval."""
import json
import ctypes
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.services.library_analysis import VERSION, build_bundle, fingerprint, generate_analysis
from backend.services.structured_ai import AIRequestError

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="content-ai")
_lock = threading.RLock()
_active = {}


def _process_alive(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True


def _save(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_state(task_dir: Path, dataset: dict) -> dict:
    with _lock:
        state = _load(task_dir / "content_analysis.json")
        if not state:
            return {"status": "idle"}
        if state["status"] == "running" and state.get("run_id") not in _active.values():
            owner_pid = state.get("process_id")
            owned_elsewhere = owner_pid != os.getpid() and _process_alive(owner_pid)
            if not owned_elsewhere:
                state.update(status="failed", stage="上次生成已中断，请直接点击“重试生成”。")
                _save(task_dir / "content_analysis.json", state)
        if state.get("dataset_fingerprint") != fingerprint(dataset):
            return {**state, "status": "stale", "stage": "笔记库已变化，请重新生成。", "report": None}
        if state.get("status") in ("ready", "running"):
            report = state.get("report")
            version_matches = (
                state.get("analysis_version") == VERSION
                and (state.get("status") != "ready" or (
                    isinstance(report, dict)
                    and report.get("version") == VERSION
                    and report.get("dataset_fingerprint") == state.get("dataset_fingerprint")
                ))
            )
            if not version_matches:
                return {**state, "status": "stale", "stage": "报告生成规则已升级，请重新生成。", "report": None}
        return state


def start_analysis(task_dir: Path, dataset: dict, goal: str, config: dict, owner: int) -> dict:
    if not config.get("configured"):
        raise ValueError("请先在设置中配置你自己的模型 API；客户不需要配置。")
    build_bundle(dataset, goal)
    with _lock:
        if owner in _active:
            raise ValueError("已有 AI 任务正在生成，请等待结束，避免重复扣费。")
        if len(_active) >= 2:
            raise ValueError("当前生成队列已满，请稍后重试。")
        run_id = uuid.uuid4().hex
        state = {"run_id": run_id, "analysis_version": VERSION, "status": "running",
                 "process_id": os.getpid(),
                 "stage": "已准备材料，等待模型处理",
                 "dataset_fingerprint": fingerprint(dataset), "goal": goal, "report": None}
        _save(task_dir / "content_analysis.json", state)
        _active[owner] = run_id
        try:
            _pool.submit(_run, task_dir, dataset, goal, dict(config), owner, dict(state))
        except Exception:
            _active.pop(owner, None)
            state.update(status="failed", stage="无法启动 AI 任务，请重试。")
            _save(task_dir / "content_analysis.json", state)
            raise ValueError(state["stage"]) from None
        return state


def _run(task_dir, dataset, goal, config, owner, state):
    def progress(stage):
        with _lock:
            state["stage"] = stage
            _save(task_dir / "content_analysis.json", state)
    try:
        report = generate_analysis(dataset, goal, config, progress)
        report["account_name"] = next((r.get("author_nickname") for r in dataset.get("rows", []) if r.get("author_nickname")), "账号内容")
        state.update(status="ready", stage="解读与草稿已生成，请复核后确认交付", report=report)
    except (ValueError, AIRequestError) as exc:
        state.update(status="failed", stage=str(exc), report=None)
    except Exception:
        state.update(status="failed", stage="生成过程中出现异常，未生成交付报告。请重试或检查本地环境。", report=None)
    finally:
        with _lock:
            _save(task_dir / "content_analysis.json", state)
            _active.pop(owner, None)


def approve(task_dir: Path, dataset: dict, run_id: str) -> dict:
    with _lock:
        state = read_state(task_dir, dataset)
        if state.get("status") != "ready" or state.get("run_id") != run_id:
            raise ValueError("报告已变化或尚未生成，请刷新后再确认。")
        state["report"]["review"] = "approved"
        _save(task_dir / "content_analysis.json", state)
        return state
