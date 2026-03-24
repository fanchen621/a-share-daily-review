# A股全时段智能复盘系统 v5

> OpenClaw 自动化 A 股复盘分析技能，覆盖盘前→午盘→收盘三个时段，具备量化策略学习和盘感成长能力。

## ✨ 核心特色

- **🕐 三时段覆盖**: 08:00盘前速递 → 12:00午盘策略 → 17:30收盘复盘
- **🔍 mimo_web_search 驱动**: 全量数据通过搜索获取，稳定可靠
- **📊 全维度分析**: 美股/亚太/大宗/比特币/社交言论/A股/板块/资金/龙虎榜
- **🤖 量化策略学习**: 追踪龙虎榜中量化营业部的策略模式
- **🧠 盘感自适应**: lessons.md 积累经验，每次复盘自动更新分析侧重
- **📱 钉钉适配**: 列表布局，手机端友好，每组数据+分析

## 🔧 数据源

```
稳定数据源:
  ├─ 东方财富 ulist API → 大盘指数 ✅
  ├─ 财联社 API → 电报/快讯 ✅
  └─ mimo_web_search → 美股/亚太/大宗/比特币/A股详情/龙虎榜/北向 ✅
```

## 📁 文件结构

```
a-share-daily-review/
├── SKILL.md                    # 技能核心指令（三时段+mimo_web_search）
├── README.md                   # 本文件
├── HOW_TO_USE.md               # 深度使用指南
├── lessons.md                  # 盘感数据库模板
├── requirements.txt            # Python 依赖（仅requests）
├── scripts/
│   └── a_share_scraper.py      # 数据采集脚本 v5
├── data/
│   ├── YYYYMMDD_premarket.md   # 盘前报告
│   ├── YYYYMMDD_midday.md      # 午盘报告
│   └── YYYYMMDD_closing.md     # 收盘报告
└── references/
    ├── dingtalk_format.md      # 钉钉格式参考
    └── dingtalk-message-format-guide.md
```

## 🚀 快速开始

```bash
# 盘前速递
python3 scripts/a_share_scraper.py --mode premarket

# 午盘策略
python3 scripts/a_share_scraper.py --mode midday

# 收盘复盘
python3 scripts/a_share_scraper.py --mode closing
```

## ⏰ Cron 定时任务

| 时间 | Cron | 内容 |
|------|------|------|
| 08:00 | `0 8 * * 1-5` | 盘前速递：外盘/大宗/比特币/新闻 → 操作方向判断 |
| 12:00 | `0 12 * * 1-5` | 午盘策略：上午数据 + 盘感 → 选股策略 |
| 17:30 | `30 17 * * 1-5` | 收盘复盘：全量数据 → 复盘 + 更新盘感 |

每个任务执行流程：
1. 运行 `a_share_scraper.py` 生成报告框架（含占位符）
2. 用 `mimo_web_search` 搜索所有缺失数据
3. 读取 `lessons.md` 获取盘感经验
4. 综合分析，生成完整报告
5. 收盘任务额外更新 `lessons.md`

## 📊 报告格式

所有报告采用**钉钉适配的列表格式**：
- ❌ 不使用表格（钉钉不支持）
- ✅ 使用列表 `- **标签**: 值`
- ✅ 每组数据后附 `> 📊 分析` 段落
- ✅ emoji 分类标识（🔥📈💰⚠️🧠）
- ✅ 手机端字号适配

## 🧠 盘感自适应

`data/lessons.md` 是系统的大脑：
- 板块联动规律（传导链+时滞）
- 情绪周期特征（冰点/修复/发酵/高潮/退潮）
- 量化营业部策略模式
- 复盘判断修正
- 有效信号总结

每次收盘复盘必须更新 lessons.md，这是系统成长的唯一途径。

## ⚠️ v5 架构说明

v5 采用 **scraper + mimo_web_search 混合架构**：
- scraper 只负责能稳定连接的 API（东方财富指数 + 财联社新闻）
- 其余所有数据（美股/大宗商品/比特币/A股详情/板块/龙虎榜等）通过 mimo_web_search 搜索获取
- 这种架构在 API 不稳定的环境下最可靠
