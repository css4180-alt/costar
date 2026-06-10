<template>
  <section class="panel">
    <div class="head">
      <p class="eyebrow">Match</p>
      <h2 class="title">공동 출연 탐색</h2>
      <p class="desc">두 명 이상을 선택하면 함께 출연한 작품을 교차로 찾아냅니다.</p>
    </div>

    <!-- 인물 선택 -->
    <div v-if="store.persons.length" class="picker">
      <button
        v-for="p in store.persons"
        :key="p.id"
        class="pick"
        :class="{ on: selected.has(p.id) }"
        @click="toggle(p.id)"
      >
        <span class="pick-thumb">
          <img v-if="p.rep_url" :src="p.rep_url" :alt="p.name" />
          <span v-else class="ph">{{ initial(p.name) }}</span>
        </span>
        <span class="pick-name">{{ p.name }}</span>
        <span v-if="selected.has(p.id)" class="tick">✓</span>
      </button>
    </div>
    <p v-else class="empty">먼저 People 탭에서 인물을 등록해 주세요.</p>

    <div v-if="store.persons.length" class="action">
      <span class="sel-count">{{ selected.size }}명 선택됨</span>
      <button class="btn" :disabled="selected.size < 2 || searching" @click="search">
        {{ searching ? '찾는 중…' : '공통 출연 찾기' }}
      </button>
    </div>

    <!-- 결과 -->
    <div v-if="searched" class="results">
      <h3 class="sub">결과 <span class="count">{{ results.length }}편</span></h3>
      <div v-if="results.length" class="grid">
        <article
          v-for="w in results"
          :key="w.id"
          class="rcard"
          @click="store.openPreview(w.rep_url, w.title)"
        >
          <div class="poster">
            <img v-if="w.rep_url" :src="w.rep_url" :alt="w.title" />
            <span v-else class="ph">🎬</span>
          </div>
          <div class="meta">
            <span class="name">{{ w.title }}</span>
            <span class="year">{{ w.year || '연도 미상' }}</span>
          </div>
        </article>
      </div>
      <p v-else class="none-result">선택한 인물들이 함께 출연한 작품이 없습니다.</p>
    </div>

    <!-- 사진으로 식별 (보너스) -->
    <div class="identify">
      <p class="eyebrow">Identify</p>
      <h3 class="id-title">사진으로 인물 찾기</h3>
      <p class="desc">얼굴 사진 한 장을 올리면 등록된 인물 중 누구인지 식별합니다.</p>
      <div class="id-row">
        <DropZone class="id-drop" :busy="idBusy" label="사진을 드래그하거나 클릭" @files="onIdentify" />
        <transition name="fade">
          <div v-if="idResult" class="id-result" :class="{ hit: idResult.matched }">
            <template v-if="idResult.matched">
              <div class="id-thumb">
                <img v-if="idResult.matched.rep_url" :src="idResult.matched.rep_url" :alt="idResult.matched.name" />
                <span v-else class="ph">{{ initial(idResult.matched.name) }}</span>
              </div>
              <div>
                <span class="id-name">{{ idResult.matched.name }}</span>
                <span class="id-sim">유사도 {{ Math.round(idResult.similarity) }}%</span>
              </div>
            </template>
            <span v-else class="id-miss">일치하는 등록 인물이 없습니다.</span>
          </div>
        </transition>
      </div>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { store } from '../store.js'
import DropZone from './DropZone.vue'

const selected = reactive(new Set())
const searching = ref(false)
const searched = ref(false)
const results = ref([])

const idBusy = ref(false)
const idResult = ref(null)

function initial(n) {
  return (n || '?').trim().charAt(0).toUpperCase()
}

function toggle(id) {
  if (selected.has(id)) selected.delete(id)
  else selected.add(id)
  searched.value = false
}

async function search() {
  if (selected.size < 2) return
  searching.value = true
  try {
    const res = await store.findCommon([...selected])
    results.value = res.works
    searched.value = true
  } catch (err) {
    store.notify(err.message, 'error')
  } finally {
    searching.value = false
  }
}

async function onIdentify([file]) {
  idBusy.value = true
  idResult.value = null
  try {
    idResult.value = await store.identifyPhoto(file)
  } catch (err) {
    store.notify(err.message, 'error')
  } finally {
    idBusy.value = false
  }
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

.picker {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 12px;
}
.pick {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 14px 10px;
  background: var(--surface);
  border: 1.5px solid var(--line);
  border-radius: var(--radius);
  cursor: pointer;
  transition: border-color 0.16s, background 0.16s, transform 0.1s;
}
.pick:hover {
  border-color: var(--line-bright);
}
.pick.on {
  border-color: var(--gold);
  background: var(--gold-soft);
}
.pick-thumb {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--surface-3);
  display: grid;
  place-items: center;
}
.pick-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.ph {
  font-family: var(--font-display);
  color: var(--ink-faint);
}
.pick-name {
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--ink);
  text-align: center;
}
.tick {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  font-size: 0.7rem;
  color: var(--ink-on-gold);
  background: var(--gold);
  border-radius: 50%;
}

.action {
  display: flex;
  align-items: center;
  gap: 14px;
}
.sel-count {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--ink-faint);
}

.results {
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 14px;
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
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 16px;
}
.rcard {
  cursor: zoom-in;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  transition: transform 0.14s, border-color 0.16s, box-shadow 0.16s;
}
.rcard:hover {
  transform: translateY(-3px);
  border-color: var(--gold);
  box-shadow: var(--shadow-md);
}
.poster {
  aspect-ratio: 16 / 9;
  background: var(--surface-3);
  display: grid;
  place-items: center;
  overflow: hidden;
}
.poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.meta {
  padding: 11px 13px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.name {
  font-weight: 600;
  font-size: 0.94rem;
  color: var(--ink);
}
.year {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--ink-dim);
}
.none-result {
  padding: 28px;
  text-align: center;
  color: var(--ink-faint);
  background: var(--surface);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}

.empty {
  padding: 36px;
  text-align: center;
  color: var(--ink-faint);
  background: var(--surface);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}

.identify {
  margin-top: 12px;
  padding-top: 24px;
  border-top: 1px solid var(--line);
}
.id-title {
  margin: 6px 0 0;
  font-family: var(--font-display);
  font-size: 1.2rem;
  color: var(--ink);
}
.id-row {
  margin-top: 14px;
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(200px, 1fr);
  gap: 16px;
  align-items: stretch;
}
@media (max-width: 640px) {
  .id-row {
    grid-template-columns: 1fr;
  }
}
.id-result {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.id-result.hit {
  border-color: var(--gold);
}
.id-thumb {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  overflow: hidden;
  background: var(--surface-3);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}
.id-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.id-name {
  display: block;
  font-family: var(--font-display);
  font-size: 1.15rem;
  color: var(--ink);
}
.id-sim {
  display: block;
  margin-top: 2px;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--gold);
}
.id-miss {
  font-size: 0.88rem;
  color: var(--ink-faint);
}
</style>
