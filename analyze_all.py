"""
xhs-blogger-analyzer — 量化分析引擎

用法:
  python analyze_all.py --notes ./data/all_notes.json --output ./data/results.json
                         [--contents ./data/contents.json]
"""

import json, re, statistics, argparse, os
from collections import Counter, defaultdict
from datetime import datetime, timezone

parser = argparse.ArgumentParser()
parser.add_argument('--notes', default='./data/all_notes.json')
parser.add_argument('--contents', default=None)
parser.add_argument('--profile', default=None)
parser.add_argument('--output', default='./data/results.json')
parser.add_argument('--quality-output', default=None)
args = parser.parse_args()

# Load data
with open(args.notes, 'r', encoding='utf-8') as f:
    all_notes = json.load(f)

contents = []
if args.contents:
    with open(args.contents, 'r', encoding='utf-8') as f:
        contents = json.load(f)

raw_note_count = len(all_notes)
deduped_notes = []
seen_note_ids = set()
duplicate_note_ids = []
for note in all_notes:
    note_id = note.get('note_id')
    if note_id:
        if note_id in seen_note_ids:
            duplicate_note_ids.append(note_id)
            continue
        seen_note_ids.add(note_id)
    deduped_notes.append(note)
all_notes = deduped_notes

deduped_contents = []
seen_content_ids = set()
duplicate_content_ids = []
for item in contents:
    note_id = item.get('note_id')
    if note_id:
        if note_id in seen_content_ids:
            duplicate_content_ids.append(note_id)
            continue
        seen_content_ids.add(note_id)
    deduped_contents.append(item)
contents = deduped_contents

def parse_count(v):
    """Convert string count to int, handling Chinese units like '2.5万'."""
    if isinstance(v, (int, float)):
        return int(v)
    if not isinstance(v, str):
        return 0
    v = v.strip()
    if not v:
        return 0
    if '万' in v:
        try:
            return int(float(v.replace('万', '')) * 10000)
        except ValueError:
            return 0
    if v.isdigit():
        return int(v)
    try:
        return int(float(v))
    except ValueError:
        return 0

def percentile(values, pct):
    """Return an interpolated percentile from an ascending numeric list."""
    if not values:
        return 0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    weight = pos - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 1)

def completion_ratio(count, total):
    return round(count / total, 2) if total else 0

def normalize_content_item(item):
    content = item.get('content') if isinstance(item.get('content'), dict) else {}
    tags = item.get('tags', content.get('tags', [])) or []
    if isinstance(tags, str):
        tags = [tags]
    text = item.get('content_text', content.get('text', '')) or ''
    return {
        'note_id': item.get('note_id', ''),
        'tags': tags,
        'text': text,
        'dateLine': item.get('dateLine', content.get('dateLine', '')) or '',
        'comment_count': item.get('comment_count'),
        'collected_count': item.get('collected_count'),
        'share_count': item.get('share_count'),
    }

def is_real_content_text(text):
    text = str(text or '').strip()
    if len(text) < 20:
        return False
    compact = re.sub(r'[\s,.，。!！?？:：#]+', '', text)
    if not compact:
        return False
    if re.fullmatch(r'\d+(\.\d+)?万?', compact):
        return False
    return True

for n in all_notes:
    for k in ('liked_count', 'collected_count', 'comment_count', 'share_count'):
        if k in n:
            n[k] = parse_count(n[k])

notes = [n for n in all_notes if n.get('liked_count', 0) > 0]
# Fallback to all notes if none have likes (avoid division by zero downstream)
if not notes:
    notes = all_notes[:]
results = {}

# Load profile info if available
profile_info = {}
if args.profile:
    try:
        with open(args.profile, 'r', encoding='utf-8') as f:
            profile_info = json.load(f)
    except:
        pass

# ---- Extract timestamps from note_ids ----
def extract_timestamp(note_id):
    try:
        ts = int(note_id[:8], 16)
        if 1500000000 < ts < 2000000000:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    except:
        pass
    return None

for n in all_notes:
    n['_dt'] = extract_timestamp(n.get('note_id', ''))

normalized_contents = [normalize_content_item(c) for c in contents]
content_map = {c['note_id']: c for c in normalized_contents if c.get('note_id')}
for n in all_notes:
    n['_content'] = content_map.get(n['note_id'])
    if n.get('_content'):
        for k in ('comment_count', 'collected_count', 'share_count'):
            value = n['_content'].get(k)
            if value not in (None, ''):
                n[k] = parse_count(value)

notes_with_dt = sorted([n for n in all_notes if n.get('_dt')], key=lambda x: x['_dt'])
print(f"Timestamps extracted: {len(notes_with_dt)}/{len(all_notes)}")

