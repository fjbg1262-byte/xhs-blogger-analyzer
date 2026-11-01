<template>
  <div class="shell">
    <aside class="side">
      <div class="brand">
        <span class="brand-mark">
          <svg viewBox="0 0 32 32" width="20" height="20" aria-hidden="true">
            <path d="M15 3.6 17.7 12.3 26.4 15 17.7 17.7 15 26.4 12.3 17.7 3.6 15 12.3 12.3Z" fill="currentColor" />
            <path d="M24.1 3.4 24.9 6 27.5 6.8 24.9 7.6 24.1 10.2 23.3 7.6 20.7 6.8 23.3 6Z" fill="currentColor" opacity=".85" />
          </svg>
        </span>
        <div class="brand-copy">
          <strong>薯光</strong>
          <span>小红书内容采集与对标</span>
        </div>
      </div>

      <nav class="nav">
        <button v-for="item in navItems" :key="item.key" type="button" class="nav-item" :class="{ active: page === item.key }" @click="page = item.key">
          <DemoIcon :name="item.icon" />
          <span>{{ item.label }}</span>
          <i v-if="item.count">{{ item.count }}</i>
        </button>
      </nav>

      <div class="side-foot">
        <button type="button" class="nav-item" :class="{ active: page === 'settings' }" @click="page = 'settings'">
          <DemoIcon name="settings" />
          <span>设置</span>
        </button>
        <div class="account-chip">
          <b>运营工作台</b>
          <span>本机账号 · 演示数据</span>
        </div>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div class="crumb"><span>工作台</span><i>/</i><strong>{{ currentLabel }}</strong></div>
        <div class="top-actions">
          <span class="demo-badge">演示数据</span>
          <router-link class="real-link" to="/library">进入真实工具</router-link>
        </div>
      </header>

      <div class="content">
        <!-- 首页 -->
        <section v-if="page === 'home'" class="page">
          <div class="page-head">
            <div>
              <p class="eyebrow">COLLECT · ORGANIZE · DELIVER</p>
              <h1>把主页内容，整理成可用的表格</h1>
              <p class="lede">采集公开笔记，整理图文与视频，下载飞书导入包，并在同一套八维里做账号对标。</p>
            </div>
            <div class="limit-chip"><b>100</b><span>单次最多笔记</span></div>
          </div>

          <section class="panel capture">
            <div class="capture-copy">
              <p class="eyebrow">START HERE</p>
              <h2>粘贴博主主页链接</h2>
              <p>也可以在已登录的小红书主页点击插件，一键启动。</p>
            </div>
            <div class="capture-form">
              <label class="url-input">
                <DemoIcon name="link" />
                <input v-model="profileUrl" placeholder="https://www.xiaohongshu.com/user/profile/..." />
              </label>
              <button class="btn primary" :disabled="collecting" @click="startCollection">{{ collecting ? '正在采集…' : '整理当前主页' }}</button>
              <button class="btn ghost" @click="page = 'history'">批量链接</button>
            </div>
            <p class="hint">演示环境使用模拟数据，不会访问小红书。</p>
          </section>

          <section v-if="showCollection" class="panel progress">
            <div class="progress-head">
              <div><span class="dot" :class="{ done: collectionState === 'done' }" />{{ collectionState === 'done' ? '采集完成' : collectionState === 'stopped' ? '已停止' : '正在采集' }}</div>
              <b>{{ progress }}%</b>
            </div>
            <div class="bar"><i :style="{ width: progress + '%' }" /></div>
            <div class="progress-counts">
              <div><span>已读取笔记</span><b>{{ readCount }} / 100</b></div>
              <div><span>详情完成</span><b>{{ detailCount }}</b></div>
              <div><span>正文成功</span><b>{{ bodyCount }}</b></div>
              <div><span>标签成功</span><b>{{ tagCount }}</b></div>
            </div>
            <div class="steps">
              <div v-for="(step, index) in progressSteps" :key="step.label" :class="{ active: progress >= step.at }">
                <span>{{ progress >= step.at ? '✓' : index + 1 }}</span>
                <div><b>{{ step.label }}</b><small>{{ progress >= step.at ? '已完成' : '等待中' }}</small></div>
              </div>
            </div>
            <div v-if="collectionState === 'running'" class="progress-foot">
              <span>正在读取第 {{ Math.min(100, readCount + 1) }} 篇笔记</span>
              <button class="btn ghost" @click="stopCollection">停止采集</button>
            </div>
            <div v-if="collectionState === 'done'" class="done-row">
              <span>已整理 100 篇笔记，其中正文 96 篇。</span>
              <button class="btn ghost" @click="page = 'library'">查看笔记库</button>
              <button class="btn primary" @click="page = 'feishu'">生成飞书文件</button>
              <button class="link-btn" @click="page = 'analysis'">账号分析 →</button>
              <small v-if="resumeNotice" class="retry-ok">{{ resumeNotice }}</small>
            </div>
            <div v-else-if="collectionState === 'stopped'" class="done-row stopped-actions">
              <span>已停止，保留 {{ readCount }} 篇已整理笔记；3 篇正文未获取，保留现有下载。</span>
              <button class="btn ghost" @click="resumeCollection">继续处理未完成笔记</button>
              <button class="btn primary" @click="page = 'library'">查看笔记库</button>
              <button class="link-btn" @click="page = 'feishu'">保留下载 →</button>
            </div>
          </section>

          <div class="section-row">
            <h2>最近采集</h2>
            <button class="link-btn" @click="page = 'history'">查看全部 →</button>
          </div>
          <div class="account-grid">
            <article v-for="account in accounts" :key="account.id" class="account-card" @click="openAccount(account)">
              <span class="avatar" :style="{ background: account.color }">{{ account.name.slice(0, 1) }}</span>
              <div class="account-copy">
                <h3>{{ account.name }}</h3>
                <p>{{ account.desc }}</p>
                <div><span>{{ account.notes }} 篇</span><span>{{ account.updated }}</span></div>
              </div>
              <span class="go">→</span>
            </article>
          </div>

          <div class="home-bottom">
            <section class="panel mini-tasks">
              <div class="panel-title"><div><p class="eyebrow">RECENT TASKS</p><h3>采集记录</h3></div><button class="link-btn" @click="page = 'history'">查看全部</button></div>
              <div v-for="task in tasks.slice(0, 3)" :key="task.id" class="task-row">
                <span class="task-status" :class="task.tone">{{ task.status }}</span>
                <div><b>{{ task.account }}</b><small>{{ task.time }} · {{ task.count }} 篇</small></div>
                <span class="task-body">{{ task.body }}</span>
              </div>
              <div class="export-status">
                <span>导出状态</span>
                <b>xlsx 备份已生成</b>
                <small>今天 14:35 · 96 篇含正文</small>
              </div>
            </section>
            <section class="panel workflow">
              <p class="eyebrow">THREE STEPS</p>
              <h3>采集完，直接进飞书</h3>
              <div class="workflow-steps">
                <div><b>01</b><p>采集主页</p><small>笔记、正文、标签和互动</small></div>
                <i>→</i>
                <div><b>02</b><p>检查表格</p><small>筛选图文、视频和缺项</small></div>
                <i>→</i>
                <div><b>03</b><p>导入飞书</p><small>下载多维表格导入包</small></div>
              </div>
              <button class="btn primary" @click="page = 'feishu'">打开飞书交付</button>
            </section>
          </div>
        </section>

        <!-- 笔记库 -->
        <section v-else-if="page === 'library'" class="page library-page">
          <div class="page-head">
            <div>
              <p class="eyebrow">NOTE LIBRARY</p>
              <h1>{{ currentAccount.name }}</h1>
              <p class="lede">{{ currentAccount.desc }} · 最近采集 今天 14:32 · <a href="#demo-note" @click.prevent>原主页 ↗</a></p>
            </div>
            <button class="btn ghost" @click="page = 'analysis'">账号八维分析 →</button>
          </div>

          <div class="kpi-row library-kpi">
            <article class="kpi"><span>笔记</span><b>{{ notes.length }}</b><small>去重后</small></article>
            <article class="kpi"><span>图文</span><b>{{ notes.filter(n => n.type === '图文').length }}</b><small>{{ Math.round(notes.filter(n => n.type === '图文').length / notes.length * 100) }}%</small></article>
            <article class="kpi"><span>视频</span><b>{{ notes.filter(n => n.type === '视频').length }}</b><small>{{ Math.round(notes.filter(n => n.type === '视频').length / notes.length * 100) }}%</small></article>
            <article class="kpi"><span>互动总量</span><b>{{ compact(notes.reduce((sum, n) => sum + total(n), 0)) }}</b><small>赞藏评享</small></article>
            <article class="kpi"><span>单篇中位数</span><b>{{ medianEngagement.toLocaleString() }}</b><small>本批笔记</small></article>
          </div>

          <div class="library-tabs">
            <button v-for="tab in libraryTabs" :key="tab.key" :class="{ active: libraryTab === tab.key }" @click="libraryTab = tab.key">{{ tab.label }}<span>{{ tabCount(tab.key) }}</span></button>
          </div>

          <div class="library-toolbar">
            <label class="search-box"><DemoIcon name="search" /><input v-model="search" placeholder="搜索标题、正文或标签" /></label>
            <select v-model="sortBy">
              <option value="engagement">按互动排序</option>
              <option value="collected">按收藏排序</option>
              <option value="comments">按评论排序</option>
              <option value="shares">按分享排序</option>
              <option value="published">按发布时间</option>
            </select>
            <button class="btn ghost filter-button" :class="{ active: filtersOpen }" @click="filtersOpen = !filtersOpen">筛选 <span v-if="activeFilterCount" class="count">{{ activeFilterCount }}</span></button>
            <div class="view-switch"><button :class="{ active: viewMode === 'table' }" @click="viewMode = 'table'">表格</button><button :class="{ active: viewMode === 'cards' }" @click="viewMode = 'cards'">封面</button></div>
            <button class="btn primary" @click="page = 'feishu'">导出到飞书</button>
          </div>

          <div v-if="filtersOpen" class="filter-panel">
            <label><span>时间范围</span>
              <select v-model="dateRange"><option value="all">全部时间</option><option value="30">近 30 天</option><option value="90">近 90 天</option><option value="180">近半年</option></select>
            </label>
            <label class="filter-check"><input v-model="onlyWithBody" type="checkbox" /><span>只看已抓到正文</span></label>
            <label class="filter-check"><input v-model="onlyIncomplete" type="checkbox" /><span>只看未完成采集</span></label>
            <button class="link-btn" @click="resetFilters">重置筛选</button>
          </div>

          <div v-if="selectedIds.length" class="selection-bar">
            <span>已选择 {{ selectedIds.length }} 篇</span>
            <button class="link-btn" @click="clearSelection">清空</button>
            <button class="link-btn" @click="page = 'feishu'">导出选中内容</button>
            <button class="link-btn" @click="toggleMarked">加入选题</button>
          </div>

          <div v-if="viewMode === 'table'" class="table-wrap">
            <table class="note-table">
              <thead><tr><th class="check"><input type="checkbox" :checked="allVisibleSelected" @change="toggleAll" /></th><th>笔记</th><th>类型</th><th>发布时间</th><th>赞 / 藏 / 评 / 享</th><th>标签</th><th>来源</th><th>采集</th><th /></tr></thead>
              <tbody>
                <tr v-for="note in visibleNotes" :key="note.id" :class="{ selected: selectedIds.includes(note.id) }">
                  <td class="check"><input type="checkbox" :checked="selectedIds.includes(note.id)" @change="toggleSelect(note.id)" /></td>
                  <td>
                    <button class="note-cell" @click="activeNote = note">
                      <span class="thumb" :class="note.cover"><b>{{ note.coverLabel }}</b></span>
                      <span class="note-text"><b>{{ note.title }}</b><small>{{ note.author }} · {{ note.id }}</small></span>
                    </button>
                  </td>
                  <td><span class="type-pill" :class="note.type === '视频' ? 'video' : 'image'">{{ note.type }}</span></td>
                  <td>{{ note.published }}</td>
                  <td class="engage"><span>赞 {{ compact(note.likes) }}</span><span>藏 {{ compact(note.collected) }}</span><span>评 {{ compact(note.comments) }}</span><span>享 {{ compact(note.shares) }}</span></td>
                  <td><span class="tags"><i v-for="tag in note.tags.slice(0, 2)" :key="tag">{{ tag }}</i></span></td>
                  <td><a class="source-col" :href="demoLink(note.id)" target="_blank" rel="noreferrer" title="来源链接">↗</a></td>
                  <td><span v-if="note.incomplete" class="status-warn" :title="note.failure">未完成</span><span v-else class="status-ok">已完成</span></td>
                  <td><button class="more" aria-label="查看详情" @click="activeNote = note">···</button></td>
                </tr>
              </tbody>
            </table>
            <div v-if="!visibleNotes.length" class="empty-state">没有符合筛选条件的笔记</div>
          </div>

          <div v-else class="note-grid">
            <article v-for="note in visibleNotes" :key="note.id" class="note-card" :class="{ selected: selectedIds.includes(note.id) }" @click="activeNote = note">
              <div class="card-cover" :class="note.cover"><b>{{ note.coverLabel }}</b><i>{{ note.type }}</i><button @click.stop="toggleSelect(note.id)">{{ selectedIds.includes(note.id) ? '✓' : '+' }}</button></div>
              <div class="note-card-copy">
                <h3>{{ note.title }}</h3>
                <p>{{ note.tags.join(' · ') }}</p>
                <div><span>赞 {{ compact(note.likes) }}</span><span>藏 {{ compact(note.collected) }}</span><span>评 {{ compact(note.comments) }}</span></div>
              </div>
            </article>
          </div>
        </section>

        <!-- 账号分析 -->
        <section v-else-if="page === 'analysis'" class="page">
          <div class="page-head">
            <div>
              <p class="eyebrow">ACCOUNT DIAGNOSIS</p>
              <h1>账号八维分析</h1>
              <p class="lede">{{ currentAccount.name }} · {{ notes.length }} 篇 · 图文 {{ imageShare }}% / 视频 {{ videoShare }}% · 最近发布 {{ latestPublish }} · 最近采集 今天 14:32</p>
            </div>
            <div class="head-actions">
              <button class="btn ghost" @click="page = 'compare'">加入账号对比</button>
              <button class="btn primary" @click="analysisReady = true">{{ analysisReady ? '重新分析' : '开始分析' }}</button>
            </div>
          </div>

          <div v-if="analysisReady" class="analysis-body">
            <nav class="tabs">
              <button v-for="tab in analysisTabs" :key="tab.key" :class="{ active: analysisTab === tab.key }" @click="analysisTab = tab.key">{{ tab.label }}</button>
            </nav>

            <section v-if="analysisTab === 'overview'" class="tab-panel">
              <div class="kpi-row">
                <article class="kpi"><span>公开互动</span><b>{{ compact(overview.totalEngagement) }}</b><small>赞 + 藏 + 评 + 分享</small></article>
                <article class="kpi"><span>单篇中位数</span><b>{{ overview.median.toLocaleString() }}</b><small>比均值更不易被爆款拉偏</small></article>
                <article class="kpi"><span>头部贡献</span><b>{{ overview.topShare }}%</b><small>Top {{ overview.topCount }} 篇公开互动占比</small></article>
                <article class="kpi"><span>正文参与</span><b>{{ notes.length }}</b><small>AI 实际阅读的正文摘录</small></article>
              </div>

              <div class="insight-grid">
                <article class="insight">
                  <p class="tag">CONCENTRATION</p>
                  <b class="figure">{{ overview.topShare }}%</b>
                  <small>头部的互动贡献</small>
                  <h3>Top {{ overview.topCount }} 篇内容贡献了主要公开互动</h3>
                  <p>本批 Top {{ overview.topCount }} 篇贡献 {{ overview.topShare }}% 的赞藏评享。这不等于账号长期只能靠爆款，但说明复盘应优先解释头部内容的结构。</p>
                </article>
                <article class="insight">
                  <p class="tag">FORMAT</p>
                  <b class="figure">{{ overview.formatRatio }}x</b>
                  <small>相对账号中位数</small>
                  <h3>视频是本批互动中位数最高的形式</h3>
                  <p>视频 {{ overview.videoCount }} 篇，互动中位数 {{ overview.videoMedian.toLocaleString() }}；图文 {{ overview.imageCount }} 篇，中位数 {{ overview.imageMedian.toLocaleString() }}。这里比较的是公开互动快照，不是浏览或曝光效率。</p>
                </article>
                <article class="insight">
                  <p class="tag">TITLE SIGNAL</p>
                  <b class="figure">{{ overview.titlePct }}%</b>
                  <small>含数字标题占比</small>
                  <h3>数字和具体价格是这批标题的主要信号</h3>
                  <p>{{ notes.length }} 篇里 {{ overview.titleCount }} 篇标题带数字。样本很小，只能作为下一批标题的对照，不构成因果。</p>
                </article>
                <article class="insight">
                  <p class="tag">CONTENT PILLAR</p>
                  <b class="figure">{{ overview.topTagCount }} 篇</b>
                  <small>最高频内容标签</small>
                  <h3>“{{ overview.topTag }}” 是当前样本最常见的内容线索</h3>
                  <p>该标签出现在 {{ overview.topTagCount }} 篇里。标签只说明内容覆盖，不等同于搜索流量或推荐权重。</p>
                </article>
              </div>
              <p class="boundary">本页只使用公开互动数据，不包含浏览、曝光、粉丝增长或转化；缺失字段不补数字。</p>
            </section>

            <section v-else-if="analysisTab === 'dimensions'" class="tab-panel">
              <div class="dimension-grid">
                <article v-for="(dim, index) in dimensions" :key="dim.title" class="dimension-card">
                  <header>
                    <span>{{ String(index + 1).padStart(2, '0') }}</span>
                    <div><h3>{{ dim.title }}</h3><small>{{ dim.badge }}</small></div>
                    <i :class="dim.tone">{{ dim.tag }}</i>
                  </header>
                  <h4>{{ dim.headline }}</h4>
                  <p>{{ dim.copy }}</p>
                  <div class="chips"><span v-for="metric in dim.metrics" :key="metric">{{ metric }}</span></div>
                  <div class="dimension-advice"><b>下一步</b><p>{{ dim.advice }}</p></div>
                </article>
              </div>
            </section>

            <section v-else-if="analysisTab === 'drafts'" class="tab-panel">
              <div class="draft-plan">
                <div class="panel-title">
                  <div><p class="eyebrow">ONE WEEK PLAN</p><h3>一周执行顺序</h3></div>
                  <small>复盘指标：收藏中位数 · 分享次数 · 评论率</small>
                </div>
                <div class="week-plan-grid">
                  <article v-for="plan in weekPlan" :key="plan.day"><span>{{ plan.day }}</span><b>{{ plan.title }}</b><p>{{ plan.copy }}</p></article>
                </div>
              </div>
              <div class="draft-list">
                <article v-for="(topic, index) in topics" :key="topic.title" class="draft">
                  <div class="draft-index">{{ String(index + 1).padStart(2, '0') }}</div>
                  <div class="draft-body">
                    <p class="tag">读者问题</p>
                    <h3>{{ topic.title }}</h3>
                    <p class="draft-problem">{{ topic.problem }}</p>
                    <div class="title-options">
                      <div><span>标题 A</span><b>{{ topic.titleA }}</b></div>
                      <div><span>标题 B</span><b>{{ topic.titleB }}</b></div>
                    </div>
                    <div class="draft-block"><span>开头</span><p class="opening">{{ topic.opening }}</p></div>
                    <div class="draft-block"><span>正文大纲</span><ol class="outline"><li v-for="step in topic.outline" :key="step">{{ step }}</li></ol></div>
                    <div class="draft-observe"><span>观察指标</span><i v-for="m in topic.observe" :key="m">{{ m }}</i></div>
                  </div>
                </article>
              </div>
            </section>

            <section v-else class="tab-panel">
              <p class="tab-note">下面每一条都来自本批已采集笔记，分析只能引用这些原句。</p>
              <div class="table-wrap">
                <table class="evidence-table">
                  <thead><tr><th>#</th><th>笔记</th><th>类型</th><th>公开互动</th><th>被引用的原句</th><th>来源</th></tr></thead>
                  <tbody>
                    <tr v-for="row in evidenceRows" :key="row.id">
                      <td class="rank">{{ row.rank }}</td>
                      <td><b>{{ row.title }}</b><small>{{ row.id }}</small></td>
                      <td>{{ row.type }}</td>
                      <td>{{ row.engagement.toLocaleString() }}</td>
                      <td class="quote">{{ row.quote }}</td>
                      <td><code>{{ demoLink(row.id) }}</code></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </section>

        <!-- 账号对标 -->
        <section v-else-if="page === 'compare'" class="page">
          <div class="page-head">
            <div>
              <p class="eyebrow">ACCOUNT BENCHMARK</p>
              <h1>账号对标</h1>
              <p class="lede">选择 2 至 5 个账号，在同一套八维里看差异和下一步动作。</p>
            </div>
            <button class="btn primary" :disabled="comparedAccounts.length < 2" @click="compareReady = true">{{ compareReady ? '重新对比' : '开始对比' }}</button>
          </div>

          <div class="compare-select">
            <button v-for="account in accounts" :key="account.id" class="pick" :class="{ active: compareAccounts.includes(account.id) }" @click="toggleCompare(account.id)">
              <span class="avatar" :style="{ background: account.color }">{{ account.name.slice(0, 1) }}</span>
              <div><b>{{ account.name }}</b><small>{{ account.notes }} 篇 · {{ account.desc }}</small></div>
              <i>{{ compareAccounts.includes(account.id) ? '✓' : '+' }}</i>
            </button>
          </div>
          <p class="hint">已选 {{ comparedAccounts.length }} 个账号（最多 5 个，至少保留 2 个）。</p>
          <p v-if="volumeHint" class="volume-hint">{{ volumeHint }}</p>

          <div v-if="compareReady" class="compare-body">
            <div class="compare-cards">
              <article v-for="account in comparedAccounts" :key="account.id">
                <span class="avatar" :style="{ background: account.color }">{{ account.name.slice(0, 1) }}</span>
                <h3>{{ account.name }}</h3>
                <p>{{ account.desc }}</p>
                <div><b>{{ account.notes }}</b><small>篇笔记</small><b>{{ account.engagement }}</b><small>公开互动</small></div>
              </article>
            </div>

            <div class="table-wrap">
              <div class="compare-table">
                <div class="compare-row header" :style="compareGridStyle"><span>维度</span><b v-for="account in comparedAccounts" :key="account.id">{{ account.name }}</b></div>
                <div v-for="row in compareRows" :key="row.title" class="compare-row" :style="compareGridStyle"><span>{{ row.title }}</span><p v-for="(cell, index) in row.values" :key="index">{{ cell }}</p></div>
              </div>
            </div>

            <div class="takeaways">
              <article>
                <p class="tag">值得借鉴</p>
                <h3>把高收藏的路线内容做成连续栏目</h3>
                <p>{{ comparedAccounts[0]?.name }} 的路线清单更容易被收藏，下一个系列可以固定为“城市 + 路线 + 时间成本”。</p>
              </article>
              <article>
                <p class="tag warn-tag">不要照搬</p>
                <h3>不要同时复制标题、封面和生活表达</h3>
                <p>保留自己的叙述方式，只测试栏目结构和信息密度。</p>
              </article>
            </div>

            <div class="panel week-plan">
              <div class="panel-title"><div><p class="eyebrow">ONE WEEK PLAN</p><h3>按对比结果排下周动作</h3></div><small>5 个可执行动作</small></div>
              <div class="week-plan-grid">
                <article v-for="plan in weekPlan" :key="plan.day"><span>{{ plan.day }}</span><b>{{ plan.title }}</b><p>{{ plan.copy }}</p></article>
              </div>
            </div>
          </div>
        </section>

        <!-- 飞书交付 -->
        <section v-else-if="page === 'feishu'" class="page">
          <div class="page-head">
            <div>
              <p class="eyebrow">FEISHU DELIVERY</p>
              <h1>飞书交付</h1>
              <p class="lede">选择数据表，一键生成多维表格导入包和 Excel 备份。</p>
            </div>
            <span class="serial-chip">飞书多维表格</span>
          </div>

          <div class="feishu">
            <section class="panel feishu-preview">
              <div class="preview-top">
                <div><b>{{ deliveryAccount.name }}内容库</b><span>6 张数据表</span></div>
                <div class="preview-tools"><span>⌕</span><button type="button">+ 新建记录</button></div>
              </div>
              <div class="preview-body">
                <aside class="preview-nav">
                  <span>▣ 账号总览</span>
                  <span class="active">▤ 全部笔记</span>
                  <span>▤ 图文笔记</span>
                  <span>▤ 视频笔记</span>
                  <span>◇ 选题清单</span>
                  <span>◷ 采集记录</span>
                </aside>
                <div class="preview-table">
                  <div class="mini-row header"><span>封面</span><span>标题</span><span>类型</span><span>点赞</span><span>收藏</span><span>评论</span><span>来源</span></div>
                  <div v-for="note in notes.slice(0, 5)" :key="note.id" class="mini-row">
                    <span class="mini-cover" :class="note.cover">{{ note.coverLabel }}</span>
                    <span class="mini-title">{{ note.title }}</span>
                    <span>{{ note.type }}</span>
                    <span>{{ note.likes.toLocaleString() }}</span>
                    <span>{{ note.collected.toLocaleString() }}</span>
                    <span>{{ note.comments }}</span>
                    <span>↗</span>
                  </div>
                </div>
              </div>
            </section>

            <aside class="panel delivery">
              <div class="delivery-head">
                <p class="eyebrow">DELIVERY TARGET</p>
                <select v-model="deliveryAccountId" class="account-select" aria-label="选择交付账号">
                  <option v-for="account in accounts" :key="account.id" :value="account.id">{{ account.name }} · {{ account.notes }} 篇</option>
                </select>
                <p>{{ deliveryAccount.notes }} 篇笔记 · {{ Math.round(deliveryAccount.notes * 0.96) }} 篇正文</p>
              </div>
              <div class="table-options">
                <label v-for="table in feishuTables" :key="table.name">
                  <input v-model="selectedTables" type="checkbox" :value="table.name" />
                  <span>{{ table.name }}</span><small>{{ table.count }}</small>
                </label>
              </div>
              <div class="destination">
                <span>交付方式</span>
                <button type="button" class="active">下载导入包</button>
                <button type="button" disabled>直接同步（后续）</button>
              </div>
              <div v-if="generatedFeishu" class="delivery-success">
                <span>✓</span>
                <div><b>飞书导入包已生成</b><small>包含 6 个工作表，可直接导入飞书多维表格。</small></div>
              </div>
              <button v-else class="btn primary wide" :disabled="generatingFeishu || !selectedTables.length" @click="generateFeishu">{{ generatingFeishu ? '正在生成…' : '生成飞书导入包' }}</button>
              <button v-if="generatedFeishu" class="btn ghost wide" @click="downloadDemoCsv"><DemoIcon name="download" />下载演示文件</button>
              <ol class="import-steps">
                <li>在飞书多维表格新建空白表</li>
                <li>导入刚下载的文件并保留表头</li>
                <li>把日期、数字和多行文本改成对应字段类型</li>
              </ol>
            </aside>
          </div>
        </section>

        <!-- 采集记录 -->
        <section v-else-if="page === 'history'" class="page">
          <div class="page-head">
            <div>
              <p class="eyebrow">COLLECTION HISTORY</p>
              <h1>采集记录</h1>
              <p class="lede">每次任务的数量、正文完成情况和备份文件都在这里。</p>
            </div>
            <button class="btn primary" @click="page = 'home'">新建采集</button>
          </div>

          <section class="panel history-card">
            <div class="history-toolbar">
              <label class="search-box"><DemoIcon name="search" /><input v-model="historySearch" placeholder="搜索账号" /></label>
              <select><option>全部状态</option><option>已完成</option><option>部分完成</option><option>未完成</option></select>
            </div>
            <div class="table-wrap">
              <table class="history-table">
                <thead><tr><th>账号</th><th>开始 / 完成</th><th>结果</th><th>目标 / 实际</th><th>正文完成</th><th>未完成原因</th><th>备份</th><th /></tr></thead>
                <tbody>
                  <tr v-for="task in filteredTasks" :key="task.id">
                    <td><b>{{ task.account }}</b><small>{{ task.id }}</small></td>
                    <td>{{ task.time }}<small class="finish-time">{{ task.end }}</small></td>
                    <td><span class="task-status" :class="task.tone">{{ task.status }}</span></td>
                    <td>{{ task.target }} / {{ task.count }}</td>
                    <td>{{ task.body }}</td>
                    <td><span v-if="task.reason" class="reason-cell" :title="task.reason">{{ task.reason }}</span><span v-else class="muted">—</span></td>
                    <td><button class="link-btn" @click="downloadBackup(task)">{{ task.backup }} ↓</button></td>
                    <td><button class="link-btn" @click="openTask(task)">查看笔记 →</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </section>

        <!-- 设置 -->
        <section v-else class="page">
          <div class="page-head">
            <div>
              <p class="eyebrow">SETTINGS</p>
              <h1>设置</h1>
              <p class="lede">演示环境只展示配置入口，不会保存真实账号信息。</p>
            </div>
          </div>
          <div class="settings-grid">
            <article class="panel"><p class="eyebrow">LOGIN</p><h3>小红书账号</h3><p>通过浏览器插件读取当前登录状态。</p><button class="btn ghost" type="button">检查连接</button></article>
            <article class="panel"><p class="eyebrow">MODEL</p><h3>AI 模型</h3><p>仅用于八维分析和选题建议。</p><button class="btn ghost" type="button">配置模型</button></article>
            <article class="panel"><p class="eyebrow">DELIVERY</p><h3>飞书</h3><p>当前支持导入文件，直接同步即将开放。</p><button class="btn ghost" type="button">选择导入模板</button></article>
            <article class="panel"><p class="eyebrow">STORAGE</p><h3>本地数据</h3><p>运行数据和备份默认保存在本机。</p><button class="btn ghost" type="button">打开目录</button></article>
            <article class="panel"><p class="eyebrow">VERSION</p><h3>版本与更新</h3><p>当前 0.3.0-beta.6 · 纯前端演示。</p><button class="btn ghost" type="button">检查更新</button></article>
            <article class="panel"><p class="eyebrow">HELP</p><h3>帮助与示例</h3><p>三分钟上手采集、筛选和飞书导入。</p><button class="btn ghost" type="button">查看手册</button></article>
          </div>
        </section>
      </div>
    </main>

    <aside v-if="activeNote" class="drawer">
      <header><span>笔记详情</span><button type="button" aria-label="关闭" @click="activeNote = null"><DemoIcon name="close" /></button></header>
      <div class="drawer-cover" :class="activeNote.cover"><b>{{ activeNote.coverLabel }}</b></div>
      <div class="drawer-body">
        <span class="type-pill" :class="activeNote.type === '视频' ? 'video' : 'image'">{{ activeNote.type }}</span>
        <h2>{{ activeNote.title }}</h2>
        <p class="drawer-meta">{{ activeNote.author }} · {{ activeNote.published }} · {{ activeNote.id }}</p>
        <div class="drawer-metrics">
          <div><b>{{ compact(activeNote.likes) }}</b><span>点赞</span></div>
          <div><b>{{ compact(activeNote.collected) }}</b><span>收藏</span></div>
          <div><b>{{ compact(activeNote.comments) }}</b><span>评论</span></div>
          <div><b>{{ compact(activeNote.shares) }}</b><span>分享</span></div>
        </div>
        <div v-if="activeNote.incomplete" class="drawer-alert">
          <span>未完成原因</span>
          <p>{{ activeNote.failure }}</p>
          <button class="btn ghost" type="button" @click="retryNote">重试这一篇</button>
          <small v-if="retriedNoteId === activeNote.id" class="retry-ok">已重新排队，队列中还有 2 篇</small>
        </div>
        <div class="drawer-section"><span>正文</span><p>{{ activeNote.body }}</p></div>
        <div class="drawer-section"><span>标签</span><div class="drawer-tags"><i v-for="tag in activeNote.tags" :key="tag">{{ tag }}</i></div></div>
        <div class="drawer-section"><span>来源链接</span><code class="source-link">{{ demoLink(activeNote.id) }}</code></div>
        <div class="drawer-actions">
          <button class="btn primary" type="button" @click="toggleMarkedFromDrawer">加入选题</button>
          <button class="btn ghost" type="button" @click="addNoteAccountToCompare">加入账号对比</button>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onUnmounted, ref, watch } from 'vue'

