<script setup>
defineProps({
  items: { type: Array, required: true },
  loading: { type: Boolean, default: false },
})
</script>

<template>
  <div class="items-panel">
    <div v-if="loading" class="panel-loading">
      <span class="spinner" />
      <span class="loading-text">Loading items…</span>
    </div>

    <div v-else-if="items.length === 0" class="panel-empty">
      No items downloaded yet.
    </div>

    <div v-else class="scroller">
      <div class="scroll-inner">
        <div v-for="item in items" :key="item.video_id" class="panel-item">
          <div class="item-titles">
            <span v-if="item.renamed_to" class="item-title">
              <span class="original">{{ item.yt_title }}</span>
              <span class="arrow"> → </span>
              <span class="renamed">{{ item.renamed_to }}</span>
              <span v-if="item.rename_tier" class="tier-badge">{{ item.rename_tier === 'yt_title_fallback' ? 'yt_title' : item.rename_tier }}</span>
            </span>
            <span v-else class="item-title plain">{{ item.yt_title }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.items-panel {
  max-height: 70vh;
  overflow: hidden;
  border-top: 1px solid var(--border);
  background: var(--bg);
}

.scroller {
  max-height: 70vh;
  overflow-y: auto;
  overflow-x: auto;
}

.scroll-inner {
  width: max-content;
  min-width: 100%;
}

.panel-loading,
.panel-empty {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  color: var(--text-muted);
  font-size: 13px;
}

.panel-item {
  display: flex;
  align-items: center;
  padding: 0 20px;
  height: 40px;
  border-bottom: 1px solid var(--border);
  box-sizing: border-box;
}

.panel-item:last-child {
  border-bottom: none;
}

.item-titles {
  flex: 1;
}

.item-title {
  display: block;
  font-size: 13px;
  white-space: nowrap;
}

.item-title.plain {
  color: var(--text);
}

.original {
  color: var(--text-muted);
}

.arrow {
  color: var(--text-muted);
}

.renamed {
  color: var(--text);
  font-weight: 500;
}

.tier-badge {
  display: inline-block;
  margin-left: 4px;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 6px;
  font-weight: 700;
  background: rgba(124, 106, 247, 0.15);
  color: var(--accent);
  vertical-align: super;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  line-height: 1;
}

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(124, 106, 247, 0.3);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