# ---- 1. Profile ----
likes_values = [n.get('liked_count', 0) for n in notes]
likes_sorted = sorted(likes_values, reverse=True)
_ln = len(likes_sorted) or 1  # guard against empty
_total_likes = sum(likes_sorted)
_avg_likes = round(_total_likes / _ln, 1)
results['profile'] = {
    'nickname': profile_info.get('nickname', ''),
    'user_id': profile_info.get('user_id', ''),
    'avatar_url': profile_info.get('avatar_url', ''),
    'bio': profile_info.get('bio', ''),
    'follower_count': profile_info.get('follower_count', 0),
    'total_interaction': profile_info.get('total_interaction', 0),
    'total_notes': len(all_notes),
    'total_with_likes': len(notes),
    'total_likes_sum': _total_likes,
    'avg_likes': _avg_likes,
    'median_likes': statistics.median(likes_values) if likes_values else 0,
    'max_likes': max(likes_sorted) if likes_sorted else 0,
    'min_likes': min(likes_sorted) if likes_sorted else 0,
    'std_likes': round(statistics.stdev(likes_sorted), 1) if len(likes_sorted) > 1 else 0,
    'p25': percentile(likes_values, 0.25),
    'p75': percentile(likes_values, 0.75),
    'video_count': len([n for n in notes if n.get('type') == 'video']),
    'image_count': len([n for n in notes if n.get('type') == 'normal']),
}

