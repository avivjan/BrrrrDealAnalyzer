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
import MemberLoan from '../views/MemberLoan.vue'
import InspectionsHome from '../views/InspectionsHome.vue'
import InspectionStart from '../views/InspectionStart.vue'
import InspectionWalkthrough from '../views/InspectionWalkthrough.vue'
import InspectionSummary from '../views/InspectionSummary.vue'
import { useAuthStore } from '../stores/authStore'
import { isOnPublicRoute } from './publicRoutes'

/** Routes that never require a session, and are not in the primary nav. */
export const AUTH_ROUTE_NAMES = ['login', 'enroll', 'pending', 'connect', 'devices'] as const

/** The Member Loan (two members only): reached from the session strip and e-mails, not the primary nav. */
export const MEMBER_LOAN_ROUTE_NAMES = ['member-loan', 'member-loan-approval', 'member-loan-sign'] as const

/** The inspection pages under the Inspections tab: public by link (`meta.public`), never a login. */
export const INSPECTION_SUB_ROUTE_NAMES = ['inspection-new', 'inspection-walkthrough', 'inspection-item', 'inspection-summary'] as const

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
    // Property inspections (tasks/todo/PropertyInspection.md): public, reached
    // by an unguessable link. The API keeps listing and deal links behind login.
    {
      path: '/inspections',
      name: 'inspections',
      component: InspectionsHome,
      meta: { public: true }
    },
    { path: '/inspections/new', name: 'inspection-new', component: InspectionStart, meta: { public: true } },
    { path: '/inspections/:inspectionId', name: 'inspection-walkthrough', component: InspectionWalkthrough, props: true, meta: { public: true } },
    { path: '/inspections/:inspectionId/items/:itemKey', name: 'inspection-item', component: InspectionWalkthrough, props: true, meta: { public: true } },
    { path: '/inspections/:inspectionId/summary', name: 'inspection-summary', component: InspectionSummary, props: true, meta: { public: true } },
    // Authentication (SECURITY_PLAN.md §3.2). `meta.auth` marks them; they are
    // deliberately absent from `shell/nav.ts`.
    { path: '/login', name: 'login', component: LoginView, meta: { auth: true } },
    { path: '/enroll', name: 'enroll', component: EnrollView, meta: { auth: true } },
    { path: '/pending', name: 'pending', component: PendingApproval, meta: { auth: true } },
    { path: '/connect', name: 'connect', component: ConnectView, meta: { auth: true } },
    { path: '/settings/devices', name: 'devices', component: SettingsDevices, meta: { auth: true } },
    // The Member Loan gates itself on the API (exactly the two members, on a
    // passkey); the session strip links it only for them.
    { path: '/member-loan', name: 'member-loan', component: MemberLoan },
    { path: '/member-loan/approvals/:eventId', name: 'member-loan-approval', component: MemberLoan, props: true },
    { path: '/member-loan/sign/:documentId', name: 'member-loan-sign', component: MemberLoan, props: true }
  ]
})

// Session guard. When the API does not enforce sessions (AUTH_MODE=off, the
// default) `load()` resolves to `off` and every route behaves exactly as
// before -- no login screen ever appears.
router.beforeEach(async (to) => {
  isOnPublicRoute.value = to.meta.public === true
  if (to.meta.auth || to.meta.public) return true
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





