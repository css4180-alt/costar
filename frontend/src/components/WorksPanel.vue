<template>
  <section class="panel">
    <div class="head">
      <div>
        <p class="eyebrow">Works</p>
        <h2 class="title">작품 등록</h2>
        <p class="desc">작품을 만들고 스틸을 올리면 얼굴을 분석해 출연 인물을 자동 색인합니다.</p>
      </div>
      <button class="btn btn-import" @click="openImport">＋ TMDB에서 임포트</button>
    </div>

    <div class="register">
      <input v-model="title" class="field" placeholder="작품 제목 (예: 기생충)" :disabled="busy" />
      <input
        v-model="year"
        class="field year"
        type="number"
        placeholder="개봉연도"
        :disabled="busy"
      />
      <button class="btn" :disabled="busy || !title.trim()" @click="onCreate">작품 추가</button>
    </div>

    <div class="list-head">
      <h3 class="sub">등록된 작품 <span class="count">{{ store.works.length }}</span></h3>
    </div>

    <div v-if="store.works.length" class="grid">
      <article v-for="w in store.works" :key="w.id" class="card" @click="openDetail(w)">
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
    <p v-else class="empty">아직 등록된 작품이 없습니다. 위에서 첫 작품을 추가해 보세요.</p>

    <!-- 상세 모달 -->
    <transition name="fade">
      <div v-if="detail" class="overlay" @click="closeDetail">
        <div class="sheet" @click.stop>
          <header class="sheet-head">
            <div>
              <h3 class="sheet-name">{{ detail.title }}</h3>
              <p class="sheet-sub">{{ detail.year || '연도 미상' }} · 스틸 {{ detail.stills?.length || 0 }}장</p>
            </div>
            <button class="close" @click="closeDetail">✕</button>
          </header>

          <!-- 출연 인물 -->
          <div>
            <p class="block-label">출연 인물</p>
            <div v-if="detail.appearances?.length" class="appears">
              <span v-for="a in detail.appearances" :key="a.person_id" class="chip appear">
                {{ a.name || '미상' }}
                <em class="sim">{{ Math.round(a.confidence) }}%</em>
              </span>
            </div>
            <p v-else class="none">아직 매칭된 인물이 없습니다. 스틸을 올려 보세요.</p>
          </div>

          <!-- 스틸 -->
          <div v-if="detail.stills?.length">
            <p class="block-label">스틸</p>
            <div class="stills">
              <button
                v-for="s in detail.stills"
                :key="s.still_id"
                class="still"
                @click="store.openPreview(s.image_url, detail.title)"
              >
                <img v-if="s.image_url" :src="s.image_url" :alt="detail.title" />
              </button>
            </div>
          </div>

          <DropZone
            multiple
            :busy="stillBusy"
            label="스틸 업로드 (여러 장 가능)"
            @files="onUploadStills"
          />

          <footer class="sheet-foot">
            <button class="btn btn-danger" :disabled="stillBusy" @click="onDelete">작품 삭제</button>
          </footer>
        </div>
      </div>
    </transition>

    <!-- TMDB 임포트 모달 -->
    <transition name="fade">
      <div v-if="importOpen" class="overlay" @click="closeImport">
        <div class="sheet" @click.stop>
          <header class="sheet-head">
            <div>
              <h3 class="sheet-name">TMDB에서 임포트</h3>
              <p class="sheet-sub">영화를 고르면 작품과 출연진 얼굴이 자동 등록됩니다</p>
            </div>
            <button class="close" @click="closeImport">✕</button>
          </header>

          <!-- 진행 중이 아니면 검색 UI -->
          <template v-if="!importJob">
            <form class="imp-search" @submit.prevent="runSearch">
              <input
                v-model="importQuery"
                class="field"
                placeholder="영화 제목 검색 (예: 공동경비구역)"
                :disabled="searching"
                autofocus
              />
              <button class="btn" :disabled="searching || !importQuery.trim()" type="submit">
                {{ searching ? '검색 중…' : '검색' }}
              </button>
            </form>

            <div v-if="results.length" class="imp-results">
              <button
                v-for="m in results"
                :key="m.tmdb_id"
                class="imp-item"
                :disabled="starting"
                @click="onPick(m)"
              >
                <div class="imp-poster">
                  <img v-if="m.poster_url" :src="m.poster_url" :alt="m.title" />
                  <span v-else class="ph">🎬</span>
                </div>
                <div class="imp-meta">
                  <span class="imp-title">{{ m.title }}</span>
                  <span class="imp-year">{{ m.year || '연도 미상' }}</span>
                </div>
              </button>
            </div>
            <p v-else-if="searched && !searching" class="none">검색 결과가 없습니다.</p>
          </template>

          <!-- 진행 중/완료 상태 -->
          <div v-else class="imp-progress">
            <p class="imp-job-title">{{ importJob.title }}</p>
            <div class="bar">
              <span class="bar-fill" :style="{ width: progressPct + '%' }"></span>
            </div>
            <p class="imp-stat">
              <span v-if="importJob.status !== 'done' && importJob.status !== 'error'">
                출연진 등록 중… {{ importJob.done }}<span v-if="importJob.total">/{{ importJob.total }}</span>
                <span v-if="importJob.skipped"> · 건너뜀 {{ importJob.skipped }}</span>
              </span>
              <span v-else-if="importJob.status === 'done'">
                ✓ {{ importJob.message || `등록 ${importJob.done}명` }}
              </span>
              <span v-else class="err">오류: {{ importJob.message }}</span>
            </p>
            <button
              v-if="importJob.status === 'done' || importJob.status === 'error'"
              class="btn"
              @click="closeImport"
            >
              닫기
            </button>
          </div>
        </div>
      </div>
    </transition>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { store } from '../store.js'
