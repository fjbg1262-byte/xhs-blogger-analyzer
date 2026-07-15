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
TAG_HAS_DATA = bool(TG.get('top30') or TG.get('total_mentions', 0))

nickname = P.get('nickname', '未知博主')
overall_avg = P.get('avg_likes', 0)
overall_median = P.get('median_likes', 0)
burst_threshold = max(overall_avg * 2, 1000)
LOW_INFO_TOPIC_NAMES = {'其他/未分类', '其它/未分类', '未分类', '其他', '未归类观察', '日常随手记录'}
CONTENT_TEXT_OK = Q.get('content_text_completeness', 0) >= 0.5
TAG_OK = Q.get('tag_completeness', 0) >= 0.5
COMMENT_OK = Q.get('comment_completeness', 0) >= 0.5
TOPIC_OK = Q.get('topic_unclassified_pct', 0) <= 50

def is_low_info_topic(name):
    return any(token in str(name) for token in LOW_INFO_TOPIC_NAMES)

def is_recommendable_pattern(data, min_count=3, min_lift=20):
    return data.get('count', 0) >= min_count and data.get('vs_overall_pct', data.get('vs_baseline_pct', 0)) > min_lift

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
        burst = len([lk for lk in likes if lk > burst_threshold])
        above_avg = len([lk for lk in likes if lk > overall_avg]) if overall_avg else 0
        found[pname] = {
            'count': len(matched),
            'pct': round(len(matched) / len(title_data) * 100, 1),
            'avg_likes': round(avg, 1),
            'vs_baseline_pct': round((avg / overall_avg - 1) * 100, 1) if overall_avg else 0,
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
            burst = len([lk for lk in likes if lk > burst_threshold])
            name = f'{p1.split("（")[0]} + {p2.split("（")[0]}'
            top_note = max(matched, key=lambda x: x[1])
            formulas[name] = {
                'count': len(matched),
                'pct': round(len(matched) / len(title_data) * 100, 1),
                'avg_likes': round(avg, 1),
                'vs_overall_pct': round((avg / overall_avg - 1) * 100, 1),
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

def classify_topic_emoji(cat, s):
    if s['burst_rate'] > 20: return '🔥'
    if s['avg_likes'] > overall_avg: return '📈'
    return '📊'

# ============================================================
# 00_博主画像卡片.md
# ============================================================

top_cats = sorted(T.items(), key=lambda x: x[1]['count'], reverse=True) if T else []
main_topics = [c for c, d in top_cats if is_reliable_topic(c, d)][:3]
if main_topics:
    audience_desc = '、'.join(main_topics) + '关注者'
else:
    audience_desc = '该账号内容受众（当前主题分类覆盖不足，暂不细分人群）'

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
    style_parts.append('理性客观、信息密度高')

domain = main_topics[0] if main_topics else '内容观察'
positioning = f'{domain}领域内容创作者'
if T and TOPIC_OK:
    top_roi = sorted(T.items(), key=lambda x: x[1]['avg_likes'], reverse=True)
    if top_roi:
        for tc, td in top_roi:
            if is_reliable_topic(tc, td):
                positioning += f'，以{tc}内容为特色'
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
| 视频占比 | {P.get('video_count',0)} ({CT.get('video',{}).get('pct','?')}%) |
| 创作周期 | ~{G.get('months_active', '?')} 个月 |
| 均赞/中位数 | {P.get('avg_likes','?')} / {P.get('median_likes','?')} |
| 最高赞 | {P.get('max_likes','?')} |
| 标准差 | {P.get('std_likes','?')}（{'波动极大，爆款驱动型' if P.get('std_likes',0) > P.get('avg_likes',1) else '分布相对集中'}） |

## 用户画像（从内容推断）

| 维度 | 特征 |
|------|------|
| 核心受众 | {audience_desc} |
| 受众痛点 | 当前缺少评论/正文数据，暂不推断具体痛点 |
| 内容消费场景 | 当前缺少用户行为数据，暂不推断消费场景 |
| 受众水平 | 仅可从标题和选题粗略观察，暂不做确定判断 |

## 人设要素

| 要素 | 表现 |
|------|------|
| 语言风格 | {''.join(style_parts)} |
| 内容价值观 | 需结合正文进一步判断 |
| 差异化定位 | 内容覆盖 {'、'.join(main_topics[:3]) if main_topics else '多个方向（当前主题分类不足）'} |
| 人格化标签 | {nickname} |

### 实际标题特征表现
{dynamic_style_lines}
"""

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
        cat_type = '主力类型' if s['count'] > 30 else '补充类型' if s['count'] > 10 else '尝试型'
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
        elif s['burst_rate'] > 20 and s['count'] > 20 and s['avg_likes'] >= overall_avg * 1.1:
            r01 += f"**策略建议**: 主力赛道。{s['count']}篇高产 + {s['burst_rate']}%爆款率，是账号核心基本盘。建议保持投入。\n\n"
        elif s['avg_likes'] > overall_avg * 1.5 and s['count'] >= 5:
            r01 += f"**策略建议**: 高ROI类型——仅{s['count']}篇产出均赞{s['avg_likes']}（整体均值{round(overall_avg)}），是拉升均赞的关键杠杆。建议增加占比。\n\n"
        elif s['burst_rate'] > 20 and s['count'] >= 5:
            r01 += f"**策略建议**: 小而美的爆款赛道。产量低（{s['count']}篇）但爆款率{s['burst_rate']}%，值得作为差异化内容定期输出。\n\n"
        elif s['avg_likes'] < overall_avg * 0.7:
            r01 += f"**策略建议**: 互动效率偏低（均赞{s['avg_likes']}，为整体均值{round(overall_avg)}的{round(s['avg_likes']/overall_avg*100)}%），建议控制发布比例或优化内容形式。\n\n"
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
        r01 += "\n**系列化内容有助于形成用户预期和长尾流量，建议持续做系列化。**\n\n"
    else:
        r01 += """## 四、系列化内容

未检测到明显的系列化内容（基于关键词聚类）。建议有意识地规划系列选题以沉淀粉丝预期。

"""

r01 += f"""## 五、内容密度

| 指标 | 数值 |
|------|------|
| 活跃月数 | {G.get('months_active', '?')} 个月 |
| 月均发布 | {round(P.get('total_notes',0)/max(G.get('months_active',1),1), 1)} 篇 |
| 周均发布 | {round(P.get('total_notes',0)/max(G.get('months_active',1),1)/4, 1)} 篇 |
"""

w('01_内容结构分析.md', r01)

# ============================================================
# 02_标题与文案分析.md  — 数据驱动版
# ============================================================

feat_rows = ''
if dynamic_patterns:
    for pname, pdata in sorted(dynamic_patterns.items(), key=lambda x: x[1]['avg_likes'], reverse=True):
        effect = '✅ 有效' if pdata['vs_baseline_pct'] > 5 else ('❌ 偏低' if pdata['vs_baseline_pct'] < -10 else '→ 中性')
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
    if best_pattern and best_pattern[1]['vs_baseline_pct'] > 10:
        title_findings.append(f"**{best_pattern[0]}** 是最有效的标题特征，使用率 {best_pattern[1]['pct']}%，均赞 {best_pattern[1]['avg_likes']}，vs 基准 {best_pattern[1]['vs_baseline_pct']:+.1f}%")

    most_used = sorted(dynamic_patterns.items(), key=lambda x: x[1]['pct'], reverse=True)[0]
    title_findings.append(f"**{most_used[0]}** 使用频率最高（{most_used[1]['pct']}%），均赞 {most_used[1]['avg_likes']}，{'效果良好' if most_used[1]['vs_baseline_pct'] > 0 else '表现一般'}")

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
- **均赞**: {fdata['avg_likes']}（{direction}整体均值 {abs(fdata['vs_overall_pct'])}%）
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
    r02 += """## 四、正文结构分析

### Hook 模式（基于已采集正文样本）

正文覆盖率已达到分析门槛，可结合爆款和普通样本继续拆解 Hook、正文结构和 CTA。

### 正文结构模板

后续版本将基于真实正文样本生成账号专属模板。
"""
else:
    r02 += f"""## 四、正文结构分析

正文覆盖率为 {round(Q.get('content_text_completeness', 0) * 100, 1)}%，低于 50% 分析门槛。本报告不输出 Hook、正文结构模板或 CTA 策略，避免把通用模板误写成该账号规律。
"""

w('02_标题与文案分析.md', r02)

# ============================================================
# 03_互动归因分析.md
# ============================================================

r03 = f"""# 互动归因分析

## 一、互动分布全景

| 指标 | 数值 |
|------|------|
| 总互动量 | {P.get('total_likes_sum','?')} |
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

**解读**: {'这是一个典型的"爆款驱动型"账号——少数笔记贡献了绝大多数互动。成功的关键不是篇篇爆款，而是持续生产"可能爆款"的内容。' if E.get('pareto_80pct_pct', 100) < 35 else '内容互动分布相对均匀，说明账号具备稳定输出的能力，不依赖单篇爆款。'}

"""

if TVB:
    top_ratio = round(TVB['top20']['avg_text_length'] / max(TVB['bot20']['avg_text_length'], 1), 1)
    r03 += f"""## 三、爆款 vs 普通两极对比

| 对比维度 | 爆款 Top 20 | 普通 Bottom 20 | 差异倍数 |
|---------|------------|---------------|---------|
| 平均点赞 | {TVB['top20_avg_likes']} | {TVB['bot20_avg_likes']} | {TVB['ratio']}x |
| 平均标签数 | {TVB['top20']['avg_tag_count']} | {TVB['bot20']['avg_tag_count']} | — |
| 平均正文长度 | {TVB['top20']['avg_text_length']:.0f} 字 | {TVB['bot20']['avg_text_length']:.0f} 字 | {top_ratio}x |
| 含日期比例 | {TVB['top20']['has_date_ratio']}% | {TVB['bot20']['has_date_ratio']}% | — |

**关键发现**:
- 爆款笔记的正文长度是普通笔记的 {top_ratio} 倍——深度内容更易引爆
- 标签数量差异不大，关键在于标签质量而非数量
- 含日期的笔记在爆款中比例更高，时效性内容更容易获得推荐

"""
else:
    r03 += """## 三、爆款 vs 普通两极对比

*正文内容数据未采集（需要 contents.json），无法进行爆款 vs 普通的正文对比分析。*

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

## 五、互动归因小结
"""

if CONTENT_TEXT_OK or COMMENT_OK:
    r03 += f"""当前可结合已采集正文/评论继续判断互动归因。初步看，互动高度集中，建议优先复盘 Top 样本的选题对象、标题承诺和内容结构。
"""
else:
    r03 += """当前只有点赞、标题、发布时间等列表数据，缺少正文和评论。因此本节只确认“互动是否集中”，不对爆款原因做确定排序，也不推断用户评论动机。
"""

w('03_互动归因分析.md', r03)

# ============================================================
# 04_成长轨迹分析.md
# ============================================================

bursts_table = ''
for b in G.get('top_bursts', [])[:15]:
    bursts_table += f"| {b['date']} | {b['title'][:50]} | {b['likes']} | {b['ratio_to_avg']}x |\n"

bursts = G.get('top_bursts', [])

# Data-driven growth phase descriptions
monthly_ma = G.get('monthly_avg_likes', {})
sorted_months = sorted(monthly_ma.keys())
phase_desc_1 = ''
phase_desc_2 = ''
phase_desc_3 = ''
phase_desc_4 = ''

if sorted_months and bursts:
    first_month_val = monthly_ma.get(sorted_months[0], 0)
    first_burst = bursts[0]
    peak_month = max(monthly_ma.items(), key=lambda x: x[1]) if monthly_ma else ('', 0)

    # Phase 1: Cold start
    p1_months = sorted_months[:max(3, len(sorted_months)//5)]
    p1_avg = round(statistics.mean([monthly_ma[m] for m in p1_months])) if len(p1_months) > 0 else 0
    p1_range = f'{p1_months[0]} ~ {p1_months[-1]}' if len(p1_months) >= 2 else (p1_months[0] if p1_months else '?')

    early_burst_in_p1 = first_burst.get('date', '')[:7] == p1_months[0] if p1_months else False
    fb_likes = first_burst.get('likes', 0)
    early_desc = f'首月即出现爆款（{fb_likes}赞）' if early_burst_in_p1 else '以基础内容积累为主，尚无爆款'

    phase_desc_1 = f"""### 阶段 1: 冷启动期（{p1_range}）

- **内容特征**: 早期以基础评测和工具分享为主，方向尚在摸索
- **互动表现**: 月均点赞约 {p1_avg}，{early_desc}
- **产出节奏**: 初步建立更新习惯"""

    # Phase 2: Breakthrough
    big_burst = None
    for b in bursts:
        if b.get('ratio_to_avg', 0) > 5:
            big_burst = b
            break
    if not big_burst:
        big_burst = bursts[0] if bursts else None

    if big_burst:
        phase_desc_2 = f"""### 阶段 2: 定位确立期（~{big_burst['date'][:7]}）

- **触发事件**: 「{big_burst['title'][:50]}」成为爆款（{big_burst['likes']} 赞，{big_burst['ratio_to_avg']}x 均值）
- **内容特征**: {'评测类内容占比提升' if T.get('AI模型/产品评测',{}).get('count',0) > 50 else '内容方向逐渐聚焦'}，形成固定更新节奏
- **互动跃迁**: 均赞站上 {round(big_burst['likes']/big_burst.get('ratio_to_avg',1))} 量级
- **IP 确立**: 通过持续输出建立领域认知"""
    else:
        phase_desc_2 = ''

    # Phase 3: Growth surge
    if peak_month[0] and peak_month[1] > p1_avg * 1.3:
        peak_idx = sorted_months.index(peak_month[0]) if peak_month[0] in sorted_months else len(sorted_months)//2
        p3_months = sorted_months[max(0, peak_idx-2):min(len(sorted_months), peak_idx+3)]
        p3_range = f'{p3_months[0]} ~ {p3_months[-1]}'
        p3_content_desc = f'形成"AI评测 + 教程 + 观点"内容矩阵' if T.get('教程/干货',{}).get('count',0) > 15 else f'以{T.get("AI模型/产品评测",{}).get("count",0) if T.get("AI模型/产品评测") else 0}篇评测覆盖热门话题'
        p3_burst_desc = f'爆款频出（共{G.get("burst_count",0)}篇）' if G.get('burst_count',0) > 15 else f'最高赞达{max(b.get("likes",0) for b in bursts)}'

        phase_desc_3 = f"""### 阶段 3: 增长爆发期（{p3_range}）

- **核心表现**: 月均点赞达 {round(peak_month[1])}，为历史峰值
- **内容结构**: {p3_content_desc}
- **爆款态势**: {p3_burst_desc}
- **内容形态**: {'持续深耕图文（图文占比' + str(normal.get('pct',0)) + '%）' if normal.get('pct',0) > 50 else '图文视频并重'}"""
    else:
        phase_desc_3 = ''

    # Phase 4: Maturity
    recent = sorted_months[-3:] if len(sorted_months) >= 3 else sorted_months[-min(len(sorted_months), 1):]
    if recent:
        recent_avg = round(statistics.mean([monthly_ma[m] for m in recent]))
        recent_range = f'{recent[0]} ~ {recent[-1]}' if len(recent) >= 2 else recent[0]
        monthly_count = round(P.get('total_notes',0)/max(G.get('months_active',1),1)) if P.get('total_notes') else 0
        recent_stable = '均赞趋于稳定' if max(monthly_ma[m] for m in recent) - min(monthly_ma[m] for m in recent) < 200 else '均赞仍有波动'
        comm_signal = f'检测到{C.get("detected_count",0)}篇商业内容（占{C.get("detected_pct",0)}%）' if C.get('detected_count',0) > 0 else '基本无商业内容，以自然增长为主'

        phase_desc_4 = f"""### 阶段 4: 成熟运营期（{recent_range}）

- **运营状态**: 稳定更新（月均~{monthly_count}篇）
- **互动表现**: 月均点赞约 {recent_avg}，{recent_stable}
- **商业化信号**: {comm_signal}
- **增长评估**: {'均赞增长放缓，需新爆款破局' if max(monthly_ma[m] for m in recent) < peak_month[1] * 0.8 and peak_month[1] > 0 else '均赞维持健康水平'}"""

# Fallback if data insufficient
if not phase_desc_1:
    phase_desc_1 = """### 阶段 1: 冷启动期

- **内容特征**: 内容定位探索阶段
- **互动表现**: 均赞较低"""
if not phase_desc_2:
    phase_desc_2 = """### 阶段 2: 定位确立期

- **触发事件**: 首条爆款出现
- **内容特征**: 内容方向逐渐聚焦"""
if not phase_desc_3:
    phase_desc_3 = """### 阶段 3: 增长爆发期

- **内容特征**: 形成稳定的内容结构
- **互动表现**: 均赞显著提升"""
if not phase_desc_4:
    phase_desc_4 = """### 阶段 4: 成熟运营期

- **状态**: 进入稳定更新节奏
- **互动表现**: 均赞稳定"""

r04 = f"""# 成长轨迹分析

## 一、时间线总览

| 指标 | 数值 |
|------|------|
| 首条笔记 | {G.get('first_month', '?')} |
| 最新笔记 | {G.get('last_month', '?')} |
| 活跃月数 | {G.get('months_active', '?')} 个月 |
| 总篇数 | {P.get('total_notes','?')} |
| 月均发布 | {round(P.get('total_notes',0)/max(G.get('months_active',1),1), 1)} 篇 |

## 二、成长阶段划分

{phase_desc_1}

{phase_desc_2}

{phase_desc_3}

{phase_desc_4}

## 三、关键转折点

| 日期 | 标题 | 点赞 | vs 均值倍数 |
|------|------|------|------------|
{bursts_table}

**趋势解读**:
- 共检测到 {G.get('burst_count', 0)} 篇爆款笔记（>均赞2倍）
- {'爆款频次较高，说明粉丝基础和传播力在持续增长' if G.get('burst_count', 0) > 20 else '爆款分布较为零散，尚未形成稳定的爆款节奏'}
- {'早期爆款和后期爆款的差距表明受众规模在扩大' if bursts and len(bursts) > 5 else '爆款表现相对稳定'}

## 四、互动趋势

| 指标 | 数值 |
|------|------|
| 总爆款数 | {G.get('burst_count', 0)} 篇 |
| 首月 | {G.get('first_month', '?')} |
| 末月 | {G.get('last_month', '?')} |
"""

w('04_成长轨迹分析.md', r04)

# ============================================================
# 05_标签与SEO分析.md
# ============================================================
if TAG_HAS_DATA:
    tag_rows = ''
    for i, t in enumerate(TG['top30'][:20]):
        tag_type = '核心标签' if t['count'] > 10 else '常用标签' if t['count'] > 5 else '场景标签'
        tag_rows += f"| {i+1} | {t['tag']} | {t['count']} | {tag_type} |\n"

    core_tags = [t['tag'] for t in TG['top30'][:5]]

    r05 = f"""# 标签与 SEO 分析

## 一、标签总览

| 指标 | 数值 |
|------|------|
| 唯一标签总数 | {TG.get('total_unique', 0)} 个 |
| 标签总引用 | {TG.get('total_mentions', 0)} 次 |
| 样本笔记数 | ~{P.get('total_notes', 0)} 篇 |

## 二、高频标签 TOP 20

| 排名 | 标签 | 使用次数 | 类型 |
|------|------|---------|------|
{tag_rows}

## 三、标签组合策略

### 核心固定组合（高频标签）
```
{' · '.join(['#' + t for t in core_tags])}
```

### 标签类型分布
- **核心标签**: 高频固定使用，建立领域关联
- **场景标签**: 低频但精准，匹配搜索意图
- **内容标签**: 与具体笔记主题相关

### 标签策略建议
1. 固定标签组合保持 {len(core_tags)} 个核心标签持续使用
2. 每篇根据内容增加 2-3 个场景/长尾标签
3. 避免使用事件限定标签（如活动名称），搜索量极低
"""
else:
    r05 = """# 标签与 SEO 分析

*标签数据需要采集笔记正文内容（tags 字段）才能分析。当前仅采集了笔记列表数据，缺少正文标签。*

## 如何获取标签数据

在 scrape 步骤之后，需要额外采集每篇笔记的详情页，提取 tags 字段。
"""

w('05_标签与SEO分析.md', r05)

# ============================================================
# 06_商业化分析.md
# ============================================================
if C:
    organic_avg = C.get('avg_likes_organic', 0)
    commercial_avg = C.get('avg_likes_commercial', 0)
    ratio = round(commercial_avg / max(organic_avg, 1) * 100, 1)
    is_early = C.get('detected_pct', 100) < 5
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
    else:
        r06 = f"""# 商业化分析

## 一、商业化数据概览

| 指标 | 数值 | 评估 |
|------|------|------|
| 检测到的商业内容 | {detected_count} 篇 | {detected_pct}% |
| 商业内容均赞 | {commercial_avg} | {'高于自然内容，选品质量高' if commercial_avg > organic_avg else '低于自然内容'} |
| 自然内容均赞 | {organic_avg} | 基准线 |
| 商业 vs 自然差距 | {ratio}% | {'商业内容表现优于自然内容' if commercial_avg > organic_avg else '商业内容尚未明显影响互动质量' if ratio > 70 else '商业内容对互动有明显损耗'} |

## 二、变现路径识别

### 路径 1: 品牌合作/广告
- **状态**: {'存在一定比例的品牌合作' if detected_count > 5 else '商业内容较少，以自然内容为主'}
- **表现**: 商业内容均赞 {commercial_avg}，{'高于自然内容' if commercial_avg > organic_avg else '低于自然内容'}
- **建议**: {'选品质量高，可适度增加合作' if commercial_avg > organic_avg else '当前阶段以内容积累为主，暂不建议大量接商单'}

### 路径 2: 内容变现（知识输出 → 影响力积累）
- 通过持续输出 AI 领域内容积累粉丝信任
- 未来可向知识付费 / 行业咨询 / 课程等方向延伸

### 路径 3: 自有工具/产品化
- **状态**: {'尚未启动' if detected_count < 3 else '初步探索中'}
- {'当前以纯内容创作为主，未检测到自有产品推广迹象' if is_early else '具备产品化能力'}
- 内容侧沉淀的方法论可逐步转化为标准化产品

## 三、商业化「三级火箭」进化评估

| 阶段 | 完成度 | 现状 |
|------|--------|------|
| 🚀 第一级：流量获取 | {'✅' if P.get('total_notes',0) > 100 else '⏳'} | {P.get('total_notes',0)} 篇笔记，月均 {round(P.get('total_notes',0)/max(G.get('months_active',1),1), 1)} 篇稳定更新 |
| 🚀 第二级：用户留存 | {'✅' if P.get('median_likes',0) > 200 else '⏳'} | 中位数点赞 {P.get('median_likes',0)}，{'粉丝粘性较好' if P.get('median_likes',0) > 300 else '粉丝粘性中等'} |
| 🚀 第三级：商业变现 | {'⏳' if is_early else '✅'} | 商业内容占 {detected_pct}%，均赞 {commercial_avg} |

## 四、商业化阶段评估

当前处于 {'早期商业化阶段' if is_early else '商业化探索期' if detected_pct < 15 else '成熟商业化阶段'}。

- 商业内容占比 {detected_pct}%
- {'商业化程度较低，内容生态健康。当前首要任务是扩大内容影响力而非急于变现。' if is_early else '商业与内容在寻找平衡点'}
- **建议**: {'保持当前内容节奏，待粉丝量级突破后再系统规划商业变现' if is_early else '建立品牌合作标准，控制商单比例不超过15%'}
"""
else:
    r06 = """# 商业化分析

*商业化检测基于标题关键词匹配，当前未检测到明显的商业内容。*
"""

w('06_商业化分析.md', r06)

# ============================================================
# 07_竞争定位分析.md
# ============================================================

positioning_line = "当前主题分类覆盖不足，只能做单账号基础画像，不判断象限定位。"
if TOPIC_OK and main_topics:
    positioning_line = "以内容主题和标题特征观察，账号更偏行业观察/实用评测混合型。"

r07 = f"""# 竞争定位分析（单博主版）

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

## 三、差异化优势（与同赛道对比推断）

| 维度 | 该博主 | 推测赛道常态 |
|------|-------|-------------|
| 内容深度 | 暂不评分 | 缺少正文数据，不能判断深度 |
| 更新频率 | {'★★★★☆' if P.get('total_notes',0)/max(G.get('months_active',1),1) > 15 else '★★★☆☆'} | 基于发布时间和样本量 |
| 内容广度 | {'暂不评分' if not TOPIC_OK else '★★★☆☆'} | {'主题未归类比例偏高' if not TOPIC_OK else '基于已归类主题观察'} |
| 差异化 | {'暂不判断' if not main_topics else '基于 ' + '/'.join(main_topics[:2]) + ' 的内容定位'} |

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

findings = []
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
        best_topic = max(topic_candidates, key=lambda x: x[1]['avg_likes'])
        findings.append(f"**{best_topic[0]} ROI 最高**: 均赞 {best_topic[1]['avg_likes']} = 整体均值的 {round(best_topic[1]['avg_likes']/max(overall_avg,1),1)} 倍，爆款率 {best_topic[1]['burst_rate']}%")
    else:
        findings.append("**主题分类可信度不足**: 本次样本中低信息分类占比较高，暂不输出“最佳内容主题”结论。")

video_eff = CT.get('video',{}).get('vs_image_pct', 0)
if video_eff and video_eff < 90:
    findings.append(f"**图文效率是视频的 {round(CT.get('normal',{}).get('avg_likes',0)/max(CT.get('video',{}).get('avg_likes',1),1),1)} 倍**: 视频均赞只有图文的 {video_eff}%")

if dynamic_patterns:
    best_pat = sorted(dynamic_patterns.items(), key=lambda x: x[1]['vs_baseline_pct'], reverse=True)[0]
    if abs(best_pat[1]['vs_baseline_pct']) > 10:
        findings.append(f"**{best_pat[0]}** vs 基准 {best_pat[1]['vs_baseline_pct']:+.1f}%: {'这是该博主最有效的标题手法' if best_pat[1]['vs_baseline_pct'] > 0 else '该模式效果不佳，建议减少使用'}")

findings.append(f"**内容集中度**: Top {E.get('pareto_80pct_pct','?')}% 笔记贡献 80% 点赞，{'典型的爆款驱动型' if E.get('pareto_80pct_pct', 100) < 35 else '分布相对均衡的'}账号")

real_burst_rate = round(burst_note_count / max(P.get('total_notes', 1), 1) * 100, 1) if P.get('total_notes') else 0

# Build title templates from ACTUAL high-performing formula data
template_lines = ''
positive_dynamic_formulas = [
    (fname, fdata) for fname, fdata in dynamic_formulas.items()
    if is_recommendable_pattern(fdata)
]
positive_tf = [
    (fname, fdata) for fname, fdata in TF.items()
    if is_recommendable_pattern(fdata)
]

if positive_dynamic_formulas:
    for fname, fdata in sorted(positive_dynamic_formulas, key=lambda x: x[1]['avg_likes'], reverse=True)[:5]:
        td = fdata
        top_title = td.get('top', '')
        direction = '⬆' if td['vs_overall_pct'] > 0 else '⬇'
        template_lines += f"| **{fname}** | 均赞 {td['avg_likes']}（{direction}{abs(td['vs_overall_pct'])}%） | 爆款率 {td['burst_rate']}% | `{top_title[:40]}` |\n"
elif positive_tf:
    for fname, fdata in sorted(positive_tf, key=lambda x: x[1]['avg_likes'], reverse=True)[:5]:
        direction = '⬆' if fdata['vs_overall_pct'] > 0 else '⬇'
        top_title = fdata.get('top', '')
        template_lines += f"| **{fname}** | 均赞 {fdata['avg_likes']}（{direction}{abs(fdata['vs_overall_pct'])}%） | 爆款率 {fdata['burst_rate']}% | `{top_title[:40]}` |\n"
else:
    template_lines = "| 暂无稳定高表现标题公式 | 本次样本没有满足推荐门槛的标题模式 | - | - |\n"

# Title formula recommendations from dynamic data or fallback
r08_title_recs = ''
top_dyn_formulas = sorted(positive_dynamic_formulas, key=lambda x: x[1]['avg_likes'], reverse=True)[:3]
top_tf = sorted(positive_tf, key=lambda x: x[1]['avg_likes'], reverse=True)[:3]

if top_dyn_formulas:
    for i, (fname, fdata) in enumerate(top_dyn_formulas, 1):
        r08_title_recs += f"{i}. **{fname}** — 均赞 {fdata['avg_likes']}，vs 整体 {'+' if fdata['vs_overall_pct'] > 0 else ''}{fdata['vs_overall_pct']}%\n"
elif top_tf:
    for i, (fname, fdata) in enumerate(top_tf, 1):
        r08_title_recs += f"{i}. **{fname}** — 均赞 {fdata['avg_likes']}，vs 整体 {'+' if fdata['vs_overall_pct'] > 0 else ''}{fdata['vs_overall_pct']}%\n"
else:
    r08_title_recs = "本次样本没有满足推荐门槛的稳定标题公式。建议先参考高赞样本的具体表达，不要套用低表现公式。\n"

if Q.get('content_text_completeness', 0) >= 0.5:
    body_template_block = """### 正文结构模板

**教程/干货类**:
```
【开头】"如果你也遇到过...问题，那这篇就是为你准备的"
【问题】"很多人以为...但其实..."
【方案】"核心就三步: 第一...第二...第三..."
【示例】"比如我最近做的这个..."
【总结】"收藏这篇，下次直接用"
```

**观点类**:
```
【Hook】"最近我在想一个问题..."
【现象】"我观察到..."
【分析】"这背后的原因是..."
【观点】"所以我认为..."
【互动】"你觉得呢？"
```
"""
else:
    body_template_block = """### 正文结构模板

本次正文数据不足，暂不输出正文结构模板。当前建议只参考标题、发布时间和互动表现；如果后续采集到完整正文，再做正文 Hook、内容结构和 CTA 拆解。
"""

tag_action_line = "- [ ] 检查标签组合：核心标签 + 场景标签" if TAG_HAS_DATA else "- [ ] 暂不做标签策略：本次标签数据不足，先聚焦选题和标题"

reliable_topic_rows = ''
reliable_topics = [
    (name, data) for name, data in sorted(T.items(), key=lambda x: x[1].get('avg_likes', 0), reverse=True)
    if TOPIC_OK and is_reliable_topic(name, data) and data.get('avg_likes', 0) >= overall_avg * 1.15
]
if reliable_topics:
    total_reliable = sum(data.get('count', 0) for _, data in reliable_topics) or 1
    for name, data in reliable_topics[:5]:
        suggested_pct = round(data.get('count', 0) / total_reliable * 100)
        reliable_topic_rows += f"| {name} | {suggested_pct}% | 当前 {data.get('count', 0)} 篇，均赞 {data.get('avg_likes', 0)}，爆款率 {data.get('burst_rate', 0)}% |\n"
else:
    reliable_topic_rows = "| 暂不输出固定配比 | - | 主题分类覆盖或样本置信不足，先复盘高赞样本，不按比例扩量 |\n"

r08 = f"""# 策略建议与行动计划

## 一、核心发现（Top {min(len(findings), 4)}）

{chr(10).join([f'{i+1}. {f}' for i, f in enumerate(findings[:4])])}

## 二、内容策略建议

### 推荐内容配比

| 方向 | 建议占比 | 依据 |
|------|---------|------|
{reliable_topic_rows}

### 标题策略

**推荐公式 Top 3**:
{r08_title_recs}

**避坑**:
- 避免纯事件性标题，互动极低
- 避免过于垂直技术的标题，受众面太窄

### 发布节奏

| 推荐频率 | 每周 3-4 篇 |
|---------|------------|
| 时间分布 | 当前未采集小时级发布时间，不判断最佳时段 |
| 系列化 | 仅在标题聚类检测到稳定系列后再规划 |

## 三、可直接套用的模板

### 标题模板（基于数据中高表现的模式）

| 模式 | 互动表现 | 爆款率 | 最佳标题示例 |
|------|---------|-------|------------|
{template_lines}

{body_template_block}

## 四、增长行动计划

### 短期（本周）
- [ ] 复盘当前 Top 10 高赞标题，记录对象、冲突点和结果承诺
{tag_action_line}
- [ ] 先补采正文/标签，再决定是否输出正文模板和 SEO 策略

### 中期（本月）
- [ ] 用 3-5 篇相邻选题验证一个方向，不直接按固定配比扩量
- [ ] 对比每篇发布后的中位数、爆款率和标题结构
- [ ] 如果主题未归类仍偏高，先优化分类词典或补充正文数据

### 长期（本季度）
- [ ] 建立固定的内容日历
- [ ] 测试 1-2 个新内容形式
- [ ] 补充 3-5 个同赛道账号后再做竞争定位
- [ ] 有商业样本后再评估商业化路径

## 五、关键指标看板

| 指标 | 当前值 | 下一步观察 |
|------|-------|------------|
| 均赞 | {P.get('avg_likes','?')} | 与中位数一起看，避免被单篇爆款带偏 |
| 爆款率 (>2x均赞) | {real_burst_rate}% | 用于验证新选题是否有效 |
| 中位数 | {P.get('median_likes','?')} | 更适合作为稳定表现基线 |
| 月发布数 | ~{round(P.get('total_notes',0)/max(G.get('months_active',1),1), 1)} | 先稳定节奏，再评估扩量 |
"""

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
| 00 | [博主画像卡片](00_博主画像卡片.md) | 总览层 | 一句话定位 · 基础数据看板 · 用户画像推断 · 人设要素矩阵 |
| 01 | [内容结构分析](01_内容结构分析.md) | 生产层 | 主题分布总览 · 各主题深度分析 · 内容形态效率对比 · 系列化内容聚类 · 内容密度 |
| 02 | [标题与文案分析](02_标题与文案分析.md) | 文本层 | 标题基础特征统计 · 标题公式库 · 正文模块按覆盖率降级 |
| 03 | [互动归因分析](03_互动归因分析.md) | 数据层 | 互动分布全景 · 帕累托分析 · 爆款vs普通两极对比 · 互动集中度指数 |
| 04 | [成长轨迹分析](04_成长轨迹分析.md) | 时间层 | 成长阶段四部曲 · 关键转折点编年史 · 互动趋势 |
| 05 | [标签与SEO分析](05_标签与SEO分析.md) | 流量层 | 标签大盘 · 高频标签Top20 · 组合策略 · 标签策略建议 |
| 06 | [商业化分析](06_商业化分析.md) | 变现层 | 商业信号检测 · 有样本才比较表现 |
| 07 | [竞争定位分析](07_竞争定位分析.md) | 策略层 | 单账号基础观察 · 对标不足时降级 |
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
| 博主画像 | 定位、人设观察 | 全量笔记元数据 + 平台公开信息，评论不足时不推断痛点 |
| 内容结构 | 8类主题分布、图文vs视频、系列化检测 | {P.get('total_notes','?')} 条笔记元数据 |
| 标题与文案 | 标题特征量化、公式检测 | {P.get('total_notes','?')} 条标题；正文覆盖率 {round(Q.get('content_text_completeness', 0) * 100, 1)}% |
| 互动归因 | 分布特征、极端值、两极样本对照、帕累托系数 | {P.get('total_notes','?')} 条互动数据 |
| 成长轨迹 | 阶段划分、转折点检测、趋势解读 | {P.get('total_notes','?')} 条时间序列 |
| 标签与SEO | 标签组合、效率排名 | {'样本标签数据' if TAG_HAS_DATA else '数据不足（需标签字段）'} |
| 商业化 | 商业信号检测 | 标题关键词弱检测；0 商业样本时不比较表现 |
| 竞争定位 | 单账号基础观察 | 缺少对标账号时不判断可复制性 |

## 数据资产清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `all_notes.json` | 原始元数据大盘 | 包含 {P.get('total_notes','?')} 条笔记的发布时间、互动数、标题等基础字段 |
| `results.json` | 量化分析结果 | 所有分析维度的结构化计算结果 |

## 可信度分级量尺

- **[Confirmed]**: 基于 30+ 样本的量化计算结论 → 属于确定性规律，可直接作为策略依据
- **[Indicative]**: 基于 10-30 样本的趋势性指向 → 属于强相关趋势，具有高度参考价值
- **[Speculative]**: 基于有限样本或外部推断 → 属于前瞻性洞察，需在实操中动态验证
"""

w('README.md', idx)

print(f"\n{'='*40}")
print(f"All reports generated in: {out}")
print(f"{'='*40}")