if len(notes_with_dt) > 1:
    span_days = (notes_with_dt[-1]['_dt'] - notes_with_dt[0]['_dt']).days
    results['profile']['content_span_months'] = max(1, span_days // 30)

# ---- Data Quality ----
total_notes = len(all_notes)
notes_with_title = len([n for n in all_notes if str(n.get('title', '')).strip()])
notes_with_like_field = len([n for n in all_notes if 'liked_count' in n])
notes_with_type = len([n for n in all_notes if str(n.get('type', '')).strip()])
contents_by_note = [n for n in all_notes if n.get('_content')]
contents_with_text = [
    n for n in contents_by_note
    if is_real_content_text(n.get('_content', {}).get('text', ''))
]
contents_with_any_text = [
    n for n in contents_by_note
    if is_real_content_text(n.get('_content', {}).get('text', ''))
]
contents_with_tags = [
    n for n in contents_by_note
    if n.get('_content', {}).get('tags')
]
notes_with_comment = len([n for n in all_notes if 'comment_count' in n])
notes_with_favorite = len([n for n in all_notes if 'collected_count' in n])
notes_with_share = len([n for n in all_notes if 'share_count' in n])

warnings = []
if total_notes < 30:
    warnings.append("样本数少于 30 条，只适合轻量观察。")
if duplicate_note_ids:
    warnings.append(f"采集结果去重：发现 {len(duplicate_note_ids)} 条重复笔记，已按 note_id 合并。")
if duplicate_content_ids:
    warnings.append(f"详情数据去重：发现 {len(duplicate_content_ids)} 条重复详情，已按 note_id 合并。")
if completion_ratio(len(contents_with_tags), total_notes) < 0.5:
    warnings.append("标签数据不足，SEO 模块应降级。")
if completion_ratio(len(contents_with_text), total_notes) < 0.5:
    warnings.append("正文数据不足，正文结构分析应降级。")
if completion_ratio(notes_with_comment, total_notes) < 0.5:
    warnings.append("评论数据不足，用户痛点和互动归因应降级。")
if completion_ratio(len(notes_with_dt), total_notes) < 0.8:
    warnings.append("时间字段不足，成长轨迹和发布节奏应谨慎解读。")

quality_score = 0
quality_score += completion_ratio(notes_with_title, total_notes) * 20
quality_score += completion_ratio(notes_with_like_field, total_notes) * 25
quality_score += completion_ratio(len(notes_with_dt), total_notes) * 20
quality_score += completion_ratio(len(contents_with_text), total_notes) * 15
quality_score += completion_ratio(len(contents_with_tags), total_notes) * 10
quality_score += completion_ratio(notes_with_comment, total_notes) * 5
quality_score += completion_ratio(notes_with_favorite, total_notes) * 5

overall_grade = "high" if quality_score >= 80 else "medium" if quality_score >= 50 else "low"
data_quality = {
    "sample_count": total_notes,
    "raw_sample_count": raw_note_count,
    "deduped_note_count": len(duplicate_note_ids),
    "deduped_content_count": len(duplicate_content_ids),
    "title_completeness": completion_ratio(notes_with_title, total_notes),
    "like_completeness": completion_ratio(notes_with_like_field, total_notes),
    "time_completeness": completion_ratio(len(notes_with_dt), total_notes),
    "type_completeness": completion_ratio(notes_with_type, total_notes),
    "content_item_completeness": completion_ratio(len(contents_by_note), total_notes),
    "content_text_completeness": completion_ratio(len(contents_with_text), total_notes),
    "content_text_any_completeness": completion_ratio(len(contents_with_any_text), total_notes),
    "tag_completeness": completion_ratio(len(contents_with_tags), total_notes),
    "comment_completeness": completion_ratio(notes_with_comment, total_notes),
    "favorite_completeness": completion_ratio(notes_with_favorite, total_notes),
    "share_completeness": completion_ratio(notes_with_share, total_notes),
    "overall_score": round(quality_score, 1),
    "overall_grade": overall_grade,
    "warnings": warnings,
}
results["data_quality"] = data_quality

# ---- 2. Topic Classification ----
# Topic detection is deliberately wider than the old fixed category rules.
# It extracts account-specific themes from titles/content snippets and keeps
# note_ids as evidence for the next insight layer.
topic_rules = [
    {
        "name": "北京周边与低成本出行",
        "keywords": [
            "北京", "周边", "草原", "崇礼", "坝上", "徒步", "线路", "高铁", "公交",
            "开车", "自驾", "当日往返", "避暑", "玩水", "旅行", "出行", "打卡",
            "公园", "路线", "目的地", "排名",
        ],
        "required_any": ["北京", "草原", "崇礼", "坝上", "徒步", "高铁", "公交", "自驾", "旅行", "出行"],
        "priority": 78,
    },
    {
        "name": "北京天气与城市观察",
        "keywords": [
            "北京", "天气", "天空", "东北冷涡", "通透度", "雨后", "晴好", "干燥",
            "风", "花信风", "海淀", "帝都", "午后", "街道", "城市", "日落",
            "云", "晴", "阴湿", "Chill",
        ],
        "required_any": ["天气", "天空", "东北冷涡", "通透度", "雨后", "晴", "风", "海淀", "帝都"],
        "priority": 76,
    },
    {
        "name": "手机摄影技巧与审美",
        "keywords": [
            "手机", "摄影", "影像", "画质", "画面", "光影", "影调", "直出", "解析力",
            "ccd", "镜头", "拍照", "拍", "质感", "诺基亚", "老手机", "十年前",
            "13年前", "10年前",
        ],
        "required_any": ["手机", "摄影", "影像", "画质", "光影", "影调", "直出", "解析力", "ccd", "镜头", "拍照"],
        "priority": 77,
    },
    {
        "name": "校园与生活观察",
        "keywords": [
            "校园", "北师大", "学生", "老师", "同学", "宿舍", "博士", "毕业",
            "大学", "课堂", "学习", "生活", "夏日", "春", "记录",
        ],
        "required_any": ["校园", "北师大", "学生", "老师", "同学", "宿舍", "博士", "毕业", "大学", "课堂"],
        "priority": 58,
    },
    {
        "name": "AI行业观点与趋势",
        "keywords": [
            "AI", "人工智能", "模型", "大模型", "行业", "趋势", "未来", "诺奖",
            "Hinton", "哈萨比斯", "Hassabis", "共识", "分歧", "创业", "具身智能",
            "Agent", "开发者", "闭源", "开源",
        ],
        "priority": 80,
    },
    {
        "name": "AI工具与模型评测",
        "keywords": [
            "ChatGPT", "OpenAI", "Claude", "DeepSeek", "Gemini", "Qwen", "通义",
            "豆包", "GLM", "Kimi", "混元", "Godot", "实测", "测评", "评测",
            "发布", "更新", "模型", "工具", "开源", "闭源",
        ],
        "priority": 75,
    },
    {
        "name": "AI应用实践与案例",
        "keywords": [
            "应用", "案例", "场景", "工作流", "自动化", "PPT", "写作", "编程",
            "开发", "生成", "提示词", "实操", "赚钱", "创作", "视频", "房间存档",
            "做出来", "工具",
        ],
        "priority": 70,
    },
    {
        "name": "产品与创业观察",
        "keywords": [
            "产品", "创业", "公司", "商业", "融资", "用户", "需求", "PMF",
            "发布会", "投资", "团队", "打工", "实习生", "成本", "Token", "token",
        ],
        "priority": 60,
    },
    {
        "name": "教育学习与家庭场景",
        "keywords": [
            "孩子", "家长", "作业", "学习", "教育", "老师", "学生", "课堂",
            "辅导", "大学", "文科生", "面试", "求职", "教学",
        ],
        "required_any": ["孩子", "家长", "学习", "教育", "老师", "学生", "课堂", "辅导", "大学", "文科生", "面试", "求职", "教学"],
        "priority": 55,
    },
]

fallback_rules = [
    ('教程/方法型内容', ['教程','Prompt','提示词','技巧','怎么','如何','保姆','步骤','方法','一文','手把手','指南','三步','解决办法']),
    ('观点/社会观察', ['思考','观点','趋势','真相','发现','告别','反思','感悟','祛魅','神话','好奇']),
    ('活动/商业信号', ['招聘','招人','有奖','征集','活动','线下','大会','闭门','合作','邀请','倒计时']),
]

def note_text(n):
    content = n.get('_content') or {}
    return f"{n.get('title', '')} {content.get('text', '')}".strip()

def rule_match_score(text, rule):
    lowered = text.lower()
    if rule.get("required_any") and not any(k.lower() in lowered for k in rule["required_any"]):
        return 0, []
    matched = [k for k in rule["keywords"] if k.lower() in lowered]
    if not matched:
        return 0, []
    # Longer, more specific keywords should outweigh generic words like "手机".
    score = len(matched) * 10 + sum(min(len(k), 8) for k in matched) + rule.get("priority", 0) / 100
    return score, matched

GENERIC_TOPIC_TERMS = {
    "一个", "这个", "那个", "什么", "怎么", "如何", "可以", "感觉", "真的", "今天",
    "昨天", "明天", "现在", "一下", "一些", "一件", "不会", "没有", "不是", "就是",
    "已经", "还是", "起来", "出来", "分享", "记录", "生活", "日常", "普通", "好像",
    "为什么", "这么", "那么", "自己", "别人", "今年", "去年", "时候", "问题",
    "方法", "解决", "推荐", "建议", "好玩", "地方", "东西", "内容", "小红书",
}


def _has_cjk(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text or ''))


