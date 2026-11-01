"""Retry detail fetch for notes that failed during a collection task.

Phase 2 keeps the original dataset and only refreshes the rows whose detail or
body is still missing, so a retry never re-collects the whole profile.
"""

import threading
from datetime import datetime

from backend.database import Cookie, Task
from backend.services.collector import Collector
from backend.services.library_collector import failure_kind
from backend.services.note_library import apply_detail, save_dataset, update_missing
from backend.services.note_workspace import dataset_path, load_dataset
from backend.tasks.worker import (
    _get_db_session,
    _progress_log,
    _state_lock,
    _task_state,
    _update_task,
)


def run_retry(task_id, max_count=10):
    session = _get_db_session()
    try:
        task = session.get(Task, task_id)
        cookie = session.get(Cookie, task.cookie_id) if task is not None and task.cookie_id else None
        dataset = load_dataset(task_id)
        if task is None or cookie is None or dataset is None:
            _update_task(
                task_id,
                status="failed",
                completed_at=datetime.utcnow(),
                error_message="没有可补采的数据或登录状态，请用浏览器插件重新采集。",
            )
            return

        pending = [row for row in dataset.get("rows") or [] if row.get("detail_status") != "成功"][:max_count]
        if not pending:
            _update_task(task_id, status="completed", progress=100, error_message=None)
            return

        _update_task(task_id, status="running", progress=5, error_message="正在补采未完成笔记。")
        collector = Collector()
        from backend.utils.cookie import cookies_array_to_dict

        collector._ensure_api(cookies_array_to_dict(cookie.cookie_json))

        for index, row in enumerate(pending, 1):
            try:
                detail = collector.get_note_detail(row.get("note_url") or "", cookie.cookie_json)
            except Exception as exc:  # network or SDK failure per note
                detail = {"ok": False, "reason": str(exc)}
            if detail.get("ok"):
                apply_detail(row, detail)
            else:
                row["detail_status"] = "失败"
                row["failure_reason"] = failure_kind(detail.get("reason"))
                update_missing(row)
            save_dataset(dataset_path(task_id), dataset)
            _update_task(
                task_id,
                progress=min(95, 5 + int(90 * index / len(pending))),
                run_log=_progress_log(f"补采 {index}/{len(pending)}", row.get("failure_reason", "")),
            )

        remaining = [row for row in dataset.get("rows") or [] if row.get("detail_status") != "成功"]
        status = "partial" if remaining else "completed"
        dataset["status"] = status
        dataset["stop_reason"] = (
            remaining[0].get("failure_reason") or "部分笔记仍未采集到正文" if remaining else ""
        )
        save_dataset(dataset_path(task_id), dataset)
        _update_task(
            task_id,
            status=status,
            progress=100,
            completed_at=datetime.utcnow(),
            error_message=dataset["stop_reason"] if status != "completed" else None,
        )
    except Exception:
        _update_task(
            task_id,
            status="failed",
            completed_at=datetime.utcnow(),
            error_message="补采中断，已采集数据仍可下载。请检查登录状态和网络后重试。",
        )
    finally:
        session.close()


def submit_retry(task_id, max_count=10):
    with _state_lock:
        _task_state[task_id] = {"status": "pending", "progress": 0}
    threading.Thread(target=run_retry, args=(task_id, max_count), daemon=True).start()
