import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HistoryTopicRegressionTests(unittest.TestCase):
    def test_history_account_is_not_forced_into_ai_campus_or_weather(self):
        titles = [
            ("为什么要延安整风", 900),
            ("三湾改编如何重塑一支队伍", 760),
            ("毛泽东为什么写实践论", 680),
            ("遵义会议之后发生了什么", 620),
            ("长征中的组织选择", 580),
            ("陈云的思维方式课", 530),
            ("星星之火为什么能够燎原", 490),
            ("革命根据地财经史", 440),
            ("林彪与四野战术体系", 1300),
            ("塔山阻击战背后的系统力", 1150),
            ("辽沈战役的战略选择", 1080),
            ("罗荣桓如何建设一支军队", 980),
            ("淮海战役预备命令", 920),
            ("抗美援朝战术体系", 870),
            ("一支军队为什么能打赢", 820),
            ("四平保卫战复盘", 760),
            ("王阳明龙场悟道", 330),
            ("王安石变法的启示", 260),
            ("钱学森与第一原理", 240),
            ("苏联市场与金融体制", 180),
            ("中国芯片产业四十年", 160),
            ("正态分布还是泊松分布", 120),
            ("大学老师如何看未来", 60),
            ("春风吹过北京城", 50),
            ("一个模型解释普通人的选择", 40),
            ("记录今天的一点想法", 30),
            ("那一年他写了一首诗", 20),
            ("慢的尊严", 18),
            ("合照缺席者", 15),
            ("同途", 12),
        ]
        notes = []
        contents = []
        for index, (title, likes) in enumerate(titles):
            note_id = f"65{index:022x}"[-24:]
            notes.append({"note_id": note_id, "title": title, "liked_count": likes, "type": "normal"})
            opening = "1935年，这个历史节点改变了组织此后的道路。" if index < 8 else "这篇内容从公开史料和人物选择开始展开分析。"
            contents.append({"note_id": note_id, "content_text": opening + "本文只讨论可以由公开材料支持的事实与启示。"})

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes_path = root / "notes.json"
            contents_path = root / "contents.json"
            profile_path = root / "profile.json"
            output_path = root / "results.json"
            quality_path = root / "quality.json"
            notes_path.write_text(json.dumps(notes, ensure_ascii=False), encoding="utf-8")
            contents_path.write_text(json.dumps(contents, ensure_ascii=False), encoding="utf-8")
            profile_path.write_text(json.dumps({"nickname": "历史观察账号"}, ensure_ascii=False), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "analyze_all.py"),
                    "--notes", str(notes_path),
                    "--contents", str(contents_path),
                    "--profile", str(profile_path),
                    "--output", str(output_path),
                    "--quality-output", str(quality_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            results = json.loads(output_path.read_text(encoding="utf-8"))
            quality = json.loads(quality_path.read_text(encoding="utf-8"))

        topics = results["topic_distribution"]
        self.assertGreaterEqual(topics.get("党史、革命史与政治人物", {}).get("count", 0), 7)
        self.assertGreaterEqual(topics.get("军事史、战役与战略", {}).get("count", 0), 7)
        self.assertLessEqual(topics.get("AI行业观点与趋势", {}).get("count", 0), 1)
        self.assertLessEqual(topics.get("校园与生活观察", {}).get("count", 0), 1)
        self.assertLessEqual(topics.get("北京天气与城市观察", {}).get("count", 0), 1)
        self.assertLessEqual(quality.get("topic_unclassified_pct", 100), 35)

        hooks = results["hook_analysis"]["patterns"]
        self.assertGreaterEqual(hooks["时间/年代切入"]["count"], 7)
        self.assertEqual(hooks["数字/清单切入"]["count"], 0)

        action = results["eight_dimensions"]["action_plan"]
        self.assertEqual(action["status"], "ready")
        self.assertTrue(any("军事史、战役与战略" in finding for finding in action["findings"]))


if __name__ == "__main__":
    unittest.main()