import DropZone from './DropZone.vue'

const title = ref('')
const year = ref('')
const busy = ref(false)
const detail = ref(null)
const stillBusy = ref(false)

// ---- TMDB 임포트 ----
const importOpen = ref(false)
const importQuery = ref('')
const searching = ref(false)
const searched = ref(false)
const results = ref([])
const starting = ref(false)
const importJob = ref(null)
let pollTimer = null

const progressPct = computed(() => {
  const j = importJob.value
  if (!j) return 0
  if (j.status === 'done') return 100
  if (!j.total) return 8
  return Math.min(100, Math.round(((j.done + j.skipped) / j.total) * 100))
})

function openImport() {
  importOpen.value = true
  importQuery.value = ''
  results.value = []
  searched.value = false
  importJob.value = null
}

function closeImport() {
  importOpen.value = false
  clearTimeout(pollTimer)
  pollTimer = null
  importJob.value = null
}

async function runSearch() {
  const q = importQuery.value.trim()
  if (!q) return
  searching.value = true
  try {
    results.value = await store.searchTmdb(q)
    searched.value = true
  } catch (err) {
    store.notify(err.message, 'error')
  } finally {
    searching.value = false
  }
}

async function onPick(movie) {
  starting.value = true
  try {
    importJob.value = await store.startImport(movie.tmdb_id)
    pollJob()
  } catch (err) {
    store.notify(err.message, 'error')
  } finally {
    starting.value = false
  }
}

async function pollJob() {
  const j = importJob.value
  if (!j) return
  if (j.status === 'done' || j.status === 'error') {
    await store.refreshAfterImport()
    if (j.status === 'done') store.notify(j.message || '임포트 완료', 'ok')
    return
  }
  pollTimer = setTimeout(async () => {
    try {
      importJob.value = await store.pollImport(j.job_id)
      pollJob()
    } catch (err) {
      store.notify(err.message, 'error')
    }
  }, 2000)
}

async function onCreate() {
  const t = title.value.trim()
  if (!t) return
  busy.value = true
  try {
    await store.addWork(t, year.value || null)
    title.value = ''
    year.value = ''
    store.notify(`'${t}' 작품을 추가했습니다.`, 'ok')
  } catch (err) {
    store.notify(err.message, 'error')
  } finally {
    busy.value = false
  }
}