def _is_generic_term(term):
    if not term or term in GENERIC_TOPIC_TERMS:
        return True
    if len(term) < 2:
        return True
    if re.fullmatch(r'\d+', term):
        return True
    if len(term) == 2 and term.endswith(("了", "的", "吗", "呢", "啊")):
        return True
    if len(term) == 2 and any(ch in term for ch in ("一", "个", "是", "在", "和", "与", "把", "被", "很")):
        return True
    if term.startswith(("这个", "那个", "一种", "一个")):
        return True
    if term.endswith(("一个", "一种", "一下", "起来")):
        return True
    return False


def _extract_topic_terms(text):
    text = str(text or '').lower()
    terms = set()
    for raw in re.findall(r'[\u4e00-\u9fff]+|[A-Za-z0-9]+', text):
        if not raw:
            continue
        if _has_cjk(raw):
            run = raw
            if 2 <= len(run) <= 8 and not _is_generic_term(run):
                terms.add(run)
            max_n = min(6, len(run))
            for n in range(2, max_n + 1):
                for i in range(0, len(run) - n + 1):
                    term = run[i:i+n]
                    if not _is_generic_term(term):
                        terms.add(term)
        elif len(raw) >= 2 and raw not in GENERIC_TOPIC_TERMS:
            terms.add(raw)
    return terms


def _term_score(term, docs, total_count, overall_avg):
    doc_count = len(docs)
    if doc_count <= 0:
        return 0
    likes = [d.get('liked_count', 0) for d in docs]
    avg_like = sum(likes) / max(doc_count, 1)
    score = doc_count * 9 + min(avg_like / max(overall_avg, 1) * 8, 24) + min(len(term), 6) * 1.5
    if doc_count > total_count * 0.45 and len(term) <= 2:
        score *= 0.35
    if doc_count == 1:
        score *= 0.35
    return score


def _compact_keywords(terms, limit=8):
    compact = []
    for term in terms:
        if _is_generic_term(term):
            continue
        if any(term != kept and term in kept for kept in compact):
            continue
        compact.append(term)
        if len(compact) >= limit:
            break
    return compact


def _rule_name_for_keywords(keywords, notes):
    text = " ".join(keywords + [note_text(n) for n in notes[:8]]).lower()
    best = None
    for rule in topic_rules:
        matched = [k for k in rule["keywords"] if k.lower() in text]
        if not matched:
            continue
        if rule.get("required_any") and not any(k.lower() in text for k in rule["required_any"]):
            continue
        score = len(matched) * 10 + rule.get("priority", 0) / 100
        current = (score, rule["name"], matched)
        if best is None or current[0] > best[0]:
            best = current
    if best and best[0] >= 20:
        return best[1], best[2]
    return "", []


def _dynamic_topic_name(keywords, notes):
    rule_name, matched = _rule_name_for_keywords(keywords, notes)
    if rule_name:
        return rule_name, matched
    label_terms = _compact_keywords(keywords, limit=3)
    if not label_terms:
        return "未归类观察", []
    return "围绕「%s」的内容线" % "、".join(label_terms), label_terms


def _fallback_rule_classify(n):
    text = note_text(n)
    best = None
    for rule in topic_rules:
        score, matched = rule_match_score(text, rule)
        if score <= 0:
            continue
        current = (score, rule.get("priority", 0), rule["name"], matched)
        if best is None or current[:2] > best[:2]:
            best = current
    if best:
        score, priority, name, matched = best
        confidence = "high" if len(matched) >= 3 else "medium" if len(matched) >= 2 or priority >= 70 else "low"
        return name, matched, confidence

    for cat, keywords in fallback_rules:
        matched = [k for k in keywords if k.lower() in text.lower()]
        if matched:
            return cat, matched, "medium"

    if len(n.get('title', '').strip()) <= 4:
        return "日常随手记录", [], "low"
    return "未归类观察", [], "low"


