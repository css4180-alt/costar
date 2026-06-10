<template>
  <div class="app">
    <!-- 초기 세션 복원 중 -->
    <div v-if="!store.authReady" class="boot">
      <span class="boot-mark">CoStar</span>
      <span class="boot-sub">불러오는 중…</span>
    </div>

    <!-- 로그인 게이트 -->
    <LoginGate v-else-if="!store.authed" />

    <!-- 메인 앱 -->
    <template v-else>
      <AppHeader />
      <main class="main">
        <PeoplePanel v-show="store.tab === 'people'" />
        <WorksPanel v-show="store.tab === 'works'" />
        <MatchPanel v-show="store.tab === 'match'" />
      </main>
    </template>

    <!-- 콜드 스타트 배너 -->
    <transition name="fade">
      <div v-if="store.waking" class="waking">
        <span class="dot" /> 서버를 깨우는 중입니다… 잠시만 기다려 주세요.
      </div>
    </transition>

    <!-- 이미지 미리보기 모달 -->
    <PreviewModal />

    <!-- 토스트 -->
    <transition name="fade">
      <div v-if="store.toast" class="toast" :class="`toast-${store.toast.kind}`">
        {{ store.toast.text }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { store } from './store.js'
import AppHeader from './components/AppHeader.vue'
import LoginGate from './components/LoginGate.vue'
import PeoplePanel from './components/PeoplePanel.vue'
import WorksPanel from './components/WorksPanel.vue'
import MatchPanel from './components/MatchPanel.vue'
import PreviewModal from './components/PreviewModal.vue'

onMounted(() => store.init())
</script>

<style scoped>
.app {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.boot {
  height: 100%;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 8px;
}
.boot-mark {
  font-family: var(--font-display);
  font-size: 2rem;
  letter-spacing: 0.04em;
  color: var(--ink);
}
.boot-sub {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--ink-faint);
}

.main {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 32px 28px 64px;
  max-width: 1180px;
  width: 100%;
  margin: 0 auto;
}

.waking {
  position: fixed;
  left: 50%;
  bottom: 22px;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 18px;
  font-size: 0.84rem;
  color: var(--ink);
  background: var(--surface-2);
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  box-shadow: var(--shadow-md);
  z-index: 200;
}
.waking .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--gold);
  animation: pulse 1s ease-in-out infinite;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 1;
  }
}

.toast {
  position: fixed;
  left: 50%;
  top: 22px;
  transform: translateX(-50%);
  padding: 11px 20px;
  font-size: 0.86rem;
  font-weight: 500;
  border-radius: 999px;
  box-shadow: var(--shadow-md);
  z-index: 300;
}
.toast-info {
  color: var(--ink);
  background: var(--surface-2);
  border: 1px solid var(--line-strong);
}
.toast-error {
  color: #fff;
  background: #3a1f1c;
  border: 1px solid var(--danger);
}
.toast-ok {
  color: var(--ink-on-gold);
  background: var(--gold);
}
</style>
