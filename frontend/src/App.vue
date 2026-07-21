<template>
  <div class="app">
    <!-- 초기 세션 복원 중: 빠르면 빈 화면으로 바로 넘어가고, 0.3초 이상일 때만
         boot 인디케이터를 띄운다. 복원 중에는 로그인 게이트를 절대 보여주지 않는다. -->
    <div v-if="!store.authReady" class="boot-wrap">
      <div v-if="showBoot" class="boot">
        <span class="boot-mark">CoStar</span>
        <span class="loader-ring" aria-hidden="true" />
        <span class="boot-sub">불러오는 중</span>
      </div>
    </div>

    <!-- 로그인 게이트 (복원 완료 후에만) -->
    <LoginGate v-else-if="!store.authed" />

    <!-- 메인 앱 -->
    <div v-else class="shell">
      <SideBar />
      <main class="main">
        <div class="main-inner">
          <PeoplePanel v-show="store.tab === 'people'" />
          <WorksPanel v-show="store.tab === 'works'" />
          <MatchPanel v-show="store.tab === 'match'" />
        </div>
      </main>
    </div>

    <!-- 콜드 스타트 배너 -->
    <transition name="fade">
      <div v-if="store.waking" class="waking">
        <span class="dot" /> 서버를 깨우는 중입니다… 잠시만 기다려 주세요.
      </div>
    </transition>

    <!-- 이미지 미리보기 모달 -->
    <PreviewModal />

    <!-- 전역 로딩 오버레이 (느린 API 호출 시 기존 화면 위에 표시) -->
    <transition name="fade">
      <div v-if="store.overlay" class="loading-overlay">
        <div class="loader">
          <span class="loader-ring" aria-hidden="true" />
          <span class="loader-text">불러오는 중</span>
        </div>
      </div>
    </transition>

    <!-- 토스트 -->
    <transition name="fade">
      <div v-if="store.toast" class="toast" :class="`toast-${store.toast.kind}`">
        {{ store.toast.text }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { store } from './store.js'
import SideBar from './components/SideBar.vue'
import LoginGate from './components/LoginGate.vue'
import PeoplePanel from './components/PeoplePanel.vue'
import WorksPanel from './components/WorksPanel.vue'
import MatchPanel from './components/MatchPanel.vue'
import PreviewModal from './components/PreviewModal.vue'

// 세션 복원이 빠르면 boot 인디케이터를 띄우지 않는다(깜빡임 방지).
// 0.3초 넘게 걸릴 때만(콜드스타트 등) 표시한다.
const showBoot = ref(false)

onMounted(async () => {
  const timer = setTimeout(() => {
    if (!store.authReady) showBoot.value = true
  }, 300)
  try {
    await store.init()
  } finally {
    clearTimeout(timer)
  }
})
</script>

<style scoped>
.app {
  height: 100%;
}

.shell {
  display: flex;
  height: 100%;
}

.boot-wrap {
  height: 100%;
}
.boot {
  height: 100%;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 20px;
}
.boot-mark {
  font-family: var(--font-display);
  font-size: 2rem;
  letter-spacing: 0.04em;
  color: var(--ink);
}
.boot .loader-ring {
  width: 38px;
  height: 38px;
}
.boot-sub {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  letter-spacing: 0.16em;
  color: var(--ink-faint);
}

.main {
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow-y: auto;
}
.main-inner {
  padding: 36px 40px 64px;
  max-width: 1100px;
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
  background: var(--surface);
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

.loading-overlay {
  position: fixed;
  inset: 0;
  z-index: 400;
  display: grid;
  place-items: center;
  background: rgba(243, 244, 246, 0.55);
  backdrop-filter: blur(3px) saturate(1.1);
}
.loader {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
/* conic-gradient를 원형 마스크로 잘라 만든 미세한 그라데이션 링 스피너 */
.loader-ring {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: conic-gradient(from 90deg, transparent 0%, var(--gold) 92%, var(--gold) 100%);
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 3.5px), #000 0);
  mask: radial-gradient(farthest-side, transparent calc(100% - 3.5px), #000 0);
  animation: spin 0.85s cubic-bezier(0.5, 0.15, 0.5, 0.85) infinite;
}
.loader-text {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  letter-spacing: 0.16em;
  color: var(--ink-soft);
}
@keyframes spin {
  to {
    transform: rotate(360deg);
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
  background: var(--surface);
  border: 1px solid var(--line-strong);
}
.toast-error {
  color: #fff;
  background: var(--danger);
}
.toast-ok {
  color: var(--ink-on-gold);
  background: var(--gold);
}
</style>
