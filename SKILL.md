---
name: a-share-daily-review
description: >
  A股全时段智能复盘系统 v7。覆盖盘前速递、午盘策略选股、收盘全量复盘三大场景。
  混合数据源: 腾讯行情API + 新浪期货API + 财联社 + 东方财富数据中心。
  数据覆盖率: 美股(指数+7只权重股) + 亚太(日经+恒生+KOSPI*) + 大宗(金/银/WTI/布伦特/碳酸锂*) + 比特币* + 马斯克特朗普* + A股全量(指数+龙虎榜+北向)。
  带*项由mimo_web_search补充，其余全部API直采。
  触发条件: A股、复盘、盘前、午盘、选股、涨停、龙虎榜等关键词。
---

# A股全时段智能复盘系统 v7

## 架构概览

三个定时任务，每个交易日自动执行：

| 时间 | 任务 | 内容 |
|------|------|------|
| 08:00 | 盘前速递 | 外盘/亚太/大宗/比特币/新闻 → 操作方向判断 |
| 12:00 | 午盘策略 | 上午行情+龙虎榜 → 选股建议+操作策略 |
| 17:30 | 收盘复盘 | 全量数据 → 复盘分析+经验更新 |

## 数据源架构

```
API直采（稳定可靠）:
  ├─ 腾讯行情API → A股指数 / 美股指数 / 美股个股 / 纽约金/银/原油 / 恒生期货
  ├─ 新浪期货API → 布伦特原油 / 日经225 / 比特币
  ├─ 财联社API   → 电报/快讯/财经新闻
  ├─ 东方财富数据中心 → 龙虎榜 / 北向资金
  └─ 汇率API      → USD/CNY / USD/JPY / USD/KRW

mimo_web_search补充（运行时搜索，仅5项）:
  ├─ 韩国KOSPI指数
  ├─ 以太坊价格
  ├─ A50期货走势
  ├─ 碳酸锂最新价格
  └─ 马斯克 & 特朗普最新言论
```

## 盘前速递 (08:00)

### 执行流程

```bash
cd ~/.openclaw/skills/a-share-daily-review
python3 scripts/a_share_scraper.py --mode premarket -o data/$(date +%Y%m%d)_premarket.md
```

### 输出内容（钉钉列表格式，每组数据附分析）

- **🇺🇸 隔夜美股**: 三大指数+纳斯达克100 + 英伟达/特斯拉/苹果/微软/谷歌/亚马逊/Meta
- **🌏 亚太市场**: 日经225期货 + 恒生指数期货 + KOSPI(mimo补充)
- **💰 大宗商品**: 纽约金/银 + WTI原油 + 布伦特原油 + 碳酸锂(mimo补充)
- **₿ 加密货币**: 比特币 + 以太坊(mimo补充)
- **🐦 马斯克&特朗普**: mimo补充最新言论
- **💱 汇率**: USD/CNY/JPY/KRW
- **📰 财联社**: 热点关键词自动提取+分析
- **📊 期货信号**: A50期货(mimo补充)
- **🎯 盘前判断**: 综合分析+风险提示

### Cron 配置
```
任务名: a-share-premarket
cron: 0 8 * * 1-5
sessionTarget: isolated
```

**AgentTurn 指令:**
```
执行A股盘前速递:

第一步: 运行scraper生成报告框架
cd ~/.openclaw/skills/a-share-daily-review
python3 scripts/a_share_scraper.py --mode premarket -o data/$(date +%Y%m%d)_premarket.md

第二步: 用 mimo_web_search 搜索以下5项数据(每条都要搜):
1. mimo_web_search: "韩国KOSPI指数 今日行情"
2. mimo_web_search: "以太坊 最新价格"
3. mimo_web_search: "富时A50期货 最新行情 走势"
4. mimo_web_search: "碳酸锂期货 最新价格 走势"
5. mimo_web_search: "马斯克 特朗普 最新言论 消息 今天"

第三步: 读取 data/lessons.md 了解近期盘感

第四步: 综合scraper报告+搜索结果，替换所有{{mimo_web_search:...}}占位符
第五步: 每个数据组补充分析判断段落
第六步: 输出完整盘前速递到 data/YYYYMMDD_premarket.md
```

---

## 午盘策略 (12:00)

### 执行流程

```bash
cd ~/.openclaw/skills/a-share-daily-review
python3 scripts/a_share_scraper.py --mode midday -o data/$(date +%Y%m%d)_midday.md
```

### 输出内容

