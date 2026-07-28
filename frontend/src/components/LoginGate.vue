<template>
  <div class="gate">
    <div class="gate-card">
      <span class="mark" aria-hidden="true">
        <svg viewBox="0 0 40 24" width="46" height="28">
          <circle cx="15" cy="12" r="8" fill="none" stroke="var(--gold)" stroke-width="2.2" />
          <circle cx="25" cy="12" r="8" fill="none" stroke="var(--red)" stroke-width="2.2" />
        </svg>
      </span>
      <h1 class="gate-title">CoStar</h1>
      <p class="gate-sub">함께 출연한 작품을 얼굴로 잇다</p>
      <p class="gate-note">
        누구나 자유롭게 둘러볼 수 있는 공개 데모입니다.
        <br />
        비용 보호를 위해 하루 사용량이 제한됩니다.
      </p>

      <button class="btn gate-btn" :disabled="loading" @click="enter">
        {{ loading ? '입장 중…' : '입장하기' }}
      </button>

      <transition name="fade">
        <p v-if="error" class="gate-error">{{ error }}</p>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { store } from '../store.js'

// 공개 데모: 비밀번호 입력 없이 클릭 한 번으로 공용 demo 계정에 로그인한다.
// 실제 비용 보호는 패스코드가 아니라 계정/사이트 일일 쿼터가 담당한다.
const DEMO_PASSCODE = 'demo1234'

const loading = ref(false)
const error = ref('')

async function enter() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    await store.login(DEMO_PASSCODE)
  } catch (err) {
    error.value = err.message || '입장에 실패했습니다. 잠시 후 다시 시도해 주세요.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.gate {
  display: grid;
  place-items: center;
  height: 100%;
  padding: 24px;
  background:
    radial-gradient(120% 90% at 50% -10%, rgba(37, 99, 235, 0.08) 0%, transparent 55%),
    var(--bg);
}

.gate-card {
  width: 100%;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 40px 34px 32px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
}

.mark {
  display: grid;
  place-items: center;
  width: 72px;
  height: 52px;
}

.gate-title {
  margin: 16px 0 0;
  font-family: var(--font-display);
  font-size: 2rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--ink);
}

.gate-sub {
  margin-top: 6px;
  font-family: var(--font-mono);
  font-size: 0.74rem;
  letter-spacing: 0.04em;
  color: var(--gold);
}

.gate-note {
  margin-top: 20px;
  font-size: 0.84rem;
  line-height: 1.6;
  color: var(--ink-soft);
}
.gate-note strong {
  color: var(--ink);
  font-weight: 600;
}

.gate-btn {
  width: 100%;
  margin-top: 24px;
  justify-content: center;
  padding: 12px;
  font-size: 0.95rem;
}

.gate-error {
  margin-top: 14px;
  font-size: 0.82rem;
  color: var(--danger);
}
</style>
