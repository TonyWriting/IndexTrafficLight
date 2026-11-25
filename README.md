# ETF 溢价率历史复盘

优先使用采集的 IOPV，缺少时使用净值模拟记录，展示 17 只场内 ETF 的历史溢价率、分位和曲线。范围为 12 只纳斯达克100 ETF、景顺长城纳指科技 ETF（159509），以及博时（513500）、南方（513650）、国泰（159612）、华夏（159655）4 只标普500 ETF；基金配置见 [config.py](backend/shared/config.py)。

## 计算口径

对同一个 A 股交易日 D，有有效 IOPV 时，使用同次采集的成交价和 IOPV；否则使用此前保存的 D 日净值模拟记录。两者都没有时跳过，不沿用其他交易日的记录。

```text
溢价率 = D 日场内收盘价 / 参考净值 - 1
```

净值模拟部分使用 D 日开盘前最近一次美股收盘对应日期 U 的正式单位净值。缺少 U 日净值就跳过，不填零、不插值、不沿用更早净值。例如 2026-06-22 使用 06-18 净值；2026-10-08 缺少所需的 10-07 净值，模拟记录跳过。

净值模拟部分是事后近似值，未逐日核对官方历史 IOPV、汇率费用差异和净值首次披露时间。

净值模拟历史工作簿位于 `C:\MarkDowns\Projects\IndexTrafficLight`：

- `纳指13只ETF_净值模拟IOPV溢价率_20251017-20261016.xlsx`，覆盖 2025-10-17 至 2026-10-16。
- `标普500四只ETF_净值模拟IOPV溢价率_20251020-20261019.xlsx`，覆盖 2025-10-20 至 2026-10-19。

## 数据管理

```powershell
cd C:\Projects\IndexTrafficLight\backend
pip install -r requirements.txt
$workbook = 'C:\MarkDowns\Projects\IndexTrafficLight\标普500四只ETF_净值模拟IOPV溢价率_20251020-20261019.xlsx'
python cli.py import-excel --file $workbook --all --dry-run
python cli.py import-excel --file $workbook --all
python cli.py verify-excel --file $workbook
python cli.py dashboard
python cli.py query 513500 --days 365 --limit 10
```

`reset-history` **直接删除四张 Excel 相关表的全部实体，不备份，保留表本身**，不清空独立采集的 `QDIIEtfIopvHistory`。执行前须保证没有其他写入程序运行。

`import-excel` 先检查整份工作簿的基金范围、日期、净值日期批注、数值、公式和跳过记录。工作簿可以只包含已配置基金中的一部分。`--all` 按 Excel 总览顺序逐只导入；`--code` 只导入指定基金。每只写完即读回核对，失败停止；同一基金可重复执行，不产生重复记录。

仅导入 Excel 保留的交易日。价格按 D 日存储，净值按 U 日去重存储，溢价按 D 日存储。`verify-excel` 只核对工作簿所含基金的分区，检查三张历史表中的日期和数值，其他基金不受影响。最后执行 `dashboard` 生成首页快照。

命令报告位于 `backend/reports/`，包含 Excel 文件哈希、数量和执行时间；该目录不提交、不部署。

## 存储与 API

使用 Azure Table Storage，通过环境变量 `AZURE_STORAGE_CONNECTION_STRING` 连接；本地 CLI 也会读取未提交的 `backend/local.settings.json`。

| 表 | 内容 |
| --- | --- |
| QDIIEtfPriceHistory | Excel 中保留的收盘价 |
| QDIIEtfNavHistory | 实际使用的正式净值，按净值日期去重 |
| QDIIEtfPremiumHistory | 净值模拟 IOPV 的估算溢价率 |
| QDIIEtfDashboardSnapshot | 最新首页快照，保留一条 |
| QDIIEtfIopvHistory | 实际采集的每日 IOPV 与成交价 |

历史表使用基金代码作为 `PartitionKey`、对应日期的 `YYYYMMDD` 作为 `RowKey`。

```text
GET /api/dashboard
GET /api/etfs
GET /api/etfs/history?code=159509&start=2025-10-17&end=2026-10-16
GET /api/review-mode
```

