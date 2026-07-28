<template>
  <section class="panel">
    <div class="head">
      <div>
        <p class="eyebrow">People</p>
        <h2 class="title">인물 관리</h2>
      </div>
      <input v-model="search" class="field search" placeholder="이름 검색" />
      <button class="btn" @click="openCreate">＋ 인물 등록</button>
    </div>

    <!-- 목록 -->
    <div class="list-head">
      <h3 class="sub">인물 <span class="count">{{ filteredPersons.length }}</span></h3>
    </div>

    <div v-if="paginatedPersons.length" class="grid">
      <article
        v-for="p in paginatedPersons"
        :key="p.id"
        class="card"
        @click="openDetail(p)"
      >
        <div class="thumb">
          <img v-if="p.rep_url" :src="p.rep_url" :alt="p.name" />
          <span v-else class="ph">{{ initial(p.name) }}</span>
        </div>
        <div class="meta">
          <span class="name">{{ p.name }}</span>
          <span class="date">{{ fmtDate(p.created_at) }}</span>
        </div>
      </article>
    </div>
    <p v-else class="empty">조건에 맞는 인물이 없습니다.</p>

    <div v-if="totalPages > 1" class="pager">
      <button class="btn btn-ghost" :disabled="page === 1" @click="page--">‹ 이전</button>
      <span class="page-info">{{ page }} / {{ totalPages }}</span>
      <button class="btn btn-ghost" :disabled="page === totalPages" @click="page++">다음 ›</button>
    </div>

    <!-- 상세 모달 -->
    <transition name="fade">
      <div v-if="detail" class="overlay" @click="closeDetail">
        <div class="sheet" @click.stop>
          <header class="sheet-head">
            <div class="sheet-id">
              <div class="sheet-thumb">
                <img v-if="detail.rep_url" :src="detail.rep_url" :alt="detail.name" />
                <span v-else class="ph">{{ initial(detail.name) }}</span>
              </div>
              <div>
                <h3 class="sheet-name">{{ detail.name }}</h3>
                <p class="sheet-sub">참조 얼굴 {{ detail.faces?.length || 0 }}장</p>
              </div>
            </div>
            <button class="close" @click="closeDetail">✕</button>
          </header>

          <div class="faces">
            <button
              v-for="f in detail.faces"
              :key="f.face_id"
              class="face"
              @click="store.openPreview(f.image_url, detail.name)"
            >
              <img v-if="f.image_url" :src="f.image_url" :alt="detail.name" />
            </button>
          </div>

          <div v-if="detail.works?.length" class="works-section">
            <p class="block-label">출연 작품 <span class="count">{{ detail.works.length }}</span></p>
            <div class="work-list">
              <button
                v-for="w in detail.works"
                :key="w.id"
                class="work-item"
                @click="store.openWork(w.id)"
              >
                <span class="work-poster">
                  <img v-if="w.rep_url" :src="w.rep_url" :alt="w.title" />
                  <span v-else class="ph">🎬</span>
                </span>
                <span class="work-title">{{ w.title }}</span>
              </button>
            </div>
          </div>

          <DropZone
            :busy="faceBusy"
            label="참조 얼굴 추가"
            @files="onAddFace"
          />

          <footer class="sheet-foot">
            <button class="btn btn-danger" :disabled="faceBusy" @click="onDelete">
              인물 삭제
            </button>
          </footer>
        </div>
      </div>
    </transition>

    <!-- 인물 등록 모달 -->
    <transition name="fade">
      <div v-if="createOpen" class="overlay" @click="closeCreate">
        <div class="sheet" @click.stop>
          <header class="sheet-head">
            <h3 class="sheet-name">인물 등록</h3>
            <button class="close" @click="closeCreate">✕</button>
          </header>

          <input
            v-model="newName"
            class="field"
            placeholder="인물 이름 (예: 송강호)"
            :disabled="createBusy"
          />
          <DropZone
            :busy="createBusy"
            label="대표 사진을 드래그하거나 클릭"
            @files="onPickPhoto"
          />

          <div v-if="store.works.length" class="works-section">
            <p class="block-label">출연 작품 연결(선택)</p>
            <div class="work-pick-list">
              <button
                v-for="w in store.works"
                :key="w.id"
                type="button"
                class="work-pick"
                :class="{ on: selectedWorkIds.has(w.id) }"
                :disabled="createBusy"
                @click="toggleWork(w.id)"
              >
                {{ w.title }}
              </button>
            </div>
          </div>

          <footer class="sheet-foot">
            <button
              class="btn"
              :disabled="createBusy || !newName.trim() || !newPhoto"
              @click="onCreatePerson"
            >
              {{ createBusy ? '등록 중…' : '등록' }}
            </button>
          </footer>
        </div>
      </div>
    </transition>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { store } from '../store.js'
import DropZone from './DropZone.vue'

const detail = ref(null)
const faceBusy = ref(false)

const search = ref('')
const page = ref(1)
const PAGE_SIZE = 24

const filteredPersons = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return store.persons
  return store.persons.filter((p) => (p.name || '').toLowerCase().includes(q))
})
const totalPages = computed(() => Math.max(1, Math.ceil(filteredPersons.value.length / PAGE_SIZE)))
const paginatedPersons = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return filteredPersons.value.slice(start, start + PAGE_SIZE)
})
watch(search, () => {
  page.value = 1
})