def _discover_dynamic_topics(all_notes):
    total = len(all_notes)
    min_cluster_size = 3 if total >= 30 else 2
    term_docs = defaultdict(list)
    for idx, note in enumerate(all_notes):
        note['_topic_index'] = idx
        terms = _extract_topic_terms(note_text(note))
        note['_topic_terms'] = terms
        for term in terms:
            term_docs[term].append(note)

    candidates = []
    for term, docs in term_docs.items():
        if len(docs) < min_cluster_size:
            continue
        if _is_generic_term(term):
            continue
        score = _term_score(term, docs, total, overall_avg)
        if score <= 0:
            continue
        candidates.append((score, term))
    candidates.sort(reverse=True)

    unassigned = {n['_topic_index'] for n in all_notes}
    clusters = []

    for _, seed in candidates:
        seed_docs = [n for n in term_docs[seed] if n['_topic_index'] in unassigned]
        if len(seed_docs) < min_cluster_size:
            continue
        if len(seed_docs) > total * 0.55 and len(seed) <= 2:
            continue

        local_counts = Counter()
        for note in seed_docs:
            local_counts.update(note.get('_topic_terms', set()))
        ranked_terms = []
        for term, local_count in local_counts.most_common(30):
            global_count = len(term_docs.get(term, []))
            if _is_generic_term(term):
                continue
            specificity = local_count / max(global_count, 1)
            score = local_count * 5 + specificity * 8 + min(len(term), 6)
            if term == seed:
                score += 8
            ranked_terms.append((score, term))
        ranked_terms.sort(reverse=True)
        signature = _compact_keywords([term for _, term in ranked_terms], limit=8)
        if seed not in signature:
            signature = [seed] + signature[:7]
        signature = _compact_keywords(signature, limit=8)
        if not signature:
            continue

        weighted_terms = {term: max(1, 7 - i) for i, term in enumerate(signature)}
        cluster_notes = []
        for note in all_notes:
            if note['_topic_index'] not in unassigned:
                continue
            note_terms = note.get('_topic_terms', set())
            overlap = [term for term in signature if term in note_terms]
            overlap_score = sum(weighted_terms[t] for t in overlap)
            if seed in note_terms and len(overlap) >= 1:
                cluster_notes.append(note)
            elif len(overlap) >= 2 and overlap_score >= 6:
                cluster_notes.append(note)

        if len(cluster_notes) < min_cluster_size:
            continue

        cluster_counter = Counter()
        for note in cluster_notes:
            cluster_counter.update(note.get('_topic_terms', set()))
        cluster_keywords = _compact_keywords([term for term, _ in cluster_counter.most_common(12)], limit=8)
        name, matched = _dynamic_topic_name(cluster_keywords, cluster_notes)
        if name in ("未归类观察", "日常随手记录"):
            continue
        if name.startswith("围绕「") and len(cluster_notes) < 5:
            continue

        clusters.append(
            {
                "name": name,
                "notes": cluster_notes,
                "keywords": cluster_keywords,
                "matched": matched or cluster_keywords,
                "confidence": "high" if len(cluster_notes) >= 5 and len(cluster_keywords) >= 3 else "medium",
                "source": "dynamic",
            }
        )
        for note in cluster_notes:
            unassigned.discard(note['_topic_index'])
        if len(clusters) >= 8:
            break

    remaining = [n for n in all_notes if n['_topic_index'] in unassigned]
    fallback_groups = {}
    for note in remaining:
        name, matched, confidence = _fallback_rule_classify(note)
        if name not in fallback_groups:
            fallback_groups[name] = {"notes": [], "keywords": Counter(), "confidence_scores": []}
        fallback_groups[name]["notes"].append(note)
        fallback_groups[name]["keywords"].update(matched)
        fallback_groups[name]["confidence_scores"].append(confidence_score_map.get(confidence, 1))

    for name, payload in fallback_groups.items():
        keyword_list = [kw for kw, _ in payload["keywords"].most_common(8)]
        avg_conf = sum(payload["confidence_scores"]) / max(len(payload["confidence_scores"]), 1)
        clusters.append(
            {
                "name": name,
                "notes": payload["notes"],
                "keywords": keyword_list,
                "matched": keyword_list,
                "confidence": "high" if avg_conf >= 2.5 and len(payload["notes"]) >= 3 else "medium" if avg_conf >= 1.8 else "low",
                "source": "fallback_rule",
            }
        )
    return clusters

cat_stats = defaultdict(lambda: {
    'count': 0,
    'likes': [],
    'notes': [],
    'note_ids': [],
    'keywords': Counter(),
    'confidence_scores': [],
    'source': '',
})
confidence_score_map = {"high": 3, "medium": 2, "low": 1}
overall_avg = results['profile']['avg_likes']
for cluster in _discover_dynamic_topics(all_notes):
    cat = cluster["name"]
    matched_keywords = cluster.get("matched", [])
    confidence = cluster.get("confidence", "low")
    for n in cluster["notes"]:
        cat_stats[cat]['count'] += 1
        cat_stats[cat]['likes'].append(n.get('liked_count', 0))
        cat_stats[cat]['notes'].append(n)
        cat_stats[cat]['note_ids'].append(n.get('note_id', ''))
    cat_stats[cat]['keywords'].update(matched_keywords)
    cat_stats[cat]['confidence_scores'].append(confidence_score_map.get(confidence, 1))
    source = cluster.get("source", "")
    if source == "dynamic" or not cat_stats[cat].get('source'):
        cat_stats[cat]['source'] = source

