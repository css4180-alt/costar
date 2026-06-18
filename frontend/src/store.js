import { reactive } from 'vue'
import {
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

  // 현재 탭: 'people' | 'works' | 'match'
  tab: localStorage.getItem(TAB_KEY) || 'people',

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

  // ---- 탭 ----
  setTab(tab) {
    this.tab = tab
    localStorage.setItem(TAB_KEY, tab)
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
    await createPerson(name, file)
    await Promise.all([this.loadPersons(), this.refreshQuota()])
  },

  async addPersonFace(personId, file) {
    await addFace(personId, file)
    await Promise.all([this.loadPersons(), this.refreshQuota()])
  },

  getPersonDetail(id) {
    return getPerson(id)
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
    const result = await addStills(workId, files)
    await Promise.all([this.loadWorks(), this.refreshQuota()])
    return result
  },

  getWorkDetail(id) {
    return getWork(id)
  },

  async removeWork(id) {
    await deleteWork(id)
    await this.loadWorks()
  },

  // ---- TMDB 임포트 ----
  async searchTmdb(query) {
    return tmdbSearch(query)
  },

  async startImport(tmdbMovieId) {
    return importWork(tmdbMovieId)
  },

  async pollImport(jobId) {
    return getImportJob(jobId)
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
