<script setup>
import { ref } from 'vue'
import NavBar from './components/NavBar.vue'
import Dashboard from './components/Dashboard.vue'
import Library from './components/Library.vue'
import Settings from './components/Settings.vue'
import ToastContainer from './components/ToastContainer.vue'

const currentPage = ref('dashboard')
</script>

<template>
  <div class="app">
    <NavBar :current-page="currentPage" @navigate="currentPage = $event" />
    <main class="main-content">
      <Dashboard v-if="currentPage === 'dashboard'" />
      <Library v-else-if="currentPage === 'library'" />
      <Settings v-else-if="currentPage === 'settings'" />
    </main>
    <ToastContainer />
  </div>
</template>

<style>
.app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
.main-content {
  flex: 1;
  max-width: 960px;
  width: 100%;
  margin: 0 auto;
  padding: 0 24px;
}
</style>
