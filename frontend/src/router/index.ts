import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from '../views/LandingPage.vue'
import AnalyzeDeal from '../views/AnalyzeDeal.vue'
import MyDeals from '../views/MyDeals.vue'

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
    }
  ]
})

export default router


