<template>
  <transition name="fade">
    <div v-if="store.preview" class="overlay" @click="store.closePreview()">
      <figure class="frame" @click.stop>
        <img :src="store.preview.url" :alt="store.preview.caption" class="img" />
        <figcaption v-if="store.preview.caption" class="cap">
          {{ store.preview.caption }}
        </figcaption>
        <button class="close" aria-label="닫기" @click="store.closePreview()">✕</button>
      </figure>
    </div>
  </transition>
</template>

<script setup>
import { store } from '../store.js'
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 400;
  display: grid;
  place-items: center;
  padding: 32px;
  background: rgba(4, 5, 8, 0.82);
  backdrop-filter: blur(3px);
}
.frame {
  position: relative;
  margin: 0;
  max-width: 90vw;
  max-height: 88vh;
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.img {
  display: block;
  max-width: 90vw;
  max-height: 78vh;
  object-fit: contain;
}
.cap {
  padding: 10px 14px;
  font-size: 0.82rem;
  color: var(--ink-soft);
  border-top: 1px solid var(--line);
}
.close {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 32px;
  height: 32px;
  font-size: 0.9rem;
  color: var(--ink);
  background: rgba(10, 12, 17, 0.7);
  border: 1px solid var(--line-strong);
  border-radius: 50%;
  cursor: pointer;
}
.close:hover {
  background: var(--surface-3);
}
</style>
