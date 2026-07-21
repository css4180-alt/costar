<template>
  <section class="panel">
    <!-- ─────────── 목록 뷰 (상세 로딩 중에도 그대로 유지, 전역 오버레이가 덮음) ─────────── -->
    <template v-if="!detail">
      <div class="head">
        <div>
          <p class="eyebrow">Works</p>
          <h2 class="title">작품 관리</h2>
        </div>
        <div class="head-actions">
          <button class="btn btn-ghost" @click="openImport">＋ TMDB 임포트</button>
          <button class="btn" @click="openCreate">＋ 작품 등록</button>
        </div>
      </div>

      <input v-model="search" class="field search" placeholder="작품 제목 검색" />

      <div class="filter-row">
        <div class="seg">
          <button
            v-for="t in typeOptions"
            :key="t.id"
            class="seg-btn"
            :class="{ on: typeFilter === t.id }"
            @click="typeFilter = t.id"
          >
            {{ t.label }}
          </button>
        </div>
        <div class="chips">
          <button
            v-for="s in statusOptions"
            :key="s.id"
            class="fchip"
            :class="[{ on: statusFilter === s.id }, s.id]"
            @click="statusFilter = s.id"
          >
            {{ s.label }}
          </button>
        </div>
      </div>

      <div v-if="filteredWorks.length" class="grid">
        <article v-for="w in filteredWorks" :key="w.id" class="card" @click="openDetail(w)">
          <div class="poster">
            <img v-if="w.rep_url" :src="w.rep_url" :alt="w.title" />
            <span v-else class="ph">🎬</span>
            <span v-if="w.media_type" class="type-badge">{{ typeLabel(w.media_type) }}</span>
          </div>
          <div class="meta">
            <span class="name">{{ w.title }}</span>
            <span class="year">{{ w.year || '연도 미상' }}</span>
            <span class="status" :class="statusClass(w)">{{ statusLabel(w) }}</span>
          </div>
        </article>
      </div>
      <p v-else class="empty">조건에 맞는 작품이 없습니다. 위에서 작품을 등록하거나 TMDB에서 임포트하세요.</p>
    </template>

    <!-- ─────────── 상세 뷰 ─────────── -->
    <template v-else>
      <button class="btn btn-ghost back" @click="closeDetail">‹ 목록으로</button>

      <div class="detail-top">
        <div class="detail-poster">
          <img v-if="detail.rep_url" :src="detail.rep_url" :alt="detail.title" />
          <span v-else class="ph">🎬</span>
        </div>
        <div class="detail-info">
          <h2 class="detail-title">
            {{ detail.title }}
            <span v-if="detail.media_type" class="type-badge inline">{{ typeLabel(detail.media_type) }}</span>
          </h2>
          <p class="detail-sub">{{ detail.release_date || detail.year || '개봉일 미상' }}</p>
          <div class="detail-meta">
            <span>TMDB ID: <strong>{{ detail.tmdb_id || '—' }}</strong></span>
            <span class="dot">·</span>
            <span>동기화: <em :class="statusClass(detail)">{{ statusLabel(detail) }}</em></span>
            <span class="dot">·</span>
            <span>등록일: <strong>{{ fmtDate(detail.created_at) }}</strong></span>
          </div>
        </div>
      </div>

      <div v-if="detail.overview" class="section">
        <h3 class="block-label">작품 개요</h3>
        <p class="overview">{{ detail.overview }}</p>
      </div>

      <div class="section">
        <div class="section-head">
          <h3 class="block-label">출연진 관리 <span class="count">{{ detail.appearances.length }}</span></h3>
          <div class="section-actions">
            <button
              v-if="detail.tmdb_id"
              class="btn btn-ghost sm"
              :disabled="resyncing"
              @click="onResync"
            >
              ↻ TMDB 동기화
            </button>
            <button class="btn sm" :disabled="resyncing" @click="openAddCast">＋ 출연진 추가</button>
          </div>
        </div>

        <div v-if="resyncing" class="resync">
          동기화 중… 출연진 {{ resyncJob?.done || 0 }}<span v-if="resyncJob?.total">/{{ resyncJob.total }}</span>
        </div>

        <div v-if="detail.appearances.length" class="cast-grid">
          <div v-for="a in detail.appearances" :key="a.person_id" class="cast-card">
            <div class="cast-thumb">
              <img v-if="a.rep_url" :src="a.rep_url" :alt="a.name" />
              <span v-else class="ph">{{ initial(a.name) }}</span>
            </div>
            <div class="cast-info">
              <span class="cast-name">{{ a.name || '미상' }}</span>
              <span v-if="a.character" class="cast-role">{{ a.character }}</span>
            </div>
            <button class="cast-remove" :disabled="resyncing" @click="onRemoveCast(a)">제거</button>
          </div>
        </div>
        <p v-else class="none">아직 출연진이 없습니다. TMDB 동기화하거나 직접 추가하세요.</p>
      </div>

      <div class="section">
        <h3 class="block-label">스틸 <span class="count">{{ detail.stills?.length || 0 }}</span></h3>
        <div v-if="detail.stills?.length" class="stills">
          <button
            v-for="s in detail.stills"
            :key="s.still_id"
            class="still"
            @click="store.openPreview(s.image_url, detail.title)"
          >
            <img v-if="s.image_url" :src="s.image_url" :alt="detail.title" />
          </button>
        </div>
        <DropZone multiple :busy="stillBusy" label="스틸 업로드 (여러 장 가능)" @files="onUploadStills" />
      </div>

      <div class="detail-foot">
        <button class="btn btn-danger" :disabled="stillBusy || resyncing" @click="onDelete">작품 삭제</button>
      </div>
    </template>

    <!-- ─────────── 작품 등록 모달 ─────────── -->
    <transition name="fade">
      <div v-if="createOpen" class="overlay" @click="closeCreate">
        <div class="sheet sm" @click.stop>
          <header class="sheet-head">
            <h3 class="sheet-name">작품 등록</h3>
            <button class="close" @click="closeCreate">✕</button>
          </header>
          <div class="create-row">
            <label class="poster-pick" :class="{ has: posterPreview }">
              <input type="file" accept="image/jpeg,image/png" hidden :disabled="busy" @change="onPosterPick" />
              <img v-if="posterPreview" :src="posterPreview" alt="포스터" />
              <span v-else class="poster-ph">＋<br />포스터</span>
            </label>
            <div class="create-fields">
              <input v-model="title" class="field" placeholder="작품 제목 (예: 기생충)" :disabled="busy" />
              <input v-model="year" class="field" type="number" placeholder="개봉연도" :disabled="busy" />
            </div>
          </div>
          <footer class="sheet-foot">
            <button class="btn" :disabled="busy || !title.trim()" @click="onCreate">추가</button>
          </footer>
        </div>
      </div>
    </transition>

    <!-- ─────────── TMDB 임포트 모달 ─────────── -->
    <transition name="fade">
      <div v-if="importOpen" class="overlay" @click="closeImport">
        <div class="sheet" @click.stop>
          <header class="sheet-head">
            <div>
              <h3 class="sheet-name">TMDB에서 임포트</h3>
              <p class="sheet-sub">영화/TV를 고르면 작품과 출연진 얼굴이 자동 등록됩니다</p>
            </div>
            <button class="close" @click="closeImport">✕</button>
          </header>

          <template v-if="!importJob">
            <div class="seg">
              <button class="seg-btn" :class="{ on: mediaType === 'movie' }" @click="setMediaType('movie')">Movie</button>
              <button class="seg-btn" :class="{ on: mediaType === 'tv' }" @click="setMediaType('tv')">TV</button>
            </div>
            <form class="imp-search" @submit.prevent="runSearch">
              <input
                v-model="importQuery"
                class="field"
                :placeholder="mediaType === 'tv' ? 'TV 제목 검색' : '영화 제목 검색'"
                :disabled="searching"
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

          <div v-else class="imp-progress">
            <p class="imp-job-title">{{ importJob.title }}</p>
            <div class="bar"><span class="bar-fill" :style="{ width: progressPct + '%' }"></span></div>
            <p class="imp-stat">
              <span v-if="importJob.status !== 'done' && importJob.status !== 'error'">
                출연진 등록 중… {{ importJob.done }}<span v-if="importJob.total">/{{ importJob.total }}</span>
                <span v-if="importJob.skipped"> · 건너뜀 {{ importJob.skipped }}</span>
              </span>
              <span v-else-if="importJob.status === 'done'">✓ {{ importJob.message || `등록 ${importJob.done}명` }}</span>
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

    <!-- ─────────── 출연진 추가 모달 ─────────── -->
    <transition name="fade">
      <div v-if="addCastOpen" class="overlay" @click="closeAddCast">
        <div class="sheet" @click.stop>
          <header class="sheet-head">
            <h3 class="sheet-name">출연진 추가</h3>
            <button class="close" @click="closeAddCast">✕</button>
          </header>
          <p class="sheet-sub">등록된 인물 중 이 작품 출연진으로 추가할 사람을 고르세요.</p>
          <div v-if="addablepersons.length" class="pick-grid">
            <button
              v-for="p in addablepersons"
              :key="p.id"
              class="pick"
              :disabled="addingCast"
              @click="onAddCast(p)"
            >
              <span class="pick-thumb">
                <img v-if="p.rep_url" :src="p.rep_url" :alt="p.name" />
                <span v-else class="ph">{{ initial(p.name) }}</span>
              </span>
              <span class="pick-name">{{ p.name }}</span>
            </button>
          </div>
          <p v-else class="none">추가할 수 있는 인물이 없습니다. People 탭에서 먼저 등록하세요.</p>
        </div>
      </div>
    </transition>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { store } from '../store.js'
