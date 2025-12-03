import { createRouter, createWebHistory } from 'vue-router';
import LandingPage from '../views/LandingPage.vue';
import AnalyzePage from '../views/AnalyzePage.vue';
import MyDealsPage from '../views/MyDealsPage.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'Landing', component: LandingPage },
    { path: '/analyze', name: 'Analyze', component: AnalyzePage },
    { path: '/my-deals', name: 'MyDeals', component: MyDealsPage },
    { path: '/:pathMatch(.*)*', redirect: '/' }
  ]
});

export default router;
