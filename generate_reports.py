"""
xhs-blogger-analyzer — 深度报告生成器（完整版）

用法:
  python generate_reports.py --input ./data/results.json --output ./reports/博主名_日期
"""

import json, os, argparse
from collections import defaultdict

parser = argparse.ArgumentParser()
parser.add_argument('--input', default='./data/results.json')
parser.add_argument('--output', default=None)
args = parser.parse_args()

with open(args.input, 'r', encoding='utf-8') as f:
    R = json.load(f)

# Determine output directory
blogger_name = '未知博主'
if args.output:
    out = args.output
else:
    from datetime import datetime
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    out = f'./reports/{blogger_name}_{ts}'

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

def w(fname, content):
    with open(f'{out}/{fname}', 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  Generated: {fname}')

# ============================================================
# Report 00: 博主画像卡片
# ============================================================
nickname = P.get('nickname', P.get('profile_nickname', '未知博主'))
r00 = f"""# 博主画像卡片：{nickname}

## 基础信息

| 字段 | 内容 |
|------|------|
| 昵称 | {nickname} |
| 内容总量 | {P.get('total_notes','?')} 篇 |
| 视频占比 | {P.get('video_count',0)} ({CT.get('video',{}).get('pct','?')}%) |
| 创作周期 | ~{G.get('months_active', '?')} 个月 |
| 均赞/中位数 | {P.get('avg_likes','?')} / {P.get('median_likes','?')} |
| 最高赞 | {P.get('max_likes','?')} |
| 标准差 | {P.get('std_likes','?')} |
"""

w('00_博主画像卡片.md', r00)

# ============================================================
# Report 01: 内容结构分析
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
    overall_avg = P.get('avg_likes', 0)
    overall_median = P.get('median_likes', 0)
    for cat, s in sorted(T.items(), key=lambda x: x[1]['avg_likes'], reverse=True):
        burst_emoji = '🔥' if s['burst_rate'] > 20 else ('📈' if s['avg_likes'] > overall_avg else '📊')
        category_type = '主力类型' if s['count'] > 30 else '补充类型' if s['count'] > 10 else '尝试型'
        avg_assess = '显著高于均值' if s['avg_likes'] > overall_avg * 1.2 else '接近均值' if s['avg_likes'] > overall_avg * 0.8 else '低于均值'
        median_assess = '分布均匀' if s['median_likes'] > overall_median else '头尾分化'
        burst_assess = '高产爆款🔥' if s['burst_rate'] > 20 else '偶尔出爆款' if s['burst_rate'] > 10 else '爆款稀缺'
        stable_assess = '稳定输出' if s['above_avg_rate'] > 30 else '分化严重'

        r01 += f"""### {burst_emoji} {cat}

| 指标 | 数值 | 评估 |
|------|------|------|
| 笔记数 | {s['count']} 篇 ({s['pct']}%) | {category_type} |
| 平均点赞 | {s['avg_likes']} | {avg_assess} |
| 中位数 | {s['median_likes']} | {median_assess} |
| 爆款率 | {s['burst_count']} 篇 ({s['burst_rate']}%) | {burst_assess} |
| 高于均值比 | {s['above_avg_rate']}% | {stable_assess} |

"""
        if s['burst_rate'] > 20 and s['count'] > 20:
            r01 += "**策略建议**: 主力赛道，建议保持投入。\n\n"
        elif s['avg_likes'] > overall_avg * 1.5:
            r01 += "**策略建议**: 高ROI类型，建议增加占比。\n\n"
        elif s['count'] < 10:
            r01 += "**策略建议**: 样本量较小，结论需谨慎。\n\n"
        else:
            r01 += "\n"

# Content type comparison
video = CT.get('video', {})
normal = CT.get('normal', {})
r01 += f"""
## 三、内容形态对比

| 形态 | 篇数 | 占比 | 均赞 | 相对图文效率 |
|------|------|------|------|------------|
| 图文 | {normal.get('count',0)} | {normal.get('pct',0)}% | {normal.get('avg_likes',0)} | 100%（基准） |
| 视频 | {video.get('count',0)} | {video.get('pct',0)}% | {video.get('avg_likes',0)} | {video.get('vs_image_pct',0)}% |

"""

if video.get('count', 0) > 0:
    r01 += f"**关键结论**: 视频虽然占比 {video.get('pct',0)}%，但均赞只有图文的 {video.get('vs_image_pct',0)}%。\n"

r01 += f"""
## 四、内容密度

| 指标 | 数值 |
|------|------|
| 活跃月数 | {G.get('months_active', '?')} 个月 |
| 月均发布 | {round(P.get('total_notes',0)/max(G.get('months_active',1),1), 1)} 篇 |
"""

w('01_内容结构分析.md', r01)

# ============================================================
# Report 02: 标题与文案分析
# ============================================================
feat_rows = ''
if TA:
    for feat_name, data in TA.items():
        if feat_name == 'avg_length':
            continue
        effect = '✅ 有效' if data.get('vs_baseline_pct', 0) > 0 else ('❌ 谨慎' if data.get('vs_baseline_pct', 0) < -10 else '—')
        feat_rows += f"| {feat_name} | {data['count']} | {data['pct']}% | {data['avg_likes']} | {data['vs_baseline_pct']:+.1f}% | {effect} |\n"

formula_rows = ''
if TF:
    for fname, data in sorted(TF.items(), key=lambda x: x[1]['avg_likes'], reverse=True):
        formula_rows += f"| {fname} | {data['count']} | {data['pct']}% | {data['avg_likes']} | {data['vs_overall_pct']:+.1f}% | {data['burst_rate']}% | {data.get('top','')[:40]} |\n"

r02 = f"""# 标题与文案分析

## 一、标题基础数据

| 指标 | 数值 |
|------|------|
| 总笔记数 | {P.get('total_notes','?')} |
| 平均标题长度 | {TA.get('avg_length','?')} 字 |
| 整体均赞 | {P.get('avg_likes','?')} |

## 二、标题特征统计

| 特征 | 使用次数 | 使用率 | 均赞 | vs 基线 | 效果判定 |
|------|---------|-------|------|---------|---------|
{feat_rows}

## 三、标题公式库

| 公式名 | 使用频次 | 占比 | 均赞 | vs均值 | 爆款率 | 最佳标题 |
|-------|---------|------|------|--------|-------|---------|
{formula_rows}

"""

if TF:
    for fname, data in sorted(TF.items(), key=lambda x: x[1]['avg_likes'], reverse=True):
        direction = '高于' if data['vs_overall_pct'] > 0 else '低于'
        r02 += f"""### {fname}

- **使用频次**: {data['count']} 次 ({data['pct']}%)
- **均赞**: {data['avg_likes']}（{direction}整体均值 {abs(data['vs_overall_pct'])}%）
- **爆款率**: {data['burst_rate']}%
- **最佳标题**: {data.get('top', '')[:60]}
"""
        samples = data.get('sample', [])
        if samples:
            r02 += "- **示例**:\n"
            for s in samples[:3]:
                r02 += f"  - `{s}`\n"
        r02 += "\n"

w('02_标题与文案分析.md', r02)

# ============================================================
# Report 03: 互动归因分析
# ============================================================
r03 = f"""# 互动归因分析

## 一、互动分布

| 指标 | 数值 |
|------|------|
| 总互动量 | {P.get('total_likes_sum','?')} |
| 平均点赞 | {P.get('avg_likes','?')} |
| 中位数 | {P.get('median_likes','?')} |
| 标准差 | {P.get('std_likes','?')} |
| P25 / P75 | {P.get('p25','?')} / {P.get('p75','?')} |
| 最高 / 最低 | {P.get('max_likes','?')} / {P.get('min_likes','?')} |

## 二、帕累托分析

| 指标 | 数值 |
|------|------|
| 前 80% 点赞集中在 | 前 {E.get('pareto_80pct_n_notes','?')} 篇（{E.get('pareto_80pct_pct','?')}%） |
| 前 10% 笔记贡献 | {E.get('top10pct_share','?')}% 的点赞 |
| 前 5 篇贡献 | {E.get('top5_share','?')}% 的点赞 |
| 后 50% 笔记贡献 | 仅 {E.get('bottom50pct_share','?')}% 的点赞 |

"""

if TVB:
    r03 += f"""## 三、爆款 vs 普通对比

| 对比维度 | 爆款 Top 20 | 普通 Bottom 20 | 差异倍数 |
|---------|------------|---------------|---------|
| 平均点赞 | {TVB.get('top20_avg_likes','?')} | {TVB.get('bot20_avg_likes','?')} | {TVB.get('ratio','?')}x |
| 平均标签数 | {TVB.get('top20',{}).get('avg_tag_count','?')} | {TVB.get('bot20',{}).get('avg_tag_count','?')} | — |
| 平均正文长度 | {TVB.get('top20',{}).get('avg_text_length',0):.0f} | {TVB.get('bot20',{}).get('avg_text_length',0):.0f} | — |
| 含日期比例 | {TVB.get('top20',{}).get('has_date_ratio','?')}% | {TVB.get('bot20',{}).get('has_date_ratio','?')}% | — |

"""

w('03_互动归因分析.md', r03)

# ============================================================
# Report 04: 成长轨迹分析
# ============================================================
bursts_table = ''
for b in G.get('top_bursts', [])[:15]:
    bursts_table += f"| {b['date']} | {b['title'][:50]} | {b['likes']} | {b['ratio_to_avg']}x |\n"

r04 = f"""# 成长轨迹分析

## 一、时间线总览

| 指标 | 数值 |
|------|------|
| 首条笔记 | {G.get('first_month', '?')} |
| 最新笔记 | {G.get('last_month', '?')} |
| 活跃月数 | {G.get('months_active', '?')} 个月 |
| 总篇数 | {P.get('total_notes','?')} |
| 月均发布 | {round(P.get('total_notes',0)/max(G.get('months_active',1),1), 1)} 篇 |

## 二、关键转折点

| 日期 | 标题 | 点赞 | 倍数 |
|------|------|------|------|
{bursts_table}

## 三、互动趋势

| 指标 | 数值 |
|------|------|
| 总爆款数 | {G.get('burst_count', 0)} 篇 |
"""
w('04_成长轨迹分析.md', r04)

# ============================================================
# Report 05: 标签与SEO分析
# ============================================================
if TG and TG.get('top30'):
    tag_rows = ''
    for i, t in enumerate(TG['top30'][:20]):
        tag_type = '核心标签' if t['count'] > 10 else '常用标签' if t['count'] > 5 else '场景标签'
        tag_rows += f"| {i+1} | {t['tag']} | {t['count']} | {tag_type} |\n"

    r05 = f"""# 标签与 SEO 分析

## 一、标签总览

| 指标 | 数值 |
|------|------|
| 唯一标签总数 | {TG.get('total_unique', 0)} 个 |
| 标签总引用 | {TG.get('total_mentions', 0)} 次 |

## 二、高频标签 TOP 20

| 排名 | 标签 | 使用次数 | 类型 |
|------|------|---------|------|
{tag_rows}
"""
else:
    r05 = """# 标签与 SEO 分析

*标签数据需要采集笔记正文内容（tags 字段）才能分析。当前仅采集了笔记列表数据，缺少正文标签。*

## 如何获取标签数据

在 scrape 步骤之后，需要额外采集每篇笔记的详情页，提取 tags 字段。这部分数据在 `note_contents.json` 中。
"""

w('05_标签与SEO分析.md', r05)

# ============================================================
# Report 06: 商业化分析
# ============================================================
if C:
    r06 = f"""# 商业化分析

## 一、商业化数据概览

| 指标 | 数值 |
|------|------|
| 检测到的商业内容 | {C.get('detected_count', 0)} 篇 |
| 占比 | {C.get('detected_pct', 0)}% |
| 商业内容均赞 | {C.get('avg_likes_commercial', 0)} |
| 自然内容均赞 | {C.get('avg_likes_organic', 0)} |
"""
else:
    r06 = """# 商业化分析

*商业化检测需要结合标题关键词和正文中的 @提及、品牌名等信息。当前版本基于标题关键词匹配进行分析。*
"""

w('06_商业化分析.md', r06)

# ============================================================
# Report 07: 竞争定位分析
# ============================================================
r07 = f"""# 竞争定位分析（单博主版）

*注意: 完整的竞争定位需要对比同赛道 3-5 个博主。以下为基于单一博主内容特征的初步分析。*

## 一、账号特征总览

| 维度 | 数据 |
|------|------|
| 内容总量 | {P.get('total_notes','?')} 篇 |
| 图文/视频 | {P.get('image_count','?')} / {P.get('video_count','?')} |
| 均赞 | {P.get('avg_likes','?')} |
| 创作周期 | ~{G.get('months_active', '?')} 个月 |
| 内容集中度 | Top {E.get('pareto_80pct_pct','?')}% 笔记占 80% 点赞 |

## 二、内容特征分析

| 维度 | 特征 |
|------|------|
| 内容深度 | 基于 {len(T)} 个主题类别分布评估 |
| 更新频率 | 月均 {round(P.get('total_notes',0)/max(G.get('months_active',1),1), 1)} 篇 |
"""

if T:
    best = max(T.items(), key=lambda x: x[1]['avg_likes'])
    r07 += f"| 最佳表现类型 | {best[0]}（均赞 {best[1]['avg_likes']}） |\n"

r07 += """
### 内容坐标系定位（推断）

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
"""
w('07_竞争定位分析.md', r07)

# ============================================================
# Report 08: 策略建议与行动计划
# ============================================================
best_topic_name = ''
best_topic_avg = 0
if T:
    best_topic = max(T.items(), key=lambda x: x[1]['avg_likes'])
    best_topic_name = best_topic[0]
    best_topic_avg = best_topic[1]['avg_likes']

r08 = f"""# 策略建议与行动计划

## 一、核心发现

1. **最佳内容类型**: {best_topic_name}（均赞 {best_topic_avg}）
2. **图文 vs 视频**: 图文是主要内容形式
3. **内容集中度**: Top {E.get('pareto_80pct_pct','?')}% 笔记贡献 80% 点赞
4. **创作节奏**: {G.get('months_active', 0)} 个月，{P.get('total_notes','?')} 篇

*具体策略建议需要结合博主所在领域和赛道特点进行定制化分析。*
"""
w('08_策略建议与行动计划.md', r08)

# ============================================================
# Index file
# ============================================================
idx = f"""# 小红书博主深度研究报告：{nickname}

## 报告清单

| # | 文件 | 内容 |
|---|------|------|
| 00 | [博主画像卡片](00_博主画像卡片.md) | 一页纸速览博主核心信息 |
| 01 | [内容结构分析](01_内容结构分析.md) | 主题分布、内容形态、系列化内容 |
| 02 | [标题与文案分析](02_标题与文案分析.md) | 标题公式库、Hook模式、正文结构 |
| 03 | [互动归因分析](03_互动归因分析.md) | 帕累托分析、爆款 vs 普通对比 |
| 04 | [成长轨迹分析](04_成长轨迹分析.md) | 阶段划分、转折点、趋势解读 |
| 05 | [标签与SEO分析](05_标签与SEO分析.md) | 标签组合策略、效率分析 |
| 06 | [商业化分析](06_商业化分析.md) | 变现路径、商业 vs 自然对比 |
| 07 | [竞争定位分析](07_竞争定位分析.md) | 生态位、可复制性、增长空间 |
| 08 | [策略建议与行动计划](08_策略建议与行动计划.md) | 可操作模板和行动清单 |

## 核心数据速览

| 指标 | 数值 |
|------|------|
| 笔记总数 | {P.get('total_notes','?')} |
| 平均点赞 | {P.get('avg_likes','?')} |
| 中位数 | {P.get('median_likes','?')} |
| 最高 | {P.get('max_likes','?')} |
| 创作周期 | ~{G.get('months_active', '?')} 个月 |
| 活跃月均 | {round(P.get('total_notes',0)/max(G.get('months_active',1),1), 1)} 篇 |
"""

w('README.md', idx)

print(f"\n{'='*40}")
print(f"All reports generated in: {out}")
print(f"{'='*40}")
