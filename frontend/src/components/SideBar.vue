<template>
  <aside class="sidebar">
    <div class="brand">
      <svg viewBox="0 0 40 24" width="32" height="20" aria-hidden="true">
        <circle cx="15" cy="12" r="8" fill="none" stroke="var(--gold)" stroke-width="2.4" />
        <circle cx="25" cy="12" r="8" fill="none" stroke="var(--red)" stroke-width="2.4" />
      </svg>
      <span class="brand-name">CoStar</span>
    </div>

    <!-- 상단: 핵심 기능 -->
    <nav class="nav">
      <button
        v-for="t in topTabs"
        :key="t.id"
        class="nav-item"
        :class="{ active: store.tab === t.id }"
        @click="store.setTab(t.id)"
      >
        <span class="nav-ic" v-html="t.icon" />
        <span class="nav-label">{{ t.label }}</span>
      </button>
    </nav>

    <!-- 하단: 관리 메뉴 -->
    <p class="nav-section">시스템 메뉴</p>
    <nav class="nav">
      <button
        v-for="t in systemTabs"
        :key="t.id"
        class="nav-item"
        :class="{ active: store.tab === t.id }"
        @click="store.setTab(t.id)"
      >
        <span class="nav-ic" v-html="t.icon" />
        <span class="nav-label">{{ t.label }}</span>
      </button>
    </nav>

    <div class="foot">
      <!-- 샘플 사진 내려받기: frontend/public/samples/ 에 넣어둔 고정 이미지 목록.
           작품 찾기(Match) 테스트용 — API 호출 없이 정적 파일만 링크. -->
      <div class="samples">
        <button class="samples-toggle" @click="samplesOpen = !samplesOpen">
          <span>샘플 사진 내려받기</span>
          <span class="chev">{{ samplesOpen ? '▾' : '▴' }}</span>
        </button>
        <div v-if="samplesOpen" class="samples-list">
          <a
            v-for="s in SAMPLE_PHOTOS"
            :key="s.file"
            class="sample-item"
            :href="`/samples/${s.file}`"
            :download="s.file"
          >
            <img :src="`/samples/${s.file}`" :alt="s.title" />
            <span class="sample-title">{{ s.title }}</span>
          </a>
        </div>
      </div>

      <div v-if="quota" class="quota" :title="quotaTitle">
        <div class="quota-row">
          <span class="quota-label">남은 사용량</span>
          <span class="quota-percent">{{ quotaPercent }}%</span>
        </div>
        <span class="quota-reset">{{ resetLabel }}</span>
        <div class="quota-bar">
          <span class="quota-bar-fill" :class="quotaLevel" :style="{ width: quotaPercent + '%' }" />
        </div>
      </div>
      <div v-if="store.account && store.account !== '__local__'" class="acct">{{ store.account }}</div>
      <button class="btn btn-ghost logout" @click="store.logout()">로그아웃</button>
    </div>
  </aside>
</template>

<script setup>
import { computed, ref } from 'vue'
import { store } from '../store.js'

// 샘플 사진: frontend/public/samples/ 에 실제 파일을 넣어두면 그대로 노출된다.
const SAMPLE_PHOTOS = [
  { file: 'sample-1.jpg', title: '기생충' },
  { file: 'sample-2.jpg', title: '밀정1' },
  { file: 'sample-3.jpg', title: '밀정2' },
  { file: 'sample-4.png', title: '공동경비구역JSA' },
  { file: 'sample-5.jpg', title: '놈놈놈' },
]

const topTabs = [
  {
    id: 'match',
    label: '작품 매칭',
    icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.2-3.2"/><path d="M8.5 11.5a2.5 2.5 0 0 0 5 0"/></svg>',
  },
]

const systemTabs = [
  {
    id: 'works',
    label: '작품 관리',
    icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 9h18M8 5v4M14 5v4M8 19v-4M14 19v-4"/></svg>',
  },
  {
    id: 'people',
    label: '인물 관리',
    icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.2"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0"/><path d="M16 6.2a3 3 0 0 1 0 5.6"/><path d="M17.5 19a5.5 5.5 0 0 0-2-4.3"/></svg>',
  },
]

const quota = computed(() => store.quota)