历史 API 按日期合并两种来源，同一天只返回一条。IOPV 记录包含 `iopv`，`nav`、`nav_date` 为 `null`，`premium_basis="iopv"`；净值模拟记录包含 `nav`、`nav_date`，`iopv=null`，`premium_basis="nav_proxy_iopv"`。两者均包含 `date`、`close`、`premium_rate`。`premium_rate` 存小数，前端显示百分比。

`QDIIEtfPremiumHistory` 保存 Excel 的净值模拟记录；IOPV 优先级在读取时应用，采集数据不会覆盖这份模拟历史。

首页从快照读取，不在请求时计算；没有快照时返回 503。观察区间为 `3m`、`6m`、`1y`，均按最新有效记录向前平移自然月。历史分位采用所选区间内小于等于当前溢价率的记录占比，状态阈值为 P10、P30、P70、P90。

首页纳斯达克100组的固定顺序和个人评级配置在 [etfDisplay.ts](frontend/src/config/etfDisplay.ts)，均沿用“从夯到拉”文章，易方达、博时排在第一行。切换区间不会改变排列；溢价状态随数据变化。超过 2 只基金的分组默认折叠，仅显示指数标题栏，点击三角展开；2 只及以下直接显示。景顺 159509 属于单独的纳指科技组，未配置该项评级。

标普500组按《全部 5 只场内标普500，从夯到拉》的 ETF 顺序排列：博时“夯”、南方“顶级”、国泰“人上人”、华夏“NPC”。易方达 161125 是 LOF，未纳入本项目的 ETF 清单。该组同样默认折叠，位于两个纳指组之后。

## IOPV 定时采集

北京时间每天 **15:30、16:30、18:30** 触发，Azure UTC cron 为 `0 30 7,8,10 * * *`。先批量请求腾讯，首次失败后最多重试 5 次，每次间隔 10 秒；未取得有效数据的基金再切换东方财富，同样首次加 5 次重试。单次 HTTP 超时 10 秒；已成功的基金不重复请求。

`QDIIEtfIopvHistory` 每只基金、每个行情日期只保留一条。字段为 `date_str`、`close`、`iopv`、`source`、`quote_at_bj`、`fetched_at_bj`；主键是基金代码和行情日期。后一次成功覆盖前一次，失败不清空已有记录。行情时间和采集时间分别记录，行情时间不代表 IOPV 独立更新时间。

周末及北京时间 15:30 前跳过；其他时段只接收当天 15:00 后的有效行情。休市返回的旧日期、缺失字段、无效数值都不会写成当天数据。成功写入后重建首页快照。

```powershell
python cli.py collect-iopv --dry-run
python cli.py collect-iopv
python cli.py collect-iopv --code 513500 513650 159612 159655
```

`--dry-run` 只采集和输出报告，不写入数据库。`--code` 可限定本次采集范围；定时任务始终采集全部已配置基金。IOPV 采集代码见 [iopv.py](backend/shared/iopv.py)。

## 开发与部署

```powershell
cd C:\Projects\IndexTrafficLight\backend
python -m unittest discover -s tests -v
func start
func azure functionapp publish underlamp

cd C:\Projects\IndexTrafficLight\frontend
npm install
npm test
npm run type-check
npm run dev:h5
npm run build:h5
npm run build:mp-weixin
```

前端使用 uni-app、Vue 3、TypeScript。`VITE_API_BASE_URL` 设置后端地址，`VITE_USE_MOCK=true` 可使用从上述 Excel 导出的本地数据。本地和生产配置均通过 `VITE_DISABLE_CACHE=false` 启用一小时缓存；设置为 `true` 会关闭并清理数据缓存。基金清单变化时增加 `CACHE_VERSION`，使旧缓存失效。

`REVIEW_MODE_ENABLED` 控制现有小程序审核展示模式。后端包含 HTTP 接口及 `collect_daily_iopv` 定时任务；部署并启动 Function App 后才会定时执行。微信小程序构建产物位于 `frontend/dist/build/mp-weixin`，通过微信开发者工具上传发布。
