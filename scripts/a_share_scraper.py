#!/usr/bin/env python3
"""
A股全时段数据采集脚本 v5 - 混合版
策略: 东方财富稳定API(指数+北向) + 财联社新闻 + mimo_web_search补充其余
此服务器对大部分金融API连接不稳定，仅保留验证可用的端点。

用法:
  python3 a_share_scraper.py --mode premarket   # 盘前(指数+新闻)
  python3 a_share_scraper.py --mode midday      # 午盘(指数+新闻)
  python3 a_share_scraper.py --mode closing     # 收盘(指数+北向+新闻)
  python3 a_share_scraper.py --mode full        # 全量
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
REQUEST_TIMEOUT = 12
MAX_RETRIES = 2
EM_REFERER = 'https://quote.eastmoney.com/'

# ============================================================
# HTTP 工具
# ============================================================

def http_get(url, referer=None, encoding='utf-8', timeout=REQUEST_TIMEOUT):
    headers = {'User-Agent': UA, 'Accept': '*/*', 'Connection': 'close'}
    if referer:
        headers['Referer'] = referer
    for attempt in range(MAX_RETRIES):
        try:
            req = Request(url, headers=headers)
            resp = urlopen(req, timeout=timeout)
            return resp.read().decode(encoding, errors='replace')
        except (HTTPError, URLError, TimeoutError, ConnectionError, OSError) as e:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(1)


def fetch_json(url, referer=None, timeout=REQUEST_TIMEOUT):
    return json.loads(http_get(url, referer=referer, timeout=timeout))


# ============================================================
# 1. 大盘指数 — 东方财富 ulist API（已验证可用）
# ============================================================

def get_indices():
    """通过东方财富 ulist 获取大盘指数 — 已验证稳定"""
    try:
        url = ('https://push2.eastmoney.com/api/qt/ulist.np/get?'
               'fltt=2&invt=2&fields=f12,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18'
               '&secids=1.000001,0.399001,0.399006,1.000688,1.000016,0.399330,1.000300')
        data = fetch_json(url, referer=EM_REFERER)
        results = []
        if data.get('data') and data['data'].get('diff'):
            for item in data['data']['diff']:
                results.append({
                    'code': str(item.get('f12', '')),
                    'name': str(item.get('f14', '')),
                    'price': float(item.get('f2', 0) or 0),
                    'change_pct': float(item.get('f3', 0) or 0),
                    'change': float(item.get('f4', 0) or 0),
                    'volume': float(item.get('f5', 0) or 0),
                    'amount': float(item.get('f6', 0) or 0) / 1e8,
                    'high': float(item.get('f15', 0) or 0),
                    'low': float(item.get('f16', 0) or 0),
                    'open': float(item.get('f17', 0) or 0),
                    'prev_close': float(item.get('f18', 0) or 0),
                })
        return results
    except Exception as e:
        print(f"    ⚠ 指数获取失败: {e}")
        return []


# ============================================================
# 2. 北向资金 — 东方财富 kamt API（已验证可用）
# ============================================================

def get_north_flow():
    """北向资金 — 解析 hk2sh(沪股通) + hk2sz(深股通)"""
    try:
        url = ('https://push2his.eastmoney.com/api/qt/kamt.kline/get?'
               'fields1=f1,f2,f3,f4&fields2=f51,f52,f53,f54,f55,f56'
               '&klt=101&lmt=10')
        data = fetch_json(url, referer=EM_REFERER)
        d = data.get('data', {})
        # 格式: date, net_buy(万), net_sell(万), cumulative(万)
        hk2sh = d.get('hk2sh', [])  # 沪股通(北向)
        hk2sz = d.get('hk2sz', [])  # 深股通(北向)
        # 按日期合并
        by_date = {}
        for line in hk2sh:
            parts = line.split(',')
            if len(parts) >= 3:
                dt = parts[0]
                net = (float(parts[1]) - float(parts[2])) / 1e4  # 万→亿
                by_date[dt] = by_date.get(dt, 0) + net
        for line in hk2sz:
            parts = line.split(',')
            if len(parts) >= 3:
                dt = parts[0]
                net = (float(parts[1]) - float(parts[2])) / 1e4
                by_date[dt] = round(by_date.get(dt, 0) + net, 2)
        results = [{'date': k, 'net_amount': v} for k, v in sorted(by_date.items())]
        return results
    except Exception as e:
        print(f"    ⚠ 北向资金失败: {e}")
        return []


# ============================================================
# 3. 财联社新闻（已验证可用）
# ============================================================

def get_cls_news(limit=15):
    """财联社电报 — 已验证稳定"""
    results = []
    try:
        url = 'https://www.cls.cn/nodeapi/updateTelegraphList?app=CailianpressWeb&os=web&sv=7.7.5&sign=1'
        data = fetch_json(url, referer='https://www.cls.cn/')
        if data.get('data') and data['data'].get('roll_data'):
            for item in data['data']['roll_data'][:limit]:
                content = item.get('content', item.get('brief', ''))
                if content:
                    ctime = item.get('ctime', 0)
                    time_str = ''
                    if ctime:
                        try:
                            time_str = datetime.fromtimestamp(int(ctime)).strftime('%H:%M')
                        except:
                            pass
                    results.append({
                        'time': time_str,
                        'title': str(content)[:120],
                        'content': str(content),
                        'source': '财联社',
                        'is_important': bool(item.get('is_important', 0)),
                    })
    except Exception as e:
        print(f"    ⚠ 财联社失败: {e}")
    return results


# ============================================================
# 报告生成（占位符版 — AI通过mimo_web_search补充数据）
# ============================================================

def generate_premarket(date_str, data):
    indices = data.get('indices', [])
    news = data.get('news', [])

    lines = [f'## ☀️ A股盘前速递 | {date_str}', '']

    # 美股（占位 — AI用mimo_web_search补充）
    lines += [
        '### 🇺🇸 隔夜美股',
        '- 道琼斯: {{mimo_web_search: "美股 道琼斯 纳斯达克 标普500 最新收盘"}}',
        '- 纳斯达克: {{同上}}',
        '- 标普500: {{同上}}', '',
        '**权重股表现:**',
        '- 英伟达(NVDA): {{mimo_web_search: "英伟达 NVDA 股价 今日"}}',
        '- 特斯拉(TSLA): {{mimo_web_search: "特斯拉 TSLA 股价 今日"}}',
        '- 苹果(AAPL): {{mimo_web_search: "苹果 AAPL 股价"}}',
        '- 微软(MSFT): {{mimo_web_search: "微软 MSFT 股价"}}', '',
    ]

    # 亚太
    lines += [
        '### 🌏 亚太早盘',
        '- 日经225: {{mimo_web_search: "日经225 韩国KOSPI 恒生指数 今日行情"}}',
        '- 韩国KOSPI: {{同上}}',
        '- 恒生指数: {{同上}}', '',
    ]

    # 大宗商品
    lines += [
        '### 💰 大宗商品',
        '- 伦敦金(XAU): {{mimo_web_search: "伦敦金 白银 布伦特原油 碳酸锂 最新价格"}}',
        '- 伦敦银(XAG): {{同上}}',
        '- 布伦特原油: {{同上}}',
        '- 碳酸锂: {{mimo_web_search: "碳酸锂 价格 最新"}}', '',
    ]

    # 加密货币
    lines += [
        '### ₿ 加密货币',
        '- 比特币(BTC): {{mimo_web_search: "比特币 以太坊 最新价格"}}',
        '- 以太坊(ETH): {{同上}}', '',
    ]

    # 马斯克 & 特朗普
    lines += [
        '### 🐦 马斯克 & 特朗普最新',
        '- 马斯克: {{mimo_web_search: "马斯克 Elon Musk 最新推特 言论"}}',
        '- 特朗普: {{mimo_web_search: "特朗普 Trump 最新政策 言论"}}', '',
    ]

    # 财联社
    if news:
        lines += ['### 📰 财联社精选', '']
        important = [n for n in news if n.get('is_important')]
        normal = [n for n in news if not n.get('is_important')]
        for n in important[:8]:
            lines.append(f"- 🔴 [{n.get('time','')}] {n.get('title','')}")
        if important and normal:
            lines.append('')
        for n in normal[:8]:
            lines.append(f"- [{n.get('time','')}] {n.get('title','')}")
        lines.append('')

    # A50期货
    lines += [
        '### 📊 期货信号',
        '- A50期货: {{mimo_web_search: "A50期货 今日 走势"}}',
        '- IF主力: {{mimo_web_search: "IF主力合约 最新行情"}}', '',
    ]

    # 盘前判断（AI填写）
    lines += [
        '### 🎯 盘前判断',
        '{AI综合以上所有信息的分析}',
        '',
        '**关注方向:**',
        '{板块判断}',
        '',
        '**风险提示:**',
        '{风险因素}', '',
    ]

    return '\n'.join(lines)


def generate_midday(date_str, data):
    indices = data.get('indices', [])
    news = data.get('news', [])

    lines = [f'## 🍜 A股午盘策略 | {date_str}', '']

    # 上午行情（如果有指数数据就用，否则占位）
    lines += ['### 📊 上午行情回顾', '']
    if indices:
        for idx in indices:
            if idx['code'] in ('000001', '399001', '399006', '000688'):
                arrow = '🔴' if idx['change_pct'] < 0 else '🟢' if idx['change_pct'] > 0 else '⚪'
                lines.append(f"- {arrow} **{idx['name']}**: {idx['price']:.2f} ({idx['change_pct']:+.2f}%) 成交{idx['amount']:.0f}亿")
    else:
        lines.append('- {{mimo_web_search: "A股 上证指数 深证成指 创业板指 今日行情"}}')

    lines += [
        '',
        '**量能:**',
        '- {{mimo_web_search: "A股今日成交额 半日成交 放量缩量"}}',
        '',
    ]

    # 涨跌情绪
    lines += [
        '### 😊 涨跌情绪',
        '- {{mimo_web_search: "A股今日涨跌家数 涨停 跌停 数量"}}',
        '- 涨跌比: {{同上}}',
        '',
    ]

    # 主线板块
    lines += [
        '### 🔥 上午主线板块',
        '- {{mimo_web_search: "A股今日领涨板块 行业涨幅排行"}}',
        '- {{同上}}',
        '',
    ]

    # 涨停连板
    lines += [
        '### 🪜 连板梯队',
        '- {{mimo_web_search: "A股今日涨停板 连板 连板梯队"}}',
        '',
    ]

    # 资金流向
    lines += [
        '### 💰 资金流向',
        '- {{mimo_web_search: "A股今日资金流向 行业资金净流入"}}',
        '',
    ]

    # 盘感判断
    lines += [
        '### 🧠 盘感判断',
        '{读取lessons.md后结合上午数据的AI分析}',
        '{当前情绪周期位置}',
        '{与盘前预判的对比}', '',
    ]

    # 选股策略
    lines += [
        '### 🎯 下午选股策略',
        '{AI综合上午数据给出的选股建议}',
        '',
        '**推荐买入:**',
        '{具体个股 + 买入原因 + 建议价位}',
        '',
        '**回避方向:**',
        '{需要回避的板块/个股及原因}',
        '',
        '**仓位建议:**',
        '{基于情绪和量能的仓位建议}', '',
    ]

    return '\n'.join(lines)


def generate_closing(date_str, data):
    indices = data.get('indices', [])
    news = data.get('news', [])

    lines = [f'## 📊 A股收盘复盘 | {date_str}', '']

    # 今日概况
    lines += ['### 🔥 今日概况', '{一句话总结今日市场特征}', '']

    # 大盘 & 量能
    lines += ['### 📈 大盘 & 量能', '']
    if indices:
        for idx in indices:
            if idx['code'] in ('000001', '399001', '399006', '000688'):
                arrow = '🔴' if idx['change_pct'] < 0 else '🟢' if idx['change_pct'] > 0 else '⚪'
                lines.append(f"- {arrow} **{idx['name']}**: {idx['price']:.2f} ({idx['change_pct']:+.2f}%) 成交{idx['amount']:.0f}亿")
    else:
        lines.append('- {{mimo_web_search: "A股收盘 上证 深证 创业板 今日"}}')

    lines += [
        '',
        '**量能:**',
        '- {{mimo_web_search: "A股今日全天成交额 放量缩量"}}',
        '',
        '**趋势:**',
        '- {{mimo_web_search: "上证指数 均线 压力位 支撑位"}}',
        '',
    ]

    # 涨跌情绪
    lines += [
        '### 😊 涨跌情绪',
        '- {{mimo_web_search: "A股今日涨跌家数 涨停 跌停 涨跌比"}}',
        '- 情绪阶段: {AI根据数据判断}',
        '',
    ]

    # 主线板块
    lines += [
        '### 🔥 主线板块TOP8',
        '- {{mimo_web_search: "A股今日领涨板块 行业涨幅排行 资金流入"}}',
        '- {{同上}}', '',
        '### 💀 弱势板块TOP5',
        '- {{mimo_web_search: "A股今日领跌板块"}}',
        '',
    ]

    # 概念板块
    lines += [
        '### 💡 概念板块TOP8',
        '- {{mimo_web_search: "A股今日概念板块涨幅排行"}}',
        '',
    ]

    # 资金流向
    lines += [
        '### 💰 资金流向',
        '- {{mimo_web_search: "A股今日行业资金流向 净流入 净流出"}}',
        '',
    ]

    # 涨停连板
    lines += [
        '### 🪜 连板天梯',
        '- {{mimo_web_search: "A股今日涨停板 连板梯队 最高板"}}',
        '',
    ]

    # 龙虎榜
    lines += [
        '### 🐉 龙虎榜亮点',
        '- {{mimo_web_search: "A股今日龙虎榜 机构买入 游资"}}',
        '',
    ]

    # 北向资金
    lines += ['### 🌊 北向资金', '- {{mimo_web_search: "北向资金 今日 净流入 沪股通 深股通"}}', '']

    # 涨跌幅榜
    lines += [
        '### 📈 涨幅TOP10',
        '- {{mimo_web_search: "A股今日涨幅排行 涨幅最大的股票"}}',
        '',
        '### 📉 跌幅TOP10',
        '- {{mimo_web_search: "A股今日跌幅排行"}}',
        '',
    ]

    # 趋势股
    lines += [
        '### 📈 趋势股跟踪',
        '- {{mimo_web_search: "A股趋势股 60日涨幅 创新高"}}',
        '',
    ]

    # ETF
    lines += [
        '### 📦 热门ETF',
        '- {{mimo_web_search: "今日热门ETF 成交额排行"}}',
        '',
    ]

    # 复盘分析
    lines += [
        '### 🧠 复盘分析',
        '{AI综合所有数据的深度分析}',
        '',
        '**量价关系:**',
        '{量能与价格的配合分析}',
        '',
        '**板块轮动:**',
        '{今日板块轮动特征和明日预判}',
        '',
        '**量化营业部:**',
        '{龙虎榜中量化席位的行为分析}', '',
    ]

    # 明日预判
    lines += [
        '### 🔮 明日预判',
        '{AI综合判断的明日操作建议}',
        '',
        '**关注方向:**',
        '{明日重点关注的板块/个股}',
        '',
        '**风险提示:**',
        '{需要警惕的风险因素}', '',
    ]

    # 财联社精选
    if news:
        lines += ['### 📰 财联社今日要闻', '']
        for n in news[:10]:
            lines.append(f"- [{n.get('time','')}] {n.get('title','')}")
        lines.append('')

    return '\n'.join(lines)


# ============================================================
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='A股数据采集 v5 混合版')
    parser.add_argument('--date', help='YYYYMMDD')
    parser.add_argument('--output', '-o', help='输出路径')
    parser.add_argument('--data-dir', help='数据目录')
    parser.add_argument('--mode', choices=['premarket', 'midday', 'closing', 'full'], default='full')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')
    args = parser.parse_args()

    today = datetime.now().strftime('%Y%m%d')
    date_str = args.date or today
    date_fmt = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}'

    data_dir = args.data_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)

    print(f'📊 A股数据采集 v5 [{args.mode}] - {date_fmt}')
    print(f'  策略: 东方财富稳定API + 财联社 + mimo_web_search补充')

    data = {}
    errors = []

    # 指数（所有模式都需要）
    print('  [指数] 东方财富 ulist...')
    try:
        data['indices'] = get_indices()
        for idx in data['indices'][:3]:
            print(f'    ✅ {idx["name"]}: {idx["price"]:.2f} ({idx["change_pct"]:+.2f}%)')
    except Exception as e:
        errors.append(f'指数: {e}')
        data['indices'] = []

    # 北向资金 — 由mimo_web_search补充(东方财富kamt数据格式异常)
    # 保留函数但不主动调用

    # 财联社新闻（盘前和收盘）
    if args.mode in ('premarket', 'closing', 'full'):
        print('  [新闻] 财联社...')
        try:
            data['news'] = get_cls_news()
            print(f'    ✅ {len(data["news"])} 条')
        except Exception as e:
            errors.append(f'新闻: {e}')
            data['news'] = []

    # 生成报告
    if args.mode == 'premarket':
        report = generate_premarket(date_fmt, data)
    elif args.mode == 'midday':
        report = generate_midday(date_fmt, data)
    else:
        report = generate_closing(date_fmt, data)

    if errors:
        report += '\n\n## ⚠️ 数据采集异常\n\n'
        for e in errors:
            report += f'- {e}\n'

    # 输出
    if args.json:
        json_path = args.output or os.path.join(data_dir, f'{date_str}_{args.mode}.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        print(f'\n✅ JSON: {json_path}')
        return json_path
    else:
        output_path = args.output or os.path.join(data_dir, f'{date_str}_{args.mode}.md')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f'\n✅ 报告: {output_path}')
        return output_path


if __name__ == '__main__':
    main()
