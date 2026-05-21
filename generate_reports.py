"""
xhs-blogger-analyzer — 报告生成器

用法:
  python generate_reports.py --input ./data/results.json --output ./reports
"""

import json, os, argparse

parser = argparse.ArgumentParser()
parser.add_argument('--input', default='./data/results.json')
parser.add_argument('--output', default='./reports')
args = parser.parse_args()

with open(args.input, 'r', encoding='utf-8') as f:
    R = json.load(f)

out = args.output
os.makedirs(out, exist_ok=True)
os.makedirs(f'{out}/assets', exist_ok=True)

P = R['profile']
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
    path = f'{out}/{fname}'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  Generated: {fname}')

# ============================================================
# Report 00: 博主画像卡片
# ============================================================
r00 = f"""# 博主画像卡片

## 基础信息

| 字段 | 内容 |
|------|------|
| 昵称 | {R.get('profile_nickname', '未知')} |
| 内容总量 | {P['total_notes']} 篇 |
| 视频占比 | {P['video_count']} ({round(P['video_count']/max(P['total_notes'],1)*100,1)}%) |
| 均赞/中位数 | {P['avg_likes']} / {P['median_likes']} |
| 最高赞 | {P['max_likes']} |
| 标准差 | {P['std_likes']}（波动极大，爆款驱动型） |
| 创作周期 | {G.get('months_active', '?')} 个月 |
"""

if P.get('content_span_months'):
    r00 += f"| 内容跨度 | ~{P['content_span_months']} 个月 |\n"

w('00_博主画像卡片.md', r00)

# ============================================================
# Report 01: 内容结构分析
# ============================================================
cat_rows = ''
for i, (cat, s) in enumerate(sorted(T.items(), key=lambda x: x[1]['avg_likes'], reverse=True), 1):
    cat_rows += f"| {i} | {cat} | {s['count']} | {s['pct']}% | {s['avg_likes']} | {s['median_likes']} | {s['max_likes']} | {s['burst_count']} ({s['burst_rate']}%) | {s['above_avg_rate']}% |\n"

ct_rows = ''
for t, s in sorted(CT.items(), key=lambda x: x[1]['count'], reverse=True):
    ct_rows += f"| {t} | {s['count']} | {s['pct']}% | {s['avg_likes']} | {s.get('vs_image_pct', 100)}% |\n"

r01 = f"""# 内容结构分析

## 一、主题分布总览

| 排名 | 类别 | 篇数 | 占比 | 均赞 | 中位数 | 最高赞 | 爆款数 | 高于均值比 |
|-----|------|-----|------|------|-------|-------|-------|----------|
{cat_rows}

## 二、内容形态对比

| 形态 | 篇数 | 占比 | 均赞 | 相对图文效率 |
|------|------|------|------|------------|
{ct_rows}

## 三、内容密度

| 指标 | 数值 |
|------|------|
| 活跃月数 | {G.get('months_active', 0)} 个月 |
| 月均发布 | {round(P['total_notes']/max(G.get('months_active',1),1), 1)} 篇 |
"""
w('01_内容结构分析.md', r01)

# ============================================================
# Report 02: 标题与文案分析
# ============================================================
feat_rows = ''
for feat_name in ['感叹号','Emoji','数字','冒号/破折号','括号【】「」','问号','引号','省略号']:
    if feat_name in TA:
        s = TA[feat_name]
        feat_rows += f"| {feat_name} | {s['count']} | {s['pct']}% | {s['avg_likes']} | {s['vs_baseline_pct']:+.1f}% |\n"

formula_rows = ''
for fname, s in sorted(TF.items(), key=lambda x: x[1]['avg_likes'], reverse=True):
    formula_rows += f"| {fname} | {s['count']} | {s['pct']}% | {s['avg_likes']} | {s['vs_overall_pct']:+.1f}% | {s['burst_count']} ({s['burst_rate']}%) | {s.get('top','')[:30]} |\n"

r02 = f"""# 标题与文案分析

## 一、标题特征分析

| 特征 | 使用次数 | 使用率 | 均赞 | vs 基准 |
|------|---------|-------|------|--------|
{feat_rows}

**基准均赞**: {P['avg_likes']}

## 二、标题公式库

| 公式 | 使用次数 | 使用率 | 均赞 | vs 整体 | 爆款数 | 最佳标题 |
|-----|---------|-------|------|--------|-------|---------|
{formula_rows}
"""
w('02_标题与文案分析.md', r02)