import DropZone from './DropZone.vue'

// ── 목록 필터 ──
const search = ref('')
const typeFilter = ref('all')
const statusFilter = ref('all')
const typeOptions = [
  { id: 'all', label: '전체 유형' },
  { id: 'movie', label: 'Movie' },
  { id: 'tv', label: 'TV' },
]
const statusOptions = [
  { id: 'all', label: '전체 상태' },
  { id: 'done', label: '동기화 완료' },
  { id: 'running', label: '동기화 중' },
  { id: 'none', label: '미동기화' },
  { id: 'error', label: '동기화 실패' },
]

function workStatus(w) {
  const s = w.import_status
  if (s === 'done') return 'done'
  if (s === 'running' || s === 'pending') return 'running'
  if (s === 'error') return 'error'
  return 'none'
}
function statusLabel(w) {
  return { done: '동기화 완료', running: '동기화 중', error: '동기화 실패', none: '미동기화' }[workStatus(w)]
}
function statusClass(w) {
  return 's-' + workStatus(w)
}
function typeLabel(t) {
  return t === 'tv' ? 'TV' : 'Movie'
}

const filteredWorks = computed(() => {
  const q = search.value.trim().toLowerCase()
  return store.works.filter((w) => {
    if (typeFilter.value !== 'all' && (w.media_type || '') !== typeFilter.value) return false
    if (statusFilter.value !== 'all' && workStatus(w) !== statusFilter.value) return false
    if (q && !(w.title || '').toLowerCase().includes(q)) return false
    return true
  })
})

