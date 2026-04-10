import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import VueVirtualScroller from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'

async function init() {
  try {
    const res = await fetch('/settings/theme')
    if (res.ok) {
      const { value } = await res.json()
      if (value === 'light') {
        document.documentElement.dataset.theme = 'light'
      }
    }
  } catch {
    // daemon not reachable — fall through to dark default
  }
  createApp(App).use(VueVirtualScroller).mount('#app')
}

init()
