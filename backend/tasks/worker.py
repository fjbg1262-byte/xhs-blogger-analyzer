"""Background task worker — runs analysis pipeline in ThreadPoolExecutor."""

import json
import threading
import time
from datetime import datetime
from pathlib import Path

from backend.config import settings, BASE_DIR
from backend.services.collector import Collector
from backend.services.analyzer import run_analysis
from backend.services.insight_brief import build_insight_brief
from backend.services.report_quality import run_report_quality_check
from backend.services.reporter import generate_reports
from backend.services.ai_agent import deconstruct_notes, diagnose_account

# In-memory task state
_task_state: dict[int, dict] = {}
_state_lock = threading.Lock()
_executor = None

MSG_COLLECT_COOKIE = "\u91c7\u96c6\u5931\u8d25\uff1aCookie \u53ef\u80fd\u5df2\u8fc7\u671f\u6216\u7f3a\u5c11\u5fc5\u8981\u5b57\u6bb5\u3002\u8bf7\u91cd\u65b0\u767b\u5f55\u5c0f\u7ea2\u4e66\u540e\u5bfc\u5165\u5b8c\u6574 Cookie\u3002"
MSG_COLLECT_TIMEOUT = "\u91c7\u96c6\u8d85\u65f6\uff1a\u7f51\u7edc\u8f83\u6162\u6216\u76ee\u6807\u63a5\u53e3\u6682\u65f6\u65e0\u54cd\u5e94\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002"
MSG_COLLECT_COMPONENT = "\u91c7\u96c6\u7ec4\u4ef6 Spider_XHS \u4e0d\u53ef\u7528\uff0c\u8bf7\u68c0\u67e5\u9879\u76ee\u4f9d\u8d56\u662f\u5426\u5b8c\u6574\u3002"
MSG_COLLECT_NOTES = "\u91c7\u96c6\u7b14\u8bb0\u5931\u8d25\uff1a"
MSG_COOKIE_NOT_FOUND = "Cookie \u4e0d\u5b58\u5728\uff0c\u8bf7\u5148\u5728\u8bbe\u7f6e\u9875\u6dfb\u52a0 Cookie\u3002"
MSG_NO_USERS = "\u672a\u627e\u5230\u5bf9\u6807\u535a\u4e3b"


def _progress_log(stage: str, detail: str = "", steps=None) -> str:
    """Encode human-readable progress metadata in the existing run_log column."""
    return json.dumps(
        {
            "stage": stage,
            "detail": detail,
            "steps": steps or [],
            "updated_at": datetime.utcnow().isoformat(),
        },
        ensure_ascii=False,
    )


FULL_ANALYSIS_STEPS = [
    {"key": "prepare", "label": "准备任务", "progress": 5},
    {"key": "collect", "label": "采集主页公开内容", "progress": 40},
    {"key": "analyze", "label": "识别主题与互动表现", "progress": 70},
    {"key": "report", "label": "生成分析报告", "progress": 90},
    {"key": "finish", "label": "保存结果", "progress": 100},
]


DETAIL_FETCH_STEPS = [
    {"key": "prepare", "label": "准备补充采集", "progress": 10},
    {"key": "fetch", "label": "补充正文与标签", "progress": 65},
    {"key": "rerun", "label": "重新分析报告", "progress": 90},
    {"key": "finish", "label": "保存结果", "progress": 100},
]


