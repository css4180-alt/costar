<template>
  <section class="panel">
    <div class="head">
      <div>
        <p class="eyebrow">Works</p>
        <h2 class="title">작품 등록</h2>
        <p class="desc">작품을 만들고 스틸을 올리면 얼굴을 분석해 출연 인물을 자동 색인합니다.</p>
      </div>
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
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { store } from '../store.js'
import DropZone from './DropZone.vue'

const title = ref('')
const year = ref('')
const busy = ref(false)
const detail = ref(null)
const stillBusy = ref(false)

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
</style>