async function openDetail(w) {
  try {
    detail.value = await store.getWorkDetail(w.id)
  } catch (err) {
    store.notify(err.message, 'error')
  }
}
function closeDetail() {
  detail.value = null
}

async function onUploadStills(files) {
  stillBusy.value = true
  try {
    const res = await store.uploadStills(detail.value.id, files)
    detail.value = await store.getWorkDetail(detail.value.id)
    const matched = res.stills.reduce((n, s) => n + (s.matched_person_ids?.length || 0), 0)
    const faces = res.stills.reduce((n, s) => n + (s.faces_detected || 0), 0)
    store.notify(`스틸 ${files.length}장 · 얼굴 ${faces}개 검출 · 매칭 ${matched}건`, 'ok')
  } catch (err) {
    store.notify(err.message, 'error')
  } finally {
    stillBusy.value = false
  }
}

async function onDelete() {
  if (!confirm(`'${detail.value.title}'을(를) 삭제할까요? 스틸과 출연 정보도 함께 삭제됩니다.`)) return
  stillBusy.value = true
  try {
    await store.removeWork(detail.value.id)
    store.notify('삭제되었습니다.', 'ok')
    closeDetail()
  } catch (err) {
    store.notify(err.message, 'error')
  } finally {
    stillBusy.value = false
  }
}
</script>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.btn-import {
  flex: 0 0 auto;
  white-space: nowrap;
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

.register {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.register .field {
  flex: 1;
  min-width: 180px;
}
.register .year {
  flex: 0 0 130px;
  min-width: 110px;
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
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
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
.ph {
  font-size: 1.8rem;
  opacity: 0.5;
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

.empty {
  padding: 40px;
  text-align: center;
  color: var(--ink-faint);
  background: var(--surface);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}

/* 모달 */
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
  max-width: 520px;
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
.sheet-name {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.4rem;
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
.block-label {
  margin: 0 0 9px;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-faint);
}
.appears {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.appear {
  color: var(--ink);
  border-color: var(--line-strong);
}
.sim {
  font-family: var(--font-mono);
  font-size: 0.66rem;
  font-style: normal;
  color: var(--gold);
}
.none {
  margin: 0;
  font-size: 0.84rem;
  color: var(--ink-dim);
}
.stills {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 9px;
}
.still {
  aspect-ratio: 16 / 10;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: 9px;
  overflow: hidden;
  background: var(--surface-3);
  cursor: zoom-in;
}
.still img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.sheet-foot {
  display: flex;
  justify-content: flex-end;
}

/* TMDB 임포트 */
.imp-search {
  display: flex;
  gap: 10px;
}
.imp-search .field {
  flex: 1;
}
.imp-results {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
  max-height: 52vh;
  overflow-y: auto;
}
.imp-item {
  padding: 0;
  text-align: left;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.14s, border-color 0.16s;
}
.imp-item:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: var(--gold);
}
.imp-item:disabled {
  opacity: 0.5;
  cursor: default;
}
.imp-poster {
  aspect-ratio: 2 / 3;
  background: var(--surface-3);
  display: grid;
  place-items: center;
  overflow: hidden;
}
.imp-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.imp-meta {
  padding: 9px 11px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.imp-title {
  font-weight: 600;
  font-size: 0.86rem;
  color: var(--ink);
}
.imp-year {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--ink-dim);
}
.imp-progress {
  display: flex;
  flex-direction: column;
  gap: 14px;
  align-items: flex-start;
}
.imp-job-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.1rem;
  color: var(--ink);
}
.bar {
  width: 100%;
  height: 8px;
  background: var(--surface-3);
  border-radius: 99px;
  overflow: hidden;
}
.bar-fill {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--red), var(--gold));
  transition: width 0.4s ease;
}
.imp-stat {
  margin: 0;
  font-size: 0.88rem;
  color: var(--ink-soft);
}
.imp-stat .err {
  color: var(--red);
}
</style>
