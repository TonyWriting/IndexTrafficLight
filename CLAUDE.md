# 指数红绿灯 - 微信小程序

## 项目概述

指数红绿灯是一个微信小程序 dashboard，用 5 级红绿灯展示 ETF 基金对应指数的高低估状态，面向长期投资者。数据每日更新。

## 技术栈

- **前端**：uni-app (Vue 3 + TypeScript + Vite) → 微信小程序
- **后端**：Azure Functions (Python 3.11+, v2 programming model)
- **存储**：Azure Table Storage（通过环境变量 `AZURE_STORAGE_CONNECTION_STRING` 连接）

## 项目结构

```
IndexTrafficLight/
├── frontend/                      # uni-app 微信小程序
│   ├── src/
│   │   ├── pages/
│   │   │   ├── index/            # 首页 Dashboard
│   │   │   └── detail/           # 指数估值详情页
│   │   ├── components/
│   │   │   ├── IndexCard.vue     # 指数卡片（含 5 级红绿灯）
│   │   │   └── ValuationChart.vue # 估值历史图表
│   │   ├── api/
│   │   │   ├── index.ts          # 后端 API 调用封装
│   │   │   └── cache.ts          # 本地缓存管理（30 分钟过期）
│   │   ├── mock/                 # Mock 数据（开发用）
│   │   │   ├── indices.json      # 模拟首页指数列表
│   │   │   └── history.json      # 模拟历史估值数据
│   │   ├── utils/
│   │   │   └── valuation.ts      # 前端百分位计算 + 红绿灯判定
│   │   ├── types/                # TypeScript 类型定义
│   │   ├── App.vue
│   │   ├── main.ts
│   │   ├── pages.json
│   │   ├── manifest.json
│   │   └── uni.scss
│   ├── package.json
│   └── vite.config.ts
├── backend/                       # Azure Functions Python
│   ├── function_app.py            # Timer + HTTP 触发器（线上用）
│   ├── cli.py                     # CLI 入口（本地批量更新用）
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── data_fetcher.py       # CSI API + 蛋卷基金 + AKShare + yfinance 数据抓取
│   │   ├── valuation.py          # PE 百分位计算 + 红绿灯判定
│   │   ├── storage.py            # Azure Table Storage 读写
│   │   └── config.py             # 指数配置（代码、数据源、阈值）
│   ├── requirements.txt
│   ├── host.json
│   └── local.settings.json
├── CLAUDE.md
└── .gitignore
```

## 指数与数据源

### 沪深300 (000300)

| 数据项 | 数据源 | 调用方式 | 历史 | 频率 | 用途 |
|--------|--------|---------|------|------|------|
| PE-TTM | CSI API | `GET csindex.com.cn/csindex-home/perf/index-perf?indexCode=000300&startDate=...&endDate=...` → `peg` 字段 | 15年 ~3918条 | 日 | **红绿灯主指标**（历史曲线，末端即当前值） |
| PB | AKShare 乐咕乐股 | `ak.stock_index_pb_lg("沪深300")` | 20年 5000+条 | 日 | 辅助展示 |

### 东证红利低波 (931446)

全称：中证东方红红利低波动指数（CSI Dongfanghong Dividend Low Volatility Index）

| 数据项 | 数据源 | 调用方式 | 历史 | 频率 | 用途 |
|--------|--------|---------|------|------|------|
| PE-TTM | CSI API | 同上, `indexCode=931446` | 15年 ~3917条 | 日 | **红绿灯主指标**（历史曲线，末端即当前值） |
| 股息率 | AKShare CSI Excel | `ak.stock_zh_index_value_csindex("931446")` | 初始~20天，每日增长 | 日 | 辅助曲线（持续积累） |

### 标普500

全称：标准普尔500指数（S&P 500 Index）

