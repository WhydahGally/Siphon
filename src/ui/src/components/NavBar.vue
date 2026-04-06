<script setup>
defineProps({ currentPage: String })
const emit = defineEmits(['navigate'])
</script>

<template>
  <nav class="navbar">
    <span class="logo">Siphon</span>
    <div class="nav-links">
      <button
        v-for="page in ['dashboard', 'library', 'settings']"
        :key="page"
        class="nav-btn"
        :class="{ active: currentPage === page }"
        @click="emit('navigate', page)"
      >
        {{ page.charAt(0).toUpperCase() + page.slice(1) }}
      </button>
    </div>
  </nav>
</template>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  gap: 32px;
  padding: 0 24px;
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
}

.nav-links {
  display: flex;
  gap: 4px;
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
</style>