- **📊 上午行情**: 四大指数+成交额+风格判断+量能分析
- **📰 上午要闻**: 财联社热点关键词
- **🐉 龙虎榜**: 上午上榜个股+机构净买入分析
- **🎯 下午操作建议**: 行情判断+风格判断+热点方向+龙虎榜重点标的

### Cron 配置
```
任务名: a-share-midday
cron: 0 12 * * 1-5
sessionTarget: isolated
```

**AgentTurn 指令:**
```
执行A股午盘策略:

第一步: 运行scraper
cd ~/.openclaw/skills/a-share-daily-review
python3 scripts/a_share_scraper.py --mode midday -o data/$(date +%Y%m%d)_midday.md

第二步: 读取今天的盘前报告 data/YYYYMMDD_premarket.md
第三步: 读取 data/lessons.md

第四步: 综合以上信息:
- 对比上午数据与盘前预判偏差
- 分析上午行情特征(风格/量能/情绪)
- 龙虎榜机构行为分析
- 推荐下午可操作个股，必须包含:
  * 个股名称和代码
  * 详细买入理由(板块逻辑/资金面/技术面)
  * 建议价位和止损位
- 输出到 data/YYYYMMDD_midday.md
```

---

## 收盘复盘 (17:30)

### 执行流程

```bash
cd ~/.openclaw/skills/a-share-daily-review
python3 scripts/a_share_scraper.py --mode closing -o data/$(date +%Y%m%d)_closing.md
```

### 输出内容（钉钉手机完整版）

- **📈 大盘&量能**: 四大指数+全天成交额+量价分析
- **🇺🇸 美股最新**: 指数+权重股
- **🐉 龙虎榜**: 全部上榜+量化席位分析+重点标的
- **🌊 北向资金**: 近5日净流入+趋势分析
- **💰 大宗商品收盘**: 金/银/WTI/布伦特/比特币
- **📰 财联社今日要闻**: 全天新闻汇总
- **🧠 复盘分析**: 量价关系+板块轮动+机构动向
- **🔮 明日关注**: 龙虎榜重点标的+商品趋势+操作建议
- **⚠️ 风险提示**

### Cron 配置
```
任务名: a-share-closing
cron: 30 17 * * 1-5
sessionTarget: isolated
```

**AgentTurn 指令:**
```
执行A股收盘复盘:

第一步: 运行scraper
cd ~/.openclaw/skills/a-share-daily-review
python3 scripts/a_share_scraper.py --mode closing -o data/$(date +%Y%m%d)_closing.md

第二步: 读取盘前和午盘报告
第三步: 读取 data/lessons.md

第四步: 综合以上信息:
- 对比盘前/午盘预判与实际偏差
- 量价关系深度分析
- 板块轮动特征
- 龙虎榜量化席位行为分析
- 北向资金趋势
- 明日预判+操作建议
- 输出到 data/YYYYMMDD_closing.md

第五步: 更新 data/lessons.md:
- 板块联动规律
- 情绪周期特征
- 量化营业部动向
- 判断修正(盘前/午盘偏差)
- 有效信号验证
```

---

## 核心模块：盘感自适应

每次收盘复盘后更新 `data/lessons.md`，形成盘感数据库。

```markdown
# A股复盘经验记录

## 板块联动规律
- 国务院AI政策 → 算力(当日) → 光模块(当日)

## 情绪周期特征
| 日期 | 涨停数 | 最高板 | 跌停数 | 情绪阶段 | 次日验证 |

## 量化营业部策略
| 日期 | 标的 | 席位 | 方向 | 金额 | 次日表现 |

## 判断修正
| 日期 | 预判 | 实际 | 偏差原因 | 教训 |
```

---

## 文件结构

```
a-share-daily-review/
├── SKILL.md                    # 技能核心指令
├── README.md                   # 项目说明
├── lessons.md                  # 盘感数据库模板
├── scripts/
│   └── a_share_scraper.py      # 数据采集 v7 (混合API版)
├── data/
│   ├── YYYYMMDD_premarket.md   # 盘前报告
│   ├── YYYYMMDD_midday.md      # 午盘报告
│   ├── YYYYMMDD_closing.md     # 收盘报告
│   └── lessons.md              # 盘感数据库
└── references/
    └── dingtalk_format.md      # 钉钉格式参考
```

## 关键原则

1. **数据覆盖优先**: API能采的全部采，仅5项用搜索补充
2. **钉钉适配**: 列表格式、不用表格、每组附分析
3. **盘感是核心**: lessons.md 每次收盘必须更新
4. **可操作性**: 给出具体标的+价位+止损，不是空谈