| 数据项 | 数据源 | 调用方式 | 历史 | 频率 | 用途 |
|--------|--------|---------|------|------|------|
| PE | 蛋卷基金 API | `GET danjuanapp.com/djapi/index_eva/pe_history/SP500?day=all` | 10年 516条 | 周 | **红绿灯主指标**（历史曲线，末端即当前值） |
| PB | 蛋卷基金 API | `GET danjuanapp.com/djapi/index_eva/pb_history/SP500?day=all` | 10年 516条 | 周 | 辅助展示 |

### CSI API 说明

- **接口**：`GET https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode={code}&startDate={YYYYMMDD}&endDate={YYYYMMDD}`
- **`peg` 字段**：滚动市盈率（PE-TTM），非 PEG ratio
- **CSI Excel 列**：市盈率1（总股本）、市盈率2（计算用股本）、股息率1（总股本）、股息率2（计算用股本）
- 数据在交易日当天或次日更新

## 红绿灯规则（5 级）

基于近 10 年 PE 百分位：

| 等级 | 颜色 | PE 百分位 | 含义 |
|------|------|----------|------|
| 1 | 深绿 | < 10% | 极度低估 |
| 2 | 浅绿 | 10%~30% | 低估 |
| 3 | 黄色 | 30%~70% | 适中 |
| 4 | 浅红 | 70%~90% | 高估 |
| 5 | 深红 | > 90% | 极度高估 |

## 存储设计

只使用一张表 **ValuationHistory**：
- **PartitionKey** = 指数代码（`000300`、`931446`、`SP500`）
- **RowKey** = 日期（`YYYYMMDD`，如 `20260213`）
- 字段：pe, close, dividend_yield（红利指数）, pb（宽基指数）
- 查询示例：`PartitionKey eq '000300' and RowKey ge '20160101'`

百分位计算和红绿灯判定由**前端**完成，用户可自选时间范围（10/15年）。

## Frontend 设计

### 详情页双图设计

每个指数详情页包含两张图，共享时间范围选择器（10Y / 15Y）：
- **图1**：PE + 收盘价（双Y轴，蓝色PE + 橙色价格，含百分位参考线）
- **图2**：辅助指标 + 收盘价（双Y轴）
  - 沪深300 / 标普500：PB + 收盘价
  - 红利低波：股息率 + 收盘价

### 缓存策略（cache.ts）

- 存储：`uni.setStorageSync('valuation_cache', { data, timestamp })`
- 缓存有效期：**30 分钟**
- 启动时：缓存未过期 → 用本地数据；过期 → 请求后端并更新缓存
- 下拉刷新：忽略缓存，强制请求后端
- 请求失败：降级使用过期缓存，提示"数据可能不是最新"

### Mock 模式（mock/valuation.json）

- 环境变量 `VITE_USE_MOCK=true` 切换
- 开发时无需启动后端，直接使用本地 JSON 数据
- Mock 数据结构与后端 API 响应完全一致

## Backend 运行模式

### 本地批量模式（cli.py）

用于初始化历史数据或补数据，与 `function_app.py` 共用 `shared/` 逻辑。

可用的指数代码：`000300`（沪深300）、`931446`（红利低波）、`SP500`（标普500）

```bash
# 回填最近10年数据（默认，所有指数）
python cli.py backfill

# 回填最近20年
python cli.py backfill --days 7300

# 只回填某个指数，最近30天
python cli.py backfill --index 000300 --days 30

# 指定截止日期（默认今天）
python cli.py backfill --days 3650 --end 2025-01-01

# 更新当天数据（调试用）
python cli.py update-today

# 查询 Storage 中的数据（默认最近30天）
python cli.py query 000300
python cli.py query SP500 --days 60
```

### 纯数据验证（不需要 Azure Storage）

不写入 Storage，只验证数据抓取和估值计算是否正常：

```bash
cd backend
python -c "
from shared.valuation import evaluate_index
for code in ['000300', '931446', 'SP500']:
    r = evaluate_index(code)
    print(f'{r[\"name\"]}: PE={r[\"pe\"]}, 百分位={r[\"pe_percentile\"]*100:.1f}%, {r[\"traffic_light_name\"]}')
"
```