type Page = 'home' | 'library' | 'analysis' | 'compare' | 'feishu' | 'history' | 'settings'
type AnalysisTab = 'overview' | 'dimensions' | 'drafts' | 'evidence'
type NoteType = '图文' | '视频'

interface DemoNote {
  id: string
  title: string
  author: string
  type: NoteType
  published: string
  likes: number
  collected: number
  comments: number
  shares: number
  tags: string[]
  cover: string
  coverLabel: string
  body: string
  incomplete?: boolean
  failure?: string
}

const iconPaths: Record<string, string[]> = {
  home: ['M3.6 10.9 12 3.9l8.4 7', 'M5.9 9.7V20h12.2V9.7', 'M9.9 20v-5.1h4.2V20'],
  library: ['M4.4 5.4h15.2v13.2H4.4z', 'M4.4 9.6h15.2', 'M9.6 9.6v9'],
  compass: ['M12 3.6a8.4 8.4 0 1 0 0 16.8 8.4 8.4 0 0 0 0-16.8z', 'M15.6 8.4l-2.2 4.9-4.9 2.2 2.2-4.9z'],
  compare: ['M4.2 7.6h8.4', 'M10.4 4.9l2.8 2.7-2.8 2.7', 'M19.8 16.4h-8.4', 'M13.6 13.7l-2.8 2.7 2.8 2.7'],
  send: ['M20.2 4.4 3.9 11.1l6.3 2.6 2.6 6.3z', 'M20.2 4.4 10.2 13.7'],
  clock: ['M12 3.9a8.1 8.1 0 1 0 0 16.2 8.1 8.1 0 0 0 0-16.2z', 'M12 7.8v4.5l3 1.8'],
  settings: ['M4 7.6h16', 'M4 12h16', 'M4 16.4h16', 'M8.2 5.3v4.6', 'M15.4 9.7v4.6', 'M11.2 14.1v4.6'],
  link: ['M10.6 13.4a3.4 3.4 0 0 0 4.8 0l2.4-2.4a3.4 3.4 0 1 0-4.8-4.8l-.9.9', 'M13.4 10.6a3.4 3.4 0 0 0-4.8 0l-2.4 2.4a3.4 3.4 0 1 0 4.8 4.8l.9-.9'],
  search: ['M10.9 17.5a6.6 6.6 0 1 0 0-13.2 6.6 6.6 0 0 0 0 13.2z', 'M15.8 15.8 20 20'],
  download: ['M12 4.2v9.6', 'M8.3 10.4 12 14.1l3.7-3.7', 'M5 17.4v1.4h14v-1.4'],
  close: ['M6.2 6.2 17.8 17.8', 'M17.8 6.2 6.2 17.8'],
}

