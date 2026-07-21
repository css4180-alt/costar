import { reactive } from 'vue'
import {
  addCast,
  addFace,
  addStills,
  analyzeMatch,
  createPerson,
  createWork,
  deletePerson,
  deleteWork,
  getImportJob,
  getMe,
  getPerson,
  getWork,
  identify,
  importWork,
  listPersons,
  listWorks,
  login,
  removeCast,
  resyncWork,
  setToken,
  setUnauthorizedHandler,
  setWakingHandler,
  tmdbSearch,
} from './api/client.js'

const TAB_KEY = 'costar.activeTab'

export const store = reactive({
  // 인증/쿼터
  authed: false,
  account: null,
  quota: null, // { account_remaining, account_limit, site_remaining, ... }
  authReady: false, // 초기 세션 복원 시도 완료 여부

  // 서버 콜드 스타트(깨어나는 중) 여부
  waking: false,

  // 현재 탭: 'people' | 'works' | 'match' (해시 URL과 동기화)
  tab: 'people',
  // 작품 상세로 진입한 작품 id (없으면 목록). URL: #/works/<id>
  workId: null,

  // 데이터
  persons: [],
  works: [],

  // 이미지 미리보기 모달 — { url, caption } 또는 null
  preview: null,

  // 전역 토스트 메시지 — { text, kind } 또는 null
  toast: null,

  // ---- 초기화 ----
  async init() {
    setWakingHandler((active) => {
      this.waking = active
    })
    setUnauthorizedHandler(() => {
      this.authed = false
      this.account = null
      this.quota = null
    })
    window.addEventListener('popstate', () => this._applyRoute())
    this._applyRoute()
    const me = await getMe()
    if (me) {
      this.applyAuth(me)
      await this.loadAll()
    }
    this.authReady = true
  },

  // ---- 인증 ----
  applyAuth(quota) {
    this.authed = true
    this.account = quota.account
    this.quota = quota
  },

  async login(passcode) {
    const data = await login(passcode)
    this.applyAuth(data.quota)
    await this.loadAll()
  },

  logout() {
    setToken(null)
    this.authed = false
    this.account = null
    this.quota = null
    this.persons = []
    this.works = []
  },

  async refreshQuota() {
    const me = await getMe()
    if (me) this.quota = me
  },

  async loadAll() {
    await Promise.all([this.loadPersons(), this.loadWorks()])
  },

  // ---- 라우팅(해시 URL 동기화) ----
  // 현재 URL 해시(#/people, #/works, #/works/<id>, #/match)를 읽어 상태에 반영한다.
  _applyRoute() {
    const raw = window.location.hash.replace(/^#\/?/, '')
    const [seg, id] = raw.split('/')
    const tab = ['people', 'works', 'match'].includes(seg)
      ? seg
      : localStorage.getItem(TAB_KEY) || 'people'
    this.tab = tab
    this.workId = tab === 'works' && id ? decodeURIComponent(id) : null
    localStorage.setItem(TAB_KEY, tab)
  },
  // 현재 상태를 URL 해시로 밀어넣는다(뒤로가기 지원).
  _pushRoute() {
    const path = this.workId ? `#/works/${this.workId}` : `#/${this.tab}`
    if (window.location.hash !== path) window.history.pushState({}, '', path)
  },

  // ---- 탭 ----
  setTab(tab) {
    this.tab = tab
    this.workId = null
    localStorage.setItem(TAB_KEY, tab)
    this._pushRoute()
  },

  openWork(id) {
    this.tab = 'works'
    this.workId = id
    this._pushRoute()
  },

  closeWork() {
    this.workId = null
    this._pushRoute()
  },

  // ---- 전역 로딩 오버레이 ----
  // 느린 API 호출에만 표시한다: 300ms 안에 끝나면 깜빡이지 않고, 그보다 길면
  // 기존 화면을 어둡게 덮고 인디케이터를 띄운다. 중첩 호출은 카운터로 처리.
  overlay: false,
  _busyCount: 0,
  _busyTimer: null,
  _beginBusy() {
    this._busyCount += 1
    if (this._busyCount === 1 && !this._busyTimer) {
      this._busyTimer = setTimeout(() => {
        this.overlay = true
        this._busyTimer = null
      }, 300)
    }
  },
  _endBusy() {
    this._busyCount = Math.max(0, this._busyCount - 1)
    if (this._busyCount === 0) {
      if (this._busyTimer) {
        clearTimeout(this._busyTimer)
        this._busyTimer = null
      }
      this.overlay = false
    }
  },
  async withOverlay(fn) {
    this._beginBusy()
    try {
      return await fn()
    } finally {
      this._endBusy()
    }
  },

  // ---- 미리보기 ----
  openPreview(url, caption = '') {
    if (url) this.preview = { url, caption }
  },
  closePreview() {
    this.preview = null
  },

  // ---- 토스트 ----
  notify(text, kind = 'info') {
    this.toast = { text, kind }
    clearTimeout(this._toastTimer)
    this._toastTimer = setTimeout(() => {
      this.toast = null
    }, 3200)
  },

  // ---- 인물 ----
  async loadPersons() {
    this.persons = await listPersons()
  },

  async addPerson(name, file) {
    await this.withOverlay(async () => {
      await createPerson(name, file)
      await Promise.all([this.loadPersons(), this.refreshQuota()])
    })
  },

  async addPersonFace(personId, file) {
    await this.withOverlay(async () => {
      await addFace(personId, file)
      await Promise.all([this.loadPersons(), this.refreshQuota()])
    })
  },

  getPersonDetail(id) {
    return this.withOverlay(() => getPerson(id))
  },

  async removePerson(id) {
    await deletePerson(id)
    await this.loadPersons()
  },

  // ---- 작품 ----
  async loadWorks() {
    this.works = await listWorks()
  },

  async addWork(title, year, file = null) {
    const work = await createWork(title, year, file)
    await this.loadWorks()
    return work
  },

  async uploadStills(workId, files) {
    return this.withOverlay(async () => {
      const result = await addStills(workId, files)
      await Promise.all([this.loadWorks(), this.refreshQuota()])
      return result
    })
  },

  getWorkDetail(id) {
    return this.withOverlay(() => getWork(id))
  },

  async removeWork(id) {
    await deleteWork(id)
    await this.loadWorks()
  },

  // ---- TMDB 임포트 ----
  async searchTmdb(query, mediaType = 'movie') {
    return tmdbSearch(query, mediaType)
  },

  async startImport(mediaType, tmdbId) {
    return importWork(mediaType, tmdbId)
  },

  async resyncWork(workId) {
    return resyncWork(workId)
  },

  async pollImport(jobId) {
    return getImportJob(jobId)
  },

  // ---- 출연진 관리 ----
  async addCast(workId, personId) {
    return this.withOverlay(() => addCast(workId, personId))
  },

  async removeCast(workId, personId) {
    return this.withOverlay(() => removeCast(workId, personId))
  },

  // 임포트 완료 후 작품·인물·쿼터를 새로고침한다.
  async refreshAfterImport() {
    await Promise.all([this.loadWorks(), this.loadPersons(), this.refreshQuota()])
  },

  // ---- 매칭 ----
  async identifyPhoto(file) {
    const result = await identify(file)
    await this.refreshQuota()
    return result
  },

  async analyzePhoto(file) {
    const result = await analyzeMatch(file)
    await this.refreshQuota()
    return result
  },
})
