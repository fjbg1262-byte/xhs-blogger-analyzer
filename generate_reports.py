"""
xhs-blogger-analyzer — 深度报告生成器（旗舰版）
覆盖 9 个文件的完整分析维度，数据层→逻辑层→策略层闭环。

用法:
  python generate_reports.py --input ./data/results.json --output ./reports/博主名_日期
"""

import json, os, argparse, re, statistics
from collections import defaultdict, Counter
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument('--input', default='./data/results.json')
parser.add_argument('--output', default=None)
args = parser.parse_args()

with open(args.input, 'r', encoding='utf-8') as f:
    R = json.load(f)
Q = R.get('data_quality', {})

# Output directory
if args.output:
    out = args.output
else:
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    out = f'./reports/report_{ts}'

os.makedirs(out, exist_ok=True)
os.makedirs(f'{out}/assets', exist_ok=True)

P = R.get('profile', {})
T = R.get('topic_distribution', {})
CT = R.get('content_type', {})
TA = R.get('title_analysis', {})
TF = R.get('title_formulas', {})
E = R.get('engagement', {})
G = R.get('growth', {})
TG = R.get('tags', {})
C = R.get('commercial', {})
TVB = R.get('top_vs_bottom', {})
DIM = R.get('eight_dimensions', {})
AI = R.get('ai_enhancement', {})
TAG_HAS_DATA = bool(TG.get('top30') or TG.get('total_mentions', 0))

nickname = P.get('nickname', '未知博主')
overall_avg = P.get('avg_likes', 0)
overall_median = P.get('median_likes', 0)
burst_threshold = max(overall_avg * 2, 1000)
LOW_INFO_TOPIC_NAMES = {'其他/未分类', '其它/未分类', '未分类', '其他', '未归类观察', '日常随手记录'}
CONTENT_TEXT_OK = Q.get('content_analysis_ready', Q.get('content_text_completeness', 0) >= 0.5)
TAG_OK = Q.get('tag_analysis_ready', Q.get('tag_completeness', 0) >= 0.5)
COMMENT_OK = Q.get('comment_analysis_ready', Q.get('comment_completeness', 0) >= 0.5)
TAG_HAS_DATA = TAG_HAS_DATA and TAG_OK
TOPIC_OK = Q.get('topic_unclassified_pct', 0) <= 35

def is_low_info_topic(name):
    return any(token in str(name) for token in LOW_INFO_TOPIC_NAMES)

def is_recommendable_pattern(data, min_count=5, min_lift=20):
    avg_lift = data.get('vs_overall_pct', data.get('vs_baseline_pct', 0))
    median_lift = data.get('vs_median_pct', 0)
    return data.get('count', 0) >= min_count and avg_lift > min_lift and median_lift > 10

def is_reliable_topic(name, data, min_count=5):
    if is_low_info_topic(name):
        return False
    if data.get('count', 0) < min_count:
        return False
    if data.get('confidence') == 'low':
        return False
    return True

def parse_count(v):
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
    try:
        return int(float(v))
    except ValueError:
        return 0

# ---- Load raw notes for title/content analysis ----
all_notes_raw = []
try:
    notes_path = args.input.replace('results.json', 'all_notes.json')
    with open(notes_path, 'r', encoding='utf-8') as f:
        all_notes_raw = json.load(f)
except:
    pass

deduped_raw_notes = []
seen_raw_note_ids = set()
for n in all_notes_raw:
    note_id = n.get('note_id')
    if note_id:
        if note_id in seen_raw_note_ids:
            continue
        seen_raw_note_ids.add(note_id)
    deduped_raw_notes.append(n)
all_notes_raw = deduped_raw_notes

# Build title+likes pairs (with int conversion to handle string values)
title_data = []
for n in all_notes_raw:
    t = n.get('title', '').strip()
    lk = parse_count(n.get('liked_count', 0))
    if t:
        title_data.append((t, lk))

# ---- Dynamic title pattern discovery ----
EMOJI_RX = re.compile(r'[\U0001F300-\U0001F9FF\U00002000-\U00002BFF☀-➿⌀-⏿✀-➿]', re.UNICODE)
PATTERN_CHECKS = {
    '感叹句式（含感叹号结尾）': lambda t: t.endswith('！') or t.endswith('!'),
    '疑问句式（含问号）': lambda t: '？' in t or '?' in t,
    'Emoji 结尾': lambda t: bool(EMOJI_RX.search(t[-1] if t else '')),
    '冒号/破折号分隔结构': lambda t: '：' in t or ':' in t or '—' in t,
    '包含引号/引用': lambda t: '「' in t or '」' in t or '“' in t or '”' in t or '‘' in t or '’' in t,
    '省略号营造悬念': lambda t: '...' in t or '……' in t,
    '数字开头': lambda t: t and t[0].isdigit(),
    '第一人称视角（我/我们）': lambda t: t.startswith('我') or t.startswith('我们'),
    '感觉/感悟类开头': lambda t: t.startswith('感觉') or t.startswith('觉得') or t.startswith('没想到'),
    '否定/对比结构': lambda t: any(w in t for w in ['不是', '而不是', '而是', '其实', '但', '却']),
    '含具体数字指标': lambda t: bool(re.search(r'\d+[%倍种个万家天岁年]', t)),
    '文化梗/事件引用': lambda t: any(w in t for w in ['时代', '终局', '未来', '革命', '杀死', '战争']),
    '对话式（含"你"）': lambda t: '你' in t or '大家' in t,
}

def discover_patterns(title_data):
    found = {}
    for pname, check_fn in PATTERN_CHECKS.items():
        matched = [(t, lk) for t, lk in title_data if check_fn(t)]
        if len(matched) < 3:
            continue
        likes = [lk for _, lk in matched]
        avg = statistics.mean(likes)
        median = statistics.median(likes)
        burst = len([lk for lk in likes if lk > burst_threshold])
        above_avg = len([lk for lk in likes if lk > overall_avg]) if overall_avg else 0
        found[pname] = {
            'count': len(matched),
            'pct': round(len(matched) / len(title_data) * 100, 1),
            'avg_likes': round(avg, 1),
            'median_likes': median,
            'vs_baseline_pct': round((avg / overall_avg - 1) * 100, 1) if overall_avg else 0,
            'vs_median_pct': round((median / overall_median - 1) * 100, 1) if overall_median else 0,
            'burst_count': burst,
            'burst_rate': round(burst / len(matched) * 100, 1),
            'above_avg_rate': round(above_avg / len(matched) * 100, 1),
            'samples': [t for t, _ in matched[:5]],
        }
    return found

dynamic_patterns = discover_patterns(title_data) if len(title_data) >= 10 else {}