const quotaLevel = computed(() => {
  const q = store.quota
  if (!q || !q.account_limit) return 'ok'
  const ratio = q.account_remaining / q.account_limit
  if (ratio <= 0.1) return 'low'
  if (ratio <= 0.35) return 'mid'
  return 'ok'
})

const quotaTitle = computed(() => {
  const q = store.quota
  if (!q) return ''
  return `계정 잔여 ${q.account_remaining}/${q.account_limit} · 사이트 잔여 ${q.site_remaining}/${q.site_limit} (얼굴 분석/일)`
})

const quotaPercent = computed(() => {
  const q = store.quota
  if (!q || !q.account_limit) return 100
  return Math.round((q.account_remaining / q.account_limit) * 100)
})

// 표시용 초기화 시각은 KST(UTC+9) 자정 기준. 남은 시간을 시간 단위로 표시.
// ponytail: 렌더 시점 스냅샷(쿼터 갱신 시마다 재계산)이며 매 초 틱하지는 않는다.
const KST_OFFSET_MS = 9 * 3600000
const resetLabel = computed(() => {
  const nowKst = Date.now() + KST_OFFSET_MS
  const kstDate = new Date(nowKst)
  const nextMidnightKst = Date.UTC(
    kstDate.getUTCFullYear(),
    kstDate.getUTCMonth(),
    kstDate.getUTCDate() + 1,
  )
  const hours = Math.max(1, Math.ceil((nextMidnightKst - nowKst) / 3600000))
  return `${hours}시간 후 초기화`
})

const samplesOpen = ref(true)
</script>

<style scoped>
.sidebar {
  flex: 0 0 232px;
  width: 232px;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 22px 16px;
  background: var(--bg-soft);
  border-right: 1px solid var(--line);
}

.brand {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 4px 10px 0;
}
.brand-name {
  font-family: var(--font-display);
  font-size: 1.3rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--ink);
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.nav:first-of-type {
  margin-top: 26px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 10px 12px;
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--ink-soft);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: color 0.16s, background 0.16s;
}
.nav-item:hover {
  background: var(--surface-2);
  color: var(--ink);
}
.nav-item.active {
  color: var(--gold);
  background: var(--gold-soft);
}
.nav-ic {
  display: inline-flex;
  color: inherit;
}

.nav-section {
  margin: 24px 12px 8px;
  font-family: var(--font-mono);
  font-size: 0.66rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-faint);
}

.samples {
  width: 100%;
}
.samples-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--ink-soft);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.samples-toggle:hover {
  background: var(--surface-2);
  color: var(--ink);
}
.chev {
  color: var(--ink-faint);
}
.samples-list {
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 260px;
  overflow-y: auto;
}
.sample-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  text-decoration: none;
  color: var(--ink-soft);
  transition: background 0.14s;
}
.sample-item:hover {
  background: var(--surface-2);
  color: var(--ink);
}
.sample-item img {
  width: 34px;
  height: 34px;
  border-radius: 6px;
  object-fit: cover;
  background: var(--surface-3);
  flex-shrink: 0;
}
.sample-title {
  font-size: 0.78rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.foot {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 6px 0;
  border-top: 1px solid var(--line);
}
.quota {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  cursor: default;
}
.quota-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.quota-label {
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--ink-soft);
}
.quota-percent {
  font-size: 0.76rem;
  font-weight: 700;
  color: var(--ink);
}
.quota-reset {
  font-family: var(--font-mono);
  font-size: 0.66rem;
  color: var(--ink-faint);
  margin-bottom: 4px;
}
.quota-bar {
  width: 100%;
  height: 6px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}
.quota-bar-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  transition: width 0.3s ease;
}
.quota-bar-fill.ok {
  background: var(--ok);
}
.quota-bar-fill.mid {
  background: var(--red-strong);
}
.quota-bar-fill.low {
  background: var(--danger);
}
.acct {
  font-family: var(--font-mono);
  font-size: 0.74rem;
  color: var(--ink-faint);
}
.logout {
  width: 100%;
  justify-content: center;
  padding: 9px 13px;
  font-size: 0.82rem;
}

@media (max-width: 720px) {
  .sidebar {
    flex-basis: 64px;
    width: 64px;
    padding: 18px 10px;
  }
  .brand-name,
  .nav-label,
  .nav-section,
  .quota,
  .acct,
  .samples {
    display: none;
  }
  .nav-item {
    justify-content: center;
  }
}
</style>
