"""Workspace API and retry worker tests (Phase 2)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import app
from backend.database import Account, Base, Cookie, Task, User, get_db
from backend.routers.auth import get_current_user


def row(note_id, title, type_, likes, collected, comments, shares, tags, body="", published="2026-08-01T10:00:00+08:00",
        detail_status="成功"):
    return {
        "note_id": note_id,
        "title": title,
        "published_at": published,
        "liked_count": likes,
        "collected_count": collected,
        "comment_count": comments,
        "share_count": shares,
        "type": type_,
        "note_url": f"https://www.xiaohongshu.com/explore/{note_id}",
        "cover_url": "",
        "content_text": body,
        "tags": tags,
        "image_urls": [],
        "video_url": "",
        "author_nickname": "野路手册",
        "author_user_id": "u1",
        "sticky": False,
        "detail_status": detail_status,
        "text_status": "已采集" if body else "未采集",
        "tags_status": "已采集" if tags else "无标签",
        "missing_fields": [] if body else ["正文"],
        "failure_reason": "" if detail_status == "成功" else "访问受限，请稍后在浏览器确认",
        "collected_at": "2026-08-02T09:00:00+08:00",
        "metric_source": "笔记详情",
        "count_precision": "接口数值",
        "likes_vs_median": None,
        "list_order": 1,
        "profile_url": "https://www.xiaohongshu.com/user/profile/abc12345",
    }


def sample_dataset():
    rows = [
        row("n1", "花35元坐公交去草原", "图文", 10000, 9000, 600, 500, ["北京周边", "公交路线"], body="全程分三段，共5.5小时。"),
        row("n2", "一个人拍旅行视频的3个镜头", "视频", 7000, 2000, 200, 1000, ["手机拍摄"], body="环境镜头、动作镜头和一句感受。"),
        row("n3", "北京冬天可以做的十件小事", "图文", 900, 800, 300, 200, ["北京周边"], detail_status="失败"),
    ]
    return {
        "schema_version": "1.0",
        "profile_url": "https://www.xiaohongshu.com/user/profile/abc12345",
        "created_at": "2026-08-02T09:00:00+08:00",
        "finished_at": "2026-08-02T09:10:00+08:00",
        "status": "partial",
        "stop_reason": "访问受限，请稍后在浏览器确认",
        "rows": rows,
        "duplicates": 0,
        "pages": 1,
        "requested_limit": 100,
        "summary": {"note_count": 3, "detail_success": 2, "likes_median": 7000.0, "known_likes_count": 3},
    }


class WorkspaceApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.engine = create_engine(
            f"sqlite:///{(self.root / 'test.db').as_posix()}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as session:
            session.add(User(id=1, username="test", password_hash="unused"))
            session.add(Cookie(id=1, user_id=1, cookie_json='{"web_session":"test"}'))
            session.add(Account(id=1, user_id=1, profile_url="https://www.xiaohongshu.com/user/profile/abc12345"))
            session.add(Task(id=1, user_id=1, account_id=1, cookie_id=1,
                             task_type="note_collection", status="partial", progress=100))
            session.add(Task(id=2, user_id=1, account_id=1, cookie_id=1,
                             task_type="note_collection", status="running", progress=40))
            session.commit()

        data = self.root / "tasks" / "1"
        data.mkdir(parents=True)
        (data / "dataset.json").write_text(json.dumps(sample_dataset(), ensure_ascii=False), encoding="utf-8")

        def db():
            with self.Session() as session:
                yield session

        app.dependency_overrides[get_db] = db
        app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "test"}
        self.client = TestClient(app)
        self.patch = patch("backend.config.settings.data_dir", str(self.root))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def test_task_list_and_accounts(self):
        payload = self.client.get("/api/workspace/tasks").json()
        self.assertEqual(payload["counts"]["tasks"], 2)
        self.assertEqual(payload["counts"]["accounts"], 1)
        card = next(item for item in payload["tasks"] if item["id"] == 1)
        self.assertEqual(card["status_label"], "部分完成")
        self.assertEqual(card["note_count"], 3)
        self.assertEqual(card["body_count"], 2)
        self.assertEqual(card["failed_count"], 1)
        self.assertEqual(card["target"], 100)
        account = payload["accounts"][0]
        self.assertEqual(account["note_count"], 3)
        self.assertEqual(account["name"], "野路手册")
        self.assertEqual(account["last_task_id"], 1)

    def test_task_detail_notes_and_stats(self):
        payload = self.client.get("/api/workspace/tasks/1").json()
        self.assertEqual(len(payload["notes"]), 3)
        first = payload["notes"][0]
        self.assertEqual(first["engagement"], 20100)
        self.assertFalse(first["incomplete"])
        failed = next(note for note in payload["notes"] if note["incomplete"])
        self.assertTrue(failed["failure"])
        stats = payload["stats"]
        self.assertEqual(stats["note_count"], 3)
        self.assertEqual(stats["total_engagement"], 20100 + 10200 + 2200)
        self.assertEqual(stats["image_count"], 2)
        self.assertEqual(stats["video_count"], 1)
        self.assertEqual(stats["failed_count"], 1)
        self.assertEqual(stats["body_count"], 2)
        self.assertAlmostEqual(stats["image_share"], 66.7, places=1)
        self.assertEqual(stats["top_tag"], "北京周边")
        self.assertEqual(stats["top_tag_count"], 2)
        self.assertEqual(stats["latest_published_at"][:10], "2026-08-01")
        self.assertEqual(stats["best_type"], "图文")
        self.assertGreater(stats["format_ratio"], 1)
        self.assertGreater(stats["top_share"], 0)
        self.assertEqual(stats["title_count"], 2)
        self.assertEqual(payload["meta"]["status"], "partial")
        self.assertEqual(payload["task"]["reason"], "访问受限，请稍后在浏览器确认")

    def test_progress_and_export(self):
        progress = self.client.get("/api/workspace/tasks/1/progress").json()
        self.assertEqual(progress["counts"]["note_count"], 3)
        self.assertEqual(progress["counts"]["body_count"], 2)
        self.assertIn("progress", progress["task"])

        for fmt in ("xlsx", "csv", "feishu"):
            response = self.client.get(f"/api/workspace/tasks/1/export?format={fmt}")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("attachment", response.headers["content-disposition"])

    def test_missing_dataset_404_and_access_control(self):
        self.assertEqual(self.client.get("/api/workspace/tasks/1/progress").status_code, 200)
        self.assertEqual(self.client.get("/api/workspace/tasks/2/progress").status_code, 200)
        self.assertEqual(self.client.get("/api/workspace/tasks/2").status_code, 404)
        app.dependency_overrides[get_current_user] = lambda: {"id": 999, "username": "other"}
        self.assertEqual(self.client.get("/api/workspace/tasks").json()["counts"]["tasks"], 0)
        self.assertEqual(self.client.get("/api/workspace/tasks/1").status_code, 404)
        self.assertEqual(self.client.get("/api/workspace/tasks/1/export").status_code, 404)

    def test_stop_completed_task_conflicts(self):
        self.assertEqual(self.client.post("/api/workspace/tasks/1/stop").status_code, 409)
        with patch("backend.tasks.worker._cancel_task", return_value=True):
            response = self.client.post("/api/workspace/tasks/2/stop")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "cancelled")

    def test_retry_queues_only_recoverable_tasks(self):
        with patch("backend.tasks.retry_worker.submit_retry") as submit:
            response = self.client.post("/api/workspace/tasks/1/retry")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["queued"], 1)
            submit.assert_called_once()
        with patch("backend.tasks.retry_worker.submit_retry") as submit:
            self.assertEqual(self.client.post("/api/workspace/tasks/2/retry").status_code, 409)
            submit.assert_not_called()

    def test_retry_worker_refreshes_failed_rows(self):
        class FakeCollector:
            def _ensure_api(self, cookies):
                self.cookies = cookies

            def get_note_detail(self, url, cookies=None):
                return {"ok": True, "content_text": "补采到的正文。", "tags": ["北京周边"], "author_nickname": "野路手册"}

        with patch("backend.tasks.retry_worker.Collector", FakeCollector), \
                patch("backend.tasks.retry_worker._get_db_session", self.Session), \
                patch("backend.tasks.worker._get_db_session", self.Session):
            from backend.tasks.retry_worker import run_retry

            run_retry(1, max_count=5)

        dataset = json.loads((self.root / "tasks" / "1" / "dataset.json").read_text(encoding="utf-8"))
        statuses = [item["detail_status"] for item in dataset["rows"]]
        self.assertEqual(statuses.count("成功"), 3)
        self.assertEqual(dataset["status"], "completed")
        self.assertEqual(dataset["rows"][2]["content_text"], "补采到的正文。")
        with self.Session() as session:
            task = session.get(Task, 1)
            self.assertEqual(task.status, "completed")
            self.assertEqual(task.progress, 100)


if __name__ == "__main__":
    unittest.main()