function initial(n) {
  return (n || '?').trim().charAt(0).toUpperCase()
}
function fmtDate(s) {
  return s ? String(s).slice(0, 10) : '—'
}

// ── 상세 (store.workId로 구동 → URL 동기화) ──
const detail = ref(null)
const stillBusy = ref(false)

function openDetail(w) {
  store.openWork(w.id) // URL 즉시 변경 + 아래 watch가 로딩 처리
}
function closeDetail() {
  store.closeWork()
}
async function reloadDetail() {
  if (detail.value) detail.value = await store.getWorkDetail(detail.value.id)
}

// workId가 바뀌면(클릭·뒤로가기·딥링크) 상세를 로드한다.
// 로딩 인디케이터는 전역 오버레이(store.getWorkDetail이 withOverlay로 감쌈)가 담당하며,
// 그동안 기존 목록 화면은 그대로 유지된다(detail이 null이라 목록이 보임).
watch(
  () => store.workId,
  async (id) => {
    if (!id) {
      detail.value = null
      return
    }
    if (detail.value && detail.value.id === id) return
    try {
      detail.value = await store.getWorkDetail(id)
    } catch (err) {
      store.notify(err.message, 'error')
      store.closeWork()
    }
  },
  { immediate: true },
)

async function onUploadStills(files) {
  stillBusy.value = true
  try {
    const res = await store.uploadStills(detail.value.id, files)
    await reloadDetail()
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
  if (!confirm(`'${detail.value.title}'을(를) 삭제할까요? 스틸·출연 정보도 함께 삭제됩니다.`)) return
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

// ── 출연진 관리 ──
async function onRemoveCast(a) {
  try {
    await store.removeCast(detail.value.id, a.person_id)
    await reloadDetail()
  } catch (err) {
    store.notify(err.message, 'error')
  }
}

const addCastOpen = ref(false)
const addingCast = ref(false)
const addablepersons = computed(() => {
  const inCast = new Set((detail.value?.appearances || []).map((a) => a.person_id))
  return store.persons.filter((p) => !inCast.has(p.id))
})
function openAddCast() {
  addCastOpen.value = true
}
function closeAddCast() {
  addCastOpen.value = false
}
async function onAddCast(p) {
  addingCast.value = true
  try {
    await store.addCast(detail.value.id, p.id)
    await reloadDetail()
    store.notify(`'${p.name}'을(를) 출연진에 추가했습니다.`, 'ok')
    if (!addablepersons.value.length) closeAddCast()
  } catch (err) {
    store.notify(err.message, 'error')
  } finally {
    addingCast.value = false
  }
}

// ── TMDB 재동기화 ──
const resyncing = ref(false)
const resyncJob = ref(null)
let resyncTimer = null
async function onResync() {
  resyncing.value = true
  resyncJob.value = null
  try {
    resyncJob.value = await store.resyncWork(detail.value.id)
    pollResync()
  } catch (err) {
    resyncing.value = false
    store.notify(err.message, 'error')
  }
}
async function pollResync() {
  const j = resyncJob.value
  if (!j) return
  if (j.status === 'done' || j.status === 'error') {
    resyncing.value = false
    await Promise.all([reloadDetail(), store.loadWorks(), store.loadPersons(), store.refreshQuota()])
    store.notify(j.status === 'done' ? j.message || '동기화 완료' : `오류: ${j.message}`, j.status === 'done' ? 'ok' : 'error')
    return
  }
  resyncTimer = setTimeout(async () => {
    try {
      resyncJob.value = await store.pollImport(j.job_id)
      pollResync()
    } catch (err) {
      resyncing.value = false
      store.notify(err.message, 'error')
    }
  }, 2000)
}

// ── 작품 등록(수동) ──
const createOpen = ref(false)
const title = ref('')
const year = ref('')
const busy = ref(false)
const posterFile = ref(null)
const posterPreview = ref(null)

function openCreate() {
  createOpen.value = true
}
function closeCreate() {
  createOpen.value = false
}
function onPosterPick(e) {
  const f = e.target.files?.[0]
  if (!f) return
  if (posterPreview.value) URL.revokeObjectURL(posterPreview.value)
  posterFile.value = f
  posterPreview.value = URL.createObjectURL(f)
}
function clearPoster() {
  if (posterPreview.value) URL.revokeObjectURL(posterPreview.value)
  posterFile.value = null
  posterPreview.value = null
}
async function onCreate() {
  const t = title.value.trim()
  if (!t) return
  busy.value = true
  try {
    await store.addWork(t, year.value || null, posterFile.value)
    title.value = ''
    year.value = ''
    clearPoster()
    store.notify(`'${t}' 작품을 추가했습니다.`, 'ok')
    closeCreate()
  } catch (err) {
    store.notify(err.message, 'error')
  } finally {
    busy.value = false
  }
}

// ── TMDB 임포트 ──
const importOpen = ref(false)
const mediaType = ref('movie')
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
function setMediaType(t) {
  mediaType.value = t
  results.value = []
  searched.value = false
}
async function runSearch() {
  const q = importQuery.value.trim()
  if (!q) return
  searching.value = true
  try {
    results.value = await store.searchTmdb(q, mediaType.value)
    searched.value = true
  } catch (err) {
    store.notify(err.message, 'error')
  } finally {
    searching.value = false
  }
}
async function onPick(item) {
  starting.value = true
  try {
    importJob.value = await store.startImport(item.media_type || mediaType.value, item.tmdb_id)
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
    await Promise.all([store.loadWorks(), store.loadPersons(), store.refreshQuota()])
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
</script>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
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
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.head-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}
.search {
  max-width: 360px;
}

/* 필터 */
.filter-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.seg {
  display: inline-flex;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  padding: 3px;
  gap: 2px;
}
.seg-btn {
  padding: 6px 16px;
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--ink-soft);
  background: transparent;
  border: none;
  border-radius: 7px;
  cursor: pointer;
}
.seg-btn.on {
  color: var(--gold);
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}
.chips {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}
.fchip {
  padding: 6px 13px;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--ink-soft);
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  cursor: pointer;
}
.fchip.on {
  color: var(--gold);
  border-color: var(--gold);
  background: var(--gold-soft);
}
.fchip.error.on {
  color: var(--danger);
  border-color: var(--danger);
  background: #fdeeec;
}

/* 그리드 */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 18px;
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
  position: relative;
  aspect-ratio: 2 / 3;
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
  font-size: 1.6rem;
  opacity: 0.5;
  font-family: var(--font-display);
  color: var(--ink-faint);
}
.type-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  padding: 2px 8px;
  font-family: var(--font-mono);
  font-size: 0.64rem;
  font-weight: 700;
  color: #fff;
  background: rgba(31, 36, 48, 0.78);
  border-radius: 5px;
}
.type-badge.inline {
  position: static;
  background: var(--gold-soft);
  color: var(--gold);
}
.meta {
  padding: 11px 13px;
  display: flex;
  flex-direction: column;
  gap: 4px;
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
.status {
  align-self: flex-start;
  margin-top: 2px;
  padding: 2px 8px;
  font-size: 0.68rem;
  font-weight: 600;
  border-radius: 5px;
}
.status.s-done {
  color: var(--ok);
  background: #e8f6ee;
}
.status.s-running {
  color: var(--red-strong);
  background: #fdeee4;
}
.status.s-error {
  color: var(--danger);
  background: #fdeeec;
}
.status.s-none {
  color: var(--ink-faint);
  background: var(--surface-2);
}

.empty,
.none {
  padding: 32px;
  text-align: center;
  color: var(--ink-faint);
  background: var(--surface);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}
.none {
  padding: 20px;
  font-size: 0.86rem;
}

/* 상세 */
.back {
  align-self: flex-start;
}
.detail-top {
  display: flex;
  gap: 22px;
}
.detail-poster {
  flex: 0 0 130px;
  width: 130px;
  aspect-ratio: 2 / 3;
  background: var(--surface-3);
  border-radius: var(--radius);
  overflow: hidden;
  display: grid;
  place-items: center;
}
.detail-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.detail-info {
  flex: 1;
  min-width: 0;
}
.detail-title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-display);
  font-size: 1.7rem;
  color: var(--ink);
}
.detail-sub {
  margin: 6px 0 0;
  font-size: 0.9rem;
  color: var(--ink-soft);
}
.detail-meta {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
  color: var(--ink-soft);
}
.detail-meta strong {
  color: var(--ink);
  font-weight: 600;
}
.detail-meta em {
  font-style: normal;
  font-weight: 600;
}
.detail-meta em.s-done {
  color: var(--ok);
}
.detail-meta em.s-running {
  color: var(--red-strong);
}
.detail-meta em.s-error {
  color: var(--danger);
}
.detail-meta em.s-none {
  color: var(--ink-faint);
}
.detail-meta .dot {
  color: var(--line-bright);
}

