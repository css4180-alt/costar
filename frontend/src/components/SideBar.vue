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
      <div v-if="quota" class="quota" :title="quotaTitle">
        <span class="quota-dot" :class="quotaLevel" />
        <span class="quota-text">오늘 {{ quota.account_remaining }}/{{ quota.account_limit }}</span>
      </div>
      <div v-if="store.account && store.account !== '__local__'" class="acct">{{ store.account }}</div>
      <button class="btn btn-ghost logout" @click="store.logout()">로그아웃</button>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { store } from '../store.js'

const topTabs = [
  {
    id: 'match',
    label: '작품 매칭',
    icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.2-3.2"/><path d="M8.5 11.5a2.5 2.5 0 0 0 5 0"/></svg>',
  },
]

const systemTabs = [
  {
    id: 'people',
    label: '인물 관리',
    icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.2"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0"/><path d="M16 6.2a3 3 0 0 1 0 5.6"/><path d="M17.5 19a5.5 5.5 0 0 0-2-4.3"/></svg>',
  },
  {
    id: 'works',
    label: '작품 관리',
    icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 9h18M8 5v4M14 5v4M8 19v-4M14 19v-4"/></svg>',
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
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 0.76rem;
  color: var(--ink-soft);
  cursor: default;
}
.quota-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.quota-dot.ok {
  background: var(--ok);
}
.quota-dot.mid {
  background: var(--red-strong);
}
.quota-dot.low {
  background: var(--danger);
}
.acct {
  font-family: var(--font-mono);
  font-size: 0.74rem;
  color: var(--ink-faint);
}
.logout {
  padding: 7px 13px;
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
  .quota-text,
  .acct {
    display: none;
  }
  .nav-item {
    justify-content: center;
  }
}
</style>
