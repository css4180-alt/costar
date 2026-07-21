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
        공개 데모입니다. 비용 보호를 위해 <strong>패스코드</strong>로 접속하며,
        <br />
        계정마다 하루 얼굴 분석 횟수가 제한됩니다.
      </p>

      <form class="gate-form" @submit.prevent="submit">
        <input
          ref="input"
          v-model="passcode"
          type="password"
          class="field gate-input"
          placeholder="패스코드"
          autocomplete="off"
          :disabled="loading"
        />
        <button type="submit" class="btn gate-btn" :disabled="loading || !passcode.trim()">
          {{ loading ? '확인 중…' : '입장' }}
        </button>
      </form>

      <transition name="fade">
        <p v-if="error" class="gate-error">{{ error }}</p>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { store } from '../store.js'

const passcode = ref('')
const loading = ref(false)
const error = ref('')
const input = ref(null)

onMounted(() => input.value?.focus())

async function submit() {
  if (loading.value || !passcode.value.trim()) return
  loading.value = true
  error.value = ''
  try {
    await store.login(passcode.value.trim())
  } catch (err) {
    error.value = err.message || '로그인에 실패했습니다.'
    passcode.value = ''
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

.gate-form {
  width: 100%;
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.gate-input {
  text-align: center;
  letter-spacing: 0.1em;
  font-family: var(--font-mono);
}

.gate-btn {
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
