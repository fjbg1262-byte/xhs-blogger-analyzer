import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated } from '../auth'

const routes = [
  { path: '/', redirect: '/dashboard' },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
  },
  {
    path: '/extension-login',
    name: 'ExtensionLogin',
    component: () => import('../views/ExtensionLoginView.vue'),
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/DashboardView.vue'),
  },
  {
    path: '/analysis/new',
    name: 'NewAnalysis',
    component: () => import('../views/NewAnalysisView.vue'),
  },
  {
    path: '/analysis/:taskId',
    name: 'AnalysisDetail',
    component: () => import('../views/AnalysisDetailView.vue'),
  },
  {
    path: '/report/:taskId/:reportType?',
    name: 'ReportViewer',
    component: () => import('../views/ReportViewerView.vue'),
  },
  {
    path: '/competitors',
    name: 'Competitors',
    component: () => import('../views/CompetitorView.vue'),
  },
  {
    path: '/ai-tools',
    name: 'AITools',
    component: () => import('../views/AIToolsView.vue'),
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('../views/HistoryView.vue'),
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/SettingsView.vue'),
  },
  {
    path: '/compare',
    name: 'Compare',
    component: () => import('../views/CompareView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const publicPaths = ['/login', '/extension-login']
  if (!publicPaths.includes(to.path) && !isAuthenticated()) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && isAuthenticated()) {
    return '/dashboard'
  }
})

export default router