# ---- Build combined formulas from top 2-pattern combinations ----
def discover_formulas(title_data, patterns_dict):
    active = [p for p in patterns_dict if patterns_dict[p]['count'] >= 5]
    if len(active) < 2:
        return {}
    formulas = {}
    for i, p1 in enumerate(active):
        for p2 in active[i+1:]:
            check1 = PATTERN_CHECKS[p1]
            check2 = PATTERN_CHECKS[p2]
            matched = [(t, lk) for t, lk in title_data if check1(t) and check2(t)]
            if len(matched) < 3:
                continue
            likes = [lk for _, lk in matched]
            avg = statistics.mean(likes)
            median = statistics.median(likes)
            burst = len([lk for lk in likes if lk > burst_threshold])
            name = f'{p1.split("（")[0]} + {p2.split("（")[0]}'
            top_note = max(matched, key=lambda x: x[1])
            formulas[name] = {
                'count': len(matched),
                'pct': round(len(matched) / len(title_data) * 100, 1),
                'avg_likes': round(avg, 1),
                'median_likes': median,
                'vs_overall_pct': round((avg / overall_avg - 1) * 100, 1),
                'vs_median_pct': round((median / overall_median - 1) * 100, 1) if overall_median else 0,
                'burst_rate': round(burst / len(matched) * 100, 1),
                'burst_count': burst,
                'top': top_note[0],
                'sample': [t for t, _ in matched[:3]],
                'p1': p1,
                'p2': p2,
            }
    return dict(sorted(formulas.items(), key=lambda x: x[1]['avg_likes'], reverse=True)[:8])

dynamic_formulas = discover_formulas(title_data, dynamic_patterns) if len(title_data) >= 10 else {}

burst_note_count = 0
if overall_avg:
    for _, lk in title_data:
        if lk > burst_threshold:
            burst_note_count += 1

