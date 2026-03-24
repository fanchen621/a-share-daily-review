# A股全时段智能复盘系统 v6

> OpenClaw 自动化 A 股复盘分析技能，覆盖盘前→午盘→收盘三个时段，具备量化策略学习和盘感成长能力。

## ✨ 核心特色

- **🕐 三时段覆盖**: 08:00盘前速递 → 12:00午盘策略 → 17:30收盘复盘
- **🔌 纯API驱动**: 不依赖搜索引擎，通过稳定公共API获取数据
- **📊 全维度分析**: 美股/亚太/大宗商品/A股/龙虎榜/北向资金
- **🤖 量化策略学习**: 追踪龙虎榜中量化营业部的策略模式
- **🧠 盘感自适应**: lessons.md 积累经验，每次复盘自动更新分析侧重
- **📱 钉钉适配**: 列表布局，手机端友好

## 🔧 数据源

```
纯API数据源:
  ├─ 腾讯行情API (qt.gtimg.cn) → A股指数/美股/商品期货 ✅
  ├─ 财联社API (cls.cn) → 电报/快讯 ✅
  ├─ 东方财富数据中心 (datacenter-web) → 龙虎榜/北向资金 ✅
  └─ 汇率API (exchangerate-api) → 主要货币汇率 ✅
```

**详细覆盖:**
- A股: 上证/深证/创业板/科创50/沪深300/上证50
- 美股: 道琼斯/纳斯达克/标普500 + 英伟达/特斯拉/苹果/微软
- 商品: 纽约金/纽约银/WTI原油
- 亚太: 恒生指数期货
- 龙虎榜: 每日上榜+席位明细
- 北向资金: 近5日净流入

## 📁 文件结构

```
a-share-daily-review/
├── SKILL.md                    # 技能核心指令
├── README.md                   # 本文件
├── lessons.md                  # 盘感数据库模板
├── scripts/
│   └── a_share_scraper.py      # 数据采集脚本 v6 (纯API版)
├── data/
│   ├── YYYYMMDD_premarket.md   # 盘前报告
│   ├── YYYYMMDD_midday.md      # 午盘报告
│   └── YYYYMMDD_closing.md     # 收盘报告
└── references/
    └── dingtalk_format.md      # 钉钉格式参考
```

## 🚀 快速开始

```bash
# 盘前速递
python3 scripts/a_share_scraper.py --mode premarket

# 午盘策略
python3 scripts/a_share_scraper.py --mode midday

# 收盘复盘
python3 scripts/a_share_scraper.py --mode closing

# 全量数据(JSON)
python3 scripts/a_share_scraper.py --mode full --json
```

## ⏰ Cron 定时任务

| 时间 | Cron | 内容 |
|------|------|------|
| 08:00 | `0 8 * * 1-5` | 盘前速递：外盘/大宗/新闻 → 操作方向判断 |
| 12:00 | `0 12 * * 1-5` | 午盘策略：上午数据 + 盘感 → 选股策略 |
| 17:30 | `30 17 * * 1-5` | 收盘复盘：全量数据 → 复盘 + 更新盘感 |

## 📊 报告格式

所有报告采用**钉钉适配的列表格式**：
- ❌ 不使用表格（钉钉不支持）
- ✅ 使用列表 `- **标签**: 值`
- ✅ emoji 分类标识（🔥📈💰⚠️🧠）
- ✅ 自动分析：脚本生成基础分析，AI补充深度解读

## 🧠 盘感自适应

`data/lessons.md` 是系统的大脑：
- 板块联动规律（传导链+时滞）
- 情绪周期特征（冰点/修复/发酵/高潮/退潮）
- 量化营业部策略模式
- 复盘判断修正

每次收盘复盘必须更新 lessons.md，这是系统成长的唯一途径。

## v6 架构变更

相比 v5（依赖 mimo_web_search），v6 改为纯API架构：
- 腾讯行情API替代 mimo_web_search 获取美股/商品/期货数据
- 东方财富数据中心API获取龙虎榜/北向资金
- 脚本直接生成完整报告，不再需要AI手动搜索填充
- 更稳定、更快速、不消耗搜索配额
