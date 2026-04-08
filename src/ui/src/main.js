import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import VueVirtualScroller from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'

createApp(App).use(VueVirtualScroller).mount('#app')
