<template>
  <div class="split-button" :class="{ 'split-button--open': open }" ref="splitRef">
    <button class="split-button__primary" :disabled="disabled" @click="$emit('click', options[0])">
      <slot :label="options[0]" />
    </button>
    <button class="split-button__trigger" :disabled="disabled" @click.stop="open = !open" aria-label="More options">
      <span class="split-button__caret">&#9662;</span>
    </button>
    <Transition name="dropdown-slide">
      <div v-if="open" class="split-button__dropdown">
        <button class="split-button__option" @click="select(1)">
          <span class="split-button__option-label">{{ options[1] }}</span>
          <span class="split-button__info" :title="tooltips[1]">&#9432;</span>
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  disabled: { type: Boolean, default: false },
  options: { type: Array, required: true },
  tooltips: { type: Array, default: () => [] },
})

const emit = defineEmits(['click'])
const open = ref(false)
const splitRef = ref(null)

function select(index) {
  open.value = false
  emit('click', props.options[index])
}

function onClickOutside(e) {
  if (splitRef.value && !splitRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('mousedown', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('mousedown', onClickOutside))
</script>

<style scoped>
.split-button {
  display: inline-flex;
  align-items: stretch;
  position: relative;
}

.split-button__primary {
  background: var(--accent);
  color: #fff;
  border: 1px solid var(--accent);
  border-right: none;
  border-radius: var(--radius-sm) 0 0 var(--radius-sm);
  /* fixed width so label swap doesn't cause layout shift */
  min-width: 100px;
  text-align: center;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  min-height: 44px;
  transition: background 0.15s, border-radius 0.15s;
}

.split-button--open .split-button__primary {
  border-radius: var(--radius-sm) 0 0 0;
}

.split-button__primary:hover:not(:disabled) {
  background: var(--accent-hover, var(--accent));
}

.split-button__primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.split-button__trigger {
  background: var(--accent);
  color: #fff;
  border: 1px solid var(--accent);
  border-left: none;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  padding: 8px 12px;
  cursor: pointer;
  min-height: 44px;
  min-width: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, border-radius 0.15s;
  position: relative;
}

.split-button--open .split-button__trigger {
  border-radius: 0 var(--radius-sm) 0 0;
}

/* Divider as pseudo-element — inset so purple background is seamless */
.split-button__trigger::before {
  content: '';
  position: absolute;
  left: 0;
  top: 25%;
  bottom: 25%;
  width: 1px;
  background: rgba(255, 255, 255, 0.3);
}

.split-button__trigger:hover:not(:disabled) {
  background: var(--accent-hover, var(--accent));
}

.split-button__trigger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.split-button__caret {
  font-size: 16px;
}

.split-button__dropdown {
  position: absolute;
  top: 100%;
  left: -1px;
  right: -1px;
  margin-top: 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-top: none;
  border-radius: 0 0 var(--radius-sm) var(--radius-sm);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  z-index: 10;
  transform-origin: top;
}

.dropdown-slide-enter-active {
  transition: transform 0.15s ease-out, opacity 0.15s ease-out;
}
.dropdown-slide-leave-active {
  transition: transform 0.1s ease-in, opacity 0.1s ease-in;
}
.dropdown-slide-enter-from {
  transform: scaleY(0);
  opacity: 0;
}
.dropdown-slide-leave-to {
  transform: scaleY(0);
  opacity: 0;
}

.split-button__option {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 18px;
  background: none;
  border: none;
  color: var(--text);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  text-align: left;
  min-height: 44px;
  transition: background 0.12s;
}

.split-button__option:hover {
  background: var(--surface-hover, rgba(255, 255, 255, 0.05));
}

.split-button__option-label {
  flex: 1;
}

.split-button__info {
  color: var(--text-muted);
  font-size: 14px;
  cursor: default;
}
</style>