for n in all_notes:
    if any(n in s['notes'] for s in cat_stats.values()):
        continue
    cat, matched_keywords, confidence = _fallback_rule_classify(n)
    cat_stats[cat]['count'] += 1
    cat_stats[cat]['likes'].append(n.get('liked_count', 0))
    cat_stats[cat]['notes'].append(n)
    cat_stats[cat]['note_ids'].append(n.get('note_id', ''))
    cat_stats[cat]['keywords'].update(matched_keywords)
    cat_stats[cat]['confidence_scores'].append(confidence_score_map.get(confidence, 1))
    if not cat_stats[cat].get('source'):
        cat_stats[cat]['source'] = "fallback_rule"

results['topic_distribution'] = {}
results['topic_clusters'] = []
for cat in sorted(cat_stats.keys(), key=lambda c: sum(cat_stats[c]['likes'])/max(len(cat_stats[c]['likes']),1), reverse=True):
    s = cat_stats[cat]
    likes = s['likes']
    burst = len([l for l in likes if l > 1000])
    above_avg = len([l for l in likes if l > overall_avg])
    top_notes = sorted(s['notes'], key=lambda x: x.get('liked_count', 0), reverse=True)[:5]
    avg_conf = sum(s['confidence_scores']) / max(len(s['confidence_scores']), 1)
    core_keyword_count = len([kw for kw, _ in s['keywords'].most_common(8)])
    if avg_conf >= 2.5 and s['count'] >= 3:
        confidence = "high"
    elif s['count'] >= 5 and core_keyword_count >= 3:
        confidence = "high"
    elif avg_conf >= 1.8 or (s['count'] >= 3 and core_keyword_count >= 2):
        confidence = "medium"
    else:
        confidence = "low"
    topic_payload = {
        'count': s['count'],
        'pct': round(s['count']/len(all_notes)*100, 1),
        'avg_likes': round(sum(likes)/len(likes), 1),
        'median_likes': statistics.median(likes) if likes else 0,
        'max_likes': max(likes) if likes else 0,
        'burst_count': burst,
        'burst_rate': round(burst/len(likes)*100, 1) if likes else 0,
        'above_avg_rate': round(above_avg/len(likes)*100, 1) if likes else 0,
        'note_ids': list(dict.fromkeys([nid for nid in s['note_ids'] if nid])),
        'evidence_note_ids': [n.get('note_id', '') for n in top_notes if n.get('note_id')],
        'evidence_sort_rule': '按该主题内点赞数从高到低选取代表样本',
        'matched_keywords': [kw for kw, _ in s['keywords'].most_common(8)],
        'topic_source': s.get('source') or 'unknown',
        'representative_titles': [n.get('title', '') for n in top_notes],
        'confidence': confidence,
    }
    results['topic_distribution'][cat] = topic_payload
    results['topic_clusters'].append({"name": cat, **topic_payload})

low_info_count = sum(
    s['count'] for name, s in cat_stats.items()
    if name in ("未归类观察", "日常随手记录")
)
unclassified_pct = round(low_info_count / len(all_notes) * 100, 1) if all_notes else 0
data_quality["topic_unclassified_pct"] = unclassified_pct
data_quality["topic_cluster_count"] = len(cat_stats)
if unclassified_pct > 50:
    data_quality["warnings"].append("主题未归类比例超过 50%，内容主题结论应降级。")

# ---- 3. Content Type ----
type_stats = defaultdict(lambda: {'count': 0, 'likes': []})
for n in all_notes:
    t = n.get('type', 'normal')
    type_stats[t]['count'] += 1
    type_stats[t]['likes'].append(n.get('liked_count', 0))

results['content_type'] = {}
for t, s in type_stats.items():
    results['content_type'][t] = {
        'count': s['count'],
        'pct': round(s['count']/len(all_notes)*100, 1),
        'avg_likes': round(sum(s['likes'])/len(s['likes']), 1),
    }
img_avg = results['content_type'].get('normal', {}).get('avg_likes', 1) or 1
for t in results['content_type']:
    results['content_type'][t]['vs_image_pct'] = round(results['content_type'][t]['avg_likes'] / img_avg * 100, 1)

