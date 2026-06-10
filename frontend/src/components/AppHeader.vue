<template>
  <header class="hdr">
    <div class="brand">
      <svg viewBox="0 0 40 24" width="34" height="20" aria-hidden="true">
        <circle cx="15" cy="12" r="8" fill="none" stroke="var(--gold)" stroke-width="2.2" />
        <circle cx="25" cy="12" r="8" fill="none" stroke="var(--red)" stroke-width="2.2" />
      </svg>
      <span class="brand-name">CoStar</span>
    </div>

    <nav class="tabs">
      <button
        v-for="t in tabs"
        :key="t.id"
        class="tab"
        :class="{ active: store.tab === t.id }"
        @click="store.setTab(t.id)"
      >
        {{ t.label }}
      </button>
    </nav>

    <div class="right">
      <span v-if="quota" class="quota" :title="quotaTitle">
        <span class="quota-dot" :class="quotaLevel" />
        오늘 {{ quota.account_remaining }}/{{ quota.account_limit }}
      </span>
      <span v-if="store.account && store.account !== '__local__'" class="acct">{{ store.account }}</span>
      <button class="btn btn-ghost logout" @click="store.logout()">로그아웃</button>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { store } from '../store.js'

const tabs = [
  { id: 'people', label: 'People' },
  { id: 'works', label: 'Works' },
  { id: 'match', label: 'Match' },
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
.hdr {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 22px;
  padding: 0 24px;
  height: 60px;
  background: var(--bg-soft);
  border-bottom: 1px solid var(--line);
}

.brand {
  display: flex;
  align-items: center;
  gap: 9px;
}
.brand-name {
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--ink);
}

.tabs {
  display: flex;
  gap: 4px;
}
.tab {
  padding: 7px 15px;
  font-size: 0.86rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--ink-faint);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: color 0.16s, background 0.16s;
}
.tab:hover {
  color: var(--ink-soft);
  background: var(--surface);
}
.tab.active {
  color: var(--gold);
  background: var(--gold-soft);
}

.right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 14px;
}

.quota {
  display: inline-flex;
  align-items: center;
  gap: 7px;
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
  background: var(--gold);
}
.quota-dot.low {
  background: var(--danger);
}

.acct {
  font-family: var(--font-mono);
  font-size: 0.74rem;
  color: var(--ink-faint);
  padding-left: 12px;
  border-left: 1px solid var(--line);
}

.logout {
  padding: 6px 12px;
  font-size: 0.8rem;
}
</style>
