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
parser.add_argument('--comments', default=None)
parser.add_argument('--search', default=None)
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

comments = []
if args.comments and os.path.exists(args.comments):
    with open(args.comments, 'r', encoding='utf-8') as f:
        comments = json.load(f)

search_landscape = {}
if args.search and os.path.exists(args.search):
    with open(args.search, 'r', encoding='utf-8') as f:
        search_landscape = json.load(f)

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

def dedupe_image_urls(urls):
    """Collapse preview/default variants that point to the same XHS image asset."""
    output = []
    positions = {}
    for value in urls or []:
        url = str(value or '').strip()
        if not url:
            continue
        match = re.search(r'/spectrum/([^!/?]+)', url)
        identity = match.group(1) if match else re.sub(r'!.*$', '', url)
        if identity in positions:
            current = output[positions[identity]]
            if '!nd_dft_' in url and '!nd_dft_' not in current:
                output[positions[identity]] = url
            continue
        positions[identity] = len(output)
        output.append(url)
    return output

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
        'image_urls': dedupe_image_urls(item.get('image_urls', content.get('image_urls', [])) or []),
        'cover_url': item.get('cover_url', content.get('cover_url', '')) or '',
        'video_url': item.get('video_url', content.get('video_url', '')) or '',
        'video_cover_url': item.get('video_cover_url', content.get('video_cover_url', '')) or '',
        'publish_time': item.get('publish_time', content.get('publish_time', 0)) or 0,
        'ip_location': item.get('ip_location', content.get('ip_location', '')) or '',
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
def extract_timestamp(note_id, explicit_time=None):
    if explicit_time not in (None, ''):
        try:
            value = float(explicit_time)
            if value > 20000000000:
                value /= 1000
            if 1500000000 < value < 2000000000:
                return datetime.fromtimestamp(value, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass
    try:
        ts = int(note_id[:8], 16)
        if 1500000000 < ts < 2000000000:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    except:
        pass
    return None

for n in all_notes:
    n['_dt'] = extract_timestamp(n.get('note_id', ''), n.get('time'))

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
    'following_count': profile_info.get('following_count', 0),
    'red_id': profile_info.get('red_id', ''),
    'gender': profile_info.get('gender'),
    'ip_location': profile_info.get('ip_location', ''),
    'profile_tags': profile_info.get('profile_tags', []),
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
notes_with_comment_count = len([n for n in all_notes if 'comment_count' in n])
notes_with_favorite = len([n for n in all_notes if 'collected_count' in n])
notes_with_share = len([n for n in all_notes if 'share_count' in n])
comment_texts = [str(item.get('content') or '').strip() for item in comments if str(item.get('content') or '').strip()]
comment_note_count = len({item.get('note_id') for item in comments if item.get('note_id')})
contents_with_media = [n for n in contents_by_note if n.get('_content', {}).get('image_urls') or n.get('_content', {}).get('video_url')]
detail_sample_count = len(contents_by_note)
detail_required_count = min(20, max(8, int(total_notes * 0.2 + 0.999))) if total_notes else 0
content_sample_completeness = completion_ratio(len(contents_with_text), detail_sample_count)
tag_sample_completeness = completion_ratio(len(contents_with_tags), detail_sample_count)
content_analysis_ready = (
    len(contents_with_text) >= detail_required_count
    and content_sample_completeness >= 0.7
)
tag_analysis_ready = (
    len(contents_with_tags) >= detail_required_count
    and tag_sample_completeness >= 0.7
)
comment_analysis_ready = len(comment_texts) >= 30 and comment_note_count >= 5
media_analysis_ready = len(contents_with_media) >= min(12, max(5, detail_required_count // 2))
search_rows_ready = [
    item for item in (search_landscape or {}).get('keywords', [])
    if item.get('suggestions') or item.get('result_count', 0) > 0
]
search_analysis_ready = bool(search_rows_ready)

warnings = []
if total_notes < 30:
    warnings.append("样本数少于 30 条，只适合轻量观察。")
if duplicate_note_ids:
    warnings.append(f"采集结果去重：发现 {len(duplicate_note_ids)} 条重复笔记，已按 note_id 合并。")
if duplicate_content_ids:
    warnings.append(f"详情数据去重：发现 {len(duplicate_content_ids)} 条重复详情，已按 note_id 合并。")
if not tag_analysis_ready:
    warnings.append(
        f"标签详情样本不足（有效 {len(contents_with_tags)} 篇，建议至少 {detail_required_count} 篇），标签与搜索模块应降级。"
    )
if not content_analysis_ready:
    warnings.append(
        f"正文详情样本不足（有效 {len(contents_with_text)} 篇，建议至少 {detail_required_count} 篇），正文结构分析应降级。"
    )
if not comment_analysis_ready:
    warnings.append(f"评论正文不足（当前 {len(comment_texts)} 条，覆盖 {comment_note_count} 篇），用户需求分析应降级。")
if not media_analysis_ready:
    warnings.append("图片或视频详情样本不足，视觉与多模态分析应降级。")
if not search_analysis_ready:
    warnings.append("未获得关键词搜索样本，搜索模块只保留标签表达观察。")
if completion_ratio(len(notes_with_dt), total_notes) < 0.8:
    warnings.append("时间字段不足，成长轨迹和发布节奏应谨慎解读。")

quality_score = 0
quality_score += completion_ratio(notes_with_title, total_notes) * 15
quality_score += completion_ratio(notes_with_like_field, total_notes) * 15
quality_score += completion_ratio(len(notes_with_dt), total_notes) * 10
quality_score += min(completion_ratio(len(contents_with_text), max(detail_required_count, 1)), 1) * 20
quality_score += min(completion_ratio(len(contents_with_tags), max(detail_required_count, 1)), 1) * 10
quality_score += min(completion_ratio(notes_with_favorite, max(detail_required_count, 1)), 1) * 10
quality_score += min(completion_ratio(len(comment_texts), 30), 1) * 10
quality_score += min(completion_ratio(len(contents_with_media), 12), 1) * 5
quality_score += (1 if search_analysis_ready else 0) * 5

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
    "detail_sample_count": detail_sample_count,
    "detail_required_count": detail_required_count,
    "content_sample_count": len(contents_with_text),
    "tag_sample_count": len(contents_with_tags),
    "content_sample_completeness": content_sample_completeness,
    "tag_sample_completeness": tag_sample_completeness,
    "content_analysis_ready": content_analysis_ready,
    "tag_analysis_ready": tag_analysis_ready,
    "comment_analysis_ready": comment_analysis_ready,
    "comment_count_completeness": completion_ratio(notes_with_comment_count, total_notes),
    "comment_completeness": completion_ratio(comment_note_count, total_notes),
    "comment_sample_count": len(comment_texts),
    "comment_note_count": comment_note_count,
    "media_analysis_ready": media_analysis_ready,
    "media_sample_count": len(contents_with_media),
    "search_analysis_ready": search_analysis_ready,
    "search_keyword_count": len(search_rows_ready),
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
        "name": "党史、革命史与政治人物",
        "keywords": [
            "党史", "中共", "共产党", "毛泽东", "周恩来", "邓小平", "刘少奇", "朱德",
            "彭德怀", "陈云", "王明", "张国焘", "延安", "遵义", "红军", "长征",
            "整风", "革命", "政治局", "三湾改编", "古田会议", "土地革命", "根据地",
        ],
        "required_any": [
            "党史", "中共", "共产党", "毛泽东", "周恩来", "邓小平", "刘少奇", "朱德",
            "彭德怀", "陈云", "王明", "张国焘", "延安", "遵义", "红军", "长征",
            "整风", "三湾改编", "古田会议", "土地革命", "根据地",
        ],
        "strong_any": [
            "党史", "毛泽东", "周恩来", "邓小平", "刘少奇", "朱德", "彭德怀", "陈云",
            "延安整风", "三湾改编", "古田会议", "遵义会议", "长征", "革命根据地",
            "实践论", "矛盾论", "实事求是",
        ],
        "min_matches": 2,
        "priority": 92,
    },
    {
        "name": "军事史、战役与战略",
        "keywords": [
            "军事", "军队", "解放军", "红军", "八路军", "新四军", "四野", "野战军",
            "战役", "战争", "作战", "战术", "战略", "兵力", "将领", "指挥员", "司令员",
            "林彪", "罗荣桓", "粟裕", "塔山", "辽沈", "平津", "淮海", "阻击", "防线",
            "进攻", "撤军", "尖刀", "兵团", "剿匪", "保卫战", "授衔", "枪杆",
        ],
        "required_any": [
            "军事", "军队", "解放军", "红军", "八路军", "新四军", "四野", "野战军",
            "战役", "战争", "作战", "战术", "战略", "兵力", "将领", "指挥员", "司令员",
            "林彪", "罗荣桓", "粟裕", "塔山", "辽沈", "平津", "淮海", "兵团",
            "剿匪", "保卫战", "授衔", "枪杆",
        ],
        "strong_any": [
            "四野", "野战军", "战役", "塔山", "辽沈战役", "淮海战役", "抗美援朝",
            "林彪", "罗荣桓", "粟裕", "军事史", "军队", "剿匪", "保卫战", "授衔", "枪杆",
        ],
        "min_matches": 2,
        "priority": 94,
    },
    {
        "name": "历史人物与思想启示",
        "keywords": [
            "历史", "人物", "王阳明", "曾国藩", "苏轼", "孔子", "孟子", "庄子", "鲁迅",
            "王安石", "谭嗣同", "韦睿", "曹景宗", "陈庆之", "钱学森", "王永志", "古人",
            "心学", "龙场悟道", "知行合一", "哲学", "思想", "心法", "处世", "人生",
            "命运", "传记", "启示", "变法", "汉唐", "帝国", "民族", "辩证法", "第一原理",
            "思维", "思考", "规律", "领导力", "宿命", "百年", "古老", "智慧",
        ],
        "required_any": [
            "历史人物", "王阳明", "曾国藩", "苏轼", "孔子", "孟子", "庄子", "鲁迅",
            "王安石", "谭嗣同", "韦睿", "曹景宗", "陈庆之", "钱学森", "王永志",
            "心学", "龙场悟道", "知行合一", "哲学", "传记", "古人", "变法", "汉唐",
            "辩证法", "第一原理", "领导力", "宿命",
        ],
        "strong_any": [
            "王阳明", "曾国藩", "苏轼", "孔子", "孟子", "庄子", "鲁迅", "王安石",
            "谭嗣同", "韦睿", "曹景宗", "陈庆之", "钱学森", "王永志", "龙场悟道",
            "心学", "知行合一", "辩证法", "第一原理", "领导力",
        ],
        "min_matches": 2,
        "priority": 86,
    },
    {
        "name": "制度、经济与社会观察",
        "keywords": [
            "制度", "政策", "改革", "经济", "国企", "经商", "商业", "社会", "国家",
            "老百姓", "群众", "治理", "权力", "财政", "土地", "就业", "内卷", "组织",
            "纪律", "利益", "市场",
        ],
        "required_any": [
            "制度", "政策", "改革", "经济", "国企", "经商", "老百姓", "群众", "治理",
            "财政", "就业", "内卷", "组织纪律",
        ],
        "strong_any": ["军队经商", "国企", "老百姓", "内卷", "分税", "农业税", "VIE", "组织纪律"],
        "min_matches": 2,
        "priority": 74,
    },
    {
        "name": "经济制度、产业与科技史",
        "keywords": [
            "经济", "金融", "财政", "市场", "价格", "投资", "工资", "税", "分税", "农业税",
            "苏联", "工厂", "产业", "科技", "芯片", "半导体", "长鑫", "硅谷", "VIE", "同股不同权",
            "概率", "正态分布", "泊松分布", "物理", "有限元", "比特", "模型", "论文", "手稿", "工程",
            "经济学", "中间商", "工资", "职场", "大众传媒", "历史", "世纪",
        ],
        "required_any": [
            "金融", "财政", "市场", "价格", "投资", "工资", "分税", "农业税", "苏联", "工厂",
            "产业", "科技", "芯片", "半导体", "长鑫", "硅谷", "VIE", "同股不同权", "概率",
            "物理", "有限元", "比特", "论文", "手稿", "工程", "经济学", "中间商", "工资",
            "职场", "大众传媒", "正态分布", "泊松分布",
        ],
        "strong_any": [
            "分税", "农业税", "苏联", "芯片", "半导体", "长鑫", "VIE", "同股不同权",
            "有限元", "科技金融", "政治经济学", "正态分布", "泊松分布", "经济学",
        ],
        "min_matches": 2,
        "priority": 82,
    },
    {
        "name": "北京周边与低成本出行",
        "keywords": [
            "北京", "周边", "草原", "崇礼", "坝上", "徒步", "线路", "高铁", "公交",
            "开车", "自驾", "当日往返", "避暑", "玩水", "旅行", "出行", "打卡",
            "公园", "路线", "目的地", "排名",
        ],
        "required_any": ["北京", "草原", "崇礼", "坝上", "徒步", "高铁", "公交", "自驾", "旅行", "出行"],
        "min_matches": 2,
        "priority": 78,
    },
    {
        "name": "北京天气与城市观察",
        "keywords": [
            "北京", "天气", "天空", "东北冷涡", "通透度", "雨后", "晴好", "干燥",
            "风", "花信风", "海淀", "帝都", "午后", "街道", "城市", "日落",
            "云", "晴", "阴湿", "Chill",
        ],
        "required_any": ["天气", "天空", "东北冷涡", "通透度", "雨后", "晴好", "海淀天气", "北京天气"],
        "strong_any": ["东北冷涡", "通透度", "北京天气"],
        "min_matches": 2,
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
        "strong_any": ["摄影", "影像", "画质", "ccd", "镜头", "拍照"],
        "min_matches": 2,
        "priority": 77,
    },
    {
        "name": "校园与生活观察",
        "keywords": [
            "校园", "北师大", "学生", "老师", "同学", "宿舍", "博士", "毕业",
            "大学", "课堂", "学习", "生活", "夏日", "春", "记录",
        ],
        "required_any": ["校园", "北师大", "学生", "老师", "同学", "宿舍", "博士", "毕业", "大学", "课堂"],
        "strong_any": ["校园", "北师大", "宿舍", "课堂"],
        "min_matches": 2,
        "priority": 58,
    },
    {
        "name": "AI行业观点与趋势",
        "keywords": [
            "AI", "人工智能", "模型", "大模型", "行业", "趋势", "未来", "诺奖",
            "Hinton", "哈萨比斯", "Hassabis", "共识", "分歧", "创业", "具身智能",
            "Agent", "开发者", "闭源", "开源",
        ],
        "required_any": ["AI", "人工智能", "大模型", "ChatGPT", "OpenAI", "Claude", "DeepSeek", "Hinton", "哈萨比斯", "Hassabis", "具身智能", "Agent"],
        "strong_any": ["人工智能", "大模型", "ChatGPT", "OpenAI", "Claude", "DeepSeek", "Hinton", "哈萨比斯", "Hassabis", "具身智能"],
        "min_matches": 2,
        "priority": 80,
    },
    {
        "name": "AI工具与模型评测",
        "keywords": [
            "ChatGPT", "OpenAI", "Claude", "DeepSeek", "Gemini", "Qwen", "通义",
            "豆包", "GLM", "Kimi", "混元", "Godot", "实测", "测评", "评测",
            "发布", "更新", "模型", "工具", "开源", "闭源",
        ],
        "required_any": ["ChatGPT", "OpenAI", "Claude", "DeepSeek", "Gemini", "Qwen", "通义", "豆包", "GLM", "Kimi", "混元"],
        "strong_any": ["ChatGPT", "OpenAI", "Claude", "DeepSeek", "Gemini", "Qwen", "通义", "豆包", "GLM", "Kimi", "混元"],
        "min_matches": 1,
        "priority": 75,
    },
    {
        "name": "AI应用实践与案例",
        "keywords": [
            "应用", "案例", "场景", "工作流", "自动化", "PPT", "写作", "编程",
            "开发", "生成", "提示词", "实操", "赚钱", "创作", "视频", "房间存档",
            "做出来", "工具",
        ],
        "required_any": ["AI", "人工智能", "大模型", "ChatGPT", "Agent", "提示词", "AI工作流"],
        "strong_any": ["AI应用", "人工智能", "ChatGPT", "Agent", "提示词", "AI工作流"],
        "min_matches": 2,
        "priority": 70,
    },
    {
        "name": "产品与创业观察",
        "keywords": [
            "产品", "创业", "公司", "商业", "融资", "用户", "需求", "PMF",
            "发布会", "投资", "团队", "打工", "实习生", "成本", "Token", "token",
        ],
        "required_any": ["产品", "创业", "融资", "PMF", "投资", "商业模式", "Token", "token"],
        "strong_any": ["PMF", "融资", "商业模式"],
        "min_matches": 2,
        "priority": 60,
    },
    {
        "name": "教育学习与家庭场景",
        "keywords": [
            "孩子", "家长", "作业", "学习", "教育", "老师", "学生", "课堂",
            "辅导", "大学", "文科生", "面试", "求职", "教学",
        ],
        "required_any": ["孩子", "家长", "学习", "教育", "老师", "学生", "课堂", "辅导", "大学", "文科生", "面试", "求职", "教学"],
        "strong_any": ["孩子", "家长", "教育", "课堂", "辅导", "教学"],
        "min_matches": 2,
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

def keyword_in_text(keyword, text):
    keyword = str(keyword or '')
    text = str(text or '')
    if re.fullmatch(r'[A-Za-z0-9.+#-]+', keyword):
        return bool(re.search(r'(?<![A-Za-z0-9])' + re.escape(keyword) + r'(?![A-Za-z0-9])', text, re.I))
    return keyword.lower() in text.lower()

def rule_match_score(text, rule):
    strong_match = any(keyword_in_text(k, text) for k in rule.get("strong_any", []))
    if rule.get("required_any") and not any(keyword_in_text(k, text) for k in rule["required_any"]) and not strong_match:
        return 0, []
    matched = [k for k in rule["keywords"] if keyword_in_text(k, text)]
    if len(matched) < rule.get("min_matches", 1) and not strong_match:
        return 0, []
    # Longer, more specific keywords should outweigh generic words like "手机".
    score = len(matched) * 10 + sum(min(len(k), 8) for k in matched) + rule.get("priority", 0) / 100
    if strong_match:
        score += 80
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
    best = None
    for rule in topic_rules:
        votes = []
        for note in notes:
            score, matched = rule_match_score(note_text(note), rule)
            if score > 0:
                votes.append((score, matched))
        minimum_votes = max(2, int(len(notes) * 0.5 + 0.999))
        if len(votes) < minimum_votes:
            continue
        matched = list(dict.fromkeys(k for _, terms in votes for k in terms))
        support = len(votes) / max(len(notes), 1)
        score = support * 100 + sum(value for value, _ in votes) / len(votes)
        current = (score, rule["name"], matched)
        if best is None or current[0] > best[0]:
            best = current
    if best:
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
    rule_names = {rule["name"] for rule in topic_rules}
    rule_groups = {}
    preassigned = set()
    for idx, note in enumerate(all_notes):
        note['_topic_index'] = idx
        name, matched, confidence = _fallback_rule_classify(note)
        if name not in rule_names or confidence == "low":
            continue
        payload = rule_groups.setdefault(name, {"notes": [], "keywords": Counter(), "scores": []})
        payload["notes"].append(note)
        payload["keywords"].update(matched)
        payload["scores"].append(confidence_score_map.get(confidence, 1))
        preassigned.add(idx)

    clusters = []
    for name, payload in rule_groups.items():
        avg_confidence = sum(payload["scores"]) / max(len(payload["scores"]), 1)
        clusters.append(
            {
                "name": name,
                "notes": payload["notes"],
                "keywords": [term for term, _ in payload["keywords"].most_common(8)],
                "matched": [term for term, _ in payload["keywords"].most_common(8)],
                "confidence": "high" if avg_confidence >= 2.5 and len(payload["notes"]) >= 3 else "medium",
                "source": "ontology_rule",
            }
        )

    term_docs = defaultdict(list)
    for idx, note in enumerate(all_notes):
        if idx in preassigned:
            continue
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

    unassigned = {n['_topic_index'] for n in all_notes if n['_topic_index'] not in preassigned}

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
                "confidence": "medium",
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
overall_median = results['profile'].get('median_likes', 0) or 0
for fname, check_fn in formulas.items():
    matched = [n for n in all_notes if check_fn(n.get('title', ''))]
    if len(matched) < 3:
        continue
    matched_likes = [n.get('liked_count', 0) for n in matched]
    avg = sum(matched_likes)/len(matched)
    median = statistics.median(matched_likes)
    burst = len([n for n in matched if n.get('liked_count', 0) > 1000])
    ranked_matched = sorted(matched, key=lambda x: x.get('liked_count', 0), reverse=True)
    results['title_formulas'][fname] = {
        'count': len(matched),
        'pct': round(len(matched)/len(all_notes)*100, 1),
        'avg_likes': round(avg, 1),
        'median_likes': median,
        'vs_overall_pct': round((avg / overall_avg - 1) * 100, 1) if overall_avg else 0,
        'vs_median_pct': round((median / overall_median - 1) * 100, 1) if overall_median else 0,
        'burst_count': burst,
        'burst_rate': round(burst/len(matched)*100, 1),
        'sample': [n.get('title', '') for n in ranked_matched[:5]],
        'note_ids': [n.get('note_id', '') for n in ranked_matched if n.get('note_id')],
        'top': ranked_matched[0].get('title', ''),
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
    comparison_size = min(20, max(5, len(sc) // 5))
    top_pool = sc[:comparison_size]
    bot_pool = sc[-comparison_size:]

    def has_detail(n):
        ct = n.get('_content') or {}
        return is_real_content_text(ct.get('text', '')) or bool(ct.get('tags'))

    top20 = [n for n in top_pool if has_detail(n)]
    bot20 = [n for n in bot_pool if has_detail(n)]

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
            'sample_count': len(notes_list),
            'avg_tag_count': round(statistics.mean(tcounts), 1),
            'avg_text_length': round(statistics.mean(wcounts), 1),
            'has_date_ratio': round(dates/len(notes_list)*100, 1),
        }

    if len(top20) >= 3 and len(bot20) >= 3:
        top_avg = sum(n.get('liked_count', 0) for n in top20) / len(top20)
        bot_avg = sum(n.get('liked_count', 0) for n in bot20) / len(bot20)
        results['top_vs_bottom'] = {
            'top20': extract_cm(top20),
            'bot20': extract_cm(bot20),
            'top20_avg_likes': round(top_avg, 1),
            'bot20_avg_likes': round(bot_avg, 1),
            'ratio': round(top_avg / max(bot_avg, 1), 1),
            'comparison_scope': '仅比较高表现组和低表现组中已成功采集详情的样本',
            'reliability': 'medium' if len(top20) >= 5 and len(bot20) >= 5 else 'low',
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
    monthly_stats = []
    for i, m in enumerate(ms):
        chunk = []
        for j in range(max(0,i-2), min(len(ms),i+3)):
            chunk.extend(nbym[ms[j]]['likes'])
        ma[m] = round(sum(chunk)/len(chunk)) if chunk else 0
        month_likes = nbym[m]['likes']
        monthly_stats.append({
            'month': m,
            'count': nbym[m]['count'],
            'avg_likes': round(statistics.mean(month_likes), 1) if month_likes else 0,
            'median_likes': statistics.median(month_likes) if month_likes else 0,
            'max_likes': max(month_likes) if month_likes else 0,
        })

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
        'monthly_stats': monthly_stats,
        'top_bursts': bursts[:30],
        'burst_count': len(bursts),
        'scope_note': '这里只观察公开笔记的发布与点赞变化，不代表粉丝增长、曝光增长或账号后台流量变化。',
    }
else:
    results['growth'] = {'months_active': 0}

# ---- 8. Tags (requires contents) ----
if contents:
    all_tags = []
    tagged_note_count = 0
    for n in normalized_contents:
        note_has_tag = False
        for tag_str in n.get('tags', []):
            for t in re.split(r'[\s# ]+', tag_str):
                t = t.strip().lstrip('#')
                if t and len(t) > 1 and not t.startswith('@'):
                    all_tags.append(t)
                    note_has_tag = True
        if note_has_tag:
            tagged_note_count += 1

    tc = Counter(all_tags)
    results['tags'] = {
        'total_unique': len(tc),
        'top30': [{'tag': t, 'count': c} for t, c in tc.most_common(30)],
        'total_mentions': len(all_tags),
        'sample_note_count': tagged_note_count,
        'detail_sample_count': len(normalized_contents),
        'sample_coverage_pct': round(tagged_note_count / max(len(normalized_contents), 1) * 100, 1),
        'source_scope': '仅统计成功采集详情的笔记标签，不代表平台搜索量、关键词热度或全账号所有历史标签。',
    }

# ---- Public comments: audience needs and response signals ----
def _comment_phrases(texts):
    stop = {'哈哈', '哈哈哈', '真的', '感觉', '就是', '这个', '那个', '一个', '可以', '还是', '什么', '怎么', '已经', '现在', '但是', '因为', '所以', '写的真好', '写的很好', '感谢分享', '点赞'}
    counter = Counter()
    for text in texts:
        for phrase in re.split(r'[，。！？!?；;：:\n\r…]+', text):
            phrase = re.sub(r'[@#][^\s，。！？!?；;：:]+', '', phrase).strip()
            phrase = re.sub(r'\[[^\]]{1,12}\]', '', phrase).strip()
            if 2 <= len(phrase) <= 18 and phrase not in stop and not phrase.isdigit():
                counter[phrase] += 1
    return [{'phrase': phrase, 'count': count} for phrase, count in counter.most_common(20)]

comment_locations = Counter(
    str(item.get('ip_location') or '').strip()
    for item in comments
    if str(item.get('ip_location') or '').strip() not in ('', '未知')
)
question_comments = [item for item in comments if re.search(r'[?？]|怎么|如何|哪里|有没有|能不能|求|请问', str(item.get('content') or ''))]
representative_comments = sorted(
    [item for item in comments if str(item.get('content') or '').strip()],
    key=lambda item: parse_count(item.get('like_count', 0)),
    reverse=True,
)[:20]
results['audience_signals'] = {
    'comment_count': len(comment_texts),
    'note_count': comment_note_count,
    'question_count': len(question_comments),
    'question_rate': round(len(question_comments) / max(len(comment_texts), 1) * 100, 1),
    'repeated_phrases': _comment_phrases(comment_texts),
    'top_comment_locations': [{'location': name, 'count': count} for name, count in comment_locations.most_common(10)],
    'representative_comments': [
        {
            'comment_id': item.get('comment_id', ''),
            'note_id': item.get('note_id', ''),
            'content': item.get('content', ''),
            'like_count': parse_count(item.get('like_count', 0)),
            'ip_location': item.get('ip_location', ''),
        }
        for item in representative_comments
    ],
    'source_scope': '基于代表笔记的公开评论样本，只用于观察需求、问题和反馈表达，不等于真实粉丝人口画像。',
}

# ---- Body opening hooks and media structure ----
hook_checks = {
    '提问开头': lambda text: bool(re.search(r'[?？]|^(你|大家).*(吗|么)', text[:60])),
    '时间/年代切入': lambda text: bool(re.search(r'(^|\D)(18|19|20)\d{2}\s*年|^(当年|那一年|多年以前|\d+年前)', text[:60])),
    '数字/清单切入': lambda text: bool(re.search(r'(^|\D)\d+\s*(个|条|步|种|点|层|件|招|法|类|组|把)\b|^[一二三四五六七八九十]+[、.]', text[:50])),
    '场景叙事开头': lambda text: bool(re.search(r'^(今天|昨天|最近|刚刚|前几天|那天|当时|这次)', text[:40])),
    '问题/矛盾切入': lambda text: bool(re.search(r'(为什么|为何|怎么会|矛盾|争议|困境|难题|不合理|反常识)', text[:80])),
    '结论先行': lambda text: bool(re.search(r'^(先说结论|结论|我发现|真正|最重要|核心|答案)', text[:50])),
    '情绪表达': lambda text: bool(re.search(r'(没想到|太|真的|居然|竟然|绝了|离谱|救命|崩溃)', text[:60])),
}
hook_patterns = {}
for name, check in hook_checks.items():
    matched = []
    for note in all_notes:
        content = note.get('_content') or {}
        text = content.get('text', '')
        if is_real_content_text(text) and check(text.strip()):
            matched.append(note)
    likes = [note.get('liked_count', 0) for note in matched]
    hook_patterns[name] = {
        'count': len(matched),
        'avg_likes': round(statistics.mean(likes), 1) if likes else 0,
        'median_likes': statistics.median(likes) if likes else 0,
        'evidence_note_ids': [note.get('note_id', '') for note in sorted(matched, key=lambda n: n.get('liked_count', 0), reverse=True)[:5]],
    }
results['hook_analysis'] = {
    'sample_count': len(contents_with_text),
    'patterns': hook_patterns,
    'source_scope': 'Hook 仅分析成功取得正文的分层样本；视频画面开头需由多模态增强另行判断。',
}

media_rows = []
for note in all_notes:
    content = note.get('_content') or {}
    image_urls = content.get('image_urls') or []
    if image_urls or content.get('video_url'):
        media_rows.append({
            'note_id': note.get('note_id', ''),
            'title': note.get('title', ''),
            'likes': note.get('liked_count', 0),
            'type': note.get('type', ''),
            'image_count': len(image_urls),
            'cover_url': content.get('cover_url') or (image_urls[0] if image_urls else ''),
            'image_urls': image_urls,
            'video_url': content.get('video_url', ''),
            'video_cover_url': content.get('video_cover_url', ''),
        })
media_sorted = sorted(media_rows, key=lambda item: item['likes'], reverse=True)
split = max(3, min(8, len(media_sorted) // 3)) if media_sorted else 0
high_media = media_sorted[:split]
low_media = media_sorted[-split:] if split else []
results['media_analysis'] = {
    'sample_count': len(media_rows),
    'image_note_count': len([item for item in media_rows if item['type'] != 'video']),
    'video_note_count': len([item for item in media_rows if item['type'] == 'video']),
    'avg_image_count': round(statistics.mean([item['image_count'] for item in media_rows]), 1) if media_rows else 0,
    'high_group_avg_image_count': round(statistics.mean([item['image_count'] for item in high_media]), 1) if high_media else 0,
    'low_group_avg_image_count': round(statistics.mean([item['image_count'] for item in low_media]), 1) if low_media else 0,
    'representative_assets': media_sorted[:18],
    'source_scope': '基础层只统计媒体数量和地址；封面风格、图中文字、画面信息和视频内容由可选多模态 AI 分析。',
}

# ---- Rich interaction comparison on detail samples ----
detail_rows = []
for note in all_notes:
    content = note.get('_content') or {}
    if not content:
        continue
    detail_rows.append({
        'note_id': note.get('note_id', ''),
        'likes': note.get('liked_count', 0),
        'favorites': note.get('collected_count', 0),
        'comments': note.get('comment_count', 0),
        'shares': note.get('share_count', 0),
        'text_length': len(content.get('text', '')),
        'tag_count': len(content.get('tags', [])),
        'image_count': len(content.get('image_urls', [])),
        'type': note.get('type', ''),
    })
detail_rows.sort(key=lambda item: item['likes'], reverse=True)
group_size = min(8, len(detail_rows) // 2)
top_detail = detail_rows[:group_size]
bottom_detail = detail_rows[-group_size:] if group_size else []

def _group_average(rows, key):
    return round(statistics.mean([row.get(key, 0) for row in rows]), 1) if rows else 0

results['engagement_drivers'] = {
    'sample_count': len(detail_rows),
    'group_size': group_size,
    'top_group': {key: _group_average(top_detail, key) for key in ('likes', 'favorites', 'comments', 'shares', 'text_length', 'tag_count', 'image_count')},
    'bottom_group': {key: _group_average(bottom_detail, key) for key in ('likes', 'favorites', 'comments', 'shares', 'text_length', 'tag_count', 'image_count')},
    'top_note_ids': [row['note_id'] for row in top_detail],
    'bottom_note_ids': [row['note_id'] for row in bottom_detail],
    'source_scope': '这是分层详情样本的相关性对比，不证明标题、正文、标签或图片数量造成互动变化。',
}

# ---- Search expression landscape ----
search_rows = []
for row in (search_landscape or {}).get('keywords', []) or []:
    public_results = row.get('results') or []
    likes = [parse_count(item.get('liked_count', 0)) for item in public_results]
    search_rows.append({
        'keyword': row.get('keyword', ''),
        'suggestions': row.get('suggestions', [])[:10],
        'result_count': len(public_results),
        'result_median_likes': statistics.median(likes) if likes else 0,
        'result_avg_likes': round(statistics.mean(likes), 1) if likes else 0,
        'representative_titles': [item.get('title', '') for item in sorted(public_results, key=lambda item: parse_count(item.get('liked_count', 0)), reverse=True)[:5]],
    })
results['search_landscape'] = {
    'keyword_count': len(search_rows),
    'keywords': search_rows,
    'source_scope': (search_landscape or {}).get('scope') or '没有取得搜索样本；不能推断搜索量、排名或搜索流量。',
}

# ---- 9. Commercial ----
commercial_signals = ['招聘', '招人', '有奖', '征集', '报名', '合作', '推广', '赞助', '广告', '好物', '品牌', '体验官', '测评', '购买', '店铺', '链接', '福利']
commercial_notes = []
for n in all_notes:
    score = 0
    for s in commercial_signals:
        if s in n.get('title', ''):
            score += 2
    ct = n.get('_content', {}) or {}
    if ct:
        txt = ct.get('text', '')
        for signal in commercial_signals:
            if signal in txt:
                score += 1
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
    'detected_note_ids': [n.get('note_id', '') for n in commercial_notes if n.get('note_id')],
    'detected_titles': [n.get('title', '') for n in commercial_notes[:10]],
    'signal_scope': '仅检测公开标题和已采集正文中的合作/推广关键词，不等于真实商单、成交或变现收入。',
    'comparison_ready': len(commercial_notes) >= 5,
}

# ---- Eight delivery dimensions ----
topic_analysis_reliable = unclassified_pct <= 35
best_topics = sorted(
    [item for item in results.get('topic_clusters', []) if item.get('confidence') != 'low'],
    key=lambda item: (item.get('count', 0), item.get('median_likes', 0)),
    reverse=True,
)[:5]
if not topic_analysis_reliable:
    best_topics = []
overall_median = results.get('profile', {}).get('median_likes', 0) or 0
validated_topics = [
    item for item in best_topics
    if item.get('count', 0) >= 8
    and (
        item.get('avg_likes', 0) >= overall_avg * 1.15
        or (overall_median and item.get('median_likes', 0) >= overall_median * 1.5)
    )
]
validated_topics.sort(
    key=lambda item: (item.get('median_likes', 0), item.get('avg_likes', 0), item.get('count', 0)),
    reverse=True,
)
best_hooks = sorted(
    [
        (name, value) for name, value in hook_patterns.items()
        if value.get('count', 0) >= 5
        and (not overall_median or value.get('median_likes', 0) >= overall_median * 1.1)
    ],
    key=lambda pair: pair[1].get('median_likes', 0),
    reverse=True,
)[:3]
top_search_terms = [item.get('keyword') for item in search_rows[:4] if item.get('keyword')]
top_comment_phrases = [
    item.get('phrase') for item in results['audience_signals']['repeated_phrases']
    if item.get('count', 0) >= 2
][:5]

def _dimension(status, confidence, sample_count, sources, findings, evidence_ids=None, limits=None):
    clean_findings = [finding for finding in findings if finding]
    clean_limits = limits or []
    if not clean_findings:
        clean_findings = [clean_limits[0] if clean_limits else '当前公开样本不足，本维度只保留数据边界。']
    return {
        'status': status,
        'confidence': confidence,
        'sample_count': sample_count,
        'sources': sources,
        'findings': clean_findings,
        'evidence_note_ids': list(dict.fromkeys(evidence_ids or [])),
        'limits': clean_limits,
    }

results['eight_dimensions'] = {
    'positioning_audience': _dimension(
        'ready' if topic_analysis_reliable and best_topics else 'limited', 'medium' if topic_analysis_reliable and best_topics else 'low', total_notes,
        ['账号简介', '公开标题与正文', f'{len(comment_texts)} 条代表评论'],
        [
            f"主要内容方向包括：{'、'.join(item.get('name', '') for item in best_topics[:3])}" if best_topics else '',
            f"评论中重复出现的表达包括：{'、'.join(top_comment_phrases)}" if top_comment_phrases else '',
            f"评论提问占比 {results['audience_signals']['question_rate']}%，可用于观察用户主动追问。" if comment_texts else '',
            f"仍有 {unclassified_pct}% 内容未形成稳定主题，本次不据此确定账号主线。" if not topic_analysis_reliable else '',
        ],
        [item.get('note_id', '') for item in representative_comments[:8]],
        ['评论反映公开表达，不等于全部粉丝画像；年龄、性别等人口属性不推断。'] + ([f'另有 {unclassified_pct}% 内容未形成稳定主题，定位结论保留不确定性。'] if unclassified_pct > 20 else []),
    ),
    'content_structure': _dimension(
        'ready' if content_analysis_ready and topic_analysis_reliable else 'limited', 'medium' if content_analysis_ready and topic_analysis_reliable else 'low', len(contents_with_text),
        ['全量标题主题', '分层正文', '图文/视频媒体结构'],
        [
            f"内容主要分布在：{'、'.join(item.get('name', '') for item in best_topics[:5])}" if best_topics else '',
            f"媒体详情样本 {len(media_rows)} 篇，平均每篇 {results['media_analysis']['avg_image_count']} 张图片。" if media_rows else '',
        ],
        [note_id for item in best_topics[:3] for note_id in item.get('evidence_note_ids', [])[:3]],
        ['媒体语义需要多模态 AI 增强；基础层只统计媒体结构。']
        + ([f'另有 {unclassified_pct}% 内容未形成稳定主题，不参与方向推荐。'] if unclassified_pct > 20 else [])
        + (['主题未归类超过 35%，内容主线暂不进入强建议。'] if not topic_analysis_reliable else []),
    ),
    'title_hook': _dimension(
        'ready' if content_analysis_ready else 'limited', 'medium' if best_hooks else 'low', len(contents_with_text),
        ['全量标题', '分层正文开头'],
        [f"正文样本中表现靠前的 Hook 类型包括：{'、'.join(name for name, _ in best_hooks)}" if best_hooks else ''],
        [note_id for _, item in best_hooks for note_id in item.get('evidence_note_ids', [])],
        ['Hook 与互动是相关性观察；视频前几秒需多模态或字幕分析。'],
    ),
    'engagement_drivers': _dimension(
        'ready' if len(detail_rows) >= detail_required_count else 'limited', 'medium' if group_size >= 5 else 'low', len(detail_rows),
        ['公开点赞', '详情收藏/评论/分享', '正文/标签/媒体数量'],
        [
            f"高表现组平均收藏 {results['engagement_drivers']['top_group']['favorites']}、评论 {results['engagement_drivers']['top_group']['comments']}、分享 {results['engagement_drivers']['top_group']['shares']}。" if top_detail else '',
            f"高表现组与低表现组正文长度分别为 {results['engagement_drivers']['top_group']['text_length']} 和 {results['engagement_drivers']['bottom_group']['text_length']} 字。" if top_detail else '',
        ],
        results['engagement_drivers']['top_note_ids'],
        ['没有曝光和点击数据，不做因果归因，只排序可验证的相关线索。'],
    ),
    'growth_trajectory': _dimension(
        'ready' if results.get('growth', {}).get('months_active', 0) >= 3 else 'limited', 'medium' if results.get('growth', {}).get('months_active', 0) >= 3 else 'low', total_notes,
        ['发布时间序列', '逐月公开互动表现'],
        [f"公开内容覆盖 {results.get('growth', {}).get('months_active', 0)} 个月，可观察发布频率和点赞中位数变化。"],
        [],
        ['这里是内容表现轨迹，不等于粉丝增长历史。'],
    ),
    'tag_search': _dimension(
        'ready' if tag_analysis_ready and search_analysis_ready else 'limited', 'medium' if tag_analysis_ready and search_analysis_ready else 'low', len(contents_with_tags),
        ['详情标签', '搜索联想', '关键词公开结果样本'],
        [f"已研究关键词：{'、'.join(top_search_terms)}" if top_search_terms else '', f"标签样本共 {len(contents_with_tags)} 篇。"],
        [],
        ['搜索结果样本不代表搜索量、实时排名或账号搜索流量。'],
    ),
    'commercial_signals': _dimension(
        'ready' if commercial_notes else 'limited', 'medium' if len(commercial_notes) >= 5 else 'low', len(commercial_notes),
        ['标题与正文商业表达', '商业信号样本公开互动'],
        [f"检测到 {len(commercial_notes)} 篇可能含合作、推广、购买或活动表达的样本。"],
        results['commercial']['detected_note_ids'],
        ['商业信号不等于真实商单、收入、转化或合作效果。'],
    ),
    'action_plan': _dimension(
        'ready' if topic_analysis_reliable and (validated_topics or best_hooks) else 'limited', 'medium' if topic_analysis_reliable and (validated_topics or best_hooks) else 'low', total_notes,
        ['前七维结构化证据'],
        [
            f"优先围绕「{validated_topics[0].get('name')}」继续做 3 篇相邻选题测试：该方向有 {validated_topics[0].get('count', 0)} 篇样本，点赞中位数 {validated_topics[0].get('median_likes', 0)}。" if validated_topics else '',
            f"标题与开头优先测试：{'、'.join(name for name, _ in best_hooks[:2])}。" if best_hooks else '',
            '先人工确认未归类内容的共同主线，再生成选题方向；当前不指定主题。' if not topic_analysis_reliable else '',
            '每轮只改变一个变量，并与账号历史中位数比较。',
        ],
        (validated_topics[0].get('evidence_note_ids', []) if validated_topics else []) + ([note_id for _, item in best_hooks[:1] for note_id in item.get('evidence_note_ids', [])]),
        ['建议是下一轮测试顺序，不承诺涨粉、爆款或成交。'],
    ),
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