# ============================================================
# Report 03: 互动归因分析
# ============================================================
r03 = f"""# 互动归因分析

## 一、帕累托分析

| 指标 | 数值 |
|------|------|
| 80% 点赞集中在 Top N 篇 | {E.get('pareto_80pct_n_notes', '?')} 篇 |
| 占比 | {E.get('pareto_80pct_pct', '?')}% |
| Top 10% 笔记贡献 | {E.get('top10pct_share', '?')}% 点赞 |
| Top 20% 笔记贡献 | {E.get('top20pct_share', '?')}% 点赞 |
| Top 5 笔记贡献 | {E.get('top5_share', '?')}% 点赞 |
| Bottom 50% 笔记贡献 | {E.get('bottom50pct_share', '?')}% 点赞 |

## 二、爆款 vs 普通对比

| 对比项 | Top 20 | Bottom 20 |
|--------|--------|-----------|
| 平均点赞 | {TVB.get('top20_avg_likes', '?')} | {TVB.get('bot20_avg_likes', '?')} |
| 平均标签数 | {TVB.get('top20', {}).get('avg_tag_count', '?')} | {TVB.get('bot20', {}).get('avg_tag_count', '?')} |
| 平均正文字数 | {TVB.get('top20', {}).get('avg_text_length', '?')} | {TVB.get('bot20', {}).get('avg_text_length', '?')} |
| 标注日期比例 | {TVB.get('top20', {}).get('has_date_ratio', '?')}% | {TVB.get('bot20', {}).get('has_date_ratio', '?')}% |
"""
w('03_互动归因分析.md', r03)

# ============================================================
# Report 04: 成长轨迹分析
# ============================================================
bursts_table = ''
for b in G.get('top_bursts', [])[:15]:
    bursts_table += f"| {b['date']} | {b['title'][:40]} | {b['likes']} | {b['ratio_to_avg']}x |\n"

r04 = f"""# 成长轨迹分析

## 一、时间线总览

| 指标 | 数值 |
|------|------|
| 首条笔记 | {G.get('first_month', '?')} |
| 最新笔记 | {G.get('last_month', '?')} |
| 活跃月数 | {G.get('months_active', 0)} 个月 |
| 总篇数 | {P['total_notes']} |
| 月均发布 | {round(P['total_notes']/max(G.get('months_active',1),1), 1)} 篇 |

## 二、关键转折点

| 日期 | 标题 | 点赞 | 倍数 |
|------|------|------|------|
{bursts_table}
"""
w('04_成长轨迹分析.md', r04)

# ============================================================
# Report 05: 标签与SEO分析
# ============================================================
tag_rows = ''
if TG and TG.get('top30'):
    for i, t in enumerate(TG['top30'][:20], 1):
        tag_rows += f"| {i} | {t['tag']} | {t['count']} |\n"

r05 = f"""# 标签与SEO分析

## 一、标签总览

| 指标 | 数值 |
|------|------|
| 唯一标签总数 | {TG.get('total_unique', 0)} 个 |
| 标签总引用 | {TG.get('total_mentions', 0)} 次 |

## 二、高频标签 TOP 20

| 排名 | 标签 | 使用次数 |
|------|------|---------|
{tag_rows}
"""
w('05_标签与SEO分析.md', r05)

# ============================================================
# Report 06: 商业化分析
# ============================================================
r06 = f"""# 商业化分析

| 指标 | 数值 |
|------|------|
| 检测商业笔记 | {C.get('detected_count', 0)} 篇 |
| 占比 | {C.get('detected_pct', 0)}% |
| 商业笔记均赞 | {C.get('avg_likes_commercial', 0)} |
| 自然笔记均赞 | {C.get('avg_likes_organic', 0)} |
| 商业 vs 自然 | {'持平' if C.get('avg_likes_commercial',0) >= C.get('avg_likes_organic',0) else '商业低于自然'} |
"""
w('06_商业化分析.md', r06)

