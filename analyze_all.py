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
parser.add_argument('--output', default='./data/results.json')
args = parser.parse_args()

# Load data
with open(args.notes, 'r', encoding='utf-8') as f:
    all_notes = json.load(f)

contents = []
if args.contents:
    with open(args.contents, 'r', encoding='utf-8') as f:
        contents = json.load(f)

notes = [n for n in all_notes if n.get('liked_count', 0) > 0]
results = {}

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

content_map = {c['note_id']: c.get('content', {}) for c in contents}
for n in all_notes:
    n['_content'] = content_map.get(n['note_id'])

notes_with_dt = [n for n in all_notes if n.get('_dt')]
print(f"Timestamps extracted: {len(notes_with_dt)}/{len(all_notes)}")

# ---- 1. Profile ----
likes_sorted = sorted([n['liked_count'] for n in notes], reverse=True)
results['profile'] = {
    'total_notes': len(all_notes),
    'total_with_likes': len(notes),
    'total_likes_sum': sum(n['liked_count'] for n in notes),
    'avg_likes': round(sum(n['liked_count'] for n in notes) / len(notes), 1),
    'median_likes': statistics.median([n['liked_count'] for n in notes]),
    'max_likes': max(n['liked_count'] for n in notes),
    'min_likes': min(n['liked_count'] for n in notes),
    'std_likes': round(statistics.stdev(likes_sorted), 1),
    'p25': likes_sorted[len(likes_sorted)//4],
    'p75': likes_sorted[len(likes_sorted)*3//4],
    'video_count': len([n for n in notes if n.get('type') == 'video']),
    'image_count': len([n for n in notes if n.get('type') == 'normal']),
}

if len(notes_with_dt) > 1:
    span_months = (notes_with_dt[-1]['_dt'] - notes_with_dt[0]['_dt']).days // 30
    results['profile']['content_span_months'] = span_months

# ---- 2. Topic Classification ----
classification_rules = [
    ('AI模型/产品评测', ['DeepSeek','Claude','ChatGPT','OpenAI','GPT','Google','Gemini',' 小米 ','实测','评测','测评','上手','体验','试用','豆包','通义']),
    ('教程/干货', ['教程','Prompt','提示词','技巧','怎么','如何','保姆','步骤','方法','一文','手把手','指南','三步']),
    ('观点/深度思考', ['杀死','思考','观点','趋势','真相','发现','告别','反思','感悟','想说','杀死']),
    ('工具/Skill发布', ['上线','开源','Skill','AIHOT','发布','工具','网站','APP','推出']),
    ('热点追踪', ['来了','突袭','刚刚','深夜','终于','悄悄','更新','官宣']),
    ('个人/日常', ['日记','感谢','陪伴','再见','周五','开机','圣诞','新年','生日快乐','感恩','年末','Party','圣诞']),
    ('商业/活动', ['招聘','招人','有奖','征集','活动','线下','大会','闭门','合作','邀请','倒计时']),
]

def classify_note(n):
    title = n.get('title', '')
    for cat, keywords in classification_rules:
        if any(k.lower() in title.lower() for k in keywords):
            return cat
    if any(w in title for w in ['AI', '人工智能', '大模型', '模型']):
        return 'AI模型/产品评测'
    if any(w in title for w in ['我', '我们', '自己']):
        return '个人/日常'
    return '其他/未分类'

cat_stats = defaultdict(lambda: {'count': 0, 'likes': [], 'notes': []})
for n in all_notes:
    cat = classify_note(n)
    cat_stats[cat]['count'] += 1
    cat_stats[cat]['likes'].append(n.get('liked_count', 0))
    cat_stats[cat]['notes'].append(n)

results['topic_distribution'] = {}
overall_avg = results['profile']['avg_likes']
for cat in sorted(cat_stats.keys(), key=lambda c: sum(cat_stats[c]['likes'])/max(len(cat_stats[c]['likes']),1), reverse=True):
    s = cat_stats[cat]
    likes = s['likes']
    burst = len([l for l in likes if l > 1000])
    above_avg = len([l for l in likes if l > overall_avg])
    results['topic_distribution'][cat] = {
        'count': s['count'],
        'pct': round(s['count']/len(all_notes)*100, 1),
        'avg_likes': round(sum(likes)/len(likes), 1),
        'median_likes': statistics.median(likes) if likes else 0,
        'max_likes': max(likes) if likes else 0,
        'burst_count': burst,
        'burst_rate': round(burst/len(likes)*100, 1) if likes else 0,
        'above_avg_rate': round(above_avg/len(likes)*100, 1) if likes else 0,
    }

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
img_avg = results['content_type'].get('normal', {}).get('avg_likes', 1)
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
        'vs_overall_pct': round((avg / overall_avg - 1) * 100, 1),
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
    'pareto_80pct_pct': round(pareto_n/len(sorted_likes)*100, 1) if sorted_likes else 0,
    'gini_coef': round(1 - sum(sorted_likes)/(len(sorted_likes)*sorted_likes[0])*0.5, 3) if sorted_likes else 0,
    'top10pct_share': round(sum(sorted_likes[:max(1, len(sorted_likes)//10)])/total_likes*100, 1),
    'top20pct_share': round(sum(sorted_likes[:max(1, len(sorted_likes)//5)])/total_likes*100, 1),
    'top5_share': round(sum(sorted_likes[:5])/total_likes*100, 1),
    'bottom50pct_share': round(sum(sorted_likes[-(len(sorted_likes)//2):])/total_likes*100, 1),
}

if contents:
    sc = sorted(contents, key=lambda x: x.get('liked_count', 0), reverse=True)
    top20 = sc[:20]
    bot20 = sc[-20:]

    def extract_cm(notes_list):
        if not notes_list:
            return {}
        tcounts = []
        wcounts = []
        dates = 0
        for n in notes_list:
            ct = n.get('content', {})
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
                'ratio_to_avg': round(n.get('liked_count', 0)/overall_avg, 1)
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
    for n in contents:
        for tag_str in n.get('content', {}).get('tags', []):
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

print(f"\nResults saved to: {args.output}")
print(f"Profile: avg_likes={results['profile']['avg_likes']}, median={results['profile']['median_likes']}, max={results['profile']['max_likes']}")
print(f"Topics: {len(results.get('topic_distribution', {}))} categories")
print(f"Growth: {results['growth'].get('months_active', 0)} months, {results['growth'].get('burst_count', 0)} burst notes")
print(f"Commercial: {results['commercial']['detected_count']} detected ({results['commercial']['detected_pct']}%)")
