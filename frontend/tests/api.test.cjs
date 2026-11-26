const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')
const ts = require('typescript')

const SRC = path.resolve(__dirname, '../src')
const flush = () => new Promise(resolve => setImmediate(resolve))

function harness({ disabled = false, mock = false } = {}) {
  const storage = new Map(), listeners = new Map(), intervals = new Map(), timeouts = new Map()
  const modules = new Map(), calls = [], writes = [], navigation = []
  let now = Date.now(), timerId = 0, revision = 1, review = false
  let respond = url => url.includes('review-mode') ? { review_mode: review }
    : url.includes('/history?') ? { code: '159696', short_name: 'ETF', revision, data: [] }
    : { revision, items: [{ code: '159696' }, { code: '513500' }, { code: '159655' }], groups: [] }
  const uni = {
    getStorageSync: key => storage.get(key),
    setStorageSync: (key, value) => { writes.push(key); storage.set(key, value) },
    removeStorageSync: key => storage.delete(key),
    getStorageInfoSync: () => ({ keys: [...storage.keys()] }),
    $on(event, callback) {
      if (!listeners.has(event)) listeners.set(event, new Set())
      listeners.get(event).add(callback)
    },
    $off: (event, callback) => listeners.get(event)?.delete(callback),
    $emit: (event, ...args) => listeners.get(event)?.forEach(callback => callback(...args)),
    request(options) {
      calls.push(options.url)
      Promise.resolve().then(() => respond(options.url)).then(
        data => options.success({ statusCode: 200, data }), options.fail,
      )
    },
    setNavigationBarTitle() {},
    stopPullDownRefresh() {},
    navigateBack: options => navigation.push(options),
    redirectTo: options => navigation.push(options),
  }
  class Clock extends Date { static now() { return now } }

  function evaluate(source, filename, hooks = {}) {
    const module = { exports: {} }
    const addHook = name => callback => { (hooks[name] ||= []).push(callback) }
    const js = ts.transpileModule(source.replaceAll('import.meta.env', 'TEST_ENV'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
    }).outputText
    vm.runInNewContext(js, {
      module, exports: module.exports, uni, console, Date: Clock,
      TEST_ENV: { VITE_API_BASE_URL: 'https://test.local', VITE_USE_MOCK: String(mock), VITE_DISABLE_CACHE: String(disabled) },
      require(id) {
        if (id === 'vue') return {
          ref: value => ({ value }), computed: fn => ({ get value() { return fn() } }),
          onMounted: addHook('mounted'), onUnmounted: addHook('unmounted'),
        }
        if (id === '@dcloudio/uni-app') return Object.fromEntries(
          ['onLoad', 'onShow', 'onHide', 'onUnload', 'onPullDownRefresh', 'onShareAppMessage', 'onShareTimeline']
            .map(key => [key, addHook(key)]),
        )
        if (id.endsWith('.vue')) return {}
        return load(path.resolve(path.dirname(filename), id))
      },
      setInterval: (fn, ms) => { const id = ++timerId; intervals.set(id, { fn, ms }); return id },
      clearInterval: id => intervals.delete(id),
      setTimeout: (fn, ms) => { const id = ++timerId; timeouts.set(id, { fn, ms }); return id },
      clearTimeout: id => timeouts.delete(id),
      getCurrentPages: () => [{}],
    }, { filename })
    return module.exports
  }
  function load(file) {
    if (!path.extname(file)) file = fs.existsSync(file + '.ts') ? file + '.ts' : path.join(file, 'index.ts')
    if (!modules.has(file)) modules.set(file, file.endsWith('.json')
      ? JSON.parse(fs.readFileSync(file, 'utf8'))
      : evaluate(fs.readFileSync(file, 'utf8'), file))
    return modules.get(file)
  }
  const api = load(path.join(SRC, 'api/index.ts'))
  function page(name) {
    const hooks = {}, filename = path.join(SRC, `pages/${name}/${name}.vue`)
    const source = fs.readFileSync(filename, 'utf8').match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1]
    const fields = name === 'index' ? 'dashboard, dashboardGroups, viewMode, toggleGroup' : 'history, displayName'
    const state = evaluate(source + `\nexports.state = { ${fields}, loading, error };`, filename, hooks).state
    return { state, async fire(event, arg) {
      for (const callback of hooks[event] || []) await callback(arg)
      await flush()
    } }
  }
  return {
    api, storage, writes, calls, intervals, timeouts, navigation, page,
    revision: value => { revision = value }, review: value => { review = value },
    respond: handler => { respond = handler }, advance: ms => { now += ms },
    count: part => calls.filter(url => url.includes(part)).length,
    async tick() {
      for (const timer of [...intervals.values()]) { assert.equal(timer.ms, 3600000); timer.fn() }
      await flush()
    },
  }
}

