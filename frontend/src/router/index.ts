import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from '../views/LandingPage.vue'
import AnalyzeDeal from '../views/AnalyzeDeal.vue'
import MyDeals from '../views/MyDeals.vue'
import BoughtDeals from '../views/BoughtDeals.vue'
import LiquidityTimeline from '../views/LiquidityTimeline.vue'
import RepsTracker from '../views/RepsTracker.vue'
import LoginView from '../views/LoginView.vue'
import EnrollView from '../views/EnrollView.vue'
import PendingApproval from '../views/PendingApproval.vue'
import ConnectView from '../views/ConnectView.vue'
import SettingsDevices from '../views/SettingsDevices.vue'
import { useAuthStore } from '../stores/authStore'

/** Routes that never require a session, and are not in the primary nav. */
export const AUTH_ROUTE_NAMES = ['login', 'enroll', 'pending', 'connect', 'devices'] as const

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: LandingPage
    },
    {
      path: '/analyze',
      name: 'analyze',
      component: AnalyzeDeal
    },
    {
      path: '/my-deals',
      name: 'my-deals',
      component: MyDeals
    },
    {
      path: '/bought-deals',
      name: 'bought-deals',
      component: BoughtDeals
    },
    {
      path: '/liquidity',
      name: 'liquidity',
      component: LiquidityTimeline
    },
    {
      path: '/reps',
      name: 'reps',
      component: RepsTracker
    },
    // Authentication (SECURITY_PLAN.md §3.2). `meta.auth` marks them; they are
    // deliberately absent from `shell/nav.ts`.
    { path: '/login', name: 'login', component: LoginView, meta: { auth: true } },
    { path: '/enroll', name: 'enroll', component: EnrollView, meta: { auth: true } },
    { path: '/pending', name: 'pending', component: PendingApproval, meta: { auth: true } },
    { path: '/connect', name: 'connect', component: ConnectView, meta: { auth: true } },
    { path: '/settings/devices', name: 'devices', component: SettingsDevices, meta: { auth: true } }
  ]
})

// Session guard. When the API does not enforce sessions (AUTH_MODE=off, the
// default) `load()` resolves to `off` and every route behaves exactly as
// before -- no login screen ever appears.
router.beforeEach(async (to) => {
  if (to.meta.auth) return true
  const auth = useAuthStore()
  const status = auth.status === 'unknown' ? await auth.load() : auth.status
  if (status === 'anon') return { name: 'login', query: { next: to.fullPath } }
  if (status === 'pending') return { name: 'pending' }
  return true
})

router.beforeEach((to, from, next) => {
  console.group('Router: Navigation');
  console.log('From:', from.fullPath);
  console.log('To:', to.fullPath);
  console.log('Params:', to.params);
  console.log('Query:', to.query);
  console.groupEnd();
  next();
});

export default router





