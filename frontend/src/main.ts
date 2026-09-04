import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config';
import App from './App.vue'
import router from './router'
import { primevuePt } from './design/primevue-pt'
import { registerUiPrimitives } from './components/ui/register'
import '@fontsource-variable/inter'
import './assets/main.css'
import 'primeicons/primeicons.css'

console.log('Main: App initializing...');

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(PrimeVue, {
    unstyled: true,
    pt: primevuePt,
    ptOptions: { mergeSections: true, mergeProps: true }
});
registerUiPrimitives(app)

app.mount('#app')
console.log('Main: App mounted');