test('one-hour cache expires and dashboard refresh invalidates cached history', async () => {
  const h = harness()
  await h.api.fetchDashboard()
  await h.api.fetchPremiumHistory('159696')
  await h.api.fetchDashboard()
  await h.api.fetchPremiumHistory('159696')
  assert.equal(h.count('/dashboard'), 1)
  assert.equal(h.count('/history?'), 1)
  h.revision(2)
  await h.api.fetchDashboard(true)
  assert.equal((await h.api.fetchPremiumHistory('159696')).revision, 2)
  h.advance(3600001)
  h.revision(3)
  assert.equal((await h.api.fetchDashboard()).revision, 3)
  assert.equal((await h.api.fetchPremiumHistory('159696')).revision, 3)
})

test('version cleanup and disabled cache preserve unrelated storage and deduplicate requests', async () => {
  const h = harness({ disabled: true })
  h.storage.set('cache_dashboard_obsolete', 'old')
  h.storage.set('cache_etf_premium_history_obsolete_159696', 'old')
  h.storage.set('preference', 'keep')
  await Promise.all([h.api.fetchDashboard(), h.api.fetchDashboard()])
  await Promise.all([h.api.fetchPremiumHistory('159696'), h.api.fetchPremiumHistory('159696')])
  assert.equal(h.count('/dashboard'), 1)
  assert.equal(h.count('/history?'), 1)
  assert.deepEqual([...h.storage.keys()], ['preference'])
  assert.equal(h.writes.length, 0)
  assert.equal(h.timeouts.size, 0)
  await h.api.fetchDashboard()
  assert.equal(h.count('/dashboard'), 2)
})

test('late history responses cannot restore an invalidated cache', async () => {
  const h = harness()
  let resolveOld, historyCalls = 0
  h.respond(url => url.includes('/history?') && ++historyCalls === 1
    ? new Promise(resolve => { resolveOld = resolve })
    : url.includes('/history?') ? { revision: 2, data: [] } : { items: [], groups: [] })
  const old = h.api.fetchPremiumHistory('159696')
  await flush()
  await h.api.fetchDashboard(true)
  const fresh = h.api.fetchPremiumHistory('159696')
  resolveOld({ revision: 1, data: [] })
  assert.equal((await old).revision, 2)
  assert.equal((await fresh).revision, 2)
  assert.equal((await h.api.fetchPremiumHistory('159696')).revision, 2)
})

test('background prefetch retains its two-request concurrency limit', async () => {
  const h = harness(), pending = []
  await h.api.fetchDashboard()
  h.respond(() => new Promise(resolve => pending.push(resolve)))
  for (const timer of h.timeouts.values()) { assert.equal(timer.ms, 800); timer.fn() }
  await flush()
  assert.equal(h.count('/history?'), 2)
  pending[0]({ data: [] })
  await flush()
  assert.equal(h.count('/history?'), 3)
  pending.slice(1).forEach(resolve => resolve({ data: [] }))
  await flush()
})

