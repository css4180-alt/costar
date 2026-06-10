<template>
  <label
    class="drop"
    :class="{ over: dragOver, busy }"
    @dragover.prevent="dragOver = true"
    @dragleave.prevent="dragOver = false"
    @drop.prevent="onDrop"
  >
    <input
      ref="input"
      type="file"
      accept="image/jpeg,image/png"
      :multiple="multiple"
      class="hidden-input"
      :disabled="busy"
      @change="onChange"
    />
    <svg viewBox="0 0 24 24" width="22" height="22" class="ico" aria-hidden="true">
      <path
        d="M12 16V5m0 0L8 9m4-4 4 4"
        fill="none"
        stroke="currentColor"
        stroke-width="1.7"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <path
        d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
        fill="none"
        stroke="currentColor"
        stroke-width="1.7"
        stroke-linecap="round"
      />
    </svg>
    <span class="label">{{ busy ? '처리 중…' : label }}</span>
    <span class="hint">JPEG · PNG{{ multiple ? ' · 여러 장 가능' : '' }}</span>
  </label>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  label: { type: String, default: '이미지를 드래그하거나 클릭해 선택' },
  multiple: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['files'])

const input = ref(null)
const dragOver = ref(false)

function emitFiles(fileList) {
  const files = Array.from(fileList).filter((f) => f.type.startsWith('image/'))
  if (!files.length) return
  emit('files', props.multiple ? files : [files[0]])
}

function onChange(e) {
  emitFiles(e.target.files)
  e.target.value = '' // 같은 파일 재선택 허용
}

function onDrop(e) {
  dragOver.value = false
  if (props.busy) return
  emitFiles(e.dataTransfer.files)
}
</script>

<style scoped>
.drop {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 26px 18px;
  text-align: center;
  color: var(--ink-faint);
  background: var(--surface-2);
  border: 1.5px dashed var(--line-strong);
  border-radius: var(--radius);
  cursor: pointer;
  transition: border-color 0.16s, background 0.16s, color 0.16s;
}
.drop:hover {
  border-color: var(--gold);
  color: var(--ink-soft);
}
.drop.over {
  border-color: var(--gold);
  background: var(--gold-soft);
  color: var(--gold);
}
.drop.busy {
  opacity: 0.6;
  cursor: progress;
}
.hidden-input {
  display: none;
}
.ico {
  color: var(--gold);
}
.label {
  font-size: 0.86rem;
  font-weight: 500;
}
.hint {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--ink-dim);
}
</style>
