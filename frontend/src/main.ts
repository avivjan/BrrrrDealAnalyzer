import { createApp } from 'vue';
import PrimeVue from 'primevue/config';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import '@primevue/themes/arya';
import 'primeicons/primeicons.css';
import './assets/main.css';

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.use(PrimeVue, { unstyled: true, ripple: true });
app.mount('#app');
