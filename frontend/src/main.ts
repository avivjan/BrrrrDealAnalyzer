import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config';
import App from './App.vue'
import router from './router'
import { primevuePt } from './design/primevue-pt'
import { registerUiPrimitives } from './components/ui/register'
import { registerMotion } from './motion'
import { initTheme } from './design/theme'
import '@fontsource-variable/inter'
import './assets/main.css'
import 'primeicons/primeicons.css'

console.log('Main: App initializing...');

// Look, mode and motion from this browser's stored choices (or the defaults),
// before the first render. The inline script in index.html already painted the
// same answer; this hands ownership to the runtime and loads the look's fonts.
initTheme()

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(PrimeVue, {
    unstyled: true,
    pt: primevuePt,
    ptOptions: { mergeSections: true, mergeProps: true }
});
registerUiPrimitives(app)
registerMotion(app)

app.mount('#app')
console.log('Main: App mounted');
