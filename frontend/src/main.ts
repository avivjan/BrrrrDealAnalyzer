import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config';
import App from './App.vue'
import router from './router'
import './assets/main.css'
import 'primeicons/primeicons.css'

console.log('Main: App initializing...');

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(PrimeVue, {
    unstyled: true,
    pt: {
        // Global Passthrough configuration can go here
        // For now we will style components individually or use a preset if we had one
    } 
});

app.mount('#app')
console.log('Main: App mounted');