test('cached data cannot bypass review mode on either page', async () => {
  for (const name of ['index', 'detail']) {
    const h = harness()
    await h.api.fetchDashboard()
    await h.api.fetchPremiumHistory('159696')
    h.review(true)
    const page = h.page(name)
    await page.fire('onLoad', { code: '159696' })
    await page.fire('onShow')
    await page.fire('mounted')
    assert.equal(h.count('review-mode'), 1)
    assert.equal(h.count('/dashboard'), 1)
    assert.equal(h.count('/history?'), 1)
    assert.equal(h.intervals.size, 0)
    if (name === 'index') assert.equal(page.state.viewMode.value, 'calculator')
    else assert.equal(h.navigation[0].url, '/pages/index/index')
  }
})

test('home entry, manual refresh and timer reuse each dashboard response', async () => {
  const h = harness({ disabled: true }), page = h.page('index')
  await page.fire('onShow')
  await page.fire('mounted')
  assert.equal(h.count('/dashboard'), 1)
  h.revision(2)
  await page.fire('onPullDownRefresh')
  assert.equal(h.count('/dashboard'), 2)
  assert.equal(page.state.dashboard.value.revision, 2)
  h.revision(3)
  await h.tick()
  assert.equal(h.count('/dashboard'), 3)
  assert.equal(page.state.dashboard.value.revision, 3)
  await page.fire('onHide')
  assert.equal(h.intervals.size, 0)
})

test('groups with more than two funds start folded and expand on toggle', async () => {
  const h = harness({ disabled: true }), page = h.page('index')
  const perRange = value => ({ '3m': value, '6m': value, '1y': value })
  const stats = perRange({ latest: { date: '2026-11-25', premium_rate: 0.1 }, percentile: 0.5, status: 3 })
  const group = (key, members) => ({
    tracking_index: key, tracking_index_name: key, members, ranges: perRange({ min_premium: 0.1, max_premium: 0.1 }),
  })
  h.respond(url => url.includes('review-mode') ? { review_mode: false } : {
    items: ['a1', 'a2', 'b1', 'b2', 'b3'].map(code => ({ code, name: code, short_name: code, fund_type: 'etf', stats })),
    groups: [group('TWO', ['a1', 'a2']), group('THREE', ['b1', 'b2', 'b3'])],
  })
  await page.fire('onShow')
  await page.fire('mounted')
  const expanded = () => page.state.dashboardGroups.value.map(item => item.expanded)
  assert.deepEqual(expanded(), [true, false])
  page.state.toggleGroup('THREE')
  assert.deepEqual(expanded(), [true, true])
})

test('shared detail supports hourly refresh, resume and unload without visiting home', async () => {
  const h = harness(), page = h.page('detail')
  await page.fire('onLoad', { code: '159696' })
  await page.fire('onShow')
  await page.fire('mounted')
  assert.equal(h.count('/dashboard'), 0)
  assert.equal(h.intervals.size, 1)
  h.revision(2)
  await h.tick()
  assert.equal(page.state.history.value.revision, 2)
  await page.fire('onHide')
  assert.equal(h.intervals.size, 0)
  h.advance(3600001)
  h.revision(3)
  await page.fire('onShow')
  assert.equal(page.state.history.value.revision, 3)
  await page.fire('onUnload')
  assert.equal(h.intervals.size, 0)
})

test('mock mode keeps all funds, homepage company names, ratings and detail fund names', async () => {
  const h = harness({ mock: true }), home = h.page('index'), detail = h.page('detail')
  await home.fire('onShow')
  assert.equal(home.state.error.value, '')
  const groups = home.state.dashboardGroups.value
  const mockEtfs = require('../src/mock/etfs.json')
  assert.equal(groups.length, new Set(mockEtfs.map(etf => etf.tracking_index)).size)
  assert.equal(groups.reduce((count, group) => count + group.members.length, 0), mockEtfs.length)
  assert.equal(groups[0].members[0].displayName, '景顺长城')
  assert.equal(groups[1].members[0].displayName, '易方达')
  assert.equal(groups[1].members[0].rating, '夯')
  assert.equal(groups[2].members[0].code, '513500')
  await detail.fire('onLoad', { code: '159696' })
  await detail.fire('onShow')
  assert.equal(detail.state.displayName.value, '纳指ETF易方达')
  assert.equal(h.calls.length, 0)
})
