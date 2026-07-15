import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _note(note_id, title, likes):
    return {
        "note_id": note_id,
        "title": title,
        "liked_count": str(likes),
        "type": "normal",
    }


def main():
    notes = [
        _note("68c1980e000000001d013dce", "被13年前老手机的画质震惊了", 37000),
        _note("697f1b31000000000a02a28d", "一百元淘到的手机能拍出什么样的画质", 19000),
        _note("68d51b790000000012023903", "被10年前手机的直出影调震惊了", 7000),
        _note("68c0d8bb000000001d008595", "诺基亚拍出了我的ccd夏日记忆", 3000),
        _note("6905f3fd00000000070397d7", "10年来手机影像的进步", 2500),
        _note("6a2f8304000000001102ea77", "花35元坐公交从北京去草原（抄作业版）", 10000),
        _note("6a2f8304000000001102ea78", "高铁1小时从北京去崇礼避暑", 700),
        _note("6a2f8304000000001102ea79", "北京周边草原主观排名", 280),
        _note("6a2f8304000000001102ea7a", "北京各徒步团和好玩线路推荐", 12),
        _note("6a2f8304000000001102ea7b", "郑州开车2.5小时 山中玩水好地方", 6),
        _note("6a2f8304000000001102ea7c", "北京的天气让我感到陌生", 456),
        _note("6a2f8304000000001102ea7d", "东北冷涡下，北京天气Chill到Next level", 20),
        _note("6a2f8304000000001102ea7e", "6.9号 帝都的通透度无敌了", 47),
        _note("6a2f8304000000001102ea7f", "感觉中国网民都好萌", 8),
        _note("6a2f8304000000001102ea80", "春", 7),
        _note("6a2f8304000000001102ea81", "柴烧陶瓷杯釉色翻车记录", 1200),
        _note("6a2f8304000000001102ea82", "手捏陶瓷杯的釉色变化太迷人了", 980),
        _note("6a2f8304000000001102ea83", "陶瓷小杯开窑那一刻真的治愈", 760),
        _note("6a2f8304000000001102ea84", "今天做了一组蓝釉陶瓷杯", 640),
        _note("6a2f8304000000001102ea85", "釉色流动的陶瓷杯真的耐看", 880),
    ]
    profile = {"nickname": "topic regression", "user_id": "local"}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        notes_path = tmp_path / "notes.json"
        profile_path = tmp_path / "profile.json"
        output_path = tmp_path / "results.json"
        quality_path = tmp_path / "data_quality.json"
        notes_path.write_text(json.dumps(notes, ensure_ascii=False), encoding="utf-8")
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "analyze_all.py"),
                "--notes",
                str(notes_path),
                "--profile",
                str(profile_path),
                "--output",
                str(output_path),
                "--quality-output",
                str(quality_path),
            ],
            cwd=str(ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            result.check_returncode()

        results = json.loads(output_path.read_text(encoding="utf-8"))
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
        topics = results["topic_distribution"]

    phone = topics.get("手机摄影技巧与审美", {})
    travel = topics.get("北京周边与低成本出行", {})
    education = topics.get("教育学习与家庭场景", {})
    dynamic_ceramic = [
        payload for name, payload in topics.items()
        if name.startswith("围绕「") and "6a2f8304000000001102ea81" in payload.get("note_ids", [])
    ]

    assert phone.get("count", 0) >= 5, "phone imagery notes must form a stable topic"
    assert phone.get("confidence") == "high", "phone imagery topic should be high confidence"
    assert "6a2f8304000000001102ea77" in travel.get("note_ids", []), (
        "the travel title with 抄作业版 must not be misclassified as education"
    )
    assert "6a2f8304000000001102ea77" not in education.get("note_ids", []), (
        "weak keyword 作业 should not trigger education topic alone"
    )
    assert quality.get("topic_unclassified_pct", 100) <= 30, (
        "topic unclassified ratio regressed above acceptable threshold"
    )
    assert dynamic_ceramic, "unlisted niche terms should form a dynamic account-specific topic"
    assert dynamic_ceramic[0].get("count", 0) >= 5, "dynamic ceramic topic should keep its samples together"

    print("topic classification regression passed")


if __name__ == "__main__":
    main()