def _get_db_session():
    """Get a sync DB session for worker updates (avoid async in threads)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    sync_url = settings.database_url.replace("+aiosqlite", "")
    engine = create_engine(sync_url)
    Session = sessionmaker(bind=engine)
    return Session()


def _update_task(task_id: int, **kwargs):
    """Update task in DB and in-memory state."""
    with _state_lock:
        if task_id in _task_state:
            _task_state[task_id].update(kwargs)

    session = _get_db_session()
    try:
        from backend.database import Task
        task = session.get(Task, task_id)
        if task:
            for k, v in kwargs.items():
                setattr(task, k, v)
            session.commit()
    except Exception as e:
        print(f"[Worker] DB update error for task {task_id}: {e}")
    finally:
        session.close()


def _is_cancelled(task_id: int) -> bool:
    with _state_lock:
        return _task_state.get(task_id, {}).get("status") == "cancelled"


def _friendly_error(exc: Exception) -> str:
    raw = str(exc)
    lower = raw.lower()
    if "cookie" in lower or "\u767b\u5f55" in raw or "unauthorized" in lower or "403" in raw:
        return MSG_COLLECT_COOKIE
    if "timeout" in lower or "timed out" in lower:
        return MSG_COLLECT_TIMEOUT
    if "spider_xhs not found" in lower:
        return MSG_COLLECT_COMPONENT
    if "failed to collect notes" in lower or "notes" in lower:
        return f"{MSG_COLLECT_NOTES}{raw[:300]}"
    return raw[:500]


def _mark_failed(task_id: int, exc: Exception):
    _update_task(task_id, status="failed", error_message=_friendly_error(exc))


def _rerun_outputs(task_id: int, task_dir: Path, account_id: int = None, session=None) -> dict:
    """Re-run analysis, brief, quality checks and markdown reports from task files."""
    notes_path = str(task_dir / "all_notes.json")
    profile_path = str(task_dir / "profile.json")
    contents_path = str(task_dir / "contents.json")
    results_path = str(task_dir / "results.json")
    data_quality_path = str(task_dir / "data_quality.json")
    insight_brief_path = str(task_dir / "insight_brief.json")
    report_quality_path = str(task_dir / "report_quality_check.json")

    results = run_analysis(
        notes_path=notes_path,
        profile_path=profile_path,
        output_path=results_path,
        contents_path=contents_path if Path(contents_path).exists() else None,
        quality_output_path=data_quality_path,
    )
    build_insight_brief(
        results_path=results_path,
        all_notes_path=notes_path,
        data_quality_path=data_quality_path,
        output_path=insight_brief_path,
    )
    run_report_quality_check(
        results_path=results_path,
        brief_path=insight_brief_path,
        data_quality_path=data_quality_path,
        output_path=report_quality_path,
    )
    reports_dir = str(BASE_DIR / "reports" / f"task_{task_id}")
    generate_reports(results_path, reports_dir)

    if session is not None and account_id:
        try:
            from backend.database import AnalysisResult
            ar = AnalysisResult(
                task_id=task_id,
                account_id=account_id,
                results_json=json.dumps(results, ensure_ascii=False),
                reports_dir=reports_dir,
                note_count=results.get("profile", {}).get("total_notes", 0),
                likes_total=results.get("profile", {}).get("total_likes_sum", 0),
                avg_likes=results.get("profile", {}).get("avg_likes", 0),
            )
            session.add(ar)
            session.commit()
        except Exception as e:
            print(f"[Worker] AnalysisResult save error: {e}")

    return results


def _run_full_analysis(task_id: int, enable_ai: bool = False):
    """Execute the full analysis pipeline: collect -> analyze -> report."""
    session = _get_db_session()
    try:
        from backend.database import Task, Cookie, Account
        task = session.get(Task, task_id)
        if not task:
            return
        owner_id = task.user_id

        cookie = session.get(Cookie, task.cookie_id)
        account = session.get(Account, task.account_id)
        if not cookie or not account:
            _update_task(task_id, status="failed", error_message="Missing cookie or account")
            return

        # Phase 1: Collect data
        _update_task(
            task_id,
            status="running",
            progress=5,
            started_at=datetime.utcnow(),
            run_log=_progress_log("准备任务", "正在检查账号、Cookie 与本地采集环境。", FULL_ANALYSIS_STEPS),
        )
        collector = Collector()
        profile_url = account.profile_url

        _update_task(
            task_id,
            progress=15,
            run_log=_progress_log("采集公开内容", "正在读取博主主页的公开笔记列表。", FULL_ANALYSIS_STEPS),
        )
        try:
            data = collector.collect_all_notes(profile_url, cookie.cookie_json)
        except RuntimeError as e:
            _mark_failed(task_id, e)
            return
        if _is_cancelled(task_id):
            return

        task_dir = Path(settings.data_dir) / "tasks" / str(task_id)
        collector.save_task_data(task_dir, data)
        _update_task(
            task_id,
            progress=40,
            run_log=_progress_log(
                "采集完成",
                f"已保存 {len(data.get('all_notes', []))} 篇公开笔记，开始做内容分析。",
                FULL_ANALYSIS_STEPS,
            ),
        )
        if _is_cancelled(task_id):
            return

        # Phase 2: Run analysis
        _update_task(
            task_id,
            progress=55,
            run_log=_progress_log("分析内容结构", "正在识别主题、互动表现和可引用证据。", FULL_ANALYSIS_STEPS),
        )
        try:
            results = _rerun_outputs(task_id, task_dir)
        except RuntimeError as e:
            _mark_failed(task_id, e)
            return
        _update_task(
            task_id,
            progress=75,
            run_log=_progress_log("生成结构化结论", "正在整理账号定位、主题地图和行动建议。", FULL_ANALYSIS_STEPS),
        )
        if _is_cancelled(task_id):
            return

        # Phase 3: Reports already generated by _rerun_outputs.
        reports_dir = str(BASE_DIR / "reports" / f"task_{task_id}")
        _update_task(
            task_id,
            progress=90,
            run_log=_progress_log("生成报告", "正在生成可阅读的报告页面与导出内容。", FULL_ANALYSIS_STEPS),
        )
        if _is_cancelled(task_id):
            return

        # Phase 4: AI Agent (optional)
        if enable_ai:
            try:
                notes_path_p = task_dir / "all_notes.json"
                if notes_path_p.exists():
                    all_notes = json.loads(notes_path_p.read_text(encoding="utf-8"))
                    ai_result = deconstruct_notes(all_notes, user_id=task.user_id)
                    (task_dir / "ai_deconstruct.txt").write_text(ai_result, encoding="utf-8")

                    ai_diagnosis = diagnose_account(results, user_id=task.user_id)
                    (task_dir / "ai_diagnosis.txt").write_text(ai_diagnosis, encoding="utf-8")
            except Exception as e:
                print(f"[Worker] AI Agent error: {e}")
            _update_task(
                task_id,
                progress=95,
                run_log=_progress_log("AI 增强分析", "正在保存 AI 增强分析结果。", FULL_ANALYSIS_STEPS),
            )

        _update_task(
            task_id,
            progress=95,
            run_log=_progress_log("保存结果", "正在写入本地数据库。", FULL_ANALYSIS_STEPS),
        )

        # Save analysis result record
        try:
            from backend.database import AnalysisResult
            ar = AnalysisResult(
                task_id=task_id,
                account_id=account.id,
                results_json=json.dumps(results, ensure_ascii=False),
                reports_dir=reports_dir,
                note_count=results.get("profile", {}).get("total_notes", 0),
                likes_total=results.get("profile", {}).get("total_likes_sum", 0),
                avg_likes=results.get("profile", {}).get("avg_likes", 0),
            )
            session.add(ar)
            account.last_task_id = task_id
            session.commit()
        except Exception as e:
            print(f"[Worker] DB save error: {e}")

        _update_task(
            task_id,
            status="completed",
            progress=100,
            completed_at=datetime.utcnow(),
            run_log=_progress_log("分析完成", "报告已生成，可以查看结果。", FULL_ANALYSIS_STEPS),
        )
        print(f"[Worker] Task {task_id} completed")

    except Exception as e:
        _mark_failed(task_id, e)
        print(f"[Worker] Task {task_id} failed: {e}")
    finally:
        session.close()


def _run_competitor_discovery(task_id: int, keyword: str, count: int):
    """Discover competitors and create child analysis tasks."""
    session = _get_db_session()
    try:
        from backend.database import Task, Cookie
        task = session.get(Task, task_id)
        if not task:
            return

        cookie = session.get(Cookie, task.cookie_id)
        if not cookie:
            _update_task(task_id, status="failed", error_message=MSG_COOKIE_NOT_FOUND)
            return

        _update_task(task_id, status="running", progress=10, started_at=datetime.utcnow())

        collector = Collector()
        users = collector.search_users(keyword, count, cookie.cookie_json)

        if not users:
            _update_task(task_id, status="completed", progress=100, error_message=MSG_NO_USERS)
            return

        _update_task(task_id, progress=30)
        if _is_cancelled(task_id):
            return

        # Create child analysis tasks for each discovered user
        from backend.database import Account, Task as TaskModel
        child_ids = []
        for u in users[:settings.max_competitor_count]:
            user_id = u.get("user_id", "")
            profile_url = f"https://www.xiaohongshu.com/user/profile/{user_id}"

            # Check if account already exists
            acc = (
                session.query(Account)
                .filter_by(user_id=owner_id, profile_url=profile_url)
                .first()
            )
            if not acc:
                acc = Account(
                    user_id=owner_id,
                    profile_url=profile_url,
                    xhs_user_id=user_id,
                    nickname=u.get("nickname", ""),
                    follower_count=u.get("follower_count", 0),
                )
                session.add(acc)
                session.flush()

            child = TaskModel(
                user_id=owner_id,
                account_id=acc.id,
                cookie_id=task.cookie_id,
                task_type="full_analysis",
                status="pending",
            )
            session.add(child)
            session.flush()
            child_ids.append(child.id)

        session.commit()

        # Process each child task
        for i, cid in enumerate(child_ids):
            if _is_cancelled(task_id):
                return
            _update_task(task_id, progress=30 + int(60 * (i / len(child_ids))))
            _run_full_analysis(cid, enable_ai=False)
            # Avoid rate limiting
            time.sleep(5)

        _update_task(task_id, status="completed", progress=100, completed_at=datetime.utcnow())

    except Exception as e:
        _mark_failed(task_id, e)
    finally:
        session.close()


def _run_detail_enrichment(task_id: int, max_count: int = 25):
    """Fetch selected note details, then regenerate analysis outputs for the same task."""
    session = _get_db_session()
    try:
        from backend.database import Task, Cookie
        task = session.get(Task, task_id)
        if not task:
            return
        cookie = session.get(Cookie, task.cookie_id)
        if not cookie:
            _update_task(task_id, status="failed", error_message=MSG_COOKIE_NOT_FOUND)
            return

        task_dir = Path(settings.data_dir) / "tasks" / str(task_id)
        if not (task_dir / "all_notes.json").exists():
            _update_task(task_id, status="failed", error_message="任务缺少原始笔记数据，无法补充详情。")
            return

        _update_task(
            task_id,
            status="running",
            progress=10,
            started_at=datetime.utcnow(),
            run_log=_progress_log("准备补充采集", "正在选择最值得补充正文和标签的笔记。", DETAIL_FETCH_STEPS),
        )
        collector = Collector()

        def update_detail_progress(done: int, total: int):
            if total <= 0:
                return
            progress = 15 + int(50 * min(done, total) / total)
            _update_task(
                task_id,
                progress=progress,
                run_log=_progress_log(
                    "补充正文与标签",
                    f"已处理 {done}/{total} 篇重点笔记。",
                    DETAIL_FETCH_STEPS,
                ),
            )

        detail_fetch = collector.enrich_note_details(
            task_dir=task_dir,
            cookies_input=cookie.cookie_json,
            max_count=max(1, min(max_count, 30)),
            progress_callback=update_detail_progress,
        )
        _update_task(
            task_id,
            progress=70,
            run_log=_progress_log("补充采集完成", "正在把正文和标签重新写入分析。", DETAIL_FETCH_STEPS),
        )
        if _is_cancelled(task_id):
            return

        _update_task(
            task_id,
            progress=85,
            run_log=_progress_log("重新分析报告", "正在更新主题、证据和正文标签判断。", DETAIL_FETCH_STEPS),
        )
        _rerun_outputs(task_id, task_dir)
        _update_task(
            task_id,
            status="completed",
            progress=100,
            completed_at=datetime.utcnow(),
            run_log=_progress_log("补充完成", "正文与标签已补充，报告已重新生成。", DETAIL_FETCH_STEPS),
            error_message=(
                f"正文与标签补采完成：成功 {detail_fetch.get('success_count', 0)} 条，"
                f"失败 {detail_fetch.get('failed_count', 0)} 条。"
            ),
        )
        print(f"[Worker] Detail enrichment for task {task_id} completed")
    except Exception as e:
        task_dir = Path(settings.data_dir) / "tasks" / str(task_id)
        try:
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / "detail_fetch.json").write_text(
                json.dumps(
                    {
                        "enabled": True,
                        "requested_count": 0,
                        "success_count": 0,
                        "failed_count": 1,
                        "failures": [{"note_id": "", "reason": _friendly_error(e)}],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass
        _update_task(
            task_id,
            status="completed",
            progress=100,
            completed_at=datetime.utcnow(),
            error_message=f"正文与标签补采失败，基础报告仍可使用：{_friendly_error(e)}",
        )
        print(f"[Worker] Detail enrichment for task {task_id} failed: {e}")
    finally:
        session.close()


# Public API
def submit_task(task_id: int, enable_ai: bool = False):
    """Submit a full-analysis task to the background worker."""
    with _state_lock:
        _task_state[task_id] = {"status": "pending", "progress": 0}

    thread = threading.Thread(target=_run_full_analysis, args=(task_id, enable_ai), daemon=True)
    thread.start()


def submit_detail_enrichment(task_id: int, max_count: int = 25):
    """Submit a detail enrichment job for an existing completed task."""
    with _state_lock:
        _task_state[task_id] = {"status": "pending", "progress": 0}

    thread = threading.Thread(target=_run_detail_enrichment, args=(task_id, max_count), daemon=True)
    thread.start()


def submit_competitor_discovery(task_id: int, keyword: str, count: int):
    """Submit a competitor discovery task to the background worker."""
    with _state_lock:
        _task_state[task_id] = {"status": "pending", "progress": 0}

    thread = threading.Thread(
        target=_run_competitor_discovery, args=(task_id, keyword, count), daemon=True
    )
    thread.start()


def _cancel_task(task_id: int) -> bool:
    """Cancel a running task. Returns True if task was running."""
    should_cancel = False
    with _state_lock:
        state = _task_state.get(task_id)
        if state and state.get("status") in ("pending", "running"):
            state["status"] = "cancelled"
            should_cancel = True
    if should_cancel:
        _update_task(task_id, status="cancelled")
    return should_cancel


def init_worker():
    """Initialize the worker (called at app startup)."""
    print("[Worker] Background worker initialized")
