<template>
  <section class="panel">
    <!-- 등록 -->
    <div class="head">
      <div>
        <p class="eyebrow">People</p>
        <h2 class="title">인물 등록</h2>
        <p class="desc">이름과 대표 얼굴 사진을 등록하면 작품 스틸과 자동으로 매칭됩니다.</p>
      </div>
    </div>

    <div class="register">
      <input
        v-model="name"
        class="field name"
        placeholder="인물 이름 (예: 송강호)"
        :disabled="busy"
        @keyup.enter="focusDrop"
      />
      <DropZone
        class="reg-drop"
        :busy="busy"
        label="대표 사진을 드래그하거나 클릭"
        @files="onRegister"
      />
    </div>

    <!-- 목록 -->
    <div class="list-head">
      <h3 class="sub">등록된 인물 <span class="count">{{ store.persons.length }}</span></h3>
    </div>

    <div v-if="store.persons.length" class="grid">
      <article
        v-for="p in store.persons"
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
    <p v-else class="empty">아직 등록된 인물이 없습니다. 위에서 첫 인물을 등록해 보세요.</p>

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
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { store } from '../store.js'
import DropZone from './DropZone.vue'

const name = ref('')
const busy = ref(false)
const detail = ref(null)
const faceBusy = ref(false)

function initial(n) {
  return (n || '?').trim().charAt(0).toUpperCase()
}
function fmtDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('ko-KR', { year: '2-digit', month: 'short', day: 'numeric' })
}
function focusDrop() {}

async function onRegister([file]) {
  const nm = name.value.trim()
  if (!nm) {
    store.notify('이름을 먼저 입력해 주세요.', 'error')
    return
  }
  busy.value = true
  try {
    await store.addPerson(nm, file)
    name.value = ''
    store.notify(`'${nm}' 등록 완료`, 'ok')
  } catch (err) {
    store.notify(err.message, 'error')
  } finally {
    busy.value = false
  }
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
.desc {
  margin: 7px 0 0;
  font-size: 0.88rem;
  color: var(--ink-soft);
}

.register {
  display: grid;
  grid-template-columns: minmax(200px, 320px) 1fr;
  gap: 16px;
  align-items: stretch;
}
.name {
  align-self: start;
}
.reg-drop {
  grid-row: span 1;
}
@media (max-width: 640px) {
  .register {
    grid-template-columns: 1fr;
  }
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
.sheet-foot {
  display: flex;
  justify-content: flex-end;
}
</style>
