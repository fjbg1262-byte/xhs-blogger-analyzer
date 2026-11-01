<template>
  <div class="demo-shell">
    <aside class="demo-sidebar">
      <div class="demo-brand">
        <div class="demo-logo">析</div>
        <div><strong>内容采集台</strong><span>小红书 · 账号对标</span></div>
      </div>
      <nav class="demo-nav">
        <button v-for="item in navItems" :key="item.key" :class="{ active: page === item.key }" @click="page = item.key">
          <span>{{ item.icon }}</span>{{ item.label }}<i v-if="item.count">{{ item.count }}</i>
        </button>
      </nav>
      <div class="sidebar-bottom">
        <button @click="page = 'settings'"><span>⚙</span>设置</button>
        <div class="user-mini"><b>运营工作台</b><span>本机账号</span></div>
      </div>
    </aside>

    <main class="demo-main">
      <header class="demo-topbar">
        <div class="breadcrumb"><span>工作台</span><b>/</b><strong>{{ currentLabel }}</strong></div>
        <div class="top-actions">
          <span class="demo-badge">演示数据</span>
          <router-link to="/library" class="real-link">进入真实工具 ↗</router-link>
        </div>
      </header>

      <section v-if="page === 'home'" class="page-content">
        <div class="page-heading">
          <div><p class="eyebrow">ONE-CLICK CONTENT WORKSPACE</p><h1>把主页内容，整理成可用的表格</h1><p>采集公开笔记，整理图文与视频，下载飞书导入包，并直接做账号对标。</p></div>
          <div class="heading-chip"><b>100</b><span>单次最多笔记</span></div>
        </div>

        <section class="capture-card">
          <div class="capture-copy"><span>开始采集</span><h2>粘贴博主主页链接</h2><p>也可以在已登录的小红书主页点击插件，一键启动。</p></div>
          <div class="capture-form">
            <div class="url-input"><span>⌁</span><input v-model="profileUrl" placeholder="https://www.xiaohongshu.com/user/profile/..." /></div>
            <button class="primary" :disabled="collecting" @click="startCollection">{{ collecting ? '正在采集…' : '整理当前主页' }}</button>
            <button class="secondary" @click="page = 'history'">批量链接</button>
          </div>
          <p class="capture-tip">当前演示使用模拟数据，不会访问小红书。</p>
        </section>

        <section v-if="showCollection" class="capture-progress">
          <div class="progress-head">
            <div><span class="status-dot" :class="{ done: collectionState === 'done' }" />{{ collectionState === 'done' ? '采集完成' : collectionState === 'stopped' ? '已停止' : '正在采集' }}</div>
            <b>{{ progress }}%</b>
          </div>
          <div class="progress-bar"><i :style="{ width: progress + '%' }" /></div>
          <div class="progress-counts">
            <div><span>已读取笔记</span><b>{{ readCount }} / 100</b></div>
            <div><span>详情完成</span><b>{{ detailCount }}</b></div>
            <div><span>正文成功</span><b>{{ bodyCount }}</b></div>
            <div><span>标签成功</span><b>{{ tagCount }}</b></div>
          </div>
          <div class="progress-steps">
            <div v-for="(step, index) in progressSteps" :key="step.label" :class="{ active: progress >= step.at }">
              <span>{{ progress >= step.at ? '✓' : index + 1 }}</span><div><b>{{ step.label }}</b><small>{{ progress >= step.at ? '已完成' : '等待中' }}</small></div>
            </div>
          </div>
          <div v-if="collectionState === 'running'" class="progress-actions">
            <span>正在读取第 {{ Math.min(100, readCount + 1) }} 篇笔记</span>
            <button class="secondary" @click="stopCollection">停止采集</button>
          </div>
          <div v-if="collectionState === 'done'" class="done-actions">
            <span>已整理 100 篇笔记，其中正文 96 篇。</span>
            <button class="secondary" @click="page = 'library'">查看笔记库</button>
            <button class="primary" @click="page = 'feishu'">生成飞书文件</button>
            <button class="text-button" @click="page = 'analysis'">账号分析 →</button>
            <small v-if="resumeNotice" class="retry-ok">{{ resumeNotice }}</small>
          </div>
          <div v-else-if="collectionState === 'stopped'" class="done-actions stopped-actions">
            <span>已停止，保留 {{ readCount }} 篇已整理笔记；3 篇正文未获取，保留现有下载。</span>
            <button class="secondary" @click="resumeCollection">继续处理未完成笔记</button>
            <button class="primary" @click="page = 'library'">查看笔记库</button>
            <button class="text-button" @click="page = 'feishu'">保留下载 →</button>
          </div>
        </section>

        <div class="section-line"><h2>最近采集</h2><button @click="page = 'history'">查看全部 <span>→</span></button></div>
        <div class="account-grid">
          <article v-for="account in accounts" :key="account.id" class="account-card" @click="openAccount(account)">
            <div class="account-avatar" :style="{ background: account.color }">{{ account.name.slice(0, 1) }}</div>
            <div class="account-copy"><h3>{{ account.name }}</h3><p>{{ account.desc }}</p><div><span>{{ account.notes }} 篇</span><span>{{ account.updated }}</span></div></div>
            <button aria-label="打开笔记库">→</button>
          </article>
        </div>

        <div class="bottom-grid">
          <section class="mini-panel">
            <div class="panel-title"><div><span>最近任务</span><h3>采集记录</h3></div><button @click="page = 'history'">查看全部</button></div>
            <div v-for="task in tasks.slice(0, 3)" :key="task.id" class="task-row">
              <span class="task-status" :class="task.tone">{{ task.status }}</span>
              <div><b>{{ task.account }}</b><small>{{ task.time }} · {{ task.count }} 篇</small></div>
              <span class="task-count">{{ task.body }}</span>
            </div>
          </section>
          <section class="workflow-panel">
            <span>三步交付</span><h3>采集完，直接进飞书</h3>
            <div class="workflow-steps">
              <div><b>01</b><p>采集主页</p><small>笔记、正文、标签和互动</small></div>
              <i>→</i><div><b>02</b><p>检查表格</p><small>筛选图文、视频和缺项</small></div>
              <i>→</i><div><b>03</b><p>导入飞书</p><small>下载多维表格导入包</small></div>
            </div>
            <button class="primary" @click="page = 'feishu'">打开飞书交付</button>
          </section>
        </div>
      </section>

      <section v-else-if="page === 'library'" class="page-content library-page">
        <div class="library-heading">
          <div><p class="eyebrow">NOTE LIBRARY</p><h1>{{ currentAccount.name }}</h1><p>{{ currentAccount.desc }} <a href="#demo-note" @click.prevent>原主页 ↗</a></p></div>
          <button class="secondary" @click="page = 'analysis'">账号八维分析 →</button>
        </div>
        <div class="account-stats">
          <article><span>笔记</span><b>{{ notes.length }}</b><small>去重后</small></article>
          <article><span>图文</span><b>{{ notes.filter(n => n.type === '图文').length }}</b><small>{{ Math.round(notes.filter(n => n.type === '图文').length / notes.length * 100) }}%</small></article>
          <article><span>视频</span><b>{{ notes.filter(n => n.type === '视频').length }}</b><small>{{ Math.round(notes.filter(n => n.type === '视频').length / notes.length * 100) }}%</small></article>
          <article><span>互动总量</span><b>{{ compact(notes.reduce((sum, n) => sum + total(n), 0)) }}</b><small>赞藏评享</small></article>
          <article><span>单篇中位数</span><b>{{ medianEngagement }}</b><small>本批笔记</small></article>
        </div>

        <div class="library-tabs">
          <button v-for="tab in libraryTabs" :key="tab.key" :class="{ active: libraryTab === tab.key }" @click="libraryTab = tab.key">{{ tab.label }}<span>{{ tabCount(tab.key) }}</span></button>
        </div>
        <section class="library-toolbar">
          <label class="search-box"><span>⌕</span><input v-model="search" placeholder="搜索标题、正文或标签" /></label>
          <select v-model="sortBy"><option value="engagement">按互动排序</option><option value="collected">按收藏排序</option><option value="comments">按评论排序</option><option value="shares">按分享排序</option><option value="published">按发布时间</option></select>
          <button class="filter-button" :class="{ active: filtersOpen }" @click="filtersOpen = !filtersOpen">筛选 <span>{{ activeFilterCount || '⌄' }}</span></button>
          <div class="view-switch"><button :class="{ active: viewMode === 'table' }" @click="viewMode = 'table'">▤ 表格</button><button :class="{ active: viewMode === 'cards' }" @click="viewMode = 'cards'">▦ 封面</button></div>
          <button class="secondary" @click="page = 'feishu'">导出到飞书</button>
        </section>

        <div v-if="filtersOpen" class="filter-panel">
          <label><span>时间范围</span>
            <select v-model="dateRange"><option value="all">全部时间</option><option value="30">近 30 天</option><option value="90">近 90 天</option><option value="180">近半年</option></select>
          </label>
          <label class="filter-check"><input v-model="onlyWithBody" type="checkbox" /><span>只看已抓到正文</span></label>
          <label class="filter-check"><input v-model="onlyIncomplete" type="checkbox" /><span>只看未完成采集</span></label>
          <button class="text-button" @click="resetFilters">重置筛选</button>
        </div>

        <div v-if="selectedIds.length" class="selection-bar"><span>已选择 {{ selectedIds.length }} 篇</span><button @click="clearSelection">清空</button><button @click="page = 'feishu'">导出选中内容</button><button @click="toggleMarked">加入选题</button></div>

        <div v-if="viewMode === 'table'" class="note-table-wrap">
          <table class="note-table">
            <thead><tr><th class="check"><input type="checkbox" :checked="allVisibleSelected" @change="toggleAll" /></th><th>笔记</th><th>类型</th><th>发布时间</th><th>赞 / 藏 / 评</th><th>标签</th><th>采集</th><th /></tr></thead>
            <tbody><tr v-for="note in visibleNotes" :key="note.id" :class="{ selected: selectedIds.includes(note.id) }">
              <td class="check"><input type="checkbox" :checked="selectedIds.includes(note.id)" @change="toggleSelect(note.id)" /></td>
              <td><button class="note-cell" @click="activeNote = note"><div class="thumb" :class="note.cover"><span>{{ note.coverLabel }}</span></div><div><b>{{ note.title }}</b><small>{{ note.author }} · {{ note.id }}</small></div></button></td>
              <td><span class="type-pill" :class="note.type === '视频' ? 'video' : 'image'">{{ note.type }}</span></td>
              <td>{{ note.published }}</td>
              <td><b>{{ compact(note.likes) }}</b><span class="muted"> / {{ compact(note.collected) }} / {{ compact(note.comments) }}</span></td>
              <td><div class="tag-list"><span v-for="tag in note.tags.slice(0, 2)" :key="tag">{{ tag }}</span></div></td>
              <td><span v-if="note.incomplete" class="status-warn" :title="note.failure">未完成</span><span v-else class="status-ok">已完成</span></td>
              <td><button class="more-button" aria-label="查看详情" @click="activeNote = note">···</button></td>
            </tr></tbody>
          </table>
          <div v-if="!visibleNotes.length" class="empty-state">没有符合筛选条件的笔记</div>
        </div>

        <div v-else class="note-grid">
          <article v-for="note in visibleNotes" :key="note.id" class="note-card" :class="{ selected: selectedIds.includes(note.id) }" @click="activeNote = note">
            <div class="card-cover" :class="note.cover"><span>{{ note.coverLabel }}</span><i>{{ note.type }}</i><button @click.stop="toggleSelect(note.id)">{{ selectedIds.includes(note.id) ? '✓' : '+' }}</button></div>
            <div class="note-card-copy"><h3>{{ note.title }}</h3><p>{{ note.tags.join(' · ') }}</p><div><span>赞 {{ compact(note.likes) }}</span><span>藏 {{ compact(note.collected) }}</span><span>评 {{ compact(note.comments) }}</span></div></div>
          </article>
        </div>
      </section>

      <section v-else-if="page === 'analysis'" class="page-content">
        <div class="analysis-head">
          <div><p class="eyebrow">ACCOUNT ANALYSIS</p><h1>账号八维分析</h1><p>{{ currentAccount.name }} · 基于 {{ notes.length }} 篇模拟笔记</p></div>
          <div><button class="secondary" @click="page = 'compare'">加入账号对比</button><button class="primary" @click="analysisReady = true">{{ analysisReady ? '重新分析' : '开始分析' }}</button></div>
        </div>
        <div class="analysis-summary">
          <div><span>笔记数</span><b>{{ notes.length }}</b><small>去重后</small></div>
          <div><span>公开互动</span><b>{{ compact(notes.reduce((sum, n) => sum + total(n), 0)) }}</b><small>赞 + 藏 + 评 + 分享</small></div>
          <div><span>单篇中位数</span><b>{{ medianEngagement }}</b><small>本批笔记</small></div>
          <div><span>图文 / 视频</span><b>78% / 22%</b><small>清单和教程更容易被收藏</small></div>
          <div><span>最近发布</span><b>2026-09-18</b><small>晚霞记录</small></div>
          <div><span>建议更新</span><b>每周 2 篇</b><small>真实节奏待账号确认</small></div>
        </div>
        <div class="dimension-grid">
          <article v-for="(dim, index) in dimensions" :key="dim.title" class="dimension-card">
            <header><span>{{ String(index + 1).padStart(2, '0') }}</span><b>{{ dim.title }}</b><i :class="dim.tone">{{ dim.badge }}</i></header>
            <strong>{{ dim.headline }}</strong><p>{{ dim.copy }}</p>
            <div class="dimension-metrics"><span v-for="metric in dim.metrics" :key="metric">{{ metric }}</span></div>
            <div v-if="expandedDimension === index" class="dimension-advice"><b>下一步建议</b><p>{{ dim.advice }}</p></div>
            <button type="button" @click="toggleAdvice(index)">{{ expandedDimension === index ? '收起建议' : '查看建议' }} <span>→</span></button>
          </article>
        </div>
        <div class="section-line"><h2>下周可以做的三个选题</h2><button @click="topicsReady = !topicsReady">{{ topicsReady ? '收起' : '展开' }} <span>⌄</span></button></div>
        <div v-if="topicsReady" class="topic-grid">
          <article v-for="(topic, index) in topics" :key="topic.title">
            <span>选题 {{ index + 1 }}</span><h3>{{ topic.title }}</h3><p>{{ topic.problem }}</p>
            <div><b>{{ topic.titleA }}</b><b>{{ topic.titleB }}</b></div>
            <small>{{ topic.format }}</small>
            <div class="topic-detail"><span>开头</span><p>{{ topic.opening }}</p><span>正文大纲</span><ol><li v-for="step in topic.outline" :key="step">{{ step }}</li></ol></div>
          </article>
        </div>
      </section>

      <section v-else-if="page === 'compare'" class="page-content">
        <div class="page-heading compact-heading"><div><p class="eyebrow">ACCOUNT BENCHMARK</p><h1>账号对标</h1><p>选择 2 至 5 个账号，在同一套八维里看差异和下一步动作。</p></div><button class="primary" :disabled="comparedAccounts.length < 2" @click="compareReady = true">{{ compareReady ? '重新对比' : '开始对比' }}</button></div>
        <div class="compare-select">
          <button v-for="account in accounts" :key="account.id" :class="{ active: compareAccounts.includes(account.id) }" @click="toggleCompare(account.id)"><span class="account-avatar small" :style="{ background: account.color }">{{ account.name.slice(0, 1) }}</span><div><b>{{ account.name }}</b><small>{{ account.notes }} 篇 · {{ account.desc }}</small></div><i>{{ compareAccounts.includes(account.id) ? '✓' : '+' }}</i></button>
        </div>
        <p class="compare-hint">已选 {{ comparedAccounts.length }} 个账号（最多 5 个，至少保留 2 个）。</p>
        <div v-if="compareReady" class="compare-content">
          <div class="compare-accounts"><article v-for="account in comparedAccounts" :key="account.id"><span class="account-avatar" :style="{ background: account.color }">{{ account.name.slice(0, 1) }}</span><h3>{{ account.name }}</h3><p>{{ account.desc }}</p><div><b>{{ account.notes }}</b><small>篇笔记</small><b>{{ account.engagement }}</b><small>公开互动</small></div></article></div>
          <div class="compare-table"><div class="compare-row header" :style="compareGridStyle"><span>维度</span><b v-for="account in comparedAccounts" :key="account.id">{{ account.name }}</b></div><div v-for="row in compareRows" :key="row.title" class="compare-row" :style="compareGridStyle"><span>{{ row.title }}</span><p v-for="(cell, index) in row.values" :key="index">{{ cell }}</p></div></div>
          <div class="next-actions"><article><span>值得借鉴</span><h3>把高收藏的路线内容做成连续栏目</h3><p>{{ comparedAccounts[0]?.name }} 的路线清单更容易被收藏，下一个系列可以固定为“城市 + 路线 + 时间成本”。</p></article><article><span>不要照搬</span><h3>不要同时复制标题、封面和生活表达</h3><p>保留自己的叙述方式，只测试栏目结构和信息密度。</p></article></div>
          <div class="week-plan"><div class="panel-title"><div><span>一周内容计划</span><h3>按对比结果排下周动作</h3></div><small>5 个可执行动作</small></div>
            <div class="week-plan-grid"><article v-for="(plan, index) in weekPlan" :key="plan.day"><span>{{ plan.day }}</span><b>{{ plan.title }}</b><p>{{ plan.copy }}</p><i>D{{ index + 1 }}</i></article></div>
          </div>
        </div>
      </section>

      <section v-else-if="page === 'feishu'" class="page-content">
        <div class="page-heading compact-heading"><div><p class="eyebrow">FEISHU DELIVERY</p><h1>飞书交付</h1><p>选择数据表，一键生成多维表格导入包和 Excel 备份。</p></div><span class="feishu-mark">飞书多维表格</span></div>
        <div class="feishu-layout">
          <section class="feishu-preview">
            <div class="preview-top"><div><span>▦</span><b>{{ currentAccount.name }}内容库</b></div><div><span>⌕</span><button>+ 新建记录</button></div></div>
            <div class="preview-body">
              <aside>
                <span>▣ 账号总览</span><span class="active">▤ 全部笔记</span><span>▤ 图文笔记</span><span>▤ 视频笔记</span><span>◇ 选题清单</span><span>◷ 采集记录</span>
              </aside>
              <div class="preview-table">
                <div class="mini-row header"><span>封面</span><span>标题</span><span>类型</span><span>点赞</span><span>收藏</span><span>评论</span><span>来源</span></div>
                <div v-for="note in notes.slice(0, 5)" :key="note.id" class="mini-row"><div class="mini-cover" :class="note.cover">{{ note.coverLabel }}</div><span>{{ note.title }}</span><span>{{ note.type }}</span><span>{{ note.likes.toLocaleString() }}</span><span>{{ note.collected.toLocaleString() }}</span><span>{{ note.comments }}</span><span>↗</span></div>
              </div>
            </div>
          </section>
          <aside class="delivery-settings">
            <div><span>交付范围</span><h2>{{ currentAccount.name }}</h2><p>100 篇笔记 · 96 篇正文</p></div>
            <div class="table-options"><label v-for="table in feishuTables" :key="table.name"><input v-model="selectedTables" type="checkbox" :value="table.name" /><span>{{ table.name }}</span><small>{{ table.count }}</small></label></div>
            <div class="destination"><span>交付方式</span><button class="active">下载导入包</button><button disabled>直接同步（后续）</button></div>
            <div v-if="generatedFeishu" class="delivery-success"><span>✓</span><div><b>飞书导入包已生成</b><small>包含 6 个工作表，可直接导入飞书多维表格。</small></div></div>
            <button v-else class="primary full" :disabled="generatingFeishu || !selectedTables.length" @click="generateFeishu">{{ generatingFeishu ? '正在生成…' : '生成飞书导入包' }}</button>
            <button v-if="generatedFeishu" class="secondary full" @click="downloadDemoCsv">下载演示文件</button>
            <p class="delivery-note">首次使用建议先下载 Excel 备份。导入飞书后再设置日期、数字和多行文本字段。</p>
          </aside>
        </div>
      </section>

      <section v-else-if="page === 'history'" class="page-content">
        <div class="page-heading compact-heading"><div><p class="eyebrow">COLLECTION HISTORY</p><h1>采集记录</h1><p>每次任务的数量、正文完成情况和备份文件都在这里。</p></div><button class="primary" @click="page = 'home'">新建采集</button></div>
        <section class="history-card">
          <div class="history-toolbar"><label class="search-box"><span>⌕</span><input v-model="historySearch" placeholder="搜索账号" /></label><select><option>全部状态</option><option>已完成</option><option>部分完成</option></select></div>
          <table class="history-table"><thead><tr><th>账号</th><th>开始 / 完成</th><th>结果</th><th>目标 / 实际</th><th>正文完成</th><th>未完成原因</th><th>备份</th><th /></tr></thead><tbody><tr v-for="task in filteredTasks" :key="task.id"><td><b>{{ task.account }}</b><small>{{ task.id }}</small></td><td>{{ task.time }}<small class="finish-time">{{ task.end }}</small></td><td><span class="task-status" :class="task.tone">{{ task.status }}</span></td><td>{{ task.target }} / {{ task.count }}</td><td>{{ task.body }}</td><td><span v-if="task.reason" class="reason-cell" :title="task.reason">{{ task.reason }}</span><span v-else class="muted">—</span></td><td><button class="text-button" @click="downloadBackup(task)">{{ task.backup }} ↓</button></td><td><button class="text-button" @click="openTask(task)">查看笔记 →</button></td></tr></tbody></table>
        </section>
      </section>

      <section v-else class="page-content">
        <div class="page-heading compact-heading"><div><p class="eyebrow">SETTINGS</p><h1>设置</h1><p>演示环境只展示配置入口，不会保存真实账号信息。</p></div></div>
        <div class="settings-grid">
          <article><span>登录状态</span><h3>小红书账号</h3><p>通过浏览器插件读取当前登录状态。</p><button class="secondary">检查连接</button></article>
          <article><span>内容分析</span><h3>AI 模型</h3><p>仅用于八维分析和选题建议。</p><button class="secondary">配置模型</button></article>
          <article><span>数据交付</span><h3>飞书</h3><p>当前支持导入文件，直接同步即将开放。</p><button class="secondary">选择导入模板</button></article>
          <article><span>本地数据</span><h3>存储位置</h3><p>运行数据和备份默认保存在本机。</p><button class="secondary">打开目录</button></article>
        </div>
      </section>
    </main>

    <aside v-if="activeNote" class="note-drawer">
      <header><span>笔记详情</span><button @click="activeNote = null">×</button></header>
      <div class="drawer-cover" :class="activeNote.cover"><span>{{ activeNote.coverLabel }}</span></div>
      <div class="drawer-body">
        <span class="type-pill" :class="activeNote.type === '视频' ? 'video' : 'image'">{{ activeNote.type }}</span>
        <h2>{{ activeNote.title }}</h2>
        <p class="drawer-meta">{{ activeNote.author }} · {{ activeNote.published }} · {{ activeNote.id }}</p>
        <div class="drawer-metrics"><div><b>{{ compact(activeNote.likes) }}</b><span>点赞</span></div><div><b>{{ compact(activeNote.collected) }}</b><span>收藏</span></div><div><b>{{ compact(activeNote.comments) }}</b><span>评论</span></div><div><b>{{ compact(activeNote.shares) }}</b><span>分享</span></div></div>
        <div v-if="activeNote.incomplete" class="drawer-alert"><span>未完成原因</span><p>{{ activeNote.failure }}</p><button class="secondary" @click="retryNote">重试这一篇</button><small v-if="retriedNoteId === activeNote.id" class="retry-ok">已重新排队，队列中还有 2 篇</small></div>
        <div class="drawer-section"><span>正文</span><p>{{ activeNote.body }}</p></div>
        <div class="drawer-section"><span>标签</span><div class="drawer-tags"><i v-for="tag in activeNote.tags" :key="tag">{{ tag }}</i></div></div>
        <div class="drawer-section"><span>来源链接</span><code class="source-link">{{ demoLink(activeNote.id) }}</code></div>
        <div class="drawer-actions"><button class="primary" @click="toggleMarkedFromDrawer">加入选题</button><button class="secondary" @click="addNoteAccountToCompare">加入账号对比</button></div>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'