// ── 인물 등록 모달 ──
const createOpen = ref(false)
const createBusy = ref(false)
const newName = ref('')
const newPhoto = ref(null)
const selectedWorkIds = ref(new Set())

function openCreate() {
  createOpen.value = true
}
function closeCreate() {
  createOpen.value = false
  newName.value = ''
  newPhoto.value = null
  selectedWorkIds.value = new Set()
}
function onPickPhoto([file]) {
  newPhoto.value = file
}
function toggleWork(id) {
  const next = new Set(selectedWorkIds.value)
  next.has(id) ? next.delete(id) : next.add(id)
  selectedWorkIds.value = next
}
async function onCreatePerson() {
  const nm = newName.value.trim()
  if (!nm || !newPhoto.value) return
  createBusy.value = true
  try {
    const person = await store.addPerson(nm, newPhoto.value)
    for (const workId of selectedWorkIds.value) {
      await store.addCast(workId, person.id)
    }
    store.notify(`'${nm}' 등록 완료`, 'ok')
    closeCreate()
  } catch (err) {
    store.notify(err.message, 'error')
  } finally {
    createBusy.value = false
  }
}

function initial(n) {
  return (n || '?').trim().charAt(0).toUpperCase()
}
function fmtDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('ko-KR', { year: '2-digit', month: 'short', day: 'numeric' })
}

async function openDetail(p) {
  try {
    detail.value = await store.getPersonDetail(p.id)
  } catch (err) {
    store.notify(err.message, 'error')
  }
}
function closeDetail() {
  detail.value = null
}

async function onAddFace([file]) {
  faceBusy.value = true
  try {
    await store.addPersonFace(detail.value.id, file)
    detail.value = await store.getPersonDetail(detail.value.id)
    store.notify('얼굴을 추가했습니다.', 'ok')
  } catch (err) {
    store.notify(err.message, 'error')
  } finally {
    faceBusy.value = false
  }
}

async function onDelete() {
  if (!confirm(`'${detail.value.name}'을(를) 삭제할까요? 등록된 얼굴과 출연 정보도 함께 삭제됩니다.`)) return
  faceBusy.value = true
  try {
    await store.removePerson(detail.value.id)
    store.notify('삭제되었습니다.', 'ok')
    closeDetail()
  } catch (err) {
    store.notify(err.message, 'error')
  } finally {
    faceBusy.value = false
  }
}
</script>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 22px;
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
.head {
  display: flex;
  align-items: center;
  gap: 18px;
}
.search {
  flex: 1;
  max-width: 320px;
}

.list-head {
  margin-top: 6px;
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
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 16px;
}
.card {
  cursor: pointer;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  transition: transform 0.14s, border-color 0.16s, box-shadow 0.16s;
}
.card:hover {
  transform: translateY(-3px);
  border-color: var(--line-bright);
  box-shadow: var(--shadow-md);
}
.thumb {
  aspect-ratio: 3 / 4;
  background: var(--surface-3);
  display: grid;
  place-items: center;
  overflow: hidden;
}
.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.ph {
  font-family: var(--font-display);
  font-size: 2.2rem;
  color: var(--ink-faint);
}
.meta {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.name {
  font-weight: 600;
  font-size: 0.92rem;
  color: var(--ink);
}
.date {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--ink-dim);
}

.empty {
  padding: 40px;
  text-align: center;
  color: var(--ink-faint);
  background: var(--surface);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
}
.page-info {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--ink-soft);
}

/* 상세 모달 */
.overlay {
  position: fixed;
  inset: 0;
  z-index: 350;
  display: grid;
  place-items: center;
  padding: 28px;
  background: rgba(4, 5, 8, 0.78);
  backdrop-filter: blur(2px);
}
.sheet {
  width: 100%;
  max-width: 440px;
  max-height: 86vh;
  overflow-y: auto;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
}
.sheet-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
.sheet-id {
  display: flex;
  gap: 13px;
  align-items: center;
}
.sheet-thumb {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  overflow: hidden;
  background: var(--surface-3);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}
.sheet-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.sheet-thumb .ph {
  font-size: 1.5rem;
}
.sheet-name {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.3rem;
  color: var(--ink);
}
.sheet-sub {
  margin: 3px 0 0;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--ink-faint);
}
.close {
  width: 30px;
  height: 30px;
  color: var(--ink-soft);
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 50%;
  cursor: pointer;
}
.close:hover {
  background: var(--surface-2);
}
.faces {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
  gap: 9px;
}
.face {
  aspect-ratio: 1;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: 9px;
  overflow: hidden;
  background: var(--surface-3);
  cursor: zoom-in;
}
.face img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.works-section {
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.block-label {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-faint);
}
.block-label .count {
  color: var(--gold);
}
.work-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.work-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  cursor: pointer;
  text-align: left;
}
.work-item:hover {
  border-color: var(--gold);
}
.work-poster {
  flex: 0 0 30px;
  width: 30px;
  height: 44px;
  border-radius: 4px;
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
.work-title {
  font-weight: 600;
  font-size: 0.86rem;
  color: var(--ink);
}
.work-pick-list {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.work-pick {
  padding: 6px 13px;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--ink-soft);
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  cursor: pointer;
}
.work-pick.on {
  color: var(--gold);
  border-color: var(--gold);
  background: var(--gold-soft);
}
.sheet-foot {
  display: flex;
  justify-content: flex-end;
}
</style>
