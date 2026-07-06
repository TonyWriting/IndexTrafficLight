# QDII ETF 溢价监控

一个用于盘后观察 QDII ETF 场内价格相对基金净值 NAV 贵不贵的微信小程序。

它关注的的问题是：

```text
场内 ETF 收盘价相对基金单位净值贵了多少？
```

项目使用交易所未复权日 K 收盘价和基金公司披露的单位净值做日期匹配，计算历史收盘溢价率，并在前端展示历史分位、溢价状态和区间曲线。

## 功能特点

- 首页按跟踪指数分组展示 QDII ETF 溢价状态
- 支持近 3 月、近 1 年、近 3 年三个观察区间
- 用单只 ETF 自身历史分布计算当前溢价率分位
- 详情页展示溢价率曲线、均值、中位数和分位参考线
- 后端定时刷新最近数据，补齐 QDII NAV 延迟披露
- 首页 dashboard 使用后端预计算快照，避免首屏请求完整历史
- 前端采用 cache-first 策略，并按后端刷新时刻自动失效
- 支持 mock 模式，方便前端独立开发

## 快速开始

### 前端

```powershell
cd frontend
npm install
npm run dev:h5
npm run dev:mp-weixin
```

当 `VITE_API_BASE_URL` 为空，并且 `VITE_USE_MOCK` 没有显式设置为 `false` 时，前端会自动使用 `frontend/src/mock/` 中的数据。

### 后端

```powershell
cd backend
pip install -r requirements.txt
func start
```

常用 CLI：

```powershell
# Backfill one ETF
python cli.py backfill --code 159509

# Refresh recent records, useful for delayed QDII NAV updates
python cli.py refresh --code 159509 --days 7

# Query recent premium records
python cli.py query 159509 --days 30 --limit 10

# Build the latest homepage dashboard snapshot
python cli.py dashboard
```

## 环境变量

### 后端

`AZURE_STORAGE_CONNECTION_STRING` 用于连接 Azure Table Storage。

```powershell
$env:AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=<account>;AccountKey=<key>;EndpointSuffix=core.windows.net"
```

### 前端

`VITE_API_BASE_URL` 指向后端 API base URL。

```text
VITE_API_BASE_URL=http://localhost:7071
```

`VITE_USE_MOCK` 控制是否使用 mock 数据。

```text
VITE_USE_MOCK=false
```

`VITE_DISABLE_CACHE` 用于调试时关闭本地缓存读写。

```text
VITE_DISABLE_CACHE=true
```

Vite 不会热更新 `.env*` 文件变更。修改前端环境变量后，需要重启前端 dev server。

## 技术栈

- 前端：uni-app、Vue 3、TypeScript、Vite、微信小程序、H5
- 后端：Azure Functions、Python 3.12、v2 programming model
- 存储：Azure Table Storage
- 数据抓取：AKShare，腾讯日 K 作为场内价格备用源

## 项目结构

```text
IndexTrafficLight/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── index/             # ETF premium dashboard
│   │   │   └── detail/            # ETF premium history detail
│   │   ├── components/
│   │   │   ├── EtfCard.vue
│   │   │   ├── EtfMiniTile.vue
│   │   │   ├── EtfGroupHeader.vue
│   │   │   └── PremiumChart.vue
│   │   ├── api/
│   │   │   ├── index.ts           # API wrapper, request dedupe, prefetch
│   │   │   └── cache.ts           # Local cache management
│   │   ├── mock/
│   │   ├── utils/
│   │   │   └── premium.ts         # Formatting, percentile, range statistics
│   │   └── types/
│   └── package.json
├── backend/
│   ├── function_app.py            # Timer and HTTP triggers
│   ├── cli.py                     # Backfill, refresh, query, snapshot generation
│   ├── shared/
│   │   ├── config.py              # Tracked ETF configuration
│   │   ├── data_fetcher.py        # Price and NAV fetching
│   │   ├── dashboard.py           # Dashboard snapshot generation
│   │   ├── pipeline.py            # Fetch, merge, premium calculation
│   │   └── storage.py             # Azure Table Storage access
│   ├── requirements.txt
│   └── host.json
└── README.md
```

## 跟踪标的

| 场内代码 | 展示名 | 跟踪指数 |
| --- | --- | --- |
| `159509` | 纳指科技ETF景顺 | 纳斯达克科技市值加权指数 |
| `513100` | 纳指ETF国泰 | 纳斯达克100指数 |
| `513300` | 纳斯达克ETF华夏 | 纳斯达克100指数 |
| `159501` | 纳指ETF嘉实 | 纳斯达克100指数 |
| `159696` | 纳指ETF易方达 | 纳斯达克100指数 |
| `159659` | 纳斯达克100ETF招商 | 纳斯达克100指数 |
| `159941` | 纳指ETF广发 | 纳斯达克100指数 |
| `513500` | 标普500ETF博时 | 标普500指数 |
| `513650` | 标普500ETF南方 | 标普500指数 |
| `513310` | 中韩半导体ETF华泰柏瑞 | 中证韩交所中韩半导体指数 |

## 计算口径

本项目只做盘后口径。它使用交易所日 K 收盘价和基金公司披露的单位净值做日期匹配，不做盘中 IOPV / IIV 实时溢价估算。

所有标的统一使用同一个公式：

```text
场内未复权收盘价 / 当日基金单位净值 NAV - 1
```

