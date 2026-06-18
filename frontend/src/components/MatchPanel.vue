<template>
  <section class="panel">
    <div class="head">
      <p class="eyebrow">Match</p>
      <h2 class="title">공동 출연 탐색</h2>
      <p class="desc">사진을 올리면 여러 얼굴을 한 번에 식별하고, 그 인물들이 함께 출연한 작품을 찾습니다.</p>
    </div>

    <!-- 이미지 분석 -->
    <DropZone
      v-if="!imageUrl"
      :busy="analyzing"
      label="공동 출연 사진을 드래그하거나 클릭 (JPEG/PNG)"
      @files="onAnalyze"
    />

    <div v-if="imageUrl" class="analyze">
      <div class="canvas-wrap">
        <div class="canvas">
          <img :src="imageUrl" alt="분석 이미지" @load="imgReady = true" />
          <template v-if="imgReady">
            <div
              v-for="(d, i) in detected"
              :key="i"
              class="fbox"
              :class="{ id: d.person_id }"
              :style="boxStyle(d.box)"
            >
              <span v-if="d.name" class="flabel">{{ d.name }}</span>
            </div>
          </template>
          <div v-if="analyzing" class="canvas-busy">분석 중…</div>
        </div>
        <button class="btn btn-ghost reset" @click="resetAnalyze">다른 사진</button>
      </div>

      <div v-if="analyzed" class="cols">
        <div class="col">
          <h3 class="sub">식별된 인물 <span class="count">{{ identified.length }}</span></h3>
          <div v-if="identified.length" class="id-list">
            <div v-for="d in identified" :key="d.person_id" class="id-item">
              <span class="id-name">{{ d.name }}</span>
              <span class="id-sim">{{ d.similarity.toFixed(1) }}% 일치</span>
            </div>
          </div>
          <p v-else class="none">등록된 인물과 일치하는 얼굴이 없습니다.</p>
        </div>

        <div class="col">
          <h3 class="sub">공통 출연 작품 <span class="count">{{ common.length }}</span></h3>
          <div v-if="common.length" class="work-list">
            <article
              v-for="w in common"
              :key="w.id"
              class="work-item"
              @click="store.openPreview(w.rep_url, w.title)"
            >
              <span class="work-poster">
                <img v-if="w.rep_url" :src="w.rep_url" :alt="w.title" />
                <span v-else class="work-ic">🎬</span>
              </span>
              <div class="work-meta">
                <span class="work-title">{{ w.title }}</span>
                <span class="work-year">{{ w.year || '연도 미상' }}</span>
              </div>
            </article>
          </div>
          <p v-else class="none">
            {{ identified.length >= 2 ? '함께 출연한 작품이 없습니다.' : '2명 이상 식별되면 공통 작품을 찾습니다.' }}
          </p>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { store } from '../store.js'
import DropZone from './DropZone.vue'

const imageUrl = ref(null)
const imgReady = ref(false)
const analyzing = ref(false)
const analyzed = ref(false)
const detected = ref([])
const common = ref([])

const identified = computed(() => detected.value.filter((d) => d.person_id))

function boxStyle(b) {
  return {
    left: b.left * 100 + '%',
    top: b.top * 100 + '%',
    width: b.width * 100 + '%',
    height: b.height * 100 + '%',
  }
}

async function onAnalyze([file]) {
  if (!file) return
  resetAnalyze()
  imageUrl.value = URL.createObjectURL(file)
  analyzing.value = true
  try {
    const res = await store.analyzePhoto(file)
    detected.value = res.detected
    common.value = res.common_works
    analyzed.value = true
  } catch (err) {
    store.notify(err.message, 'error')
    resetAnalyze()
  } finally {
    analyzing.value = false
  }
}

function resetAnalyze() {
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  imageUrl.value = null
  imgReady.value = false
  analyzed.value = false
  detected.value = []
  common.value = []
}
</script>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.eyebrow {
  margin: 0 0 6px;
}
.title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.5rem;
  color: var(--ink);
}
.desc {
  margin: 7px 0 0;
  font-size: 0.88rem;
  color: var(--ink-soft);
}

/* 이미지 분석 */
.analyze {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.canvas-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.canvas {
  position: relative;
  display: inline-block;
  max-width: 100%;
  line-height: 0;
  border-radius: var(--radius);
  overflow: hidden;
  border: 1px solid var(--line);
}
.canvas img {
  display: block;
  max-width: 100%;
  max-height: 56vh;
}
.fbox {
  position: absolute;
  border: 2px solid var(--ink-faint);
  border-radius: 3px;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.4);
  pointer-events: none;
}
.fbox.id {
  border-color: #22d3ee;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.5), 0 0 12px rgba(34, 211, 238, 0.4);
}
.flabel {
  position: absolute;
  top: -21px;
  left: -2px;
  padding: 1px 7px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  line-height: 1.5;
  color: #06262c;
  background: #22d3ee;
  border-radius: 4px 4px 0 0;
  white-space: nowrap;
}
.canvas-busy {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  color: var(--gold);
  background: rgba(6, 8, 12, 0.55);
}
.reset {
  align-self: center;
}

.cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 22px;
}
@media (max-width: 640px) {
  .cols {
    grid-template-columns: 1fr;
  }
}
.col {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.sub {
  margin: 0;
  font-size: 1rem;
  color: var(--ink);
}
.count {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--gold);
  margin-left: 4px;
}
.id-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.id-item {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 12px 14px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.id-name {
  font-weight: 600;
  font-size: 0.96rem;
  color: var(--ink);
}
.id-sim {
  font-family: var(--font-mono);
  font-size: 0.74rem;
  color: var(--gold);
}
.work-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.work-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  cursor: zoom-in;
  transition: border-color 0.16s, transform 0.12s;
}
.work-item:hover {
  border-color: var(--gold);
  transform: translateX(2px);
}
.work-poster {
  flex: 0 0 auto;
  width: 38px;
  height: 56px;
  border-radius: 5px;
  overflow: hidden;
  background: var(--surface-3);
  display: grid;
  place-items: center;
}
.work-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.work-ic {
  font-size: 1.1rem;
}
.work-meta {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.work-title {
  font-weight: 600;
  font-size: 0.94rem;
  color: var(--ink);
}
.work-year {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--ink-dim);
}
.none {
  margin: 0;
  padding: 16px;
  font-size: 0.86rem;
  color: var(--ink-faint);
  background: var(--surface);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}
</style>
