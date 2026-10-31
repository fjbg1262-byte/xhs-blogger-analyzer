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
from backend.services.ai_agent import build_grounded_ai_enhancement, enhancement_fingerprint
from backend.services.telemetry import classify_error, track

# In-memory task state
_task_state: dict[int, dict] = {}
_state_lock = threading.Lock()
_executor = None

MSG_COLLECT_COOKIE = "\u91c7\u96c6\u5931\u8d25\uff1aCookie \u53ef\u80fd\u5df2\u8fc7\u671f\u6216\u7f3a\u5c11\u5fc5\u8981\u5b57\u6bb5\u3002\u8bf7\u91cd\u65b0\u767b\u5f55\u5c0f\u7ea2\u4e66\u540e\u5bfc\u5165\u5b8c\u6574 Cookie\u3002"
MSG_COLLECT_TIMEOUT = "\u91c7\u96c6\u8d85\u65f6\uff1a\u7f51\u7edc\u8f83\u6162\u6216\u76ee\u6807\u63a5\u53e3\u6682\u65f6\u65e0\u54cd\u5e94\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002"
MSG_COLLECT_NETWORK = "采集网络连接失败：暂时无法连接小红书。请先确认浏览器可以正常打开小红书，然后等待 30 秒再重试。"
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
    {"key": "collect", "label": "采集主页公开内容", "progress": 28},
    {"key": "enrich", "label": "补充正文、媒体、评论与搜索", "progress": 70},
    {"key": "analyze", "label": "完成八维证据分析", "progress": 84},
    {"key": "report", "label": "生成分析报告", "progress": 90},
    {"key": "finish", "label": "保存结果", "progress": 100},
]