const DemoIcon = (props: { name: string }) =>
  h(
    'svg',
    {
      viewBox: '0 0 24 24',
      width: 17,
      height: 17,
      fill: 'none',
      stroke: 'currentColor',
      'stroke-width': 1.6,
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round',
      'aria-hidden': 'true',
    },
    (iconPaths[props.name] || []).map(d => h('path', { d })),
  )

const navItems = [
  { key: 'home' as Page, label: '首页', icon: 'home' },
  { key: 'library' as Page, label: '笔记库', icon: 'library', count: 12 },
  { key: 'analysis' as Page, label: '账号分析', icon: 'compass' },
  { key: 'compare' as Page, label: '账号对比', icon: 'compare' },
  { key: 'feishu' as Page, label: '飞书交付', icon: 'send', count: 12 },
  { key: 'history' as Page, label: '采集记录', icon: 'clock' },
]

const allowedPages: Page[] = ['home', 'library', 'analysis', 'compare', 'feishu', 'history', 'settings']
const params = new URLSearchParams(window.location.search)
const requestedPage = params.get('page') as Page | null
const page = ref<Page>(requestedPage && allowedPages.includes(requestedPage) ? requestedPage : 'home')

const analysisTabs = [
  { key: 'overview' as AnalysisTab, label: '经营总览' },
  { key: 'dimensions' as AnalysisTab, label: '八维解读' },
  { key: 'drafts' as AnalysisTab, label: '3 个选题与草稿' },
  { key: 'evidence' as AnalysisTab, label: '原始依据' },
]
const requestedTab = params.get('tab') as AnalysisTab | null
const analysisTab = ref<AnalysisTab>(analysisTabs.some(tab => tab.key === requestedTab) ? (requestedTab as AnalysisTab) : 'overview')

