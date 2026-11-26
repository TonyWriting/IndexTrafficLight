const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const ts = require('typescript')

const SRC = path.resolve(__dirname, '../src')

function load(file) {
  if (!path.extname(file)) file = fs.existsSync(file + '.ts') ? file + '.ts' : path.join(file, 'index.ts')
  const { outputText } = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  })
  const module = { exports: {} }
  new Function('module', 'exports', 'require', outputText)(
    module, module.exports, id => load(path.resolve(path.dirname(file), id)),
  )
  return module.exports
}

const { filterByRange, formatPremiumRate, percentileRank, summarizePremium } = load(path.join(SRC, 'utils/premium'))
const { PREMIUM_STATUS_CONFIG } = load(path.join(SRC, 'types'))

const record = (date, premium_rate = 0.05) => ({
  date, close: 2.1, nav: 2, nav_date: date, iopv: null, premium_basis: 'nav_proxy_iopv', premium_rate,
})

// n daily records whose latest premium ranks k-th from the bottom.
function series(n, k) {
  const rates = Array.from({ length: n }, (_, i) => i + 1).filter(value => value !== k).concat(k)
  return rates.map((rate, i) => record(`2026-10-${String(i + 1).padStart(2, '0')}`, rate / 100))
}

test('status thresholds and labels match the backend dashboard', () => {
  // Keep this table identical to backend/tests/test_dashboard.py.
  for (const [n, k, status, label] of [
    [11, 1, 1, '过低'], [10, 1, 2, '偏低'], [10, 2, 2, '偏低'], [10, 3, 3, '中游'],
    [10, 6, 3, '中游'], [10, 7, 4, '偏高'], [10, 8, 4, '偏高'], [10, 9, 5, '过高'],
  ]) {
    const summary = summarizePremium(series(n, k), '3m')
    assert.equal(summary.status, status, `percentile ${k}/${n}`)
    assert.equal(PREMIUM_STATUS_CONFIG[summary.status].label, label)
  }
  assert.equal(percentileRank(0.2, [0.1, 0.2, 0.2, 0.3]), 0.75)
})

test('detail statistics report the mean and interpolated median', () => {
  const { mean, median } = summarizePremium(series(10, 10), '3m')
  assert.ok(Math.abs(mean - 0.055) < 1e-12)
  assert.ok(Math.abs(median - 0.055) < 1e-12)
})

test('range filter drops invalid records and clamps the cutoff to month end', () => {
  // The invalid latest record must not move the cutoff, which clamps to February 29.
  const records = ['2024-02-28', '2024-02-29', '2024-08-31'].map(day => record(day))
  records.push(record('2024-09-30', NaN))
  assert.deepEqual(filterByRange(records, '6m').map(row => row.date), ['2024-02-29', '2024-08-31'])
})

test('premium rates show an explicit sign and a placeholder for missing values', () => {
  assert.deepEqual(
    [0.1708, -0.0123, 0, null, NaN].map(value => formatPremiumRate(value)),
    ['+17.08%', '-1.23%', '0.00%', '--', '--'],
  )
})