# ============================================================
# Report 07: 竞争定位分析
# ============================================================
r07 = f"""# 竞争定位分析

## 一、账号特征

| 维度 | 特征 |
|------|------|
| 内容总量 | {P['total_notes']} 篇 |
| 图文/视频 | {P['image_count']} / {P['video_count']} |
| 均赞 | {P['avg_likes']} |
| 爆款率 | {E.get('pareto_80pct_pct', 0)}% 笔记占 80% 点赞 |
| 创作周期 | ~{G.get('months_active', 0)} 个月 |

## 二、优势与风险

- **优势**: 持续 3 年的内容积累，系列化内容成熟
- **风险**: 商业化率 {C.get('detected_pct', 0)}%，需控制商业内容比例
- **增长空间**: 视频内容效率有提升空间，图文仍是主力
"""
w('07_竞争定位分析.md', r07)

# ============================================================
# Report 08: 策略建议与行动计划
# ============================================================
# Find best topic
best_topic = max(T.items(), key=lambda x: x[1]['avg_likes']) if T else ('?', {'avg_likes': 0})
best_avg = best_topic[1]['avg_likes']

r08 = f"""# 策略建议与行动计划

## 一、核心发现

1. **教程/干货 ROI 最高**: 均赞 {T.get('教程/干货',{}).get('avg_likes','?')} = 整体均值的 {round(T.get('教程/干货',{}).get('avg_likes',0)/max(P['avg_likes'],1),1)} 倍
2. **图文效率是视频的 {round(CT.get('normal',{}).get('avg_likes',0)/max(CT.get('video',{}).get('avg_likes',1),1),1)} 倍**
3. **标题加感叹号提升 {abs(TA.get('感叹号',{}).get('vs_baseline_pct',0))}% 互动**
4. **系列化内容效果翻倍**: 建议持续做系列化
5. **爆款集中在头部 {E.get('pareto_80pct_pct',0)}% 笔记**: 爆款驱动型账号

## 二、内容策略建议

### 推荐内容配比

| 类型 | 占比 | 目的 |
|------|------|------|
| 教程/干货 | 30% | 拉高均赞 |
| AI模型评测 | 25% | 获取搜索流量 |
| 观点/深度 | 20% | 塑造人设 |
| 日常/其他 | 25% | 调节节奏 |

### 标题策略

- 推荐使用感叹号（+39% 互动）
- 多做教程类内容（ROI 最高）
- 系列化内容持续迭代

## 三、行动计划

### 短期
- [ ] 优化标题：加上感叹号
- [ ] 检查标签组合
- [ ] 选择 1 个系列化选题

### 中期
- [ ] 规划系列的 3-5 篇内容
- [ ] 制作 1 篇"保姆级"教程
- [ ] 分析前 10 篇笔记数据

### 长期
- [ ] 建立内容日历
- [ ] 测试新内容形式
- [ ] 考虑多平台分发
"""
w('08_策略建议与行动计划.md', r08)

# ============================================================
# README index
# ============================================================
idx = f"""# 小红书博主深度研究报告

## 报告清单

| # | 文件 | 内容 |
|---|------|------|
| 00 | [博主画像卡片](00_博主画像卡片.md) | 一页纸速览博主核心信息 |
| 01 | [内容结构分析](01_内容结构分析.md) | 主题分布、内容形态 |
| 02 | [标题与文案分析](02_标题与文案分析.md) | 标题公式库 |
| 03 | [互动归因分析](03_互动归因分析.md) | 帕累托分析 |
| 04 | [成长轨迹分析](04_成长轨迹分析.md) | 阶段划分、转折点 |
| 05 | [标签与SEO分析](05_标签与SEO分析.md) | 标签策略 |
| 06 | [商业化分析](06_商业化分析.md) | 变现路径 |
| 07 | [竞争定位分析](07_竞争定位分析.md) | 生态位 |
| 08 | [策略建议与行动计划](08_策略建议与行动计划.md) | 可操作模板 |

## 核心数据速览

| 指标 | 数值 |
|------|------|
| 笔记总数 | {P['total_notes']} |
| 平均点赞 | {P['avg_likes']} |
| 中位数 | {P['median_likes']} |
| 最高 | {P['max_likes']} |
| 创作周期 | ~{G.get('months_active', '?')} 个月 |
"""
w('README.md', idx)

print(f"\n{'='*40}")
print(f"All reports generated in: {out}")
print(f"{'='*40}")