type Page = 'home' | 'library' | 'analysis' | 'compare' | 'feishu' | 'history' | 'settings'
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

const navItems = [
  { key: 'home' as Page, label: '首页', icon: '⌂' },
  { key: 'library' as Page, label: '笔记库', icon: '▤' },
  { key: 'analysis' as Page, label: '账号分析', icon: '◎' },
  { key: 'compare' as Page, label: '账号对比', icon: '⇄' },
  { key: 'feishu' as Page, label: '飞书交付', icon: '↗', count: 12 },
  { key: 'history' as Page, label: '采集记录', icon: '◷' },
]
const requestedPage = new URLSearchParams(window.location.search).get('page') as Page | null
const allowedPages: Page[] = ['home', 'library', 'analysis', 'compare', 'feishu', 'history', 'settings']
const page = ref<Page>(requestedPage && allowedPages.includes(requestedPage) ? requestedPage : 'home')
const currentLabel = computed(() => navItems.find(item => item.key === page.value)?.label || '设置')
watch(page, (value) => {
  const url = new URL(window.location.href)
  url.searchParams.set('page', value)
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
  { id: 'a1', name: '野路手册', desc: '城市周边路线与周末去处', notes: 100, updated: '今天 14:20', color: '#1b75d0', engagement: '6.3万' },
  { id: 'a2', name: '一页食光', desc: '家常菜、咖啡和小店清单', notes: 86, updated: '昨天 19:08', color: '#e36b53', engagement: '4.8万' },
  { id: 'a3', name: '小城慢拍', desc: '手机摄影和城市观察', notes: 74, updated: '10月28日', color: '#22896c', engagement: '3.2万' },
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

function noteDate(note: DemoNote) { return new Date(`${note.published}T00:00:00`) }
function withinRange(note: DemoNote) {
  if (dateRange.value === 'all') return true
  const days = Number(dateRange.value)
  const age = (Date.now() - noteDate(note).getTime()) / 86400000
  return age <= days
}

const visibleNotes = computed(() => {
  const query = search.value.trim().toLowerCase()
  const rows = notes.value.filter(note => {
    const tabOk = libraryTab.value === 'all' || (libraryTab.value === 'image' && note.type === '图文') || (libraryTab.value === 'video' && note.type === '视频') || (libraryTab.value === 'high' && total(note) >= medianEngagement.value) || (libraryTab.value === 'marked' && markedIds.value.includes(note.id)) || (libraryTab.value === 'incomplete' && note.incomplete)
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
const medianEngagement = computed(() => {
  const values = notes.value.map(total).sort((a, b) => a - b)
  const middle = Math.floor(values.length / 2)
  return values.length % 2 ? values[middle] : Math.round((values[middle - 1] + values[middle]) / 2)
})

const dimensions = [
  { title: '账号定位', badge: '清晰', tone: 'blue', headline: '城市周边路线与周末去处', copy: '围绕路线、时间成本和实际体验做内容，适合想低成本出门的人。', metrics: ['路线类 42%', '生活观察 28%'], advice: '主页简介和置顶笔记统一写“北京出发、公交可达、成本多少”，让新用户三秒内判断这是不是自己要找的账号。' },
  { title: '内容方向', badge: '3 个主线', tone: 'green', headline: '路线清单、城市散步、旅居选择', copy: '路线清单更容易被收藏，城市散步适合补充日常感。', metrics: ['图文 78%', '视频 22%'], advice: '三条主线按 5:3:2 排内容量：路线清单保底收藏，城市散步拉近距离，旅居选择做高客单探索。' },
  { title: '选题结构', badge: '可连续', tone: 'blue', headline: '“城市 + 路线 + 成本”最好复用', copy: '把目的地、时间和花费写清楚的内容，收藏明显更高。', metrics: ['清单类 34%', '攻略类 27%'], advice: '固定三个信息位：总花费、总时长、返程末班车。每篇只替换目的地，形成可连续更新的栏目。' },
  { title: '标题与封面', badge: '数字更常见', tone: 'orange', headline: '数字、价格和具体地点出现频繁', copy: '标题直接给出路线成本或件数，比泛泛的旅行感受更容易判断价值。', metrics: ['含数字 31%', '含地点 48%'], advice: '标题保留具体数字，封面统一用大字地名 + 一句成本，避免每篇换风格导致识别度下降。' },
  { title: '互动表现', badge: '收藏突出', tone: 'green', headline: '路线清单的收藏和分享更高', copy: '用户更愿意保存能直接照着走的路线，而不是只看风景。', metrics: ['收藏占比 42%', '分享占比 19%'], advice: '在正文末尾加一句“出发前先存这一条”，把收藏意图写出来；分享高的内容可补二条同目的地。' },
  { title: '发布节奏', badge: '偏集中', tone: 'orange', headline: '六月内容量最高', copy: '周末出行内容有自己的季节性，建议按目的地建立系列。', metrics: ['月均 9 篇', '高峰 15 篇'], advice: '按季节提前一个月排期，周四晚发布周末路线，节假日前两周发长线与短线各一篇。' },
  { title: '标签与搜索', badge: '地域集中', tone: 'blue', headline: '北京、周边路线和双月湾出现最多', copy: '地域标签能帮助内容归类，但不能直接说明搜索流量。', metrics: ['北京 34 篇', '周边 21 篇'], advice: '每篇固定 3 个地域标签 + 1 个成本标签，方便后续在飞书按标签分组复盘，不宣称搜索排名。' },
  { title: '下一步建议', badge: '3 个选题', tone: 'green', headline: '先做低成本路线系列', copy: '固定成本、路线和返程三个信息，连续做两周再看收藏变化。', metrics: ['每周 2 篇', '连续 2 周'], advice: '两周做 4 篇同结构路线，第三周对比收藏中位数是否提升，再决定是否扩到城市散步。' },
]
const expandedDimension = ref<number | null>(null)
function toggleAdvice(index: number) {
  expandedDimension.value = expandedDimension.value === index ? null : index
}
const analysisReady = ref(true)
const topicsReady = ref(true)
const topics = [
  { title: '北京出发，三条不超过50元的周末公交路线', problem: '想出门但不想自驾、不想临时查换乘。', titleA: '50元以内，公交能到的三个北京周末目的地', titleB: '不用自驾：我整理了三条便宜又好走的路线', format: '路线清单 + 每段车费和时间', opening: '先算一笔账：三个人自驾一天油费过路费大约多少，再对比公交的三段票价，差距一眼能看出来。', outline: ['总成本对比：自驾 vs 公交三段票价', '路线一：城里出发，换乘一次，末班车时间', '路线二：目的地补给点和厕所位置', '路线三：适合拍照的时段和机位', '三条路线的适用人群和避坑提醒'] },
  { title: '双月湾住一周：先按四件生活小事选房', problem: '海景房看起来都差不多，住进去才发现采买和出行不方便。', titleA: '海景房不是越近海越好：先看这四件事', titleB: '双月湾住一周，我会这样筛掉一半房源', format: '四栏比较 + 一天生活路线', opening: '住进去第一天就发现，离海十米不如离菜市场五百米，这篇把一周里真正影响体验的四件事列出来。', outline: ['睡眠：楼层、朝向和夜间噪音', '采购：菜市场步行距离与营业时间', '出行：打车难不难、停车多少钱', '海景：楼层高度与遮挡物', '一天生活路线示范 + 订房前必问的三个问题'] },
  { title: '城市散步系列：一条路看老店、树荫和傍晚', problem: '想拍城市但不知道从哪里开始。', titleA: '一条路走完北京的树荫、老店和傍晚', titleB: '周末不赶景点，我更喜欢这样走一座城', format: '路线地图 + 三个停留点', opening: '这条路我走了三次，每次都能看到不同的傍晚。不用门票，也不用赶时间，两个半小时刚好。', outline: ['起点：地铁哪一站、几点出发光线最好', '停留点一：开了二十年的老店和它的招牌', '停留点二：树荫最密的一段路', '停留点三：傍晚看天际线的机位', '路上能吃什么 + 返程建议'] },
]

const compareAccounts = ref(['a1', 'a2'])
const compareReady = ref(true)
const comparedAccounts = computed(() => accounts.filter(account => compareAccounts.value.includes(account.id)))
const compareGridStyle = computed(() => ({ gridTemplateColumns: `150px repeat(${Math.max(1, comparedAccounts.value.length)}, minmax(0, 1fr))` }))
const compareDimensions = ['账号定位', '内容方向', '选题结构', '标题与封面', '互动表现', '发布节奏', '标签与搜索', '下一步动作']
const compareMatrix: Record<string, string[]> = {
  a1: ['城市周边路线与低成本出行', '路线、旅居、城市散步', '成本 + 路线 + 时间', '地点和价格明确', '收藏和分享突出', '周末集中', '北京及周边为主', '做连续路线栏目'],
  a2: ['城市吃喝与周末小店', '咖啡、小馆、城市散步', '地点 + 菜单 + 消费', '清单感更强', '收藏偏高，评论稳定', '工作日和周末都发', '城市与店铺为主', '补充一人食路线'],
  a3: ['手机摄影与城市观察', '摄影技巧、城市记录', '机位 + 参数 + 对比', '画面感和对比强', '收藏低、分享高', '随天气和素材更新', '摄影与城市关键词', '固定机位做前后对比'],
}
const compareRows = computed(() => compareDimensions.map((title, index) => ({
  title,
  values: comparedAccounts.value.map(account => compareMatrix[account.id]?.[index] ?? '未获取'),
})))
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

const tasks = [
  { id: 'task-08', account: '野路手册', status: '已完成', tone: 'ok', time: '今天 14:20', end: '今天 14:32', count: 100, target: 100, body: '96 篇', backup: 'xlsx', reason: '' },
  { id: 'task-07', account: '一页食光', status: '已完成', tone: 'ok', time: '昨天 19:08', end: '昨天 19:19', count: 86, target: 100, body: '83 篇', backup: 'xlsx', reason: '' },
  { id: 'task-06', account: '小城慢拍', status: '部分完成', tone: 'warn', time: '10月28日 10:42', end: '10月28日 10:59', count: 74, target: 100, body: '70 篇', backup: 'xlsx', reason: '访问受限，4 篇正文未获取' },
  { id: 'task-05', account: '周末地图', status: '未完成', tone: 'danger', time: '10月27日 16:31', end: '10月27日 16:38', count: 31, target: 100, body: '28 篇', backup: 'csv', reason: '登录状态失效，任务提前停止' },
]
const historySearch = ref('')
const filteredTasks = computed(() => tasks.filter(task => task.account.includes(historySearch.value)))

function total(note: DemoNote) { return note.likes + note.collected + note.comments + note.shares }
function compact(value: number) {
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`
  return value.toLocaleString('zh-CN')
}
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
function clearSelection() { selectedIds.value = [] }
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
function toggleCompare(id: string) {
  if (compareAccounts.value.includes(id)) {
    if (compareAccounts.value.length > 2) compareAccounts.value = compareAccounts.value.filter(value => value !== id)
  } else if (compareAccounts.value.length < 5) compareAccounts.value.push(id)
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
function downloadDemoCsv() {
  const header = ['标题', '类型', '点赞', '收藏', '评论', '分享', '标签', '来源链接']
  const rows = notes.value.map(note => [note.title, note.type, note.likes, note.collected, note.comments, note.shares, note.tags.join(' / '), demoLink(note.id)])
  downloadCsv('飞书导入示例-野路手册.csv', [header, ...rows])
}
onUnmounted(() => { clearInterval(collectionTimer); clearTimeout(feishuTimer) })
</script>

<style scoped>
.demo-shell{--blue:#1677d2;--blue-dark:#0d5aa7;--navy:#152437;--ink:#1d2938;--muted:#6f7d8e;--line:#dfe6ee;--soft:#f4f7fb;min-height:100vh;display:grid;grid-template-columns:232px minmax(0,1fr);background:#f6f8fb;color:var(--ink);font-family:Inter,"PingFang SC","Microsoft YaHei",sans-serif;line-height:1.5}.demo-shell *{box-sizing:border-box}.demo-shell button,.demo-shell input,.demo-shell select{font:inherit}.demo-sidebar{position:sticky;top:0;height:100vh;background:#fff;border-right:1px solid var(--line);padding:22px 14px 16px;display:flex;flex-direction:column}.demo-brand{display:flex;align-items:center;gap:10px;padding:0 8px;margin-bottom:28px}.demo-logo{width:38px;height:38px;border-radius:11px;background:var(--blue);color:#fff;display:grid;place-items:center;font-size:20px;font-weight:800;box-shadow:0 7px 18px rgba(22,119,210,.22)}.demo-brand div:last-child{display:flex;flex-direction:column}.demo-brand strong{font-size:16px}.demo-brand span{font-size:10px;color:#8a97a7;margin-top:2px}.demo-nav{display:grid;gap:5px}.demo-nav button,.sidebar-bottom>button{border:0;background:transparent;display:flex;align-items:center;gap:10px;padding:11px 12px;border-radius:9px;color:#637183;text-align:left;cursor:pointer;font-size:13px;font-weight:600}.demo-nav button>span,.sidebar-bottom>button>span{width:20px;text-align:center;font-size:16px}.demo-nav button:hover,.sidebar-bottom>button:hover{background:#f1f5fa;color:var(--ink)}.demo-nav button.active{background:#eaf3fd;color:var(--blue-dark);font-weight:800}.demo-nav button i{margin-left:auto;background:#e4edf7;color:#607488;border-radius:20px;padding:1px 7px;font-size:10px;font-style:normal}.sidebar-bottom{margin-top:auto;border-top:1px solid #edf1f5;padding-top:12px}.user-mini{margin-top:12px;background:#f8fafc;border:1px solid #e5ebf2;border-radius:9px;padding:10px;display:flex;flex-direction:column}.user-mini b{font-size:12px}.user-mini span{font-size:10px;color:#8d98a6;margin-top:2px}.demo-main{min-width:0}.demo-topbar{height:60px;background:rgba(255,255,255,.96);border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 28px;position:sticky;top:0;z-index:30}.breadcrumb{display:flex;align-items:center;gap:9px;color:#8793a2;font-size:12px}.breadcrumb b{font-weight:400}.breadcrumb strong{color:#38475a}.top-actions{display:flex;align-items:center;gap:13px}.demo-badge{font-size:10px;color:#15704d;background:#e9f8f1;border:1px solid #cdeee0;border-radius:20px;padding:3px 9px}.real-link{color:var(--blue-dark);font-size:12px;font-weight:700;text-decoration:none}.page-content{max-width:1440px;margin:auto;padding:30px 34px 52px}.page-heading{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin-bottom:24px}.eyebrow{font-size:10px!important;font-weight:800;letter-spacing:.13em;color:var(--blue)!important;margin:0 0 6px!important}.page-heading h1,.library-heading h1,.analysis-head h1{font-size:31px;line-height:1.25;margin:0;color:#142335}.page-heading>div>p:last-child,.library-heading>div>p:last-child,.analysis-head>div>p:last-child{font-size:13px;color:var(--muted);margin:7px 0 0}.heading-chip{background:#fff;border:1px solid var(--line);border-radius:12px;min-width:130px;padding:12px 17px;display:flex;align-items:baseline;gap:8px}.heading-chip b{font-size:28px;color:var(--blue)}.heading-chip span{font-size:11px;color:#7f8c9c}.capture-card{background:#fff;border:1px solid #dfe7f0;border-radius:15px;padding:25px;box-shadow:0 10px 30px rgba(42,61,83,.06);margin-bottom:22px}.capture-copy>span,.analysis-summary span,.delivery-settings>div>span,.settings-grid article>span{font-size:10px;color:var(--blue);font-weight:800;letter-spacing:.08em}.capture-copy h2{font-size:22px;margin:5px 0}.capture-copy p{font-size:12px;color:var(--muted);margin:0}.capture-form{display:grid;grid-template-columns:minmax(300px,1fr) auto auto;gap:10px;margin-top:20px}.url-input,.search-box{display:flex;align-items:center;gap:8px;border:1px solid #d7e0ea;background:#fbfcfe;border-radius:9px;padding:0 12px}.url-input span,.search-box span{color:#8a98a8}.url-input input,.search-box input{border:0;background:transparent;box-shadow:none;padding:11px 0;outline:none;width:100%;font-size:13px}.demo-shell button{border-radius:8px;border:1px solid #d5e0eb;background:#fff;padding:9px 15px;color:#42536a;font-weight:700;font-size:12px;cursor:pointer}.demo-shell button.primary{background:var(--blue);border-color:var(--blue);color:#fff;box-shadow:0 6px 14px rgba(22,119,210,.18)}.demo-shell button.primary:hover{background:var(--blue-dark)}.demo-shell button.secondary:hover,.demo-shell button:hover{border-color:#acc9e7}.demo-shell button:disabled{cursor:not-allowed;opacity:.55}.capture-tip{font-size:10px;color:#94a0ae;margin:10px 0 0}.capture-progress{background:#fff;border:1px solid #cfe2f5;border-radius:14px;padding:20px 22px;margin-bottom:22px}.progress-head{display:flex;justify-content:space-between;font-size:12px;align-items:center}.progress-head>div{display:flex;align-items:center;gap:7px;font-weight:700}.status-dot{width:8px;height:8px;border-radius:50%;background:var(--blue);box-shadow:0 0 0 4px #e5f2ff}.status-dot.done{background:#18a06a;box-shadow:0 0 0 4px #e4f8ef}.progress-head>b{color:var(--blue)}.progress-bar{height:7px;background:#e8eef5;border-radius:10px;overflow:hidden;margin:12px 0 18px}.progress-bar i{display:block;height:100%;background:linear-gradient(90deg,#368ce1,#12a6a0);transition:width .25s}.progress-steps{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.progress-steps>div{display:flex;align-items:center;gap:8px;color:#9aa5b2}.progress-steps>div>span{width:22px;height:22px;border-radius:50%;border:1px solid #d6e0eb;display:grid;place-items:center;font-size:10px;background:#f8fafc}.progress-steps>div.active{color:#37506a}.progress-steps>div.active>span{background:#e7f4ff;border-color:#a9d1f6;color:var(--blue)}.progress-steps div div{display:flex;flex-direction:column}.progress-steps b{font-size:11px}.progress-steps small{font-size:9px;color:#91a0af}.done-actions{display:flex;align-items:center;gap:9px;border-top:1px solid #e9eff5;margin-top:16px;padding-top:14px}.done-actions>span{font-size:11px;color:#607184;margin-right:auto}.done-actions .text-button,.text-button{border:0;background:transparent!important;color:var(--blue-dark)!important;padding:6px!important;box-shadow:none!important}.section-line{display:flex;align-items:center;justify-content:space-between;margin:26px 0 12px}.section-line h2{font-size:17px;margin:0}.section-line button{border:0;background:transparent!important;color:#708094!important;font-size:11px}.section-line button span{margin-left:4px}.account-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.account-card{background:#fff;border:1px solid var(--line);border-radius:13px;padding:16px;display:flex;gap:11px;align-items:center;cursor:pointer;transition:.18s}.account-card:hover{transform:translateY(-2px);border-color:#bfd6eb;box-shadow:0 8px 22px rgba(41,67,94,.07)}.account-avatar{width:42px;height:42px;border-radius:11px;display:grid;place-items:center;color:#fff;flex:0 0 42px;font-size:17px;font-weight:800}.account-avatar.small{width:32px;height:32px;flex-basis:32px;border-radius:8px;font-size:13px}.account-copy{flex:1;min-width:0}.account-copy h3{font-size:14px;margin:0}.account-copy p{font-size:10px;color:#8793a0;margin:2px 0 7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.account-copy div{display:flex;gap:10px;font-size:9px;color:#8392a2}.account-card>button{border:0;background:#f4f8fc!important;color:#5f7b98!important;width:28px;height:28px;padding:0!important}.bottom-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:12px;margin-top:25px}.mini-panel,.workflow-panel{background:#fff;border:1px solid var(--line);border-radius:13px;padding:18px}.panel-title{display:flex;justify-content:space-between;align-items:start;margin-bottom:7px}.panel-title span,.workflow-panel>span{font-size:9px;color:var(--blue);font-weight:800;letter-spacing:.08em}.panel-title h3,.workflow-panel h3{font-size:17px;margin:3px 0 0}.panel-title button{border:0;background:transparent!important;padding:3px!important;color:#7a8a9d!important;font-size:10px}.task-row{display:grid;grid-template-columns:62px 1fr auto;gap:10px;align-items:center;padding:10px 0;border-top:1px solid #edf1f5}.task-status{font-size:9px;padding:3px 7px;border-radius:4px;width:fit-content}.task-status.ok{color:#157453;background:#e8f8f0}.task-status.warn{color:#94651a;background:#fff3d9}.task-status.danger{color:#b13945;background:#ffeaed}.task-row div{display:flex;flex-direction:column}.task-row b{font-size:11px}.task-row small,.task-count{font-size:9px;color:#8995a3}.workflow-panel{background:linear-gradient(145deg,#10253b,#173f65);color:#fff;display:flex;flex-direction:column}.workflow-panel>span{color:#80c7ff}.workflow-panel h3{margin:4px 0 18px}.workflow-steps{display:flex;align-items:center;gap:8px}.workflow-steps div{flex:1}.workflow-steps b{font-size:18px;color:#85ccff}.workflow-steps p{font-size:11px;font-weight:700;margin:3px 0}.workflow-steps small{font-size:8px;color:#9eb8d0}.workflow-steps i{font-style:normal;color:#648aa9}.workflow-panel>button{margin-top:auto;background:#fff!important;color:#163f64!important;border-color:#fff!important;align-self:flex-start}.library-heading{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:18px}.account-stats{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin-bottom:18px}.account-stats article{background:#fff;border:1px solid var(--line);border-radius:10px;padding:13px 14px}.account-stats span{display:block;font-size:10px;color:#7d8b9b}.account-stats b{display:block;font-size:21px;margin-top:3px}.account-stats small{font-size:9px;color:#97a2af}.library-tabs{display:flex;gap:4px;border-bottom:1px solid #dbe3ec;margin-bottom:12px}.library-tabs button{border:0!important;background:transparent!important;padding:9px 12px!important;border-bottom:2px solid transparent!important;border-radius:0!important;color:#6f7f90!important}.library-tabs button.active{color:var(--blue-dark)!important;border-bottom-color:var(--blue)!important;font-weight:800}.library-tabs button span{margin-left:5px;font-size:9px;color:#93a0ad}.library-toolbar{display:flex;gap:8px;align-items:center;background:#fff;border:1px solid var(--line);border-radius:10px;padding:9px;margin-bottom:10px}.library-toolbar .search-box{flex:1;min-width:200px}.library-toolbar select{border:1px solid #dbe4ed;border-radius:7px;padding:9px 11px;font-size:11px;background:#fff;color:#56677a}.filter-button{background:#f8fafc!important}.view-switch{display:flex;border:1px solid #dae4ee;border-radius:7px;overflow:hidden}.view-switch button{border:0!important;border-radius:0!important;padding:8px 10px!important;background:#fff!important;color:#758598!important}.view-switch button.active{background:#eaf4fd!important;color:var(--blue-dark)!important}.selection-bar{display:flex;align-items:center;gap:9px;background:#eaf4fd;border:1px solid #cfe4f9;border-radius:8px;padding:8px 12px;font-size:11px;margin-bottom:8px}.selection-bar button{margin-left:4px;padding:5px 8px;font-size:10px;background:#fff!important}.note-table-wrap{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:auto}.note-table{width:100%;min-width:920px;border-collapse:collapse}.note-table th{background:#f7f9fc;color:#718093;font-size:10px;font-weight:700;padding:10px 8px;text-align:left;border-bottom:1px solid #e4eaf1}.note-table td{padding:9px 8px;border-bottom:1px solid #edf1f5;font-size:11px}.note-table tr.selected{background:#f3f9ff}.note-table .check{width:34px;text-align:center}.note-table input{width:14px;height:14px}.note-cell{display:flex;align-items:center;gap:10px;border:0!important;background:transparent!important;padding:0!important;text-align:left;min-width:280px}.thumb{width:46px;height:57px;border-radius:6px;display:grid;place-items:center;color:#fff;font-size:8px;font-weight:900;letter-spacing:.08em;flex:0 0 46px;position:relative;overflow:hidden}.thumb::after,.card-cover::after,.drawer-cover::after,.mini-cover::after{content:"";position:absolute;inset:0;background:linear-gradient(155deg,transparent 45%,rgba(0,0,0,.18))}.note-cell b{display:block;font-size:11px;line-height:1.5;color:#26384c}.note-cell small{display:block;color:#8b98a7;font-size:8px;margin-top:3px}.type-pill{display:inline-flex;padding:3px 7px;border-radius:4px;font-size:9px;font-weight:700}.type-pill.image{color:#176d52;background:#e8f7f1}.type-pill.video{color:#6c4db6;background:#f0ebff}.tag-list{display:flex;gap:4px;flex-wrap:wrap}.tag-list span{background:#f2f6fa;border-radius:4px;padding:2px 5px;font-size:8px;color:#627589;white-space:nowrap}.status-ok{color:#16815c;font-size:9px}.status-ok::before{content:"●";margin-right:3px}.more-button{border:0!important;background:transparent!important;color:#8b99a8!important;padding:2px!important}.empty-state{text-align:center;padding:50px;color:#8b98a6;font-size:12px}.note-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.note-card{background:#fff;border:1px solid var(--line);border-radius:11px;overflow:hidden;cursor:pointer;transition:.18s}.note-card:hover,.note-card.selected{border-color:#a8c9e8;box-shadow:0 8px 22px rgba(40,72,105,.08)}.card-cover{height:170px;padding:15px;display:flex;align-items:flex-end;color:#fff;position:relative}.card-cover>span{font-size:19px;font-weight:900;z-index:1;letter-spacing:.04em}.card-cover>i{position:absolute;right:10px;top:10px;background:rgba(0,0,0,.28);padding:3px 7px;border-radius:4px;font-size:9px;font-style:normal;z-index:1}.card-cover>button{position:absolute;left:10px;top:10px;border:0!important;background:rgba(255,255,255,.88)!important;color:#32516e!important;width:24px;height:24px;padding:0!important;z-index:2}.note-card-copy{padding:12px}.note-card-copy h3{height:42px;overflow:hidden;font-size:12px;line-height:1.55;margin:0}.note-card-copy p{font-size:9px;color:#8794a2;margin:6px 0 9px}.note-card-copy div{display:flex;gap:10px;font-size:9px;color:#66798d}.cover-a{background:linear-gradient(145deg,#1e6da3,#7daf8b)}.cover-b{background:linear-gradient(145deg,#263b50,#b16b4d)}.cover-c{background:linear-gradient(145deg,#6d7781,#c5a884)}.cover-d{background:linear-gradient(145deg,#1a658a,#83c4d4)}.cover-e{background:linear-gradient(145deg,#453d7d,#d56c79)}.cover-f{background:linear-gradient(145deg,#355d41,#bca556)}.cover-g{background:linear-gradient(145deg,#4e3f34,#d59665)}.cover-h{background:linear-gradient(145deg,#573426,#c59165)}.cover-i{background:linear-gradient(145deg,#ad4a57,#e5a567)}.cover-j{background:linear-gradient(145deg,#485c3b,#a9a66f)}.cover-k{background:linear-gradient(145deg,#6f7fa5,#dba4a1)}.cover-l{background:linear-gradient(145deg,#49565d,#a8a296)}.analysis-head{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:18px}.analysis-head>div:last-child{display:flex;gap:8px}.analysis-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin-bottom:16px}.analysis-summary>div{background:#fff;border:1px solid var(--line);border-radius:10px;padding:15px}.analysis-summary b{display:block;font-size:23px;margin:5px 0}.analysis-summary small{font-size:9px;color:#8c98a6}.dimension-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.dimension-card{background:#fff;border:1px solid var(--line);border-radius:11px;padding:15px;min-height:220px;display:flex;flex-direction:column}.dimension-card header{display:flex;align-items:center;gap:8px}.dimension-card header>span{font-size:10px;color:#9aa5b2}.dimension-card header>b{font-size:12px}.dimension-card header>i{margin-left:auto;font-size:8px;padding:3px 6px;border-radius:4px;font-style:normal}.dimension-card i.blue{background:#e8f3fe;color:#1766ae}.dimension-card i.green{background:#e8f7f1;color:#197558}.dimension-card i.orange{background:#fff2e3;color:#9b601a}.dimension-card>strong{display:block;font-size:15px;line-height:1.5;margin:18px 0 7px}.dimension-card>p{font-size:10px;line-height:1.7;color:#6d7c8d;margin:0}.dimension-metrics{display:flex;flex-wrap:wrap;gap:5px;margin:10px 0}.dimension-metrics span{background:#f5f8fb;padding:3px 6px;border-radius:4px;font-size:8px;color:#65788b}.dimension-card>button{margin-top:auto;border:0!important;background:transparent!important;text-align:left;padding:8px 0 0!important;color:var(--blue-dark)!important;font-size:10px}.topic-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.topic-grid article{background:#fff;border:1px solid var(--line);border-radius:11px;padding:16px}.topic-grid article>span{font-size:9px;color:var(--blue);font-weight:800}.topic-grid h3{font-size:14px;line-height:1.55;margin:6px 0}.topic-grid p{font-size:10px;color:#728194;margin:0 0 10px}.topic-grid article>div{display:grid;gap:5px}.topic-grid article>div b{font-size:10px;background:#f4f8fc;padding:7px;border-radius:5px}.topic-grid small{display:block;font-size:9px;color:#8a97a5;margin-top:9px}.compare-select{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-bottom:15px}.compare-select>button{display:flex;align-items:center;gap:9px;text-align:left;padding:10px!important}.compare-select>button.active{border-color:#7eb7e8;background:#f0f8ff}.compare-select>button>div{display:flex;flex-direction:column;flex:1}.compare-select b{font-size:11px}.compare-select small{font-size:9px;color:#8997a5}.compare-select i{font-style:normal;color:var(--blue)}.compare-accounts{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px}.compare-accounts article{background:#fff;border:1px solid var(--line);border-radius:11px;padding:16px;display:grid;grid-template-columns:44px 1fr;column-gap:10px}.compare-accounts h3{margin:0;font-size:14px}.compare-accounts p{grid-column:2;font-size:10px;color:#7f8d9b;margin:2px 0 9px}.compare-accounts article>div{grid-column:1/-1;display:flex;gap:7px;align-items:baseline;border-top:1px solid #edf1f5;padding-top:9px}.compare-accounts article>div b{font-size:17px}.compare-accounts article>div small{font-size:9px;color:#8a97a4;margin-right:10px}.compare-table{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden}.compare-row{display:grid;grid-template-columns:150px repeat(3,1fr);border-top:1px solid #edf1f5}.compare-row.header{background:#f7f9fc;border-top:0}.compare-row>*{padding:11px 13px;font-size:10px;margin:0}.compare-row>span{font-weight:700;color:#54677b}.compare-row.header b{font-size:10px;color:#617489}.next-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.next-actions article{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px}.next-actions span{font-size:9px;color:var(--blue);font-weight:800}.next-actions h3{font-size:14px;margin:5px 0}.next-actions p{font-size:10px;color:#728193;margin:0}.feishu-mark{background:#e9f3ff;color:#176bbb;font-size:11px;padding:6px 11px;border-radius:6px;font-weight:700}.feishu-layout{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(300px,.7fr);gap:13px}.feishu-preview,.delivery-settings{background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden}.preview-top{display:flex;justify-content:space-between;align-items:center;padding:12px 14px;border-bottom:1px solid var(--line);font-size:10px}.preview-top>div{display:flex;align-items:center;gap:9px}.preview-top button{padding:5px 8px!important;font-size:9px!important;background:var(--blue)!important;color:#fff!important;border-color:var(--blue)!important}.preview-body{display:grid;grid-template-columns:145px 1fr;min-height:420px}.preview-body>aside{border-right:1px solid var(--line);padding:10px;display:grid;align-content:start;gap:3px;background:#fbfcfe}.preview-body>aside span{padding:8px;border-radius:5px;color:#758697;font-size:9px}.preview-body>aside span.active{background:#eaf3fd;color:var(--blue-dark);font-weight:800}.preview-table{overflow:hidden;padding:9px}.mini-row{display:grid;grid-template-columns:48px minmax(150px,1.8fr) 50px 65px 65px 50px 30px;align-items:center;gap:6px;border-bottom:1px solid #edf1f5;padding:7px 3px;font-size:8px;color:#5f7083}.mini-row.header{background:#f7f9fc;color:#808d9c;font-weight:700}.mini-cover{width:38px;height:45px;border-radius:4px;display:grid;place-items:center;color:#fff;font-size:6px;font-weight:900;position:relative;overflow:hidden}.delivery-settings{padding:18px}.delivery-settings h2{font-size:19px;margin:4px 0 2px}.delivery-settings p{font-size:10px;color:#8290a0;margin:0}.table-options{border-top:1px solid #edf1f5;margin-top:14px;padding-top:10px;display:grid;gap:3px}.table-options label{display:flex;align-items:center;gap:8px;padding:8px;border-radius:6px;font-size:11px;margin:0;cursor:pointer}.table-options label:hover{background:#f6f9fc}.table-options input{width:14px;height:14px}.table-options small{margin-left:auto;font-size:9px;color:#8c99a7}.destination{border-top:1px solid #edf1f5;margin-top:9px;padding-top:12px}.destination>span{display:block;margin-bottom:7px}.destination button{padding:7px 9px!important;font-size:9px!important}.destination button.active{background:#eaf4fe!important;color:var(--blue-dark)!important;border-color:#bdd9f1!important}.delivery-success{display:flex;gap:8px;background:#ebf8f2;border:1px solid #ccebdd;border-radius:8px;padding:10px;margin:12px 0}.delivery-success>span{width:22px;height:22px;border-radius:50%;background:#149966;color:#fff;display:grid;place-items:center;flex:0 0 22px;font-size:11px}.delivery-success div{display:flex;flex-direction:column}.delivery-success b{font-size:11px;color:#18664b}.delivery-success small{font-size:9px;color:#568474;line-height:1.5}.full{width:100%;margin-top:10px!important}.delivery-note{font-size:9px!important;line-height:1.6;color:#8b98a6!important;margin-top:10px!important}.history-card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px}.history-toolbar{display:flex;gap:8px;margin-bottom:10px}.history-toolbar .search-box{flex:1}.history-toolbar select{border:1px solid #dbe4ed;border-radius:7px;padding:8px 10px;font-size:10px}.history-table{width:100%;border-collapse:collapse}.history-table th{text-align:left;background:#f7f9fc;color:#718194;font-size:9px;padding:9px}.history-table td{padding:11px 9px;border-top:1px solid #edf1f5;font-size:10px}.history-table td>b,.history-table td>small{display:block}.history-table td>small{font-size:8px;color:#929dab;margin-top:2px}.settings-grid{display:grid;grid-template-columns:1fr 1fr;gap:11px}.settings-grid article{background:#fff;border:1px solid var(--line);border-radius:11px;padding:18px}.settings-grid h3{font-size:15px;margin:4px 0}.settings-grid p{font-size:10px;color:#7e8d9d;margin:0 0 13px}.settings-grid button{padding:6px 9px!important;font-size:9px!important}.note-drawer{position:fixed;top:0;right:0;width:min(420px,92vw);height:100vh;background:#fff;border-left:1px solid #dce5ee;box-shadow:-12px 0 40px rgba(25,48,70,.14);z-index:100;overflow:auto}.note-drawer>header{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid var(--line)}.note-drawer>header span{font-size:12px;font-weight:800}.note-drawer>header button{border:0!important;background:transparent!important;font-size:20px!important;color:#7c8b9b!important}.drawer-cover{height:170px;display:flex;align-items:flex-end;padding:18px;color:#fff;font-size:24px;font-weight:900;position:relative}.drawer-body{padding:18px}.drawer-body h2{font-size:19px;line-height:1.45;margin:9px 0 4px}.drawer-meta{font-size:9px;color:#8a97a6;margin:0}.drawer-metrics{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);border-radius:8px;margin:15px 0;padding:10px}.drawer-metrics div{text-align:center;border-right:1px solid #edf1f5}.drawer-metrics div:last-child{border-right:0}.drawer-metrics b{display:block;font-size:15px}.drawer-metrics span{font-size:8px;color:#8592a2}.drawer-section{border-top:1px solid #edf1f5;padding-top:13px;margin-top:13px}.drawer-section>span{font-size:9px;color:var(--blue);font-weight:800}.drawer-section p{font-size:11px;line-height:1.8;color:#5e6e80}.drawer-tags{display:flex;flex-wrap:wrap;gap:5px}.drawer-tags i{font-style:normal;background:#f1f6fb;padding:4px 7px;border-radius:4px;font-size:9px}.drawer-actions{display:flex;gap:8px;margin-top:20px}.drawer-actions button{flex:1}.compact-heading{align-items:flex-start;margin-bottom:20px}.compact-heading h1{font-size:27px}@media(max-width:1120px){.dimension-grid,.note-grid{grid-template-columns:repeat(3,1fr)}.account-grid{grid-template-columns:1fr 1fr}.feishu-layout{grid-template-columns:1fr}.delivery-settings{order:-1}.bottom-grid{grid-template-columns:1fr}.compare-select{grid-template-columns:1fr 1fr}}@media(max-width:820px){.demo-shell{grid-template-columns:186px minmax(0,1fr)}.demo-sidebar{padding:18px 8px}.demo-brand{padding:0 6px}.page-content{padding:22px 18px 36px}.capture-form{grid-template-columns:1fr 1fr}.url-input{grid-column:1/-1}.account-grid,.dimension-grid,.note-grid,.compare-accounts,.topic-grid,.settings-grid{grid-template-columns:1fr 1fr}.account-stats{grid-template-columns:repeat(3,1fr)}.progress-steps{grid-template-columns:1fr 1fr}.analysis-summary{grid-template-columns:1fr 1fr}.compare-row{grid-template-columns:110px repeat(3,minmax(100px,1fr))}.compare-table{overflow-x:auto}.feishu-preview{overflow-x:auto}.preview-body{min-width:680px}}@media(max-width:600px){.demo-shell{display:block}.demo-sidebar{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line);padding:12px}.demo-brand{margin-bottom:10px}.demo-nav{display:flex;overflow-x:auto;gap:4px}.demo-nav button{white-space:nowrap;padding:8px}.demo-nav button>span,.demo-nav button i,.sidebar-bottom{display:none}.demo-topbar{padding:0 14px}.demo-badge{display:none}.page-content{padding:18px 14px 34px}.page-heading,.library-heading,.analysis-head{flex-direction:column;align-items:stretch;gap:12px}.page-heading h1,.library-heading h1,.analysis-head h1{font-size:24px}.capture-card{padding:18px}.capture-form{grid-template-columns:1fr}.account-grid,.dimension-grid,.note-grid,.compare-accounts,.topic-grid,.settings-grid,.analysis-summary{grid-template-columns:1fr}.account-stats{grid-template-columns:1fr 1fr}.library-toolbar{flex-wrap:wrap}.library-toolbar .search-box{flex-basis:100%}.library-tabs{overflow-x:auto}.library-tabs button{white-space:nowrap}.note-drawer{width:100vw}.progress-steps{grid-template-columns:1fr}.done-actions{flex-direction:column;align-items:stretch}.workflow-steps{display:grid;grid-template-columns:1fr}.workflow-steps i{display:none}.compare-select{grid-template-columns:1fr}.next-actions{grid-template-columns:1fr}.feishu-mark{display:none}}
.status-warn{color:#a66b13;font-size:9px}.status-warn::before{content:"●";margin-right:3px}
.progress-counts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:14px 0 4px;padding:12px;border:1px solid #e7edf4;border-radius:10px;background:#fff}
.progress-counts div{display:flex;flex-direction:column;gap:2px}
.progress-counts span{font-size:10px;color:#8d98a6}
.progress-counts b{font-size:15px;color:#1d2938}
.progress-actions{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:12px;font-size:12px;color:#6f7d8e}
.stopped-actions{background:#fff8e8;border:1px solid #f2dfae;border-radius:10px}
.filter-panel{display:flex;flex-wrap:wrap;align-items:center;gap:14px;padding:12px 14px;margin:0 0 12px;border:1px solid #e7edf4;border-radius:10px;background:#fff;font-size:12px}
.filter-panel label{display:flex;align-items:center;gap:8px;color:#5c6a7b;font-weight:600;margin:0}
.filter-panel select{width:auto;padding:6px 10px;border:1px solid #dfe6ee;border-radius:7px;font-size:12px;background:#fff}
.filter-check input{width:auto;margin:0}
.filter-button.active{background:#eaf3fd;border-color:#b9d6f5;color:#0d5aa7}
.drawer-alert{margin:14px 0;padding:12px;border:1px solid #f4d9a8;background:#fff8e8;border-radius:9px;display:grid;gap:6px}
.drawer-alert>span{font-size:10px;font-weight:800;color:#a66b13;letter-spacing:.04em}
.drawer-alert p{font-size:12px;color:#7a5a17}
.drawer-alert button{justify-self:start}
.retry-ok{font-size:11px;color:#0d7a4f}
.source-link{display:block;word-break:break-all;font-size:11px;color:#1677d2;background:#f4f8fd;border:1px solid #e3edf9;border-radius:7px;padding:8px;font-family:ui-monospace,Consolas,monospace}
.dimension-advice{margin:10px 0;padding:10px 12px;border-left:3px solid #1677d2;background:#f4f8fd;border-radius:0 7px 7px 0}
.dimension-advice b{display:block;font-size:10px;color:#0d5aa7;margin-bottom:4px}
.dimension-advice p{font-size:12px;color:#3d4b5c}
.topic-detail{margin-top:10px;padding-top:10px;border-top:1px dashed #e3eaf2;display:grid;gap:4px}
.topic-detail>span{font-size:10px;font-weight:800;color:#8a97a7;letter-spacing:.04em}
.topic-detail p{font-size:12px;color:#3d4b5c}
.topic-detail ol{margin:2px 0 0 16px;display:grid;gap:3px;font-size:12px;color:#3d4b5c}
.compare-hint{margin:8px 0 0;font-size:11px;color:#8a97a7}
.week-plan{margin-top:14px;background:#fff;border:1px solid #e7edf4;border-radius:12px;padding:16px}
.week-plan-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-top:12px}
.week-plan-grid article{position:relative;border:1px solid #e7edf4;border-radius:10px;padding:12px;background:#fafcff;display:flex;flex-direction:column;gap:4px}
.week-plan-grid article>span{font-size:10px;font-weight:800;color:#0d5aa7}
.week-plan-grid article b{font-size:12px}
.week-plan-grid article p{font-size:11px;color:#6f7d8e;line-height:1.45}
.week-plan-grid article i{position:absolute;top:10px;right:10px;font-size:9px;font-style:normal;color:#b6c2d0}
.library-toolbar>button,.library-toolbar>select,.library-toolbar .view-switch{flex-shrink:0}
.library-toolbar>select{width:auto}
.library-toolbar button,.library-toolbar select{white-space:nowrap}
.analysis-summary{grid-template-columns:repeat(3,minmax(0,1fr))}
.history-toolbar select{width:auto;flex-shrink:0}
.finish-time{display:block;font-size:10px;color:#8d98a6;margin-top:2px}
.reason-cell{font-size:11px;color:#a66b13}
@media (max-width:1280px){.week-plan-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.progress-counts{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