.section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.section-actions {
  display: flex;
  gap: 8px;
}
.btn.sm,
.btn-ghost.sm {
  padding: 7px 12px;
  font-size: 0.8rem;
}
.block-label {
  margin: 0;
  font-size: 1.05rem;
  color: var(--ink);
}
.count {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--gold);
  margin-left: 4px;
}
.overview {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.7;
  color: var(--ink-soft);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 18px;
}
.resync {
  font-size: 0.84rem;
  color: var(--red-strong);
  background: #fdeee4;
  border-radius: var(--radius-sm);
  padding: 9px 14px;
}

.cast-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.cast-card {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 10px 12px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.cast-thumb {
  flex: 0 0 40px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--surface-3);
  display: grid;
  place-items: center;
}
.cast-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.cast-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.cast-name {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cast-role {
  font-size: 0.72rem;
  color: var(--ink-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cast-remove {
  flex-shrink: 0;
  padding: 5px 11px;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--danger);
  background: #fff;
  border: 1px solid #f1c4c0;
  border-radius: 999px;
  cursor: pointer;
}
.cast-remove:hover:not(:disabled) {
  background: #fdeeec;
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
.detail-foot {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--line);
  padding-top: 16px;
}

/* 모달 */
.overlay {
  position: fixed;
  inset: 0;
  z-index: 350;
  display: grid;
  place-items: center;
  padding: 28px;
  background: rgba(20, 24, 33, 0.55);
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
  gap: 16px;
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
}
.sheet.sm {
  max-width: 440px;
}
.sheet-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
.sheet-name {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.3rem;
  color: var(--ink);
}
.sheet-sub {
  margin: 2px 0 0;
  font-size: 0.82rem;
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
.sheet-foot {
  display: flex;
  justify-content: flex-end;
}

/* 작품 등록 모달 */
.create-row {
  display: flex;
  gap: 14px;
}
.create-fields {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.poster-pick {
  flex: 0 0 92px;
  width: 92px;
  aspect-ratio: 2 / 3;
  display: grid;
  place-items: center;
  overflow: hidden;
  background: var(--surface-2);
  border: 1.5px dashed var(--line-bright);
  border-radius: var(--radius);
  cursor: pointer;
}
.poster-pick.has {
  border-style: solid;
}
.poster-pick img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.poster-ph {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  line-height: 1.5;
  text-align: center;
  color: var(--ink-faint);
}

/* 임포트 모달 */
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
}
.imp-item:hover:not(:disabled) {
  border-color: var(--gold);
}
.imp-item:disabled {
  opacity: 0.5;
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
  background: linear-gradient(90deg, var(--gold), var(--red-strong));
  transition: width 0.4s ease;
}
.imp-stat {
  margin: 0;
  font-size: 0.88rem;
  color: var(--ink-soft);
}
.imp-stat .err {
  color: var(--danger);
}

/* 출연진 추가 모달 */
.pick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 12px;
  max-height: 56vh;
  overflow-y: auto;
}
.pick {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 14px 8px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  cursor: pointer;
}
.pick:hover:not(:disabled) {
  border-color: var(--gold);
}
.pick-thumb {
  width: 52px;
  height: 52px;
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
.pick-name {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--ink);
  text-align: center;
}
</style>
