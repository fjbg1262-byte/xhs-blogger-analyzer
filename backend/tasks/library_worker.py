"""Collection-only worker; old analysis/report pipeline is never invoked."""
import threading
from datetime import datetime
from pathlib import Path
from backend.config import settings
from backend.database import Account, Cookie, Task
from backend.services.library_collector import collect_library
from backend.services.note_library import save_dataset
from backend.tasks.worker import _get_db_session, _is_cancelled, _progress_log, _state_lock, _task_state, _update_task


def run_collection(task_id):
    session = _get_db_session()
    try:
        task = session.get(Task, task_id)
        account = session.get(Account, task.account_id)
        cookie = session.get(Cookie, task.cookie_id)
        if _is_cancelled(task_id):
            return
        _update_task(task_id, status="running", started_at=datetime.utcnow(), progress=1)

        def checkpoint(dataset, stage):
            save_dataset(Path(settings.data_dir) / "tasks" / str(task_id) / "dataset.json", dataset)
            done = sum(r["detail_status"] != "未尝试" for r in dataset["rows"])
            progress = min(98, 10 + int(85 * done / max(1, len(dataset["rows"]))))
            _update_task(task_id, progress=progress, run_log=_progress_log(stage, dataset.get("stop_reason", ""), []))

        dataset = collect_library(account.profile_url, cookie.cookie_json, checkpoint,
                                  cancelled=lambda: _is_cancelled(task_id), limit=min(100, settings.max_notes_per_task))
        _update_task(task_id, status=dataset["status"], progress=100,
                     completed_at=datetime.utcnow(), error_message=dataset["stop_reason"] if dataset["status"] != "completed" else None)
    except Exception:
        _update_task(task_id, status="failed", completed_at=datetime.utcnow(), error_message="整理中断，已采集数据仍可下载。请检查登录状态和网络后重新创建任务。")
    finally:
        session.close()


def submit_collection(task_id):
    with _state_lock:
        _task_state[task_id] = {"status": "pending", "progress": 0}
    threading.Thread(target=run_collection, args=(task_id,), daemon=True).start()