### 线上定时模式（function_app.py）

Timer Trigger 每日两次：
- 10:00 UTC（18:00 北京时间）：A 股收盘后
- 14:00 UTC（22:00 北京时间）：二次更新确保数据完整

流程：抓取各数据源 → 存入 Azure Table Storage（ValuationHistory 表）

HTTP Trigger：
- `GET /api/indices` → 返回所有指数列表及最新数据点（首页用）
- `GET /api/history?index=000300[&start=2020-01-01&end=2026-02-13]` → 返回单个指数完整 PE 历史（详情页用）

## 环境变量

### `AZURE_STORAGE_CONNECTION_STRING`

后端连接 Azure Table Storage 的凭证。

```powershell
# PowerShell（当前会话）
$env:AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"

# PowerShell（永久，用户级别）
[Environment]::SetEnvironmentVariable("AZURE_STORAGE_CONNECTION_STRING", "连接字符串", "User")
```

```bash
# Bash / Git Bash
export AZURE_STORAGE_CONNECTION_STRING="连接字符串"
```

- `cli.py` 直接读取系统环境变量
- `func start` 从 `backend/local.settings.json` 加载
- 云端通过 Azure Function App 的 Application Settings 配置

## 本地开发

### 前端

```bash
cd frontend && npm install
npm run dev:h5             # 浏览器预览
npm run dev:mp-weixin      # 微信小程序（需微信开发者工具导入 dist/dev/mp-weixin）
```

Mock 模式：当 `VITE_API_BASE_URL` 为空时自动启用，无需后端。
连接真实后端：修改 `frontend/.env.development`：
```
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://localhost:7071
```

### 后端

```bash
cd backend && pip install -r requirements.txt
func start                 # 启动本地 Azure Functions（http://localhost:7071）
python cli.py backfill     # 批量回填数据
python cli.py query 000300 # 查看 Storage 数据
```

## 部署

### 部署 Azure Function

**前置工具：**
```bash
npm install -g azure-functions-core-tools@4 --unsafe-perm true
az login
```

**创建 Function App（首次）：**
1. Azure Portal → 搜索 "Function App" → 创建
2. Runtime: Python 3.11, Plan: Consumption
3. Storage account: 选已有的 storage account

**配置环境变量：**
```bash
az functionapp config appsettings set \
  --name <function-app名称> \
  --resource-group <资源组名> \
  --settings AZURE_STORAGE_CONNECTION_STRING="连接字符串"
```

**部署代码：**
```bash
cd backend
func azure functionapp publish <function-app名称>
```

部署成功后 HTTP API 地址为：
- `https://<function-app名称>.azurewebsites.net/api/indices`
- `https://<function-app名称>.azurewebsites.net/api/history?index=000300`

### 发布微信小程序

```bash
cd frontend
npm run build:mp-weixin    # 构建生产版本
```

用微信开发者工具导入 `dist/build/mp-weixin`，点击"上传"发布。
生产环境配置在 `frontend/.env.production`：
```
VITE_USE_MOCK=false
VITE_API_BASE_URL=https://<function-app名称>.azurewebsites.net
```

## 开发规范

- 前端：Vue 3 Composition API + `<script setup>` 语法，TypeScript
- 后端：Python type hints，async/await
- 代码和注释使用英文，用户界面使用中文
- 使用中文回答问题

## 关键依赖

- **后端**：akshare, yfinance, beautifulsoup4, azure-functions, azure-data-tables, requests, pandas
- **前端**：@dcloudio/uni-app, vue 3, typescript

## 待办（暂缓）

- 纳斯达克100：无免费历史 PE 数据源，待找到合适数据源后补充
- 恒生港股通中国央企红利 (HSSCSOY)：恒生指数公司编制，PE/股息率数据需付费订阅（HSI API 返回 401），待找到免费数据源后补充
