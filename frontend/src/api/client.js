// CoStar API 클라이언트.
// BASE는 같은 도메인의 /api (dev는 Vite 프록시, prod는 CloudFront 라우팅).
const BASE = '/api'

// Lambda 콜드 스타트 동안 게이트웨이가 돌려줄 수 있는 상태 코드.
const COLD_STATUSES = new Set([502, 503, 504])
const MAX_RETRIES = 30
const RETRY_DELAY = 3000

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const TOKEN_KEY = 'costar.token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}
export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

// 저장된 토큰을 커스텀 헤더로 만든다(없으면 빈 객체).
// CloudFront OAC가 Lambda Function URL 호출 시 Authorization 헤더를 sigv4
// 서명에 사용하므로, 앱 토큰은 X-Costar-Token으로 보내 충돌을 피한다.
function authHeaders() {
  const token = getToken()
  return token ? { 'X-Costar-Token': token } : {}
}

// 콜드 스타트 진행 상태를 UI에 알리는 훅(스토어가 등록).
let wakingHandler = null
export function setWakingHandler(fn) {
  wakingHandler = fn
}
function notifyWaking(active) {
  wakingHandler?.(active)
}

// 401(미인증/세션 만료) 시 로그인 화면으로 되돌리는 훅.
let unauthorizedHandler = null
export function setUnauthorizedHandler(fn) {
  unauthorizedHandler = fn
}
function notifyUnauthorized() {
  unauthorizedHandler?.()
}

/**
 * 콜드 스타트(502/503/504/네트워크 오류)에 자동 재시도하는 fetch.
 * 항상 저장된 토큰을 Authorization 헤더로 실어 보낸다.
 */
async function fetchRetry(url, opts = {}) {
  opts = { ...opts, headers: { ...authHeaders(), ...(opts.headers || {}) } }
  let signaled = false
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(url, opts)
      if (res.status === 401) {
        setToken(null)
        notifyUnauthorized()
        return res
      }
      if (COLD_STATUSES.has(res.status) && attempt < MAX_RETRIES) {
        if (!signaled) {
          signaled = true
          notifyWaking(true)
        }
        await sleep(RETRY_DELAY)
        continue
      }
      if (signaled) notifyWaking(false)
      return res
    } catch (err) {
      if (attempt < MAX_RETRIES) {
        if (!signaled) {
          signaled = true
          notifyWaking(true)
        }
        await sleep(RETRY_DELAY)
        continue
      }
      if (signaled) notifyWaking(false)
      throw err
    }
  }
}

// 응답을 JSON으로 파싱하되, 실패 시 서버의 detail 메시지를 예외로 던진다.
async function parse(res, fallback) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || fallback)
  }
  return res.json()
}

// ---- 인증 ----

/** 패스코드로 로그인. 성공 시 토큰을 저장하고 {token, quota}를 반환한다. */
export async function login(passcode) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ passcode }),
  })
  const data = await parse(res, '로그인에 실패했습니다.')
  setToken(data.token)
  return data
}

/** 현재 토큰의 계정·쿼터 정보(세션 복원용). 실패 시 null. */
export async function getMe() {
  const token = getToken()
  if (!token) return null
  const res = await fetchRetry(`${BASE}/auth/me`)
  if (!res.ok) {
    if (res.status === 401) setToken(null)
    return null
  }
  return res.json()
}

// ---- 인물(People) ----

export async function listPersons() {
  return parse(await fetchRetry(`${BASE}/persons`), '인물 목록 조회 실패')
}

export async function getPerson(id) {
  return parse(await fetchRetry(`${BASE}/persons/${id}`), '인물 상세 조회 실패')
}

export async function createPerson(name, file) {
  const form = new FormData()
  form.append('name', name)
  form.append('file', file)
  return parse(
    await fetchRetry(`${BASE}/persons`, { method: 'POST', body: form }),
    '인물 등록 실패',
  )
}

export async function addFace(personId, file) {
  const form = new FormData()
  form.append('file', file)
  return parse(
    await fetchRetry(`${BASE}/persons/${personId}/faces`, { method: 'POST', body: form }),
    '얼굴 추가 실패',
  )
}

export async function deletePerson(id) {
  const res = await fetchRetry(`${BASE}/persons/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('인물 삭제 실패')
}

// ---- 작품(Works) ----

export async function listWorks() {
  return parse(await fetchRetry(`${BASE}/works`), '작품 목록 조회 실패')
}

export async function getWork(id) {
  return parse(await fetchRetry(`${BASE}/works/${id}`), '작품 상세 조회 실패')
}

export async function createWork(title, year, file = null) {
  const form = new FormData()
  form.append('title', title)
  if (year != null && year !== '') form.append('year', year)
  if (file) form.append('file', file)
  return parse(
    await fetchRetry(`${BASE}/works`, { method: 'POST', body: form }),
    '작품 생성 실패',
  )
}

export async function addStills(workId, files) {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  return parse(
    await fetchRetry(`${BASE}/works/${workId}/stills`, { method: 'POST', body: form }),
    '스틸 업로드 실패',
  )
}

export async function deleteWork(id) {
  const res = await fetchRetry(`${BASE}/works/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('작품 삭제 실패')
}

/** 작품 출연진을 TMDB에서 다시 동기화한다. job 객체를 반환한다. */
export async function resyncWork(id) {
  return parse(
    await fetchRetry(`${BASE}/works/${id}/resync`, { method: 'POST' }),
    'TMDB 동기화 실패',
  )
}

/** 등록된 인물을 작품 출연진으로 추가한다. */
export async function addCast(workId, personId) {
  return parse(
    await fetchRetry(`${BASE}/works/${workId}/cast`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ person_id: personId }),
    }),
    '출연진 추가 실패',
  )
}

/** 작품에서 특정 인물의 출연을 제거한다. */
export async function removeCast(workId, personId) {
  const res = await fetchRetry(`${BASE}/works/${workId}/cast/${personId}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error('출연진 제거 실패')
}

// ---- 매칭(Match) ----

/** 사진 한 장에서 등록 인물을 식별한다. */
export async function identify(file) {
  const form = new FormData()
  form.append('file', file)
  return parse(
    await fetchRetry(`${BASE}/identify`, { method: 'POST', body: form }),
    '식별 실패',
  )
}

/** 사진에서 여러 얼굴을 식별하고 공통 출연작을 함께 조회한다. */
export async function analyzeMatch(file) {
  const form = new FormData()
  form.append('file', file)
  return parse(
    await fetchRetry(`${BASE}/match/analyze`, { method: 'POST', body: form }),
    '이미지 분석 실패',
  )
}

// ---- TMDB 임포트 ----

/** 제목으로 TMDB 영화/TV를 검색한다. */
export async function tmdbSearch(query, mediaType = 'movie') {
  const qs = `query=${encodeURIComponent(query)}&media_type=${mediaType}`
  return parse(await fetchRetry(`${BASE}/tmdb/search?${qs}`), 'TMDB 검색 실패')
}

/** 영화/TV 1편 임포트를 시작한다. job 객체(진행 폴링용)를 반환한다. */
export async function importWork(mediaType, tmdbId) {
  return parse(
    await fetchRetry(`${BASE}/works/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ media_type: mediaType, tmdb_id: tmdbId }),
    }),
    '임포트 시작 실패',
  )
}

/** 임포트 작업 진행 상태를 조회한다. */
export async function getImportJob(jobId) {
  return parse(await fetchRetry(`${BASE}/imports/${jobId}`), '임포트 상태 조회 실패')
}