const currentLabel = computed(() => navItems.find(item => item.key === page.value)?.label || '设置')
watch([page, analysisTab], ([nextPage, nextTab]) => {
  const url = new URL(window.location.href)
  url.searchParams.set('page', nextPage)
  if (nextPage === 'analysis') url.searchParams.set('tab', nextTab)
  else url.searchParams.delete('tab')
  window.history.replaceState({}, '', url)
})

const profileUrl = ref('')
const collecting = ref(false)
const showCollection = ref(false)
const progress = ref(0)
const collectionState = ref<'idle' | 'running' | 'done' | 'stopped'>('idle')
const resumeNotice = ref('')
let collectionTimer: ReturnType<typeof setInterval> | undefined
let resuming = false
const readCount = computed(() => Math.min(100, Math.round(progress.value)))
const detailCount = computed(() => Math.max(0, Math.min(100, Math.round(((progress.value - 12) / 88) * 100))))
const bodyCount = computed(() => Math.round(detailCount.value * 0.96))
const tagCount = computed(() => Math.round(detailCount.value * 0.94))
const progressSteps = [
  { label: '读取主页', at: 12 },
  { label: '整理正文和标签', at: 34 },
  { label: '检查图片与视频', at: 66 },
  { label: '生成笔记库', at: 92 },
]

const accounts = [
  { id: 'a1', name: '野路手册', desc: '城市周边路线与周末去处', notes: 100, updated: '今天 14:20', color: '#c0442a', engagement: '6.3万' },
  { id: 'a2', name: '一页食光', desc: '家常菜、咖啡和小店清单', notes: 86, updated: '昨天 19:08', color: '#96702c', engagement: '4.8万' },
  { id: 'a3', name: '小城慢拍', desc: '手机摄影和城市观察', notes: 74, updated: '10月28日', color: '#3f6b5c', engagement: '3.2万' },
]
const currentAccount = ref(accounts[0])

const notes = ref<DemoNote[]>([
  { id: 'note-001', title: '花35元坐公交从北京去草原（抄作业版）', author: '野路手册', type: '图文', published: '2026-06-15', likes: 10000, collected: 9397, comments: 625, shares: 5627, tags: ['北京周边', '公交路线', '周末'], cover: 'cover-a', coverLabel: 'BUS 35', body: '全程分三段，共5.5小时。把上车点、换乘站和返程末班车一次写清楚，周末不用自驾也能到草原。' },
  { id: 'note-002', title: '一百元淘到的手机能拍出什么样的画质', author: '小城慢拍', type: '图文', published: '2026-02-01', likes: 15000, collected: 2859, comments: 999, shares: 3260, tags: ['手机摄影', '旧手机', 'CCD'], cover: 'cover-b', coverLabel: 'PHONE 01', body: '所有照片都是直出随手拍。先比较不同年份手机的直出色彩，再看高光、暗部和边缘解析力。' },
  { id: 'note-003', title: '北京冬天可以做的十件小事', author: '野路手册', type: '图文', published: '2025-12-15', likes: 924, collected: 821, comments: 355, shares: 202, tags: ['北京', '冬天', '城市生活'], cover: 'cover-c', coverLabel: 'WINTER', body: '整理了一些不赶时间的小事，适合周末慢慢走，也适合一个人随手记录。' },
  { id: 'note-004', title: '双月湾住一个月，用四栏表选到合适房源', author: '野路手册', type: '图文', published: '2026-09-09', likes: 551, collected: 152, comments: 847, shares: 72, tags: ['双月湾', '旅居', '避坑'], cover: 'cover-d', coverLabel: 'MONTH', body: '睡眠、采购、出行和海景四个条件放在一起看，便宜海景房不一定适合一个月长住。' },
  { id: 'note-005', title: '一个人拍旅行视频，这3个镜头就够了', author: '小城慢拍', type: '视频', published: '2026-08-22', likes: 7426, collected: 2180, comments: 264, shares: 1180, tags: ['旅行视频', '手机拍摄'], cover: 'cover-e', coverLabel: '01:28', body: '一个人也能完成的旅行视频：环境镜头、动作镜头和一句感受。先保证画面稳定，再考虑转场。' },
  { id: 'note-006', title: '北京周边草原主观排名，不只看风景', author: '野路手册', type: '图文', published: '2026-06-15', likes: 371, collected: 496, comments: 56, shares: 329, tags: ['草原', '北京周边', '自驾'], cover: 'cover-f', coverLabel: 'RANK', body: '按路程、补给、住宿和拍照时段排了一个主观顺序，适合第一次去的人做路线选择。' },
  { id: 'note-007', title: '只有本地人才知道的上海小众打卡地', author: '一页食光', type: '图文', published: '2026-02-21', likes: 353, collected: 55, comments: 280, shares: 385, tags: ['上海', '城市散步'], cover: 'cover-g', coverLabel: 'SHANGHAI', body: '避开热门路口，整理了五个适合散步和拍照的小地方，附上附近咖啡和地铁出口。' },
  { id: 'note-008', title: '周末咖啡店清单：坐一下午也不赶人', author: '一页食光', type: '图文', published: '2026-07-12', likes: 684, collected: 1012, comments: 88, shares: 146, tags: ['咖啡店', '周末'], cover: 'cover-h', coverLabel: 'COFFEE', body: '从座位、插座、安静程度和续杯价格四个角度筛选，适合带电脑去坐一下午。' },
  { id: 'note-009', title: '手机拍晚霞，先别急着加滤镜', author: '小城慢拍', type: '视频', published: '2026-08-03', likes: 2310, collected: 1196, comments: 203, shares: 311, tags: ['手机摄影', '晚霞'], cover: 'cover-i', coverLabel: '00:47', body: '先把曝光压下来，再决定天空和高光怎么取舍。滤镜最后加，前期先把颜色留住。' },
  { id: 'note-010', title: '菜市场附近最好吃的三家小馆', author: '一页食光', type: '图文', published: '2026-05-18', likes: 1270, collected: 1664, comments: 132, shares: 205, tags: ['小馆', '城市美食'], cover: 'cover-j', coverLabel: 'LOCAL', body: '不排队、价格稳定、适合一个人吃饭，把菜单和人均写在每一家下面。' },
  { id: 'note-011', title: '突然降温后的晚霞，城市天际线变成了粉色', author: '小城慢拍', type: '图文', published: '2026-09-18', likes: 857, collected: 243, comments: 97, shares: 181, tags: ['晚霞', '手机摄影'], cover: 'cover-k', coverLabel: 'SUNSET', body: '天气变化快的时候，天空层次也会变得更明显。记录同一机位在降温前后的颜色变化。' },
  { id: 'note-012', title: '没有计划的一天，绕着小城走了七公里', author: '野路手册', type: '图文', published: '2026-03-06', likes: 189, collected: 68, comments: 21, shares: 14, tags: ['城市散步', '生活记录'], cover: 'cover-l', coverLabel: '7 KM', body: '没有安排景点，只记录几个路口、两家小店和一段很安静的路。', incomplete: true, failure: '正文未获取，可稍后重试' },
])

const libraryTabs = [
  { key: 'all', label: '全部' },
  { key: 'image', label: '图文' },
  { key: 'video', label: '视频' },
  { key: 'high', label: '互动较高' },
  { key: 'marked', label: '已加入选题' },
  { key: 'incomplete', label: '未完成' },
]
const libraryTab = ref('all')
const search = ref('')
const sortBy = ref('engagement')
const viewMode = ref<'table' | 'cards'>('table')
const selectedIds = ref<string[]>([])
const activeNote = ref<DemoNote | null>(null)
const markedIds = ref<string[]>(['note-001', 'note-004'])
const filtersOpen = ref(false)
const dateRange = ref<'all' | '30' | '90' | '180'>('all')
const onlyWithBody = ref(false)
const onlyIncomplete = ref(false)
const activeFilterCount = computed(() => (dateRange.value !== 'all' ? 1 : 0) + (onlyWithBody.value ? 1 : 0) + (onlyIncomplete.value ? 1 : 0))