DETAIL_FETCH_STEPS = [
    {"key": "prepare", "label": "准备补充采集", "progress": 10},
    {"key": "fetch", "label": "补充正文、媒体、评论与搜索", "progress": 70},
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
    if raw.startswith("采集网络连接失败："):
        return raw[:500]
    if "cookie" in lower or "\u767b\u5f55" in raw or "unauthorized" in lower or "403" in raw:
        return MSG_COLLECT_COOKIE
    if any(marker in lower for marker in (
        "newconnectionerror",
        "max retries exceeded",
        "failed to establish a new connection",
        "connection refused",
        "name resolution",
        "getaddrinfo failed",
        "proxyerror",
    )):
        return MSG_COLLECT_NETWORK
    if "timeout" in lower or "timed out" in lower:
        return MSG_COLLECT_TIMEOUT
    if "spider_xhs not found" in lower:
        return MSG_COLLECT_COMPONENT
    if "failed to collect notes" in lower or "notes" in lower:
        return f"{MSG_COLLECT_NOTES}{raw[:300]}"
    return raw[:500]


def _duration_ms(started_monotonic: float) -> int:
    return max(0, int((time.monotonic() - started_monotonic) * 1000))


def _mark_failed(
    task_id: int,
    exc: Exception,
    *,
    stage: str = "unknown",
    task_type: str = "full_analysis",
    started_monotonic: float = None,
):
    _update_task(task_id, status="failed", error_message=_friendly_error(exc))
    properties = {
        "task_type": task_type if task_type in ("full_analysis", "detail_fetch", "competitor_discovery") else "full_analysis",
        "error_code": classify_error(exc),
        "stage": stage,
    }
    if started_monotonic is not None:
        properties["duration_ms"] = _duration_ms(started_monotonic)
    track("analysis_failed", properties)


def _rerun_outputs(
    task_id: int,
    task_dir: Path,
    account_id: int = None,
    session=None,
    ai_user_id: int = None,
) -> dict:
    """Re-run analysis, brief, quality checks and markdown reports from task files."""
    notes_path = str(task_dir / "all_notes.json")
    profile_path = str(task_dir / "profile.json")
    contents_path = str(task_dir / "contents.json")
    comments_path = str(task_dir / "comments.json")
    search_path = str(task_dir / "search_landscape.json")
    results_path = str(task_dir / "results.json")
    data_quality_path = str(task_dir / "data_quality.json")
    insight_brief_path = str(task_dir / "insight_brief.json")
    report_quality_path = str(task_dir / "report_quality_check.json")

    results = run_analysis(
        notes_path=notes_path,
        profile_path=profile_path,
        output_path=results_path,
        contents_path=contents_path if Path(contents_path).exists() else None,
        comments_path=comments_path if Path(comments_path).exists() else None,
        search_path=search_path if Path(search_path).exists() else None,
        quality_output_path=data_quality_path,
    )
    ai_path = task_dir / "ai_enhancement.json"
    all_notes = json.loads(Path(notes_path).read_text(encoding="utf-8"))
    contents = json.loads(Path(contents_path).read_text(encoding="utf-8")) if Path(contents_path).exists() else []
    comments = json.loads(Path(comments_path).read_text(encoding="utf-8")) if Path(comments_path).exists() else []
    from backend.services.delivery import load_context
    context = load_context(task_dir)
    input_fingerprint = enhancement_fingerprint(results, all_notes, contents, comments, context)
    if ai_user_id is not None:
        ai_enhancement = build_grounded_ai_enhancement(
            results,
            all_notes,
            contents,
            comments,
            user_id=ai_user_id,
            context=context,
        )
        ai_enhancement["input_fingerprint"] = input_fingerprint
        ai_path.write_text(json.dumps(ai_enhancement, ensure_ascii=False, indent=2), encoding="utf-8")
        results["ai_enhancement"] = ai_enhancement
        Path(results_path).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    elif ai_path.exists():
        try:
            cached = json.loads(ai_path.read_text(encoding="utf-8"))
            results["ai_enhancement"] = cached if cached.get("input_fingerprint") == input_fingerprint else {
                "enabled": False, "status": "stale", "dimensions": {},
                "message": "原始数据或客户目标已变化，旧 AI 结果未复用。",
            }
            Path(results_path).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, ValueError, TypeError):
            pass
    build_insight_brief(
        results_path=results_path,
        all_notes_path=notes_path,
        data_quality_path=data_quality_path,
        output_path=insight_brief_path,
    )
    reports_dir = str(Path(settings.reports_dir) / f"task_{task_id}")
    generate_reports(results_path, reports_dir)
    run_report_quality_check(
        results_path=results_path,
        brief_path=insight_brief_path,
        data_quality_path=data_quality_path,
        output_path=report_quality_path,
        reports_dir=reports_dir,
    )

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
    started_monotonic = time.monotonic()
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
            _mark_failed(
                task_id,
                RuntimeError("Missing cookie or account"),
                stage="prepare",
                task_type="full_analysis",
                started_monotonic=started_monotonic,
            )
            return
        track("analysis_started", {"task_type": "full_analysis"})

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
            _mark_failed(
                task_id,
                e,
                stage="collect",
                task_type="full_analysis",
                started_monotonic=started_monotonic,
            )
            return
        if _is_cancelled(task_id):
            return

        task_dir = Path(settings.data_dir) / "tasks" / str(task_id)
        collector.save_task_data(task_dir, data)
        _update_task(
            task_id,
            progress=28,
            run_log=_progress_log(
                "采集完成",
                f"已保存 {len(data.get('all_notes', []))} 篇公开笔记，开始选择分层详情样本。",
                FULL_ANALYSIS_STEPS,
            ),
        )
        if _is_cancelled(task_id):
            return

        # Phase 2: Initial analysis selects balanced detail and research samples.
        _update_task(
            task_id,
            progress=32,
            run_log=_progress_log("识别初步主题", "正在为详情、评论和媒体采集选择代表样本。", FULL_ANALYSIS_STEPS),
        )
        try:
            results = _rerun_outputs(task_id, task_dir)
        except RuntimeError as e:
            _mark_failed(
                task_id,
                e,
                stage="analyze",
                task_type="full_analysis",
                started_monotonic=started_monotonic,
            )
            return
        def update_detail_progress(done: int, total: int):
            if total:
                _update_task(
                    task_id,
                    progress=35 + int(20 * done / total),
                    run_log=_progress_log("补充笔记详情", f"正在采集正文、标签、媒体与完整互动：{done}/{total}", FULL_ANALYSIS_STEPS),
                )

        enrichment_errors = []
        try:
            collector.enrich_note_details(
                task_dir=task_dir,
                cookies_input=cookie.cookie_json,
                max_count=30,
                progress_callback=update_detail_progress,
            )
        except Exception as exc:
            enrichment_errors.append(f"详情补采：{_friendly_error(exc)}")

        # Re-run once so search terms can use the actual detail tags and topics.
        try:
            results = _rerun_outputs(task_id, task_dir)
        except RuntimeError as exc:
            enrichment_errors.append(f"详情分析：{_friendly_error(exc)}")

        def update_comment_progress(done: int, total: int):
            if total:
                _update_task(
                    task_id,
                    progress=56 + int(11 * done / total),
                    run_log=_progress_log("采集代表评论", f"正在读取代表内容的公开评论：{done}/{total}", FULL_ANALYSIS_STEPS),
                )

        try:
            collector.enrich_comments(
                task_dir=task_dir,
                cookies_input=cookie.cookie_json,
                max_notes=12,
                comments_per_note=10,
                progress_callback=update_comment_progress,
            )
        except Exception as exc:
            enrichment_errors.append(f"评论采集：{_friendly_error(exc)}")

        _update_task(
            task_id,
            progress=68,
            run_log=_progress_log("研究搜索表达", "正在读取少量关键词联想和公开搜索结果。", FULL_ANALYSIS_STEPS),
        )
        try:
            collector.enrich_search_landscape(task_dir, cookie.cookie_json, max_keywords=4, results_per_keyword=10)
        except Exception as exc:
            enrichment_errors.append(f"搜索研究：{_friendly_error(exc)}")

        _update_task(
            task_id,
            progress=74,
            run_log=_progress_log("完成八维分析", "正在合并标题、正文、媒体、评论和搜索证据。", FULL_ANALYSIS_STEPS),
        )
        try:
            results = _rerun_outputs(
                task_id,
                task_dir,
                ai_user_id=task.user_id if enable_ai else None,
            )
        except RuntimeError as e:
            _mark_failed(
                task_id,
                e,
                stage="analyze",
                task_type="full_analysis",
                started_monotonic=started_monotonic,
            )
            return
        if enrichment_errors:
            (task_dir / "enrichment_warnings.json").write_text(
                json.dumps({"warnings": enrichment_errors}, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        if _is_cancelled(task_id):
            return

        # Phase 3: Reports already generated by _rerun_outputs.
        reports_dir = str(Path(settings.reports_dir) / f"task_{task_id}")
        _update_task(
            task_id,
            progress=90,
            run_log=_progress_log("生成报告", "正在生成可阅读的报告页面与导出内容。", FULL_ANALYSIS_STEPS),
        )
        if _is_cancelled(task_id):
            return

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
        track(
            "analysis_completed",
            {"task_type": "full_analysis", "duration_ms": _duration_ms(started_monotonic)},
        )
        print(f"[Worker] Task {task_id} completed")

    except Exception as e:
        _mark_failed(
            task_id,
            e,
            stage="unknown",
            task_type="full_analysis",
            started_monotonic=started_monotonic,
        )
        print(f"[Worker] Task {task_id} failed: {e}")
    finally:
        session.close()


def _run_competitor_discovery(task_id: int, keyword: str, count: int):
    """Discover competitors and create child analysis tasks."""
    started_monotonic = time.monotonic()
    session = _get_db_session()
    try:
        from backend.database import Task, Cookie
        task = session.get(Task, task_id)
        if not task:
            return
        track("analysis_started", {"task_type": "competitor_discovery"})

        cookie = session.get(Cookie, task.cookie_id)
        if not cookie:
            _mark_failed(
                task_id,
                RuntimeError(MSG_COOKIE_NOT_FOUND),
                stage="prepare",
                task_type="competitor_discovery",
                started_monotonic=started_monotonic,
            )
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
        track(
            "analysis_completed",
            {
                "task_type": "competitor_discovery",
                "duration_ms": _duration_ms(started_monotonic),
            },
        )

    except Exception as e:
        _mark_failed(
            task_id,
            e,
            stage="collect",
            task_type="competitor_discovery",
            started_monotonic=started_monotonic,
        )
    finally:
        session.close()


def _run_detail_enrichment(task_id: int, max_count: int = 25):
    """Fetch selected note details, then regenerate analysis outputs for the same task."""
    started_monotonic = time.monotonic()
    session = _get_db_session()
    try:
        from backend.database import Task, Cookie
        task = session.get(Task, task_id)
        if not task:
            return
        track("analysis_started", {"task_type": "detail_fetch"})
        cookie = session.get(Cookie, task.cookie_id)
        if not cookie:
            _mark_failed(
                task_id,
                RuntimeError(MSG_COOKIE_NOT_FOUND),
                stage="prepare",
                task_type="detail_fetch",
                started_monotonic=started_monotonic,
            )
            return

        task_dir = Path(settings.data_dir) / "tasks" / str(task_id)
        if not (task_dir / "all_notes.json").exists():
            _mark_failed(
                task_id,
                RuntimeError("任务缺少原始笔记数据，无法补充详情。"),
                stage="prepare",
                task_type="detail_fetch",
                started_monotonic=started_monotonic,
            )
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
            progress = 15 + int(35 * min(done, total) / total)
            _update_task(
                task_id,
                progress=progress,
                run_log=_progress_log(
                    "补充正文、媒体与互动",
                    f"已处理 {done}/{total} 篇代表笔记。",
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
            progress=52,
            run_log=_progress_log("补充详情完成", "正在选择评论和搜索研究样本。", DETAIL_FETCH_STEPS),
        )
        if _is_cancelled(task_id):
            return

        _rerun_outputs(task_id, task_dir)
        enrichment_errors = []
        try:
            collector.enrich_comments(
                task_dir=task_dir,
                cookies_input=cookie.cookie_json,
                max_notes=12,
                comments_per_note=10,
            )
        except Exception as exc:
            enrichment_errors.append(f"评论采集：{_friendly_error(exc)}")
        _update_task(
            task_id,
            progress=72,
            run_log=_progress_log("研究搜索表达", "正在补充关键词联想与公开结果样本。", DETAIL_FETCH_STEPS),
        )
        try:
            collector.enrich_search_landscape(task_dir, cookie.cookie_json, max_keywords=4, results_per_keyword=10)
        except Exception as exc:
            enrichment_errors.append(f"搜索研究：{_friendly_error(exc)}")
        _update_task(
            task_id,
            progress=86,
            run_log=_progress_log("重新分析报告", "正在更新八维结论、证据和数据边界。", DETAIL_FETCH_STEPS),
        )
        _rerun_outputs(task_id, task_dir)
        if enrichment_errors:
            (task_dir / "enrichment_warnings.json").write_text(
                json.dumps({"warnings": enrichment_errors}, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        _update_task(
            task_id,
            status="completed",
            progress=100,
            completed_at=datetime.utcnow(),
            run_log=_progress_log("补充完成", "正文、媒体、评论和搜索样本已补充，报告已重新生成。", DETAIL_FETCH_STEPS),
            error_message=(
                f"公开数据补采完成：详情成功 {detail_fetch.get('success_count', 0)} 条，"
                f"失败 {detail_fetch.get('failed_count', 0)} 条。"
            ),
        )
        track(
            "analysis_completed",
            {"task_type": "detail_fetch", "duration_ms": _duration_ms(started_monotonic)},
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
            error_message=f"公开数据补采失败，基础报告仍可使用：{_friendly_error(e)}",
        )
        track(
            "analysis_failed",
            {
                "task_type": "detail_fetch",
                "duration_ms": _duration_ms(started_monotonic),
                "error_code": classify_error(e),
                "stage": "collect",
            },
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


def regenerate_outputs(task_id: int) -> dict:
    """Regenerate analysis, reports and semantic quality checks from saved task data."""
    task_dir = Path(settings.data_dir) / "tasks" / str(task_id)
    if not (task_dir / "all_notes.json").exists():
        raise RuntimeError("任务缺少原始笔记数据，无法重新生成报告。")
    return _rerun_outputs(task_id, task_dir)


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