# ---- 4. Title Analysis ----
title_analysis = {'avg_length': round(statistics.mean([len(n.get('title', '')) for n in all_notes]), 1)}
fns = {
    '感叹号': lambda t: '！' in t or '!' in t,
    '问号': lambda t: '？' in t or '?' in t,
    '括号【】「」': lambda t: '【' in t or '】' in t or '「' in t or '」' in t,
    '数字': lambda t: bool(re.search(r'\d', t)),
    'Emoji': lambda t: bool(re.search(r'[\U0001F300-\U0001F9FF\U00002000-\U00002BFF☀-➿]', t)),
    '省略号': lambda t: '...' in t or '……' in t,
    '冒号/破折号': lambda t: '：' in t or ':' in t or '—' in t,
    '引号': lambda t: '“' in t or '”' in t or '「' in t or '」' in t,
}

for feat_name, check_fn in fns.items():
    matched = [n for n in all_notes if check_fn(n.get('title', ''))]
    avg = sum(n.get('liked_count', 0) for n in matched)/len(matched) if matched else 0
    title_analysis[feat_name] = {
        'count': len(matched),
        'pct': round(len(matched)/len(all_notes)*100, 1),
        'avg_likes': round(avg, 1),
        'vs_baseline_pct': round((avg / overall_avg - 1) * 100, 1) if overall_avg else 0,
    }
results['title_analysis'] = title_analysis

# ---- 5. Title Formulas ----
formulas = {
    '情绪感叹开头': lambda t: any(t.startswith(w) for w in ['我靠','麻了','绝了','疯了吧','破防','爽','天哪','离谱','无语','我人傻了']),
    '「标签」+价值承诺': lambda t: bool(re.match(r'^[【「].+[】」]', t)),
    '时间锚+领域': lambda t: bool(re.search(r'(三年|几个月|一周|一天|\d+年|\d+个月)', t)),
    '断言/判断句式': lambda t: bool(re.search(r'(杀了|杀死|正在|才是|其实是|不是|才是|不过是)', t)),
    '疑问/反问结尾': lambda t: t.endswith('？') or t.endswith('??') or t.endswith('？？'),
    '省略号悬念结尾': lambda t: t.endswith('...') or t.endswith('..."') or t.endswith('……'),
    '数字承诺结构': lambda t: bool(re.search(r'(一文|三步|一招|\d+个|\d+种|X个)', t)),
    '否定/对比开头': lambda t: t.startswith('别') or t.startswith('不要') or t.startswith('别再'),
}

results['title_formulas'] = {}
for fname, check_fn in formulas.items():
    matched = [n for n in all_notes if check_fn(n.get('title', ''))]
    if len(matched) < 3:
        continue
    avg = sum(n.get('liked_count', 0) for n in matched)/len(matched)
    burst = len([n for n in matched if n.get('liked_count', 0) > 1000])
    results['title_formulas'][fname] = {
        'count': len(matched),
        'pct': round(len(matched)/len(all_notes)*100, 1),
        'avg_likes': round(avg, 1),
        'vs_overall_pct': round((avg / overall_avg - 1) * 100, 1) if overall_avg else 0,
        'burst_count': burst,
        'burst_rate': round(burst/len(matched)*100, 1),
        'sample': [n.get('title', '') for n in matched[:3]],
        'top': max(matched, key=lambda x: x.get('liked_count', 0)).get('title', ''),
    }

# ---- 6. Engagement ----
sorted_likes = sorted([n.get('liked_count', 0) for n in all_notes], reverse=True)
total_likes = sum(sorted_likes)
cumsum = 0
pareto_n = 0
for i, l in enumerate(sorted_likes):
    cumsum += l
    if cumsum >= total_likes * 0.8:
        pareto_n = i + 1
        break

