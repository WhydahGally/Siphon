import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/playlists': 'http://localhost:8000',
      '/jobs': 'http://localhost:8000',
      '/settings': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/version': 'http://localhost:8000',
      '/factory-reset': 'http://localhost:8000',
      '/info': 'http://localhost:8000',
    },
  },
})