def w(fname, content):
    with open(f'{out}/{fname}', 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  Generated: {fname}')

def dimension_evidence_section(key):
    dimension = DIM.get(key, {})
    ai_item = (AI.get('dimensions') or {}).get(key, {}) if AI.get('enabled') else {}
    if not dimension and not ai_item:
        return ''
    findings = dimension.get('findings', [])
    sources = '、'.join(dimension.get('sources', [])) or '公开内容样本'
    limits = dimension.get('limits', [])
    text = f"""

## 本维度的数据与证据

- **状态**：{dimension.get('status', 'limited')}；置信度 {dimension.get('confidence', 'low')}
- **样本**：{dimension.get('sample_count', 0)}
- **数据来源**：{sources}
"""
    if findings:
        text += '\n### 结构化观察\n\n' + '\n'.join(f'- {item}' for item in findings) + '\n'
    if ai_item:
        text += f"""

### AI 增强解读

{ai_item.get('summary', '')}

{chr(10).join(f'- {item}' for item in ai_item.get('findings', []))}

> AI 模型：{AI.get('model', '已配置模型')}；{'包含代表封面多模态观察' if AI.get('multimodal') else '本次为文本证据增强'}。引用笔记：{len(ai_item.get('evidence_note_ids', []))} 篇。
"""
    if limits or ai_item.get('limits'):
        text += '\n### 解释边界\n\n' + '\n'.join(
            f'- {item}' for item in (limits + ai_item.get('limits', []))
        ) + '\n'
    return text

def classify_topic_emoji(cat, s):
    if s['burst_rate'] > 20: return '🔥'
    if s['avg_likes'] > overall_avg: return '📈'
    return '📊'

# ============================================================
# 00_博主画像卡片.md
# ============================================================

top_cats = sorted(T.items(), key=lambda x: x[1]['count'], reverse=True) if T else []
main_topics = [c for c, d in top_cats if is_reliable_topic(c, d)][:3]
audience_signal_count = R.get('audience_signals', {}).get('comment_count', 0)
audience_desc = (
    f'已结合 {audience_signal_count} 条代表评论观察关注问题与需求表达；不等同于粉丝人口画像'
    if audience_signal_count else
    '缺少评论正文与后台数据，不推断核心受众'
)

style_parts = []
deduced_style = False
for sp_name, sp_data in sorted(dynamic_patterns.items(), key=lambda x: x[1]['vs_baseline_pct'], reverse=True):
    if sp_data['pct'] > 15 and sp_data['vs_baseline_pct'] > 10:
        if 'Emoji' in sp_name:
            style_parts.append(f'善用Emoji增强表达（使用率{sp_data["pct"]}%）')
            deduced_style = True
        elif '感叹' in sp_name:
            style_parts.append(f'情绪表达强烈，善用感叹（使用率{sp_data["pct"]}%）')
            deduced_style = True
        elif '疑问' in sp_name:
            style_parts.append(f'倾向提问式互动（使用率{sp_data["pct"]}%）')
            deduced_style = True
        elif '人称' in sp_name:
            style_parts.append(f'对话感强，善用第二人称（使用率{sp_data["pct"]}%）')
            deduced_style = True
        elif '冒号' in sp_name:
            style_parts.append(f'信息密度高，多用冒号结构化表达（使用率{sp_data["pct"]}%）')
            deduced_style = True
        elif '数字' in sp_name:
            style_parts.append(f'偏好数据化表达（使用率{sp_data["pct"]}%）')
            deduced_style = True
if not deduced_style:
    style_parts.append('未检测到达到门槛的稳定标题表达特征')

domain = main_topics[0] if main_topics else '内容观察'
positioning = f'公开内容主要覆盖：{domain}'
if T and TOPIC_OK:
    top_roi = sorted(T.items(), key=lambda x: x[1]['avg_likes'], reverse=True)
    if top_roi:
        for tc, td in top_roi:
            if is_reliable_topic(tc, td):
                positioning += f'；「{tc}」为较高表现候选方向'
                break

dynamic_style_lines = ''
top_styles = sorted(dynamic_patterns.items(), key=lambda x: x[1]['pct'], reverse=True)[:4]
for sname, sdata in top_styles:
    if sdata['pct'] > 10:
        direction = '↑ 高于均值' if sdata['vs_baseline_pct'] > 5 else '→ 接近均值' if sdata['vs_baseline_pct'] > -5 else '↓ 低于均值'
        dynamic_style_lines += f"| {sname} | 使用率 {sdata['pct']}%，均赞 {sdata['avg_likes']}，{direction} |\n"

r00 = f"""# 博主画像卡片：{nickname}

## 一句话定位
{positioning}。

## 基础信息

| 字段 | 内容 |
|------|------|
| 昵称 | {nickname} |
| 内容总量 | {P.get('total_notes','?')} 篇 |
| 视频占比 | {P.get('video_count',0)} ({CT.get('video',{}).get('pct',0)}%) |
| 创作周期 | ~{G.get('months_active', '?')} 个月 |
| 均赞/中位数 | {P.get('avg_likes','?')} / {P.get('median_likes','?')} |
| 最高赞 | {P.get('max_likes','?')} |
| 标准差 | {P.get('std_likes','?')}（{'波动极大，爆款驱动型' if P.get('std_likes',0) > P.get('avg_likes',1) else '分布相对集中'}） |

## 受众信息边界

| 维度 | 特征 |
|------|------|
| 核心受众 | {audience_desc} |
| 受众痛点 | 当前缺少评论/正文数据，暂不推断具体痛点 |
| 内容消费场景 | 当前缺少用户行为数据，暂不推断消费场景 |
| 受众水平 | 仅可从标题和选题粗略观察，暂不做确定判断 |

## 可观察表达要素

| 要素 | 表现 |
|------|------|
| 语言风格 | {''.join(style_parts)} |
| 内容价值观 | 需结合正文和创作者自述进一步判断 |
| 内容覆盖 | {'、'.join(main_topics[:3]) if main_topics else '多个方向（当前主题分类不足）'} |
| 人设判断 | 缺少评论、主页自述和长期对标，不做确定判断 |

### 实际标题特征表现
{dynamic_style_lines}
"""

r00 += dimension_evidence_section('positioning_audience')
w('00_博主画像卡片.md', r00)

# ============================================================
# 01_内容结构分析.md
# ============================================================

topic_rows = ''
if T:
    for i, (cat, s) in enumerate(sorted(T.items(), key=lambda x: x[1]['avg_likes'], reverse=True)):
        topic_rows += f"| {i+1} | {cat} | {s['count']} | {s['pct']}% | {s['avg_likes']} | {s['median_likes']} | {s['max_likes']} | {s['burst_count']} ({s['burst_rate']}%) | {s['above_avg_rate']}% |\n"

r01 = f"""# 内容结构分析

## 一、主题分布总览

| 排名 | 类别 | 篇数 | 占比 | 均赞 | 中位数 | 最高赞 | 爆款数 | 高于均值比 |
|-----|------|-----|------|------|-------|-------|-------|----------|
{topic_rows}

## 二、各主题深度分析

"""

if T:
    for cat, s in sorted(T.items(), key=lambda x: x[1]['avg_likes'], reverse=True):
        emoji = classify_topic_emoji(cat, s)
        cat_type = '主要内容' if s['count'] >= max(20, P.get('total_notes', 0) * 0.25) else '稳定支线' if s['count'] >= 8 else '探索样本'
        avg_assess = '显著高于均值' if s['avg_likes'] > overall_avg * 1.2 else '接近均值' if s['avg_likes'] > overall_avg * 0.8 else '低于均值'
        median_assess = '分布均匀' if s['median_likes'] > overall_median else '头尾分化'
        burst_assess = '高产爆款🔥' if s['burst_rate'] > 20 else '偶尔出爆款' if s['burst_rate'] > 10 else '爆款稀缺'
        stable_assess = '稳定输出' if s['above_avg_rate'] > 30 else '分化严重'

        r01 += f"""### {emoji} {cat}

| 指标 | 数值 | 评估 |
|------|------|------|
| 笔记数 | {s['count']} 篇 ({s['pct']}%) | {cat_type} |
| 平均点赞 | {s['avg_likes']} | {avg_assess} |
| 中位数 | {s['median_likes']} | {median_assess} |
| 爆款率 | {s['burst_count']} 篇 ({s['burst_rate']}%) | {burst_assess} |
| 高于均值比 | {s['above_avg_rate']}% | {stable_assess} |

"""
        if is_low_info_topic(cat):
            r01 += "**策略建议**: 该类属于未充分归类内容，只用于观察样本构成，不作为选题策略依据。\n\n"
        elif not is_reliable_topic(cat, s):
            r01 += f"**策略建议**: 样本量或分类置信度不足，当前只作观察，不建议据此增加发布占比。\n\n"
        elif s['count'] >= 8 and s['avg_likes'] >= overall_avg * 1.15 and s.get('median_likes', 0) >= overall_median * 1.1:
            r01 += f"**验证建议**: 该方向有 {s['count']} 篇样本，均值与中位数都高于账号基线，可优先连续测试 3 篇；这仍是相关性线索，不证明主题单独造成高点赞。\n\n"
        elif s['avg_likes'] < overall_avg * 0.7:
            r01 += f"**验证建议**: 当前均赞低于账号基线，但需结合中位数与具体样本复核；先调整一个变量做 3 篇测试，不直接停更该方向。\n\n"
        elif s['count'] < 5:
            r01 += "**策略建议**: 样本量较小（<5篇），结论需谨慎参考。\n\n"
        else:
            r01 += "\n"

video = CT.get('video', {})
normal = CT.get('normal', {})
video_pct = video.get('pct', 0)
video_eff = video.get('vs_image_pct', 0)

r01 += f"""## 三、内容形态效率对比

| 形态 | 篇数 | 占比 | 均赞 | 相对图文效率 |
|------|------|------|------|------------|
| 图文 | {normal.get('count',0)} | {normal.get('pct',0)}% | {normal.get('avg_likes',0)} | 100%（基准） |
| 视频 | {video.get('count',0)} | {video.get('pct',0)}% | {video.get('avg_likes',0)} | {video_eff}% |

"""

if video.get('count', 0) > 10 and video_eff < 80:
    r01 += f"**关键结论**: 视频占比{video_pct}%，但均赞只有图文的{video_eff}%。视频制作的投入产出比显著低于图文，需评估是否值得持续投入。\n\n"
elif video.get('count', 0) > 0 and video_eff >= 80:
    r01 += f"**关键结论**: 视频与图文互动效率接近，可以持续做视频内容。\n\n"
else:
    r01 += f"**关键结论**: 该博主以图文为主，视频占比较低。\n\n"

all_titles = [n.get('title', '') for n in all_notes_raw]
if all_titles:
    word_groups = defaultdict(list)
    series_keywords = ['系列', '实测', '保姆', '教程', '指南', '分享', '对比', '评测', '推荐', '合集', '开源', '上线', '发布']
    for t in all_titles:
        for kw in series_keywords:
            if kw in t:
                word_groups[kw].append(t)
    series_detected = [(kw, titles) for kw, titles in word_groups.items() if len(titles) >= 3]
    if series_detected:
        r01 += """## 四、系列化内容

从标题聚类中识别到以下系列化内容:

| 系列关键词 | 篇数 | 代表性标题 |
|----------|------|-----------|
"""
        for kw, titles in sorted(series_detected, key=lambda x: len(x[1]), reverse=True)[:6]:
            r01 += f"| 「{kw}」系列 | {len(titles)} 篇 | {titles[0][:40]} |\n"
        r01 += "\n以上只说明标题中存在重复系列词。是否有利于用户预期或搜索表现，需要后续发布测试验证。\n\n"
    else:
        r01 += """## 四、系列化内容

未检测到明显的系列化标题词（基于关键词聚类）。可把系列化作为待测试方案，而不是账号既有规律。

"""

r01 += f"""## 五、内容密度

| 指标 | 数值 |
|------|------|
| 活跃月数 | {G.get('months_active', '?')} 个月 |
| 月均发布 | {round(P.get('total_notes',0)/max(G.get('months_active',1),1), 1)} 篇 |
| 周均发布 | {round(P.get('total_notes',0)/max(G.get('months_active',1),1)/4, 1)} 篇 |
"""

r01 += dimension_evidence_section('content_structure')
w('01_内容结构分析.md', r01)

# ============================================================
# 02_标题与文案分析.md  — 数据驱动版
# ============================================================

feat_rows = ''
if dynamic_patterns:
    for pname, pdata in sorted(dynamic_patterns.items(), key=lambda x: x[1]['avg_likes'], reverse=True):
        effect = '可优先测试' if is_recommendable_pattern(pdata) else ('谨慎测试' if pdata['count'] >= 5 and pdata['vs_baseline_pct'] < -30 and pdata.get('vs_median_pct', 0) < -10 else '仅观察')
        feat_rows += f"| {pname} | {pdata['count']} | {pdata['pct']}% | {pdata['avg_likes']} | {pdata['vs_baseline_pct']:+.1f}% | {effect} |\n"
elif TA:
    for fn, d in TA.items():
        if fn == 'avg_length' or not isinstance(d, dict): continue
        effect = '✅ 有效' if d.get('vs_baseline_pct', 0) > 0 else ('❌ 谨慎' if d.get('vs_baseline_pct', 0) < -10 else '—')
        feat_rows += f"| {fn} | {d['count']} | {d['pct']}% | {d['avg_likes']} | {d['vs_baseline_pct']:+.1f}% | {effect} |\n"

formula_rows = ''
if dynamic_formulas:
    for fname, fdata in sorted(dynamic_formulas.items(), key=lambda x: x[1]['avg_likes'], reverse=True):
        formula_rows += f"| {fname} | {fdata['count']} | {fdata['pct']}% | {fdata['avg_likes']} | {fdata['vs_overall_pct']:+.1f}% | {fdata['burst_rate']}% | {fdata.get('top','')[:40]} |\n"
elif TF:
    for fname, fdata in sorted(TF.items(), key=lambda x: x[1]['avg_likes'], reverse=True):
        formula_rows += f"| {fname} | {fdata['count']} | {fdata['pct']}% | {fdata['avg_likes']} | {fdata['vs_overall_pct']:+.1f}% | {fdata['burst_rate']}% | {fdata.get('top','')[:40]} |\n"

title_findings = []
if dynamic_patterns:
    sorted_p = sorted(dynamic_patterns.items(), key=lambda x: x[1]['avg_likes'], reverse=True)
    best_pattern = sorted_p[0] if sorted_p else None
    if best_pattern and is_recommendable_pattern(best_pattern[1]):
        title_findings.append(f"**{best_pattern[0]}** 达到测试门槛：{best_pattern[1]['count']} 篇，均赞相对基线 {best_pattern[1]['vs_baseline_pct']:+.1f}%，中位数相对基线 {best_pattern[1]['vs_median_pct']:+.1f}%")

    most_used = sorted(dynamic_patterns.items(), key=lambda x: x[1]['pct'], reverse=True)[0]
    title_findings.append(f"**{most_used[0]}** 使用频率最高（{most_used[1]['pct']}%）；高频只说明写作习惯，不自动等于有效。")

    worst = sorted(dynamic_patterns.items(), key=lambda x: x[1]['avg_likes'])[0]
    if worst[1]['avg_likes'] < overall_avg * 0.7:
        title_findings.append(f"**{worst[0]}** 均赞仅 {worst[1]['avg_likes']}（vs 基准 {worst[1]['vs_baseline_pct']:+.1f}%），需谨慎使用")

formula_deep_dives = ''
formulas_to_show = dynamic_formulas if dynamic_formulas else TF
if formulas_to_show:
    for fname, fdata in sorted(formulas_to_show.items(), key=lambda x: x[1]['avg_likes'], reverse=True):
        direction = '高于' if fdata['vs_overall_pct'] > 0 else '低于'
        formula_deep_dives += f"""### {fname}

- **使用频次**: {fdata['count']} 次 ({fdata['pct']}%)
- **均赞 / 中位数**: {fdata['avg_likes']} / {fdata.get('median_likes', 0)}
- **相对基线**: 均值 {fdata['vs_overall_pct']:+.1f}% / 中位数 {fdata.get('vs_median_pct', 0):+.1f}%
- **爆款率**: {fdata['burst_rate']}%
- **最佳标题**: {fdata.get('top', '')[:60]}

"""
        samples = fdata.get('sample', [])
        if samples:
            formula_deep_dives += "**示例**:\n"
            for s in samples[:3]:
                formula_deep_dives += f"- `{s}`\n"
        formula_deep_dives += "\n"

r02 = f"""# 标题与文案分析

## 一、标题基础数据

| 指标 | 数值 |
|------|------|
| 总笔记数 | {P.get('total_notes','?')} |
| 平均标题长度 | {TA.get('avg_length','?') if isinstance(TA.get('avg_length'), (int, float)) else '?'} 字 |
| 整体均赞 | {P.get('avg_likes','?')} |

## 二、标题特征统计

| 特征 | 使用次数 | 使用率 | 均赞 | vs 基线 | 效果判定 |
|------|---------|-------|------|---------|---------|
{feat_rows}

**关键发现**:
{chr(10).join(f'- {f}' for f in title_findings) if title_findings else '标题数据不足以得出显著模式。'}

## 三、标题公式库

| 公式名 | 使用频次 | 占比 | 均赞 | vs均值 | 爆款率 | 最佳标题 |
|-------|---------|------|------|--------|-------|---------|
{formula_rows}

"""

if formula_deep_dives:
    r02 += formula_deep_dives
else:
    r02 += "标题公式需要更多数据样本才能提取有意义的模式。\n\n"

if CONTENT_TEXT_OK:
    r02 += f"""## 四、正文结构分析

### Hook 模式（基于已采集正文样本）

已采集 {Q.get('content_sample_count', 0)} 篇有效正文，在本次分层详情样本中覆盖 {round(Q.get('content_sample_completeness', 0) * 100, 1)}%。正文只做样本内结构观察，不推断全部历史内容。

### 正文结构模板

当前版本不硬套通用模板。建议在证据样本中复核开头承诺、主体信息和结尾动作，再做 3 篇受控测试。
"""
else:
    r02 += f"""## 四、正文结构分析

有效正文为 {Q.get('content_sample_count', 0)} 篇，未达到本次所需的 {Q.get('detail_required_count', 0)} 篇分层样本门槛。本报告不输出 Hook、正文结构模板或 CTA 策略。
"""

r02 += dimension_evidence_section('title_hook')
w('02_标题与文案分析.md', r02)

# ============================================================
# 03_公开点赞表现分析.md
# ============================================================

r03 = f"""# 公开点赞表现分析

## 一、互动分布全景

| 指标 | 数值 |
|------|------|
| 公开点赞总数 | {P.get('total_likes_sum','?')} |
| 平均点赞 | {P.get('avg_likes','?')} |
| 中位数 | {P.get('median_likes','?')} |
| 标准差 | {P.get('std_likes','?')}（{'离散度高，爆款驱动' if P.get('std_likes',0) > P.get('avg_likes',1) else '分布较集中'}） |
| P75 / P25 | {P.get('p75','?')} / {P.get('p25','?')} |
| 最高 / 最低 | {P.get('max_likes','?')} / {P.get('min_likes','?')} |

## 二、帕累托分析（二八定律）

| 指标 | 数值 |
|------|------|
| 前 80% 点赞集中在 | 前 {E.get('pareto_80pct_n_notes','?')} 篇（{E.get('pareto_80pct_pct','?')}%） |
| 前 10% 笔记贡献 | {E.get('top10pct_share','?')}% 的点赞 |
| 前 5 篇贡献 | {E.get('top5_share','?')}% 的点赞 |
| 后 50% 笔记贡献 | 仅 {E.get('bottom50pct_share','?')}% 的点赞 |

**解读**: {'公开点赞集中在少数笔记，复盘时必须同时查看头部样本和账号中位数。' if E.get('pareto_80pct_pct', 100) < 35 else '公开点赞分布相对均匀，单篇异常值对整体判断的影响较小。'}

"""

if TVB:
    top_ratio = round(TVB['top20']['avg_text_length'] / max(TVB['bot20']['avg_text_length'], 1), 1)
    tag_ratio = round(TVB['top20']['avg_tag_count'] / max(TVB['bot20']['avg_tag_count'], 1), 1)
    date_gap = round(TVB['top20']['has_date_ratio'] - TVB['bot20']['has_date_ratio'], 1)
    observed = []
    if top_ratio >= 1.2:
        observed.append(f"高表现详情样本的正文平均更长（{top_ratio} 倍），可作为待验证线索，不能据此认定长正文导致高赞。")
    elif top_ratio <= 0.8:
        observed.append(f"高表现详情样本的正文平均更短（{top_ratio} 倍），可测试更紧凑的表达，但不能据此认定短正文导致高赞。")
    else:
        observed.append(f"两组正文长度接近（{top_ratio} 倍），当前没有明显长度线索。")
    if tag_ratio >= 1.2 or tag_ratio <= 0.8:
        observed.append(f"两组平均标签数存在差异（{tag_ratio} 倍），只说明样本相关性，不代表标签数量带来流量。")
    else:
        observed.append("两组平均标签数接近，当前没有明显数量线索。")
    if abs(date_gap) >= 10:
        observed.append(f"两组含日期比例相差 {abs(date_gap)} 个百分点，只作样本观察，不推断推荐机制。")
    else:
        observed.append("两组含日期比例接近，当前没有明显时效性线索。")
    r03 += f"""## 三、高表现 vs 低表现详情样本对比

本节仅比较已成功采集详情的分层样本：高表现组 {TVB['top20'].get('sample_count', 0)} 篇，低表现组 {TVB['bot20'].get('sample_count', 0)} 篇；可靠度 {TVB.get('reliability', 'low')}。

| 对比维度 | 爆款 Top 20 | 普通 Bottom 20 | 差异倍数 |
|---------|------------|---------------|---------|
| 平均点赞 | {TVB['top20_avg_likes']} | {TVB['bot20_avg_likes']} | {TVB['ratio']}x |
| 平均标签数 | {TVB['top20']['avg_tag_count']} | {TVB['bot20']['avg_tag_count']} | — |
| 平均正文长度 | {TVB['top20']['avg_text_length']:.0f} 字 | {TVB['bot20']['avg_text_length']:.0f} 字 | {top_ratio}x |
| 含日期比例 | {TVB['top20']['has_date_ratio']}% | {TVB['bot20']['has_date_ratio']}% | — |

**样本内观察**:
{chr(10).join(f'- {item}' for item in observed)}

"""
else:
    r03 += """## 三、爆款 vs 普通两极对比

*高表现组或低表现组的有效详情样本少于 3 篇，本次不做正文和标签对比，避免把缺失数据当成零。*

"""

burst_rate_str = '?'
if overall_avg and P.get('total_notes'):
    burst_rate_str = f"{round(burst_note_count / P.get('total_notes', 1) * 100, 1)}%"

r03 += f"""## 四、互动集中度指数

| 级别 | 总赞占比 |
|------|---------|
| 头部 Top 5 篇 | {E.get('top5_share','?')}% |
| Top 10% 笔记 | {E.get('top10pct_share','?')}% |
| Top 20% 笔记 | {E.get('top20pct_share','?')}% |
| 底部 50% 笔记 | {E.get('bottom50pct_share','?')}% |

## 五、点赞表现小结
"""

if CONTENT_TEXT_OK or COMMENT_OK:
    r03 += f"""当前可结合已采集正文样本观察关联特征。建议优先复盘高赞样本的选题对象、标题承诺和内容结构，并用后续 3 篇内容验证；本报告不把相关性写成因果。
"""
else:
    r03 += """当前只有点赞、标题、发布时间等列表数据，缺少足够正文和评论。因此本节只确认“点赞是否集中”，不对高赞原因做确定排序，也不推断用户动机。
"""

r03 += dimension_evidence_section('engagement_drivers')
w('03_互动归因分析.md', r03)

# ============================================================
# 04_发布与公开表现轨迹.md
# ============================================================

bursts_table = ''
for b in G.get('top_bursts', [])[:15]:
    bursts_table += f"| {b['date']} | {b['title'][:50]} | {b['likes']} | {b['ratio_to_avg']}x |\n"

monthly_rows = ''
for row in G.get('monthly_stats', []):
    monthly_rows += f"| {row.get('month')} | {row.get('count')} | {row.get('median_likes')} | {row.get('avg_likes')} | {row.get('max_likes')} |\n"

monthly_stats = G.get('monthly_stats', [])
trajectory_note = '时间样本不足，当前只展示可读取的发布记录。'
if len(monthly_stats) >= 3:
    split = max(1, len(monthly_stats) // 3)
    early = monthly_stats[:split]
    recent = monthly_stats[-split:]
    early_median = statistics.median([m.get('median_likes', 0) for m in early])
    recent_median = statistics.median([m.get('median_likes', 0) for m in recent])
    if early_median > 0:
        delta = round((recent_median / early_median - 1) * 100, 1)
        trajectory_note = f"最近时段的月度点赞中位数相对早期时段 {delta:+.1f}%。这是公开笔记表现变化，不代表粉丝或曝光增长。"

r04 = f"""# 发布与公开表现轨迹

## 一、时间线总览

| 指标 | 数值 |
|------|------|
| 首条笔记 | {G.get('first_month', '?')} |
| 最新笔记 | {G.get('last_month', '?')} |
| 活跃月数 | {G.get('months_active', '?')} 个月 |
| 总篇数 | {P.get('total_notes','?')} |
| 月均发布 | {round(P.get('total_notes',0)/max(G.get('months_active',1),1), 1)} 篇 |

## 二、逐月发布与点赞表现

| 月份 | 发布数 | 点赞中位数 | 平均点赞 | 单月最高 |
|------|-------|-----------|---------|---------|
{monthly_rows or '| 暂无 | 0 | 0 | 0 | 0 |'}

**时段观察**: {trajectory_note}

## 三、关键转折点

| 日期 | 标题 | 点赞 | vs 均值倍数 |
|------|------|------|------------|
{bursts_table}

**说明**: 上表列出相对全账号均赞较高的公开笔记，便于回看选题和标题；不能据此推断账号处于冷启动、增长或成熟阶段。

## 四、互动趋势

| 指标 | 数值 |
|------|------|
| 总爆款数 | {G.get('burst_count', 0)} 篇 |
| 首月 | {G.get('first_month', '?')} |
| 末月 | {G.get('last_month', '?')} |

> {G.get('scope_note', '这里只观察公开笔记的发布与点赞变化，不代表粉丝增长、曝光增长或账号后台流量变化。')}
"""

r04 += dimension_evidence_section('growth_trajectory')
w('04_成长轨迹分析.md', r04)

# ============================================================
# 05_标签与SEO分析.md
# ============================================================
if TAG_HAS_DATA:
    tag_rows = ''
    for i, t in enumerate(TG['top30'][:20]):
        tag_type = '高频样本词' if t['count'] > 10 else '重复样本词' if t['count'] > 5 else '长尾样本词'
        tag_rows += f"| {i+1} | {t['tag']} | {t['count']} | {tag_type} |\n"

    core_tags = [t['tag'] for t in TG['top30'][:5]]

    r05 = f"""# 标签与 SEO 分析

## 一、标签总览

| 指标 | 数值 |
|------|------|
| 唯一标签总数 | {TG.get('total_unique', 0)} 个 |
| 标签总引用 | {TG.get('total_mentions', 0)} 次 |
| 详情样本数 | {TG.get('detail_sample_count', Q.get('detail_sample_count', 0))} 篇 |
| 有标签样本 | {TG.get('sample_note_count', Q.get('tag_sample_count', 0))} 篇 |
| 详情样本内覆盖 | {TG.get('sample_coverage_pct', round(Q.get('tag_sample_completeness', 0) * 100, 1))}% |

## 二、高频标签 TOP 20

| 排名 | 标签 | 使用次数 | 类型 |
|------|------|---------|------|
{tag_rows}

## 三、标签与搜索表达观察

### 高频标签样本
```
{' · '.join(['#' + t for t in core_tags])}
```

这些标签只代表已采集详情样本中的使用频次，不代表平台搜索量或关键词热度。

### 下一轮测试建议
1. 从高频词中选 1-2 个与内容真正一致的表达，不机械复制整组标签。
2. 标题、正文关键词与标签保持语义一致，一次只测试一套表达。
3. 连续记录至少 3 篇新内容的公开表现，再判断是否保留。

> {TG.get('source_scope', '')}
"""
else:
    r05 = """# 标签与 SEO 分析

*有效标签详情样本未达到本次分析门槛，因此不输出标签组合或 SEO 策略。*

## 如何获取标签数据

点击“补充正文与标签分析”，系统会按高赞、低赞、中位、近期和主题分层补采；达到门槛后再生成样本内观察。
"""

r05 += dimension_evidence_section('tag_search')
w('05_标签与SEO分析.md', r05)

# ============================================================
# 06_商业化分析.md
# ============================================================
if C:
    organic_avg = C.get('avg_likes_organic', 0)
    commercial_avg = C.get('avg_likes_commercial', 0)
    ratio = round(commercial_avg / max(organic_avg, 1) * 100, 1)
    detected_count = C.get('detected_count', 0)
    detected_pct = C.get('detected_pct', 0)

    if detected_count <= 0:
        r06 = f"""# 商业化分析

## 一、商业化数据概览

| 指标 | 数值 | 评估 |
|------|------|------|
| 检测到的商业内容 | 0 篇 | 未检测到明确商业样本 |
| 自然内容均赞 | {organic_avg} | 基准线 |
| 商业 vs 自然差距 | - | 0 个商业样本，不能比较损耗或增益 |

## 二、变现路径识别

当前只能说明：在标题和列表元数据中未检测到明确商单/推广信号。由于没有正文、评论、置顶链接和商品组件数据，本报告不判断真实商业化阶段，也不评估商业内容表现。
"""
    elif not C.get('comparison_ready'):
        titles = '、'.join(C.get('detected_titles', [])[:5]) or '无'
        r06 = f"""# 商业化信号观察

## 一、检测结果

在公开标题和已采集正文中检测到 {detected_count} 篇可能含合作/推广表达的样本，占 {detected_pct}%。代表标题：{titles}。

样本少于 5 篇，不能稳定比较商业样本与其他内容，也不能判断商业化阶段、收入、转化或粉丝接受度。

## 二、交付建议

如客户关心商业化，请人工复核上述样本，并补充店铺、合作标记、置顶内容或客户提供的后台信息；在没有这些证据前，本报告只给信号清单。

> {C.get('signal_scope', '')}
"""
    else:
        r06 = f"""# 商业化分析

## 一、商业化数据概览

| 指标 | 数值 | 评估 |
|------|------|------|
| 检测到的商业内容 | {detected_count} 篇 | {detected_pct}% |
| 商业信号样本均赞 | {commercial_avg} | 公开点赞样本值 |
| 自然内容均赞 | {organic_avg} | 基准线 |
| 信号样本 / 其他样本 | {ratio}% | 相关性观察，不代表商业内容造成变化 |

## 二、样本内观察

商业信号样本与其他样本存在公开点赞差异，但这不能证明商业内容带来增益或损耗。建议人工复核被识别样本是否确为合作内容，再结合客户目标做定价、选品或合作策略。

## 三、证据边界

{C.get('signal_scope', '')}
"""
else:
    r06 = """# 商业化分析

*商业化检测基于标题关键词匹配，当前未检测到明显的商业内容。*
"""

r06 += dimension_evidence_section('commercial_signals')
w('06_商业化分析.md', r06)

# ============================================================
# 07_竞争定位分析.md
# ============================================================

positioning_line = "当前主题分类覆盖不足，只能做单账号基础画像，不判断象限定位。"
if TOPIC_OK and main_topics:
    positioning_line = "以内容主题和标题特征观察，账号更偏行业观察/实用评测混合型。"

r07 = f"""# 单账号内容坐标与竞争假设

*完整竞争定位需要对比同赛道 3-5 个博主。以下为基于单一博主内容特征的初步推断。*

## 一、内容坐标系定位

```
                    深度（长文+观点）
                        ↑
                        │
             实用派     │     思辨派
            (教程/工具)  │   (观点/趋势)
                        │
        ────────────────┼────────────────→ 广度（题材多元）
                        │
             资讯派     │      娱乐派
            (热点速递)  │   (轻松/趣味)
                        │
                        ↓
                    浅度（短文+资讯）
```

**该博主定位**: {positioning_line}

## 二、账号特征总览

| 维度 | 数据 |
|------|------|
| 内容总量 | {P.get('total_notes','?')} 篇 |
| 图文/视频 | {P.get('image_count','?')} / {P.get('video_count','?')} |
| 均赞 | {P.get('avg_likes','?')} |
| 创作周期 | ~{G.get('months_active', '?')} 个月 |
| 内容集中度 | Top {E.get('pareto_80pct_pct','?')}% 笔记占 80% 点赞 |

## 三、单账号特征（不是竞品对比）

| 维度 | 该博主 | 证据边界 |
|------|-------|-------------|
| 内容深度 | 暂不评分 | 缺少正文数据，不能判断深度 |
| 更新频率 | {'★★★★☆' if P.get('total_notes',0)/max(G.get('months_active',1),1) > 15 else '★★★☆☆'} | 基于发布时间和样本量 |
| 内容广度 | {'暂不评分' if not TOPIC_OK else '★★★☆☆'} | {'主题未归类比例偏高' if not TOPIC_OK else '基于已归类主题观察'} |
| 差异化 | {'暂不判断' if not main_topics else '候选方向：' + '/'.join(main_topics[:2])} | 缺少同赛道账号，不能判断差异化优势 |

## 四、壁垒与可复制性评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 方法论可复制 | 暂不评分 | 需要正文样本和对标账号才能判断 |
| 时间积累壁垒 | ★★★☆☆ | {G.get('months_active', 0)} 个月内容沉淀是事实，但壁垒强弱需对标验证 |
| 人设门槛 | 暂不评分 | 缺少正文和评论，不判断人设门槛 |
| 生产成本 | 暂不评分 | 仅凭标题和点赞不能判断真实生产成本 |

**综合评估**: 单账号数据不足以判断可复制性，建议补充 3-5 个同赛道账号后再做竞争定位。
"""

w('07_竞争定位分析.md', r07)

# ============================================================
# 08_策略建议与行动计划.md
# ============================================================

real_burst_rate = round(burst_note_count / max(P.get('total_notes', 1), 1) * 100, 1) if P.get('total_notes') else 0
reliable_topics = [
    (name, data) for name, data in sorted(T.items(), key=lambda x: x[1].get('avg_likes', 0), reverse=True)
    if TOPIC_OK and is_reliable_topic(name, data, 8)
    and data.get('avg_likes', 0) >= overall_avg * 1.15
    and data.get('median_likes', 0) >= overall_median * 1.1
]
topic_test = reliable_topics[0] if reliable_topics else None
positive_formulas = [
    (name, data) for name, data in {**dynamic_formulas, **TF}.items()
    if is_recommendable_pattern(data)
]
positive_formulas.sort(key=lambda item: item[1].get('median_likes', 0), reverse=True)
title_test = positive_formulas[0] if positive_formulas else None

topic_block = (
    f"优先验证「{topic_test[0]}」：{topic_test[1].get('count')} 篇，点赞中位数 {topic_test[1].get('median_likes')}、均值 {topic_test[1].get('avg_likes')}。"
    if topic_test else
    "当前没有同时通过样本量、均值和中位数门槛的主题，不给固定内容配比。"
)
title_block = (
    f"优先验证「{title_test[0]}」：{title_test[1].get('count')} 篇，点赞中位数相对基线 {title_test[1].get('vs_median_pct', 0):+.1f}%。"
    if title_test else
    "当前没有通过稳健门槛的标题模式，不输出万能标题公式。"
)
body_block = (
    f"已获得 {Q.get('content_sample_count', 0)} 篇有效正文，可从证据样本逐篇拆解开头承诺、主体信息和结尾动作；不生成脱离原文的通用模板。"
    if CONTENT_TEXT_OK else
    f"有效正文 {Q.get('content_sample_count', 0)} 篇，未达到 {Q.get('detail_required_count', 0)} 篇门槛，正文策略暂缓。"
)
tag_block = (
    f"已获得 {Q.get('tag_sample_count', 0)} 篇标签样本，只测试标题、正文关键词与标签的一致性，不把频次当搜索热度。"
    if TAG_HAS_DATA else
    "标签样本未达到门槛，不输出 SEO 或固定标签组合。"
)

r08 = f"""# 策略建议与行动计划

## 一、结论先行

1. {topic_block}
2. {title_block}
3. 公开点赞中位数为 {P.get('median_likes', '?')}；Top {E.get('pareto_80pct_pct', '?')}% 笔记贡献 80% 点赞，复盘必须同时看典型样本与高赞样本。
4. {body_block}
5. {tag_block}

以上是本次公开样本支持的测试优先级，不是平台机制、用户动机或因果结论。

## 二、未来 7 天执行表

| 天数 | 动作 | 完成标准 |
|------|------|---------|
| 第 1 天 | 复核报告引用的 5 条高赞证据 | 写下对象、场景、标题承诺和实际内容 |
| 第 2 天 | 选择 1 个待测试主题 | 只改主题，不同时改多个变量 |
| 第 3 天 | 为同一选题写 10 个标题 | 保留 3 个信息具体、正文能兑现的版本 |
| 第 4 天 | 完成 1 篇内容 | 不套通用模板，逐项核对标题与正文一致 |
| 第 5 天 | 发布并记录 | 记录主题、标题、时间和公开可见数据 |
| 第 6 天 | 与账号中位数比较 | 不只和最高赞比较，不以单篇下结论 |
| 第 7 天 | 决定下一轮 | 至少累计 3 次同类测试后再放大或停止 |

## 三、明确避坑

- 不根据单篇爆款认定“用户喜欢某主题”。
- 不根据平均值单独推荐标题，必须同时通过中位数与样本量门槛。
- 不把标签使用频次写成搜索量，不承诺排名或流量。
- 不从公开点赞推断粉丝增长、曝光增长、收入或用户画像。
- 不在没有竞品样本时声称具有赛道优势。

## 四、后续复盘看板

| 指标 | 当前值 | 使用方式 |
|------|-------|---------|
| 点赞中位数 | {P.get('median_likes','?')} | 作为常态基线 |
| 平均点赞 | {P.get('avg_likes','?')} | 与中位数一起看，识别异常值影响 |
| 高表现样本率 (>2x均赞) | {real_burst_rate}% | 只作历史分布观察 |
| 月均发布 | ~{round(P.get('total_notes',0)/max(G.get('months_active',1),1), 1)} | 观察节奏，不直接给频次目标 |
"""

r08 += dimension_evidence_section('action_plan')
w('08_策略建议与行动计划.md', r08)

# ============================================================
# README.md (Index)
# ============================================================

best_topic_name = ''
best_topic_avg = 0
if T:
    topic_candidates = [
        item for item in T.items()
        if (
            TOPIC_OK
            and is_reliable_topic(item[0], item[1])
            and item[1].get('avg_likes', 0) >= overall_avg * 1.15
        )
    ]
    if topic_candidates:
        bt = max(topic_candidates, key=lambda x: x[1]['avg_likes'])
        best_topic_name = bt[0]
        best_topic_avg = bt[1]['avg_likes']
    else:
        best_topic_name = '分类可信度不足，暂不判断'
        best_topic_avg = '-'

idx = f"""# 小红书博主深度研究报告：{nickname}

## 报告清单

| # | 文件 | 定位 | 核心拆解项 |
|---|------|------|-----------|
| 00 | [博主画像卡片](00_博主画像卡片.md) | 总览层 | 内容覆盖 · 基础数据看板 · 受众信息边界 · 表达要素 |
| 01 | [内容结构分析](01_内容结构分析.md) | 生产层 | 主题分布总览 · 各主题深度分析 · 内容形态效率对比 · 系列化内容聚类 · 内容密度 |
| 02 | [标题与文案分析](02_标题与文案分析.md) | 文本层 | 标题基础特征统计 · 标题公式库 · 正文模块按覆盖率降级 |
| 03 | [公开点赞表现](03_互动归因分析.md) | 数据层 | 点赞分布 · 帕累托分析 · 分层详情样本对比 · 证据边界 |
| 04 | [发布与公开表现轨迹](04_成长轨迹分析.md) | 时间层 | 逐月发布 · 中位数变化 · 高表现样本时间线 |
| 05 | [标签与搜索表达](05_标签与SEO分析.md) | 文本层 | 详情样本覆盖 · 高频标签 · 一致性测试建议 |
| 06 | [商业化分析](06_商业化分析.md) | 变现层 | 商业信号检测 · 有样本才比较表现 |
| 07 | [内容坐标与竞争假设](07_竞争定位分析.md) | 策略层 | 单账号基础观察 · 对标不足时明确降级 |
| 08 | [策略建议与行动计划](08_策略建议与行动计划.md) | 执行层 | 核心发现 · 内容/标题策略 · 模板库 · 三段式落地清单 · 指标看板 |

## 核心数据速览

| 指标 | 数值 |
|------|------|
| 大盘笔记总数 | {P.get('total_notes','?')} |
| 平均点赞 (Mean) | {P.get('avg_likes','?')} |
| 中位数 (Median) | {P.get('median_likes','?')} |
| 最高赞 (Max) | {P.get('max_likes','?')} |
| 创作周期 (Timeline) | ~{G.get('months_active', '?')} 个月 |
| 形态大盘 | {P.get('image_count',0)} 图文 / {P.get('video_count',0)} 视频 |
| 最佳内容类型 | {best_topic_name}（均赞 {best_topic_avg}）|

## 分析方法论矩阵

| 分析维度 | 微观拆解要素 | 数据源/底层逻辑 |
|---------|-------------|----------------|
| 博主画像 | 内容覆盖、表达观察 | 全量笔记元数据 + 平台公开信息，评论不足时不推断受众与痛点 |
| 内容结构 | 8类主题分布、图文vs视频、系列化检测 | {P.get('total_notes','?')} 条笔记元数据 |
| 标题与文案 | 标题特征量化、公式检测 | {P.get('total_notes','?')} 条标题；正文覆盖率 {round(Q.get('content_text_completeness', 0) * 100, 1)}% |
| 点赞表现 | 分布特征、极端值、分层详情样本对照、帕累托系数 | {P.get('total_notes','?')} 条公开点赞数据 |
| 发布轨迹 | 逐月发布、点赞中位数变化 | {P.get('total_notes','?')} 条时间序列；不代表粉丝或曝光增长 |
| 标签与搜索表达 | 样本内频次、一致性测试 | {'分层详情标签样本' if TAG_HAS_DATA else '数据不足（已降级）'} |
| 商业化 | 商业信号检测 | 标题关键词弱检测；0 商业样本时不比较表现 |
| 竞争定位 | 单账号基础观察 | 缺少对标账号时不判断可复制性 |

## 数据资产清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `all_notes.json` | 原始元数据大盘 | 包含 {P.get('total_notes','?')} 条笔记的发布时间、互动数、标题等基础字段 |
| `results.json` | 量化分析结果 | 所有分析维度的结构化计算结果 |

## 可信度分级量尺

- **事实**: 可直接从公开样本读取或计算，例如样本数、点赞中位数、发布月份。
- **线索**: 同时通过样本量、均值和中位数门槛的相关性，适合优先测试，不代表因果。
- **暂缓**: 数据缺失、样本过少或需要竞品/后台信息的模块，不输出确定策略。
"""

w('README.md', idx)

print(f"\n{'='*40}")
print(f"All reports generated in: {out}")
print(f"{'='*40}")