`close` 使用场内实际收盘价，不做复权处理。复权价格适合分析长期持有收益，但不适合和当日单位净值直接相除计算收盘溢价率。

## 数据源

| 数据项 | 数据源 | AKShare 调用 | 用途 |
| --- | --- | --- | --- |
| 场内未复权收盘价 | 东方财富 ETF 日 K，腾讯不复权日 K 作为备用源 | `ak.fund_etf_hist_em(symbol=code, period="daily", adjust="")` | 溢价率分子 |
| 基金单位净值 | 天天基金 | `ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")` | 溢价率分母 |

实现采用日期内连接：只有同一天同时存在收盘价和 NAV 时，才生成一条溢价率记录。

QDII ETF 的 NAV 通常会滞后披露，所以最近 1-2 个交易日可能暂时缺失。后端定时任务会回扫最近 7 个自然日，用来补齐晚间、凌晨或次日上午才披露的 NAV。

## 历史分位

溢价率以小数存储，前端展示为百分比。

历史分位回答的问题是：

```text
当前溢价率高于过去同一观察区间内多少比例的交易日？
```

| 历史分位 | 展示状态 | 含义 |
| --- | --- | --- |
| `>= P90` | 过高 | 当前溢价处在自身历史高位 |
| `P70 ~ P90` | 偏高 | 当前溢价高于中游区间 |
| `P30 ~ P70` | 中游 | 当前溢价接近历史中枢 |
| `P10 ~ P30` | 偏低 | 当前溢价低于中游区间 |
| `< P10` | 过低 | 当前溢价处在自身历史低位 |

观察区间按最新一条有效溢价记录的日期向前平移自然月计算，而不是按设备当天日期计算：

- `3m`：近 3 个自然月
- `1y`：近 12 个自然月
- `3y`：近 36 个自然月

## API

```text
GET /api/dashboard
GET /api/etfs
GET /api/etfs/history?code=159509[&start=2026-01-01&end=2026-05-29]
```

`GET /api/dashboard` 只读取已生成的首页快照，不在请求路径里现场计算。如果 `QDIIEtfDashboardSnapshot` 还没有 `dashboard/latest`，接口会返回 `503`。

`GET /api/etfs/history` 返回单只 ETF 的完整溢价率历史。详情页会基于这份历史数据在前端本地计算均值、中位数和分位线。

## 缓存策略

前端缓存由 `frontend/src/api/index.ts` 和 `frontend/src/api/cache.ts` 管理，缓存落在 `uni.setStorageSync`。

缓存有效性对齐后端刷新时刻。写入后只要跨过后端的下一个数据刷新点，缓存即失效：

```text
北京时间 08:15 / 12:15 / 21:15 / 22:45
```

首页和详情请求采用 cache-first 策略：

- 首页优先读取有效的 dashboard snapshot 缓存
- dashboard 缓存缺失或失效时，再请求 `/api/dashboard`
- dashboard 返回后，前端会在后台低优先级预取各 ETF 的详情历史
- 详情页优先读取单只 ETF 的历史缓存
- 如果缓存不存在，当前 ETF 的历史请求会提升为前台优先级立即执行
- 如果后台预取已经在请求同一只 ETF，前台会复用同一个请求

同一类后端请求使用 `singleFlight` 去重。并发请求 `/api/dashboard` 时只发出一次首页 API；并发请求同一只 ETF 的 history 时只发出一次历史 API。

## 后端任务

Azure Functions Timer cron 使用 UTC 时间：

```text
0 0 0,4,13 * * *  # 北京时间 08:00 / 12:00 / 21:00
0 30 14 * * *     # 北京时间 22:30
```

每次触发都会对配置中的全部跟踪 ETF 抓取最近 7 个自然日的收盘价和 NAV，计算 `premium_rate` 后写入 Storage。所有 ETF 刷新完成后，任务会预计算首页需要的近 3 月、近 1 年和近 3 年统计，并将结果写入 dashboard snapshot。

## 存储表

后端使用四张 Azure Table Storage 表：

| 表名 | 用途 |
| --- | --- |
| `QDIIEtfPriceHistory` | 原始场内日 K 数据 |
| `QDIIEtfNavHistory` | 原始基金单位净值数据 |
| `QDIIEtfPremiumHistory` | 计算后的溢价率历史 |
| `QDIIEtfDashboardSnapshot` | 首页预计算快照 |

`QDIIEtfDashboardSnapshot` 只服务首页首屏，不承载详情页分析。它保留首页卡片和分组头需要的信息：当前溢价率、数据日期、历史分位、展示状态，以及同组 ETF 的当前溢价率范围。

## 部署

### Azure Functions

```powershell
cd backend
func azure functionapp publish <function-app-name>
```

首次部署支持 `/api/dashboard` 的版本后，需要先生成一次首页快照，避免前端请求 `/api/dashboard` 时遇到 `503`：

```powershell
cd backend
python cli.py dashboard
```

这条命令只基于已经写入 Azure Table Storage 的 `QDIIEtfPremiumHistory` 生成首页快照，不会重新抓取 AKShare 数据。

### 微信小程序

```powershell
cd frontend
npm run build:mp-weixin
```

用微信开发者工具导入 `dist/build/mp-weixin` 后上传。

## 免责声明

本项目是基于公开信息和项目自身计算逻辑生成的数据整理与展示工具，不保证数据的准确性、完整性和及时性。内容仅供学习研究和信息参考，不构成任何投资建议，也不应作为买入或卖出依据。