function total(note: DemoNote) {
  return note.likes + note.collected + note.comments + note.shares
}
function compact(value: number) {
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`
  return value.toLocaleString('zh-CN')
}
function median(values: number[]) {
  if (!values.length) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : Math.round((sorted[mid - 1] + sorted[mid]) / 2)
}
function noteDate(note: DemoNote) {
  return new Date(`${note.published}T00:00:00`)
}
function withinRange(note: DemoNote) {
  if (dateRange.value === 'all') return true
  const age = (Date.now() - noteDate(note).getTime()) / 86400000
  return age <= Number(dateRange.value)
}

const visibleNotes = computed(() => {
  const query = search.value.trim().toLowerCase()
  const rows = notes.value.filter(note => {
    const tabOk =
      libraryTab.value === 'all' ||
      (libraryTab.value === 'image' && note.type === '图文') ||
      (libraryTab.value === 'video' && note.type === '视频') ||
      (libraryTab.value === 'high' && total(note) >= medianEngagement.value) ||
      (libraryTab.value === 'marked' && markedIds.value.includes(note.id)) ||
      (libraryTab.value === 'incomplete' && note.incomplete)
    const queryOk = !query || `${note.title} ${note.body} ${note.tags.join(' ')}`.toLowerCase().includes(query)
    const bodyOk = !onlyWithBody.value || !note.incomplete
    const incompleteOk = !onlyIncomplete.value || Boolean(note.incomplete)
    return tabOk && queryOk && bodyOk && incompleteOk && withinRange(note)
  })
  const sorters: Record<string, (a: DemoNote, b: DemoNote) => number> = {
    collected: (a, b) => b.collected - a.collected,
    comments: (a, b) => b.comments - a.comments,
    shares: (a, b) => b.shares - a.shares,
    published: (a, b) => b.published.localeCompare(a.published),
    engagement: (a, b) => total(b) - total(a),
  }
  return [...rows].sort(sorters[sortBy.value] || sorters.engagement)
})
const allVisibleSelected = computed(() => visibleNotes.value.length > 0 && visibleNotes.value.every(note => selectedIds.value.includes(note.id)))
const medianEngagement = computed(() => median(notes.value.map(total)))
const imageShare = computed(() => Math.round(notes.value.filter(note => note.type === '图文').length / notes.value.length * 100))
const videoShare = computed(() => 100 - imageShare.value)
const latestPublish = computed(() => [...notes.value].sort((a, b) => b.published.localeCompare(a.published))[0]?.published || '—')

const overview = computed(() => {
  const totals = notes.value.map(total)
  const totalEngagement = totals.reduce((sum, value) => sum + value, 0)
  const ranked = [...notes.value].sort((a, b) => total(b) - total(a))
  const topCount = Math.max(1, Math.ceil(notes.value.length * 0.2))
  const topSum = ranked.slice(0, topCount).reduce((sum, note) => sum + total(note), 0)
  const topShare = totalEngagement ? Math.round((topSum / totalEngagement) * 1000) / 10 : 0
  const videos = notes.value.filter(note => note.type === '视频')
  const images = notes.value.filter(note => note.type === '图文')
  const videoMedian = median(videos.map(total))
  const imageMedian = median(images.map(total))
  const formatRatio = imageMedian ? Math.round((videoMedian / imageMedian) * 10) / 10 : 0
  const withDigits = notes.value.filter(note => /\d/.test(note.title))
  const tagCounts = new Map<string, number>()
  notes.value.forEach(note => note.tags.forEach(tag => tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1)))
  const top = [...tagCounts.entries()].sort((a, b) => b[1] - a[1])[0] || ['—', 0]
  return {
    totalEngagement,
    median: medianEngagement.value,
    topCount,
    topShare,
    videoCount: videos.length,
    imageCount: images.length,
    videoMedian,
    imageMedian,
    formatRatio,
    titleCount: withDigits.length,
    titlePct: Math.round((withDigits.length / notes.value.length) * 100),
    topTag: top[0],
    topTagCount: top[1],
  }
})

const evidenceRows = computed(() =>
  [...notes.value]
    .sort((a, b) => total(b) - total(a))
    .slice(0, 6)
    .map((note, index) => ({
      rank: index + 1,
      id: note.id,
      title: note.title,
      type: note.type,
      engagement: total(note),
      quote: `${note.body.split('。')[0]}。`,
    })),
)

const dimensions = [
  { title: '账号定位', badge: '清晰', tag: '定位', tone: 'blue', headline: '城市周边路线与周末去处', copy: '围绕路线、时间成本和实际体验做内容，适合想低成本出门的人。', metrics: ['路线类 42%', '生活观察 28%'], advice: '主页简介和置顶笔记统一写“北京出发、公交可达、成本多少”，让新用户三秒内判断这是不是自己要找的账号。' },
  { title: '内容方向', badge: '3 个主线', tag: '方向', tone: 'green', headline: '路线清单、城市散步、旅居选择', copy: '路线清单更容易被收藏，城市散步适合补充日常感。', metrics: ['图文 78%', '视频 22%'], advice: '三条主线按 5:3:2 排内容量：路线清单保底收藏，城市散步拉近距离，旅居选择做高客单探索。' },
  { title: '选题结构', badge: '可连续', tag: '选题', tone: 'blue', headline: '“城市 + 路线 + 成本”最好复用', copy: '把目的地、时间和花费写清楚的内容，收藏明显更高。', metrics: ['清单类 34%', '攻略类 27%'], advice: '固定三个信息位：总花费、总时长、返程末班车。每篇只替换目的地，形成可连续更新的栏目。' },
  { title: '标题与封面', badge: '数字更常见', tag: '标题', tone: 'orange', headline: '数字、价格和具体地点出现频繁', copy: '标题直接给出路线成本或件数，比泛泛的旅行感受更容易判断价值。', metrics: ['含数字 31%', '含地点 48%'], advice: '标题保留具体数字，封面统一用大字地名 + 一句成本，避免每篇换风格导致识别度下降。' },
  { title: '互动表现', badge: '收藏突出', tag: '互动', tone: 'green', headline: '路线清单的收藏和分享更高', copy: '用户更愿意保存能直接照着走的路线，而不是只看风景。', metrics: ['收藏占比 42%', '分享占比 19%'], advice: '在正文末尾加一句“出发前先存这一条”，把收藏意图写出来；分享高的内容可补二条同目的地。' },
  { title: '发布节奏', badge: '偏集中', tag: '节奏', tone: 'orange', headline: '六月内容量最高', copy: '周末出行内容有自己的季节性，建议按目的地建立系列。', metrics: ['月均 9 篇', '高峰 15 篇'], advice: '按季节提前一个月排期，周四晚发布周末路线，节假日前两周发长线与短线各一篇。' },
  { title: '标签与搜索', badge: '地域集中', tag: '标签', tone: 'blue', headline: '北京、周边路线和双月湾出现最多', copy: '地域标签能帮助内容归类，但不能直接说明搜索流量。', metrics: ['北京 34 篇', '周边 21 篇'], advice: '每篇固定 3 个地域标签 + 1 个成本标签，方便后续在飞书按标签分组复盘，不宣称搜索排名。' },
  { title: '下一步建议', badge: '3 个选题', tag: '动作', tone: 'green', headline: '先做低成本路线系列', copy: '固定成本、路线和返程三个信息，连续做两周再看收藏变化。', metrics: ['每周 2 篇', '连续 2 周'], advice: '两周做 4 篇同结构路线，第三周对比收藏中位数是否提升，再决定是否扩到城市散步。' },
]
const analysisReady = ref(true)
const topicsReady = ref(true)
const topics = [
  { title: '北京出发，三条不超过50元的周末公交路线', problem: '想出门但不想自驾、不想临时查换乘。', titleA: '50元以内，公交能到的三个北京周末目的地', titleB: '不用自驾：我整理了三条便宜又好走的路线', format: '路线清单 + 每段车费和时间', opening: '先算一笔账：三个人自驾一天油费过路费大约多少，再对比公交的三段票价，差距一眼能看出来。', outline: ['总成本对比：自驾 vs 公交三段票价', '路线一：城里出发，换乘一次，末班车时间', '路线二：目的地补给点和厕所位置', '路线三：适合拍照的时段和机位', '三条路线的适用人群和避坑提醒'], observe: ['收藏中位数', '路线类评论'] },
  { title: '双月湾住一周：先按四件生活小事选房', problem: '海景房看起来都差不多，住进去才发现采买和出行不方便。', titleA: '海景房不是越近海越好：先看这四件事', titleB: '双月湾住一周，我会这样筛掉一半房源', format: '四栏比较 + 一天生活路线', opening: '住进去第一天就发现，离海十米不如离菜市场五百米，这篇把一周里真正影响体验的四件事列出来。', outline: ['睡眠：楼层、朝向和夜间噪音', '采购：菜市场步行距离与营业时间', '出行：打车难不难、停车多少钱', '海景：楼层高度与遮挡物', '一天生活路线示范 + 订房前必问的三个问题'], observe: ['收藏率', '长评论占比'] },
  { title: '城市散步系列：一条路看老店、树荫和傍晚', problem: '想拍城市但不知道从哪里开始。', titleA: '一条路走完北京的树荫、老店和傍晚', titleB: '周末不赶景点，我更喜欢这样走一座城', format: '路线地图 + 三个停留点', opening: '这条路我走了三次，每次都能看到不同的傍晚。不用门票，也不用赶时间，两个半小时刚好。', outline: ['起点：地铁哪一站、几点出发光线最好', '停留点一：开了二十年的老店和它的招牌', '停留点二：树荫最密的一段路', '停留点三：傍晚看天际线的机位', '路上能吃什么 + 返程建议'], observe: ['分享次数', '收藏中位数'] },
]

const compareAccounts = ref(['a1', 'a2'])
const compareReady = ref(true)
const comparedAccounts = computed(() => accounts.filter(account => compareAccounts.value.includes(account.id)))
const compareGridStyle = computed(() => ({ gridTemplateColumns: `140px repeat(${Math.max(1, comparedAccounts.value.length)}, minmax(0, 1fr))` }))
const compareDimensions = ['账号定位', '内容方向', '选题结构', '标题与封面', '互动表现', '发布节奏', '标签与搜索', '下一步动作']
const compareMatrix: Record<string, string[]> = {
  a1: ['城市周边路线与低成本出行', '路线、旅居、城市散步', '成本 + 路线 + 时间', '地点和价格明确', '收藏和分享突出', '周末集中', '北京及周边为主', '做连续路线栏目'],
  a2: ['城市吃喝与周末小店', '咖啡、小馆、城市散步', '地点 + 菜单 + 消费', '清单感更强', '收藏偏高，评论稳定', '工作日和周末都发', '城市与店铺为主', '补充一人食路线'],
  a3: ['手机摄影与城市观察', '摄影技巧、城市记录', '机位 + 参数 + 对比', '画面感和对比强', '收藏低、分享高', '随天气和素材更新', '摄影与城市关键词', '固定机位做前后对比'],
}
const compareRows = computed(() =>
  compareDimensions.map((title, index) => ({
    title,
    values: comparedAccounts.value.map(account => compareMatrix[account.id]?.[index] || '未获取'),
  })),
)
const volumeHint = computed(() => {
  if (comparedAccounts.value.length < 2) return ''
  const counts = comparedAccounts.value.map(account => account.notes)
  const min = Math.min(...counts)
  const max = Math.max(...counts)
  if (!min || max / min < 1.25) return ''
  return `笔记数差异较大（${min} 至 ${max} 篇，相差 ${Math.round((max / min - 1) * 100)}%）：对比时看结构和比例，不直接比绝对值。`
})
const weekPlan = [
  { day: '周一', title: '整理本周三个目的地', copy: '按车费、时长和返程三个字段建表，先选出可复用的目的地。' },
  { day: '周二', title: '发布路线一篇', copy: '50 元以内公交路线，封面统一大字地名 + 成本。' },
  { day: '周三', title: '补拍封面和三张路线图', copy: '同一机位、同一字体，保证系列识别度。' },
  { day: '周五', title: '发布城市散步一篇', copy: '一条路三个停留点，结尾引导收藏备用。' },
  { day: '周日', title: '复盘收藏中位数', copy: '对比两周同结构内容的收藏和分享，再决定是否扩题。' },
]

const feishuTables = [
  { name: '账号总览', count: '3 条' },
  { name: '全部笔记', count: '100 条' },
  { name: '图文笔记', count: '78 条' },
  { name: '视频笔记', count: '22 条' },
  { name: '选题清单', count: '12 条' },
  { name: '采集记录', count: '6 条' },
]
const selectedTables = ref(feishuTables.map(item => item.name))
const generatingFeishu = ref(false)
const generatedFeishu = ref(false)
const deliveryAccountId = ref(currentAccount.value.id)
const deliveryAccount = computed(() => accounts.find(account => account.id === deliveryAccountId.value) || currentAccount.value)

const tasks = [
  { id: 'task-08', account: '野路手册', status: '已完成', tone: 'ok', time: '今天 14:20', end: '今天 14:32', count: 100, target: 100, body: '96 篇', backup: 'xlsx', reason: '' },
  { id: 'task-07', account: '一页食光', status: '已完成', tone: 'ok', time: '昨天 19:08', end: '昨天 19:19', count: 86, target: 100, body: '83 篇', backup: 'xlsx', reason: '' },
  { id: 'task-06', account: '小城慢拍', status: '部分完成', tone: 'warn', time: '10月28日 10:42', end: '10月28日 10:59', count: 74, target: 100, body: '70 篇', backup: 'xlsx', reason: '访问受限，4 篇正文未获取' },
  { id: 'task-05', account: '周末地图', status: '未完成', tone: 'danger', time: '10月27日 16:31', end: '10月27日 16:38', count: 31, target: 100, body: '28 篇', backup: 'csv', reason: '登录状态失效，任务提前停止' },
]
const historySearch = ref('')
const filteredTasks = computed(() => tasks.filter(task => task.account.includes(historySearch.value)))

function tabCount(key: string) {
  if (key === 'all') return notes.value.length
  if (key === 'image') return notes.value.filter(note => note.type === '图文').length
  if (key === 'video') return notes.value.filter(note => note.type === '视频').length
  if (key === 'high') return notes.value.filter(note => total(note) >= medianEngagement.value).length
  if (key === 'marked') return markedIds.value.length
  return notes.value.filter(note => note.incomplete).length
}
function resetFilters() {
  dateRange.value = 'all'
  onlyWithBody.value = false
  onlyIncomplete.value = false
}
function runProgress() {
  collecting.value = true
  collectionState.value = 'running'
  clearInterval(collectionTimer)
  collectionTimer = setInterval(() => {
    progress.value = Math.min(100, progress.value + Math.ceil(Math.random() * 7))
    if (progress.value >= 100) {
      clearInterval(collectionTimer)
      collecting.value = false
      collectionState.value = 'done'
      if (resuming) {
        resumeNotice.value = '继续处理完成：1 篇仍访问受限，已保留现有下载。'
        resuming = false
      }
    }
  }, 110)
}
function startCollection() {
  showCollection.value = true
  progress.value = 0
  resuming = false
  resumeNotice.value = ''
  runProgress()
}
function stopCollection() {
  clearInterval(collectionTimer)
  collecting.value = false
  collectionState.value = 'stopped'
}
function resumeCollection() {
  resuming = true
  runProgress()
}
function openAccount(account: typeof accounts[number]) {
  currentAccount.value = account
  page.value = 'library'
}
function toggleSelect(id: string) {
  selectedIds.value = selectedIds.value.includes(id) ? selectedIds.value.filter(value => value !== id) : [...selectedIds.value, id]
}
function toggleAll() {
  selectedIds.value = allVisibleSelected.value ? [] : visibleNotes.value.map(note => note.id)
}
function clearSelection() {
  selectedIds.value = []
}
function toggleMarked() {
  markedIds.value = [...new Set([...markedIds.value, ...selectedIds.value])]
  selectedIds.value = []
}
function toggleMarkedFromDrawer() {
  if (!activeNote.value) return
  if (!markedIds.value.includes(activeNote.value.id)) markedIds.value.push(activeNote.value.id)
}
const retriedNoteId = ref('')
function retryNote() {
  if (!activeNote.value) return
  retriedNoteId.value = activeNote.value.id
}
function demoLink(id: string) {
  return `https://www.xiaohongshu.com/explore/${id}`
}
function addNoteAccountToCompare() {
  if (!activeNote.value) return
  const account = accounts.find(item => item.name === activeNote.value?.author)
  if (account && !compareAccounts.value.includes(account.id) && compareAccounts.value.length < 5) compareAccounts.value.push(account.id)
  activeNote.value = null
  compareReady.value = true
  page.value = 'compare'
}
function openTask(task: typeof tasks[number]) {
  const account = accounts.find(item => item.name === task.account)
  if (account) currentAccount.value = account
  page.value = 'library'
}
function downloadCsv(filename: string, rows: (string | number)[][]) {
  const content = rows.map(row => row.map(value => `"${String(value).replace(/"/g, '""')}"`).join(',')).join('\n')
  const url = URL.createObjectURL(new Blob(['\ufeff' + content], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
function downloadBackup(task: typeof tasks[number]) {
  const header = ['标题', '类型', '发布时间', '点赞', '收藏', '评论', '分享', '标签', '来源链接']
  const rows = notes.value.map(note => [note.title, note.type, note.published, note.likes, note.collected, note.comments, note.shares, note.tags.join(' / '), demoLink(note.id)])
  downloadCsv(`${task.account}-采集备份-${task.id}.csv`, [header, ...rows])
}
function downloadDemoCsv() {
  const header = ['标题', '类型', '点赞', '收藏', '评论', '分享', '标签', '来源链接']
  const rows = notes.value.map(note => [note.title, note.type, note.likes, note.collected, note.comments, note.shares, note.tags.join(' / '), demoLink(note.id)])
  downloadCsv('飞书导入示例-野路手册.csv', [header, ...rows])
}
function toggleCompare(id: string) {
  if (compareAccounts.value.includes(id)) {
    if (compareAccounts.value.length > 2) compareAccounts.value = compareAccounts.value.filter(value => value !== id)
  } else if (compareAccounts.value.length < 5) {
    compareAccounts.value.push(id)
  }
}
let feishuTimer: ReturnType<typeof setTimeout> | undefined
function generateFeishu() {
  generatingFeishu.value = true
  generatedFeishu.value = false
  feishuTimer = setTimeout(() => {
    generatingFeishu.value = false
    generatedFeishu.value = true
  }, 900)
}
onUnmounted(() => {
  clearInterval(collectionTimer)
  clearTimeout(feishuTimer)
})
</script>

<style scoped>
.shell {
  --xhs: #ff2442;
  --xhs-dark: #d8102f;
  --xhs-soft: #fff0f2;
  --rust: #b5430c;
  --rust-soft: #f2e6d8;
  --paper: #f5f0e7;
  --paper-2: #fbf7f0;
  --card: #fffdf9;
  --ink: #28251f;
  --ink-2: #4b453b;
  --muted: #7d7364;
  --muted-2: #9b8d79;
  --line: #ded4c5;
  --line-soft: #e9e1d5;
  --serif: "Songti SC", "STSong", "SimSun", Georgia, serif;
  display: grid;
  grid-template-columns: 236px minmax(0, 1fr);
  min-height: 100vh;
  background: var(--paper);
  color: var(--ink);
  font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 13px;
  line-height: 1.6;
}
.shell * { box-sizing: border-box; }
.shell button, .shell input, .shell select { font: inherit; }

/* 侧栏 */
.side {
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 22px 14px 16px;
  background: var(--paper-2);
  border-right: 1px solid var(--line);
}
.brand { display: flex; align-items: center; gap: 10px; padding: 0 8px; margin-bottom: 26px; }
.brand-mark {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: var(--xhs);
  color: #fff;
  box-shadow: 0 5px 14px rgba(255, 36, 66, 0.24);
}
.brand-copy { display: flex; flex-direction: column; }
.brand-copy strong { font-family: var(--serif); font-size: 18px; letter-spacing: 0.02em; line-height: 1.2; }
.brand-copy span { margin-top: 3px; font-size: 10px; color: var(--muted-2); letter-spacing: 0.02em; }
.nav { display: grid; gap: 2px; }
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 11px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--ink-2);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.nav-item svg { color: var(--xhs); opacity: 0.72; flex: 0 0 auto; transition: opacity 0.15s; }
.nav-item span { flex: 1; }
.nav-item i {
  font-style: normal;
  font-size: 10px;
  color: var(--rust);
  background: var(--rust-soft);
  border-radius: 20px;
  padding: 1px 7px;
}
.nav-item:hover { background: #f3ece0; color: var(--ink); }
.nav-item.active { background: var(--xhs-soft); color: var(--xhs-dark); font-weight: 700; }
.nav-item.active svg { opacity: 1; }
.side-foot { margin-top: auto; padding-top: 12px; border-top: 1px solid var(--line-soft); }
.account-chip {
  margin-top: 10px;
  padding: 10px 11px;
  border: 1px solid var(--line-soft);
  border-radius: 7px;
  background: #f8f2e8;
  display: flex;
  flex-direction: column;
}
.account-chip b { font-size: 11.5px; }
.account-chip span { font-size: 10px; color: var(--muted-2); margin-top: 2px; }

/* 顶栏 */
.main { min-width: 0; }
.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 52px;
  padding: 0 30px;
  background: rgba(251, 247, 240, 0.94);
  border-bottom: 1px solid var(--line);
  backdrop-filter: blur(6px);
}
.crumb { display: flex; align-items: center; gap: 7px; font-size: 11.5px; color: var(--muted-2); }
.crumb i { font-style: normal; color: #c9bda9; }
.crumb strong { color: var(--ink-2); font-weight: 600; }
.top-actions { display: flex; align-items: center; gap: 12px; }
.demo-badge {
  padding: 3px 9px;
  border-radius: 20px;
  background: var(--xhs-soft);
  color: var(--xhs-dark);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.real-link { font-size: 11.5px; color: var(--muted); text-decoration: none; border-bottom: 1px solid transparent; }
.real-link:hover { color: var(--xhs-dark); border-color: currentColor; }

.content { max-width: 1240px; margin: 0 auto; padding: 28px 32px 64px; }

/* 通用 */
.eyebrow {
  margin: 0 0 7px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted-2);
}
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 20px; }
.page-head h1 { margin: 0; font-family: var(--serif); font-size: 30px; line-height: 1.22; letter-spacing: -0.01em; }
.lede { margin: 8px 0 0; max-width: 620px; font-size: 12.5px; color: var(--muted); }
.lede a { color: var(--rust); text-decoration: none; border-bottom: 1px solid #dcc3ad; }
.head-actions { display: flex; gap: 8px; flex-shrink: 0; }
.limit-chip {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 12px 16px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--card);
}
.limit-chip b { font-family: var(--serif); font-size: 30px; color: var(--rust); line-height: 1; }
.limit-chip span { font-size: 10.5px; color: var(--muted-2); }
.serial-chip {
  padding: 5px 11px;
  border: 1px solid var(--rust);
  border-radius: 4px;
  color: var(--rust);
  font-size: 10.5px;
  letter-spacing: 0.04em;
}
.panel { background: var(--card); border: 1px solid var(--line); border-radius: 7px; padding: 18px 20px; }
.hint { margin: 10px 0 0; font-size: 10.5px; color: var(--muted-2); }
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 34px;
  padding: 7px 15px;
  border: 1px solid transparent;
  border-radius: 5px;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.btn.primary { background: var(--xhs); color: #fff; box-shadow: 0 4px 12px rgba(255, 36, 66, 0.18); }
.btn.primary:hover { background: var(--xhs-dark); }
.btn.primary:disabled { background: #e7b3bd; box-shadow: none; cursor: not-allowed; }
.btn.ghost { background: #fff; border-color: var(--line); color: var(--ink-2); }
.btn.ghost:hover { border-color: var(--rust); color: var(--rust); }
.btn.ghost.active { border-color: var(--xhs); color: var(--xhs-dark); background: var(--xhs-soft); }
.btn.wide { width: 100%; margin-top: 12px; }
.link-btn { border: 0; background: none; padding: 0; color: var(--rust); font-size: 11.5px; cursor: pointer; }
.link-btn:hover { text-decoration: underline; }
.muted { color: var(--muted-2); }

/* 指标与卡 */
.kpi-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.library-kpi { grid-template-columns: repeat(5, minmax(0, 1fr)); margin-bottom: 18px; }
.kpi { background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 14px 15px 13px; }
.kpi span { display: block; font-size: 10px; font-weight: 700; letter-spacing: 0.04em; color: var(--rust); }
.kpi b { display: block; margin-top: 7px; font-family: var(--serif); font-size: 32px; line-height: 1.1; color: var(--ink); }
.kpi small { display: block; margin-top: 5px; font-size: 10px; color: var(--muted-2); }

/* 首页 */
.capture { margin-top: 22px; }
.capture-copy h2 { margin: 0; font-family: var(--serif); font-size: 22px; }
.capture-copy p { margin: 6px 0 0; font-size: 12px; color: var(--muted); }
.capture-form { display: flex; gap: 8px; margin-top: 16px; }
.url-input {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: 5px;
  background: #fdfbf7;
  color: var(--muted-2);
}
.url-input input { flex: 1; min-width: 0; padding: 9px 0; border: 0; background: transparent; color: var(--ink); font-size: 12.5px; outline: none; }
.progress { margin-top: 12px; }
.progress-head { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--ink-2); }
.progress-head b { font-family: var(--serif); font-size: 18px; color: var(--rust); }
.dot { display: inline-block; width: 6px; height: 6px; margin-right: 7px; border-radius: 50%; background: var(--xhs); vertical-align: middle; }
.dot.done { background: #2f7a55; }
.bar { height: 4px; margin-top: 10px; background: #e7ded0; border-radius: 4px; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--xhs); transition: width 0.12s linear; }
.progress-counts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 14px; }
.progress-counts div { padding: 9px 11px; border: 1px solid var(--line-soft); border-radius: 5px; background: #fcf8f1; display: flex; flex-direction: column; gap: 2px; }
.progress-counts span { font-size: 10px; color: var(--muted-2); }
.progress-counts b { font-family: var(--serif); font-size: 17px; }
.steps { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.steps div { display: flex; gap: 8px; align-items: flex-start; opacity: 0.5; }
.steps div.active { opacity: 1; }
.steps div > span { width: 18px; height: 18px; flex: 0 0 18px; display: grid; place-items: center; border-radius: 50%; border: 1px solid var(--line); font-size: 9px; color: var(--muted); }
.steps div.active > span { background: var(--xhs-soft); border-color: #f6b9c4; color: var(--xhs-dark); }
.steps b { display: block; font-size: 11.5px; font-weight: 600; }
.steps small { font-size: 9.5px; color: var(--muted-2); }
.progress-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 14px; font-size: 11.5px; color: var(--muted); }
.done-row { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-top: 14px; padding-top: 14px; border-top: 1px dashed var(--line); font-size: 11.5px; color: var(--ink-2); }
.stopped-actions { background: #fdf6e7; border: 1px dashed #e5cf9f; border-radius: 6px; padding: 12px; }
.retry-ok { flex-basis: 100%; font-size: 11px; color: #2f7a55; }
.section-row { display: flex; align-items: baseline; justify-content: space-between; margin: 26px 0 12px; }
.section-row h2 { margin: 0; font-family: var(--serif); font-size: 18px; }
.account-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.account-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 15px;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 7px;
  cursor: pointer;
  transition: border-color 0.15s, transform 0.15s;
}
.account-card:hover { border-color: var(--xhs); transform: translateY(-1px); }
.avatar { width: 34px; height: 34px; flex: 0 0 34px; display: grid; place-items: center; border-radius: 8px; color: #fff; font-size: 14px; font-weight: 700; }
.account-copy { min-width: 0; flex: 1; }
.account-copy h3 { margin: 0; font-family: var(--serif); font-size: 14px; }
.account-copy p { margin: 2px 0 0; font-size: 11px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.account-copy div { display: flex; gap: 12px; margin-top: 6px; font-size: 10px; color: var(--muted-2); }
.go { color: var(--muted-2); }
.home-bottom { display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 12px; margin-top: 18px; }
.panel-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.panel-title h3 { margin: 0; font-family: var(--serif); font-size: 16px; }
.panel-title small { font-size: 10px; color: var(--muted-2); }
.task-row { display: flex; align-items: center; gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--line-soft); }
.task-row:last-child { border-bottom: 0; }
.task-row div { flex: 1; min-width: 0; }
.task-row b { display: block; font-size: 12px; font-weight: 600; }
.task-row small { font-size: 10px; color: var(--muted-2); }
.task-body { font-size: 10.5px; color: var(--muted); }
.task-status { font-size: 10px; padding: 2px 7px; border-radius: 20px; white-space: nowrap; }
.task-status.ok { background: #e7f2e9; color: #2f7a55; }
.task-status.warn { background: #fbeed8; color: #9a6a12; }
.task-status.danger { background: #fde8e6; color: #b03a2e; }
.workflow h3 { margin: 0; font-family: var(--serif); font-size: 19px; }
.workflow-steps { display: flex; align-items: flex-start; gap: 8px; margin: 14px 0 16px; }
.workflow-steps div { flex: 1; }
.workflow-steps b { font-family: var(--serif); font-size: 18px; color: var(--rust); }
.workflow-steps p { margin: 2px 0 0; font-size: 11.5px; font-weight: 600; }
.workflow-steps small { display: block; margin-top: 3px; font-size: 9.5px; color: var(--muted-2); line-height: 1.5; }
.workflow-steps i { color: #c3b49c; font-style: normal; margin-top: 2px; }

/* 笔记库 */
.library-tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--line); margin-bottom: 12px; }
.library-tabs button {
  border: 0;
  background: none;
  padding: 9px 12px 10px;
  font-size: 12px;
  color: var(--muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.library-tabs button span { margin-left: 5px; font-size: 10px; color: var(--muted-2); }
.library-tabs button.active { color: var(--ink); font-weight: 700; border-bottom-color: var(--xhs); }
.library-tabs button.active span { color: var(--xhs-dark); }
.library-toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; }
.search-box {
  flex: 1;
  min-width: 180px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 11px;
  border: 1px solid var(--line);
  border-radius: 5px;
  background: #fdfbf7;
  color: var(--muted-2);
}
.search-box input { flex: 1; min-width: 0; padding: 8px 0; border: 0; background: transparent; font-size: 12px; outline: none; color: var(--ink); }
.library-toolbar select { width: auto; padding: 7px 9px; border: 1px solid var(--line); border-radius: 5px; background: #fff; font-size: 11.5px; color: var(--ink-2); }
.library-toolbar .btn { min-height: 32px; padding: 5px 12px; font-size: 11.5px; flex-shrink: 0; }
.filter-button .count { margin-left: 4px; padding: 0 5px; border-radius: 20px; background: var(--xhs); color: #fff; font-size: 9px; }
.view-switch { display: flex; border: 1px solid var(--line); border-radius: 5px; overflow: hidden; flex-shrink: 0; }
.view-switch button { border: 0; background: #fff; padding: 7px 11px; font-size: 11.5px; color: var(--muted); cursor: pointer; }
.view-switch button.active { background: var(--xhs-soft); color: var(--xhs-dark); font-weight: 700; }
.filter-panel {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px;
  margin-bottom: 10px;
  padding: 11px 13px;
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: #fcf8f1;
  font-size: 11.5px;
  color: var(--ink-2);
}
.filter-panel label { display: flex; align-items: center; gap: 7px; margin: 0; }
.filter-panel select { width: auto; padding: 5px 8px; border: 1px solid var(--line); border-radius: 4px; background: #fff; font-size: 11px; }
.filter-check input { width: 13px; height: 13px; margin: 0; }
.selection-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 10px;
  padding: 9px 13px;
  border: 1px solid #f3c3cc;
  border-radius: 6px;
  background: var(--xhs-soft);
  font-size: 11.5px;
  color: var(--xhs-dark);
}
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; background: var(--card); }
.note-table { width: 100%; border-collapse: collapse; }
.note-table th {
  padding: 9px 10px;
  background: #f4ecdf;
  border-bottom: 1px solid var(--line);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: #6f6355;
  text-align: left;
  white-space: nowrap;
}
.note-table td { padding: 9px 10px; border-bottom: 1px solid var(--line-soft); font-size: 11.5px; vertical-align: middle; }
.note-table tr:last-child td { border-bottom: 0; }
.note-table tr.selected { background: #fff7f8; }
.note-table .check { width: 34px; }
.note-table .check input { width: 13px; height: 13px; }
.note-cell { display: flex; align-items: center; gap: 10px; border: 0; background: none; padding: 0; text-align: left; cursor: pointer; }
.note-cell .thumb {
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  border-radius: 4px;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 8px;
  letter-spacing: 0.06em;
  font-weight: 700;
}
.note-text { display: flex; flex-direction: column; min-width: 0; }
.note-text b { font-size: 12px; font-weight: 600; color: var(--ink); }
.note-text small { margin-top: 2px; font-size: 9.5px; color: var(--muted-2); }
.type-pill { font-size: 9.5px; padding: 2px 7px; border-radius: 20px; border: 1px solid var(--line); color: var(--muted); white-space: nowrap; }
.type-pill.image { background: #f6efe3; }
.type-pill.video { background: #f4e9e4; color: #a4543a; border-color: #e8cdc2; }
.tags { display: flex; gap: 4px; flex-wrap: wrap; }
.tags i { font-style: normal; font-size: 9.5px; padding: 1px 6px; border-radius: 3px; background: #f4ecdf; color: #7d6b56; }
.status-ok { font-size: 10px; color: #2f7a55; }
.status-warn { font-size: 10px; color: #a5720f; }
.more { border: 0; background: none; color: var(--muted-2); cursor: pointer; letter-spacing: 0.1em; }
.empty-state { padding: 30px; text-align: center; color: var(--muted-2); font-size: 12px; }
.note-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.note-card { background: var(--card); border: 1px solid var(--line); border-radius: 6px; overflow: hidden; cursor: pointer; transition: border-color 0.15s, transform 0.15s; }
.note-card:hover { border-color: var(--xhs); transform: translateY(-1px); }
.note-card.selected { border-color: var(--xhs); box-shadow: 0 0 0 2px var(--xhs-soft); }
.card-cover { position: relative; height: 116px; display: grid; place-items: center; color: #fff; }
.card-cover b { font-family: var(--serif); font-size: 19px; letter-spacing: 0.04em; }
.card-cover i { position: absolute; top: 8px; left: 8px; font-style: normal; font-size: 9px; padding: 1px 6px; border-radius: 3px; background: rgba(0, 0, 0, 0.35); }
.card-cover button { position: absolute; top: 7px; right: 7px; width: 20px; height: 20px; border: 0; border-radius: 50%; background: rgba(255, 255, 255, 0.92); color: var(--xhs-dark); font-size: 11px; cursor: pointer; }
.note-card-copy { padding: 10px 11px 12px; }
.note-card-copy h3 { margin: 0; font-size: 11.5px; line-height: 1.55; font-weight: 600; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.note-card-copy p { margin: 5px 0 0; font-size: 9.5px; color: var(--muted-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.note-card-copy div { display: flex; gap: 8px; margin-top: 7px; font-size: 9.5px; color: var(--muted); }

/* 分析 */
.tabs { display: flex; gap: 26px; border-bottom: 1px solid var(--line); margin: 16px 0 20px; }
.tabs button {
  position: relative;
  border: 0;
  background: none;
  padding: 0 0 10px;
  font-size: 12.5px;
  color: var(--muted);
  cursor: pointer;
}
.tabs button.active { color: var(--ink); font-weight: 700; }
.tabs button.active::after { content: ""; position: absolute; left: 0; right: 0; bottom: -1px; height: 2px; background: var(--rust); }
.insight-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
.insight { background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 18px 20px 20px; }
.tag { margin: 0; font-size: 9px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: #9a8b74; }
.insight .figure { display: block; margin-top: 12px; font-family: var(--serif); font-size: 42px; line-height: 1; color: var(--rust); }
.insight small { display: block; margin-top: 6px; font-size: 10px; color: var(--muted-2); }
.insight h3 { margin: 16px 0 8px; font-family: var(--serif); font-size: 18px; line-height: 1.45; font-weight: 700; }
.insight > p:last-child { margin: 0; font-size: 11.5px; line-height: 1.8; color: #5f584d; }
.boundary { margin: 14px 0 0; padding: 10px 13px; background: #efe7da; border-radius: 4px; font-size: 10.5px; color: #776d5d; }
.dimension-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.dimension-card { background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 15px 17px 16px; }
.dimension-card > header { display: flex; align-items: center; gap: 11px; padding-bottom: 10px; border-bottom: 1px solid var(--line-soft); }
.dimension-card > header > span { font-family: var(--serif); font-size: 24px; line-height: 1; color: var(--rust); }
.dimension-card > header > div { flex: 1; min-width: 0; }
.dimension-card h3 { margin: 0; font-family: var(--serif); font-size: 15px; }
.dimension-card header small { font-size: 9.5px; color: var(--muted-2); }
.dimension-card header i { font-style: normal; font-size: 9px; padding: 1px 7px; border-radius: 20px; border: 1px solid var(--line); color: var(--muted); }
.dimension-card header i.blue { color: #35597f; border-color: #cfdcea; background: #eef3f9; }
.dimension-card header i.green { color: #2f7a55; border-color: #cfe2d5; background: #edf6ef; }
.dimension-card header i.orange { color: #a5720f; border-color: #ecdcb9; background: #fbf3e2; }
.dimension-card h4 { margin: 12px 0 7px; font-family: var(--serif); font-size: 14.5px; line-height: 1.5; font-weight: 700; }
.dimension-card > p { margin: 0; font-size: 11.5px; line-height: 1.75; color: #5f584d; }
.chips { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 10px; }
.chips span { font-size: 9.5px; padding: 2px 7px; border-radius: 3px; background: #f4ecdf; color: #7d6b56; }
.dimension-advice { margin-top: 11px; padding: 10px 12px; background: #f8f1e6; border-left: 2px solid var(--rust); border-radius: 0 4px 4px 0; }
.dimension-advice b { display: block; font-size: 9px; letter-spacing: 0.08em; color: var(--rust); margin-bottom: 4px; }
.dimension-advice p { margin: 0; font-size: 11px; line-height: 1.75; color: #5f584d; }
.draft-list { display: grid; gap: 12px; }
.draft { display: grid; grid-template-columns: 48px minmax(0, 1fr); gap: 16px; background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 18px 20px 20px; }
.draft-index { font-family: var(--serif); font-size: 30px; line-height: 1; color: var(--rust); }
.draft-body h3 { margin: 6px 0 4px; font-family: var(--serif); font-size: 19px; line-height: 1.45; }
.draft-problem { margin: 0; font-size: 11.5px; color: var(--muted); }
.title-options { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 13px; }
.title-options > div { padding: 10px 12px; background: #f8f1e6; border-radius: 4px; }
.title-options span { display: block; font-size: 9px; letter-spacing: 0.08em; color: #9a8b74; text-transform: uppercase; }
.title-options b { display: block; margin-top: 4px; font-size: 12px; font-weight: 600; line-height: 1.6; }
.draft-block { margin-top: 13px; }
.draft-block > span { display: block; font-size: 9px; font-weight: 700; letter-spacing: 0.08em; color: #8a3b18; text-transform: uppercase; margin-bottom: 5px; }
.opening { margin: 0; padding: 10px 12px; background: #fdfbf7; border-left: 2px solid var(--rust); font-family: var(--serif); font-size: 12.5px; line-height: 1.85; }
.outline { margin: 0; padding-left: 18px; columns: 2; column-gap: 22px; }
.outline li { font-size: 11.5px; line-height: 1.75; margin-bottom: 4px; break-inside: avoid; }
.draft-observe { display: flex; align-items: center; gap: 6px; margin-top: 13px; }
.draft-observe > span { font-size: 9px; letter-spacing: 0.08em; color: #9a8b74; text-transform: uppercase; }
.draft-observe i { font-style: normal; font-size: 9.5px; padding: 2px 7px; border: 1px dashed var(--line); border-radius: 3px; color: var(--muted); }
.tab-note { margin: 0 0 10px; font-size: 11.5px; color: var(--muted); }
.evidence-table { width: 100%; border-collapse: collapse; min-width: 720px; }
.evidence-table th { padding: 8px 9px; background: #28251f; color: #f4ecdf; font-size: 9.5px; letter-spacing: 0.04em; text-align: left; }
.evidence-table td { padding: 9px; border-bottom: 1px solid var(--line-soft); font-size: 11px; vertical-align: top; }
.evidence-table td b { display: block; font-weight: 600; }
.evidence-table td small { display: block; margin-top: 2px; font-size: 9px; color: var(--muted-2); }
.evidence-table .rank { font-family: var(--serif); font-size: 14px; color: var(--rust); }
.evidence-table .quote { font-family: var(--serif); font-size: 11.5px; line-height: 1.75; color: #4b453b; }
.evidence-table code { font-size: 9.5px; color: var(--muted); word-break: break-all; }

/* 对标 */
.compare-select { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 4px; }
.pick { display: flex; align-items: center; gap: 10px; padding: 12px 13px; background: var(--card); border: 1px solid var(--line); border-radius: 6px; cursor: pointer; text-align: left; }
.pick.active { border-color: var(--xhs); background: var(--xhs-soft); }
.pick div { flex: 1; min-width: 0; }
.pick b { display: block; font-family: var(--serif); font-size: 13px; }
.pick small { display: block; margin-top: 2px; font-size: 10px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pick i { font-style: normal; color: var(--xhs); font-size: 12px; }
.compare-body { margin-top: 16px; display: grid; gap: 12px; }
.compare-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
.compare-cards article { background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 14px 15px; }
.compare-cards h3 { margin: 10px 0 2px; font-family: var(--serif); font-size: 15px; }
.compare-cards p { margin: 0; font-size: 10.5px; color: var(--muted); }
.compare-cards div { display: flex; align-items: baseline; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
.compare-cards div b { font-family: var(--serif); font-size: 20px; color: var(--rust); }
.compare-cards div small { font-size: 9.5px; color: var(--muted-2); margin-right: 8px; }
.compare-table { min-width: 640px; }
.compare-row { display: grid; align-items: stretch; border-bottom: 1px solid var(--line-soft); }
.compare-row > span { padding: 10px 12px; font-size: 11px; color: var(--muted); background: #faf5ec; border-right: 1px solid var(--line-soft); }
.compare-row > p, .compare-row > b { margin: 0; padding: 10px 12px; font-size: 11.5px; border-right: 1px solid var(--line-soft); }
.compare-row > b { font-family: var(--serif); font-size: 12.5px; }
.compare-row.header { background: #f4ecdf; border-bottom: 1px solid var(--line); }
.compare-row.header > span, .compare-row.header > b { font-weight: 700; color: #6f6355; background: transparent; }
.compare-row:last-child { border-bottom: 0; }
.takeaways { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.takeaways article { background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 15px 17px; }
.takeaways h3 { margin: 8px 0 6px; font-family: var(--serif); font-size: 15px; line-height: 1.5; }
.takeaways p:last-child { margin: 0; font-size: 11.5px; line-height: 1.75; color: #5f584d; }
.warn-tag { color: #a4543a; }
.week-plan-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.week-plan-grid article { padding: 11px 12px; border: 1px solid var(--line-soft); border-radius: 5px; background: #fcf8f1; }
.week-plan-grid span { font-size: 9px; letter-spacing: 0.06em; color: var(--rust); }
.week-plan-grid b { display: block; margin-top: 4px; font-size: 11.5px; }
.week-plan-grid p { margin: 4px 0 0; font-size: 10px; line-height: 1.65; color: var(--muted); }

/* 飞书 */
.feishu { display: grid; grid-template-columns: 1.3fr 0.7fr; gap: 12px; }
.feishu-preview { padding: 0; overflow: hidden; }
.preview-top { display: flex; align-items: center; justify-content: space-between; padding: 12px 15px; border-bottom: 1px solid var(--line-soft); background: #faf5ec; }
.preview-top b { font-family: var(--serif); font-size: 13px; }
.preview-top span { margin-left: 8px; font-size: 9.5px; color: var(--muted-2); }
.preview-tools { display: flex; align-items: center; gap: 8px; color: var(--muted-2); }
.preview-tools button { border: 1px solid var(--line); background: #fff; border-radius: 4px; padding: 4px 9px; font-size: 10.5px; color: var(--ink-2); }
.preview-body { display: grid; grid-template-columns: 122px minmax(0, 1fr); min-height: 250px; }
.preview-nav { display: flex; flex-direction: column; gap: 2px; padding: 10px 8px; border-right: 1px solid var(--line-soft); background: #fdfbf7; }
.preview-nav span { padding: 6px 8px; border-radius: 4px; font-size: 10.5px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.preview-nav span.active { background: var(--xhs-soft); color: var(--xhs-dark); font-weight: 600; }
.preview-table { padding: 0; overflow-x: auto; }
.mini-row { display: grid; grid-template-columns: 46px minmax(140px, 1.25fr) 46px 66px 62px 50px 36px; align-items: center; gap: 6px; padding: 6px 10px; border-bottom: 1px solid var(--line-soft); font-size: 10px; color: var(--muted); }
.mini-row.header { background: #f4ecdf; font-weight: 700; color: #6f6355; }
.mini-cover { width: 34px; height: 26px; display: grid; place-items: center; border-radius: 3px; color: #fff; font-size: 7px; font-weight: 700; }
.mini-title { color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.delivery-head h2 { margin: 4px 0 2px; font-family: var(--serif); font-size: 20px; }
.delivery-head p { margin: 0; font-size: 10.5px; color: var(--muted-2); }
.table-options { display: grid; gap: 2px; margin: 14px 0; }
.table-options label { display: flex; align-items: center; gap: 8px; padding: 7px 0; border-bottom: 1px solid var(--line-soft); font-size: 11.5px; cursor: pointer; margin: 0; }
.table-options input { width: 13px; height: 13px; margin: 0; }
.table-options label > span { flex: 1; }
.table-options small { font-size: 9.5px; color: var(--muted-2); }
.destination { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 10.5px; color: var(--muted); }
.destination button { border: 1px solid var(--line); background: #fff; border-radius: 4px; padding: 4px 9px; font-size: 10.5px; color: var(--ink-2); }
.destination button.active { border-color: var(--xhs); color: var(--xhs-dark); background: var(--xhs-soft); }
.destination button:disabled { color: #bcb2a3; }
.delivery-success { display: flex; gap: 9px; align-items: flex-start; margin-top: 12px; padding: 10px 12px; border: 1px solid #cfe2d5; background: #eff7f1; border-radius: 5px; }
.delivery-success > span { color: #2f7a55; font-weight: 700; }
.delivery-success b { display: block; font-size: 11.5px; }
.delivery-success small { font-size: 10px; color: #55705f; }
.import-steps { margin: 12px 0 0; padding-left: 16px; font-size: 10px; color: var(--muted); line-height: 1.8; }

/* 采集记录 */
.history-card { padding: 14px; }
.history-toolbar { display: flex; gap: 8px; margin-bottom: 10px; }
.history-toolbar select { width: auto; flex-shrink: 0; padding: 6px 9px; border: 1px solid var(--line); border-radius: 5px; background: #fff; font-size: 11px; }
.history-table { width: 100%; border-collapse: collapse; min-width: 760px; }
.history-table th { padding: 8px 10px; background: #f4ecdf; font-size: 10px; font-weight: 700; letter-spacing: 0.03em; color: #6f6355; text-align: left; white-space: nowrap; }
.history-table td { padding: 9px 10px; border-bottom: 1px solid var(--line-soft); font-size: 11px; }
.history-table td small { display: block; font-size: 9px; color: var(--muted-2); }
.history-table td b { font-weight: 600; }
.finish-time { margin-top: 2px; }
.reason-cell { font-size: 10.5px; color: #a5720f; }

/* 设置 */
.settings-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.settings-grid h3 { margin: 0 0 4px; font-family: var(--serif); font-size: 16px; }
.settings-grid p { margin: 0 0 12px; font-size: 11px; color: var(--muted); }

/* 抽屉 */
.drawer {
  position: fixed;
  top: 0;
  right: 0;
  z-index: 40;
  width: 400px;
  max-width: 92vw;
  height: 100vh;
  overflow-y: auto;
  background: var(--card);
  border-left: 1px solid var(--line);
  box-shadow: -18px 0 40px rgba(40, 33, 24, 0.12);
}
.drawer header { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--line-soft); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted-2); }
.drawer header button { border: 0; background: none; color: var(--muted); cursor: pointer; display: grid; place-items: center; }
.drawer-cover { height: 150px; display: grid; place-items: center; color: #fff; }
.drawer-cover b { font-family: var(--serif); font-size: 26px; letter-spacing: 0.04em; }
.drawer-body { padding: 16px 18px 28px; }
.drawer-body h2 { margin: 8px 0 4px; font-family: var(--serif); font-size: 20px; line-height: 1.4; }
.drawer-meta { margin: 0; font-size: 10px; color: var(--muted-2); }
.drawer-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 14px 0 4px; }
.drawer-metrics div { padding: 8px 9px; border: 1px solid var(--line-soft); border-radius: 4px; background: #fcf8f1; text-align: center; }
.drawer-metrics b { display: block; font-family: var(--serif); font-size: 15px; }
.drawer-metrics span { font-size: 9px; color: var(--muted-2); }
.drawer-alert { margin: 14px 0; padding: 11px 12px; background: #fdf6e7; border: 1px solid #e7d2a4; border-radius: 5px; display: grid; gap: 6px; }
.drawer-alert > span { font-size: 9px; font-weight: 700; letter-spacing: 0.08em; color: #a5720f; text-transform: uppercase; }
.drawer-alert p { margin: 0; font-size: 11.5px; color: #7a5f24; }
.drawer-alert button { justify-self: start; }
.drawer-section { margin-top: 16px; }
.drawer-section > span { display: block; font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase; color: #9a8b74; margin-bottom: 6px; }
.drawer-section p { margin: 0; font-size: 12px; line-height: 1.85; color: #4b453b; }
.drawer-tags { display: flex; flex-wrap: wrap; gap: 5px; }
.drawer-tags i { font-style: normal; font-size: 10px; padding: 2px 8px; border-radius: 3px; background: #f4ecdf; color: #7d6b56; }
.source-link { display: block; padding: 8px 10px; border: 1px solid var(--line-soft); border-radius: 4px; background: #fcf8f1; font-size: 10px; color: #7d6b56; word-break: break-all; font-family: ui-monospace, Consolas, monospace; }
.drawer-actions { display: flex; gap: 8px; margin-top: 18px; padding-top: 16px; border-top: 1px dashed var(--line); }

/* 封面配色：压低饱和度，让红色回到品牌本身 */
.cover-a { background: linear-gradient(135deg, #2f4a5f, #1d2f3d); }
.cover-b { background: linear-gradient(135deg, #5a4a3c, #38302a); }
.cover-c { background: linear-gradient(135deg, #6c6152, #48413a); }
.cover-d { background: linear-gradient(135deg, #2f5c58, #1f3d3a); }
.cover-e { background: linear-gradient(135deg, #7a4a38, #4d2d22); }
.cover-f { background: linear-gradient(135deg, #4a5a3a, #2f3a26); }
.cover-g { background: linear-gradient(135deg, #4a455f, #2f2c3d); }
.cover-h { background: linear-gradient(135deg, #6b5236, #443322); }
.cover-i { background: linear-gradient(135deg, #8a5a3c, #5a3822); }
.cover-j { background: linear-gradient(135deg, #6a4a2e, #43301d); }
.cover-k { background: linear-gradient(135deg, #7d4a52, #4f2b31); }
.cover-l { background: linear-gradient(135deg, #4a5560, #2f3841); }

.engage { display: flex; gap: 9px; white-space: nowrap; font-size: 11px; color: var(--muted); }
.source-col { color: var(--rust); text-decoration: none; font-size: 12px; }
.source-col:hover { text-decoration: underline; }
.export-status { display: flex; align-items: baseline; gap: 8px; margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--line); font-size: 10.5px; color: var(--muted); }
.export-status > span { font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase; color: #9a8b74; }
.export-status b { color: var(--rust); font-weight: 600; }
.export-status small { margin-left: auto; color: var(--muted-2); }
.account-select { width: 100%; margin: 6px 0; padding: 7px 9px; border: 1px solid var(--line); border-radius: 5px; background: #fff; font-family: var(--serif); font-size: 14px; color: var(--ink); }
.draft-plan { margin-bottom: 14px; padding: 14px 16px; background: #fbf7f0; border: 1px solid var(--line-soft); border-radius: 6px; }
.draft-plan .week-plan-grid { margin-top: 10px; }
.volume-hint { margin: 8px 0 0; padding: 8px 11px; border: 1px solid #ecdcb9; background: #fdf6e7; border-radius: 5px; font-size: 11px; color: #8a6a2a; }

@media (max-width: 1180px) {
  .content { padding: 24px 22px 56px; }
  .kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .library-kpi { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .insight-grid { grid-template-columns: 1fr; }
  .note-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .week-plan-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .compare-select { grid-template-columns: 1fr; }
  .feishu { grid-template-columns: 1fr; }
  .home-bottom { grid-template-columns: 1fr; }
}
</style>