results['engagement'] = {
    'pareto_80pct_n_notes': pareto_n,
    'pareto_80pct_pct': round(pareto_n/len(sorted_likes)*100, 1) if len(sorted_likes) > 1 else 0,
    'gini_coef': round(1 - sum(sorted_likes)/(len(sorted_likes)*max(sorted_likes[0], 1))*0.5, 3) if sorted_likes else 0,
    'top10pct_share': round(sum(sorted_likes[:max(1, len(sorted_likes)//10)])/max(total_likes, 1)*100, 1),
    'top20pct_share': round(sum(sorted_likes[:max(1, len(sorted_likes)//5)])/max(total_likes, 1)*100, 1),
    'top5_share': round(sum(sorted_likes[:5])/max(total_likes, 1)*100, 1),
    'bottom50pct_share': round(sum(sorted_likes[-(len(sorted_likes)//2):])/max(total_likes, 1)*100, 1),
}

if contents:
    sc = sorted(all_notes, key=lambda x: x.get('liked_count', 0), reverse=True)
    top20 = sc[:20]
    bot20 = sc[-20:]

    def extract_cm(notes_list):
        if not notes_list:
            return {}
        tcounts = []
        wcounts = []
        dates = 0
        for n in notes_list:
            ct = n.get('_content') or {}
            tcounts.append(len(ct.get('tags', [])))
            txt = ct.get('text', '')
            if '猜你想搜' in txt:
                txt = txt.split('猜你想搜')[0]
            wcounts.append(len(txt))
            if ct.get('dateLine', '').strip():
                dates += 1
        return {
            'avg_tag_count': round(statistics.mean(tcounts), 1),
            'avg_text_length': round(statistics.mean(wcounts), 1),
            'has_date_ratio': round(dates/len(notes_list)*100, 1),
        }

    results['top_vs_bottom'] = {
        'top20': extract_cm(top20),
        'bot20': extract_cm(bot20),
        'top20_avg_likes': round(sum(n.get('liked_count', 0) for n in top20)/len(top20), 1),
        'bot20_avg_likes': round(sum(n.get('liked_count', 0) for n in bot20)/len(bot20), 1),
        'ratio': round(sum(n.get('liked_count', 0) for n in top20)/max(sum(n.get('liked_count', 0) for n in bot20),1), 1),
    }

# ---- 7. Growth ----
nbym = defaultdict(lambda: {'count': 0, 'likes': [], 'titles': []})
for n in all_notes:
    if n.get('_dt'):
        ym = n['_dt'].strftime('%Y-%m')
        nbym[ym]['count'] += 1
        nbym[ym]['likes'].append(n.get('liked_count', 0))
        nbym[ym]['titles'].append(n.get('title', ''))

ms = sorted(nbym.keys())
if len(ms) > 1:
    ma = {}
    for i, m in enumerate(ms):
        chunk = []
        for j in range(max(0,i-2), min(len(ms),i+3)):
            chunk.extend(nbym[ms[j]]['likes'])
        ma[m] = round(sum(chunk)/len(chunk)) if chunk else 0

    bursts = []
    for n in all_notes:
        if n.get('_dt') and n.get('liked_count', 0) > overall_avg * 2:
            bursts.append({
                'date': n['_dt'].strftime('%Y-%m-%d'),
                'title': n.get('title', ''),
                'likes': n.get('liked_count', 0),
                'ratio_to_avg': round(n.get('liked_count', 0)/overall_avg, 1) if overall_avg else 0,
            })
    bursts.sort(key=lambda x: x['date'])

    results['growth'] = {
        'months_active': len(ms),
        'first_month': ms[0],
        'last_month': ms[-1],
        'monthly_avg_likes': ma,
        'top_bursts': bursts[:30],
        'burst_count': len(bursts),
    }
else:
    results['growth'] = {'months_active': 0}

# ---- 8. Tags (requires contents) ----
if contents:
    all_tags = []
    for n in normalized_contents:
        for tag_str in n.get('tags', []):
            for t in re.split(r'[\s# ]+', tag_str):
                t = t.strip().lstrip('#')
                if t and len(t) > 1 and not t.startswith('@'):
                    all_tags.append(t)

    tc = Counter(all_tags)
    results['tags'] = {
        'total_unique': len(tc),
        'top30': [{'tag': t, 'count': c} for t, c in tc.most_common(30)],
        'total_mentions': len(all_tags),
    }

# ---- 9. Commercial ----
commercial_signals = ['招聘', '招人', '有奖', '征集', '报名', '合作', '推广', '赞助', '广告', '好物']
commercial_notes = []
for n in all_notes:
    score = 0
    for s in commercial_signals:
        if s in n.get('title', ''):
            score += 2
    ct = n.get('_content', {})
    if ct:
        txt = ct.get('text', '')
        ats = re.findall(r'@\w+', txt)
        if ats:
            score += 0.5
    if score >= 2:
        commercial_notes.append(n)

com_ids = {n.get('note_id') for n in commercial_notes}
organic_notes = [n for n in all_notes if n.get('note_id') not in com_ids]

results['commercial'] = {
    'detected_count': len(commercial_notes),
    'detected_pct': round(len(commercial_notes)/len(all_notes)*100, 1),
    'avg_likes_commercial': round(sum(n.get('liked_count', 0) for n in commercial_notes)/len(commercial_notes), 1) if commercial_notes else 0,
    'avg_likes_organic': round(sum(n.get('liked_count', 0) for n in organic_notes)/len(organic_notes), 1) if organic_notes else 0,
}

# ---- Save ----
os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
with open(args.output, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

quality_output = args.quality_output or os.path.join(
    os.path.dirname(args.output) or '.',
    'data_quality.json',
)
with open(quality_output, 'w', encoding='utf-8') as f:
    json.dump(data_quality, f, ensure_ascii=False, indent=2)

print(f"\nResults saved to: {args.output}")
print(f"Data quality saved to: {quality_output}")
print(f"Profile: avg_likes={results['profile']['avg_likes']}, median={results['profile']['median_likes']}, max={results['profile']['max_likes']}")
print(f"Topics: {len(results.get('topic_distribution', {}))} categories")
print(f"Growth: {results['growth'].get('months_active', 0)} months, {results['growth'].get('burst_count', 0)} burst notes")
print(f"Commercial: {results['commercial']['detected_count']} detected ({results['commercial']['detected_pct']}%)")
