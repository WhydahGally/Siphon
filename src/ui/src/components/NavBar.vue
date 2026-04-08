<script setup>
defineProps({ currentPage: String })
const emit = defineEmits(['navigate'])
</script>

<template>
  <nav class="navbar">
    <span class="logo">Siphon</span>

    <div class="nav-center">
      <button
        v-for="page in ['dashboard', 'library']"
        :key="page"
        class="nav-btn"
        :class="{ active: currentPage === page }"
        @click="emit('navigate', page)"
      >
        {{ page.charAt(0).toUpperCase() + page.slice(1) }}
      </button>
    </div>

    <button
      class="settings-btn"
      :class="{ active: currentPage === 'settings' }"
      :title="'Settings'"
      @click="emit('navigate', 'settings')"
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
    </button>
  </nav>
</template>

<style scoped>
.navbar {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  padding: 0 20px;
  height: 56px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.logo {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.3px;
  color: var(--accent);
  user-select: none;
  justify-self: start;
  transition: text-shadow 0.2s;
}

.logo:hover {
  text-shadow: 0 0 10px var(--accent), 0 0 24px rgba(124, 106, 247, 0.5);
}

.nav-center {
  display: flex;
  gap: 4px;
  justify-self: center;
}

.nav-btn {
  background: none;
  border: none;
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-size: 14px;
  font-weight: 500;
  transition: color 0.15s, background 0.15s;
}

.nav-btn:hover {
  color: var(--text);
  background: var(--surface-2);
}

.nav-btn.active {
  color: var(--text);
  background: var(--surface-2);
  position: relative;
}

.nav-btn.active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 14px;
  right: 14px;
  height: 2px;
  background: var(--accent);
  border-radius: 2px 2px 0 0;
}

.settings-btn {
  justify-self: end;
  background: none;
  border: none;
  color: var(--text-muted);
  padding: 6px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s, background 0.15s;
}

.settings-btn:hover {
  color: var(--text);
  background: var(--surface-2);
}

.settings-btn.active {
  color: var(--accent);
}
</style>
