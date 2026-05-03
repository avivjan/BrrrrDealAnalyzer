import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from '../views/LandingPage.vue'
import AnalyzeDeal from '../views/AnalyzeDeal.vue'
import MyDeals from '../views/MyDeals.vue'
import BoughtDeals from '../views/BoughtDeals.vue'
import LiquidityTimeline from '../views/LiquidityTimeline.vue'
import RepsTracker from '../views/RepsTracker.vue'

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
    }
  ]
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





