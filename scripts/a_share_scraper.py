#!/usr/bin/env python3
"""
A股全时段数据采集脚本 v7 - 混合API版
策略: 稳定API获取大部分数据 + mimo_web_search补充无法API获取的少数项

数据源:
  腾讯行情API (qt.gtimg.cn):
    A股指数 / 美股指数 / 美股个股 / 纽约金银原油 / 恒生指数期货
  新浪期货API (hq.sinajs.cn):
    布伦特原油 / 日经225期货 / 比特币期货
  财联社API (cls.cn):
    电报/快讯/财经新闻
  东方财富数据中心 (datacenter-web):
    龙虎榜 / 北向资金
  汇率API (exchangerate-api.com):
    主要货币汇率
  mimo_web_search (运行时补充):
    KOSPI / 以太坊 / A50期货 / 碳酸锂 / 马斯克特朗普最新

用法:
  python3 a_share_scraper.py --mode premarket
  python3 a_share_scraper.py --mode midday
  python3 a_share_scraper.py --mode closing
  python3 a_share_scraper.py --mode full
"""

import argparse
import json
import os
import sys
import time
import re
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
REQUEST_TIMEOUT = 12
MAX_RETRIES = 2

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
# 解析器
# ============================================================

def parse_tencent_index(raw):
    """解析腾讯A股/港股指数"""
    m = re.search(r'"([^"]+)"', raw)
    if not m:
        return None
    parts = m.group(1).split('~')
    if len(parts) < 38:
        return None
    try:
        return {
            'name': parts[1], 'code': parts[2],
            'price': float(parts[3] or 0), 'prev_close': float(parts[4] or 0),
            'open': float(parts[5] or 0), 'volume': float(parts[6] or 0),
            'change': float(parts[31] or 0) if len(parts) > 31 else 0,
            'change_pct': float(parts[32] or 0) if len(parts) > 32 else 0,
            'high': float(parts[33] or 0) if len(parts) > 33 else 0,
            'low': float(parts[34] or 0) if len(parts) > 34 else 0,
            'amount': float(parts[37] or 0) if len(parts) > 37 else 0,  # 万
            'time': parts[30] if len(parts) > 30 else '',
        }
    except (ValueError, IndexError):
        return None


def parse_tencent_us(raw):
    """解析腾讯美股指数/个股"""
    m = re.search(r'"([^"]+)"', raw)
    if not m:
        return None
    parts = m.group(1).split('~')
    if len(parts) < 33:
        return None
    try:
        return {
            'name': parts[1], 'code': parts[2],
            'price': float(parts[3] or 0), 'prev_close': float(parts[4] or 0),
            'open': float(parts[5] or 0), 'volume': float(parts[6] or 0),
            'change': float(parts[31] or 0), 'change_pct': float(parts[32] or 0),
            'high': float(parts[33] or 0) if len(parts) > 33 else 0,
            'low': float(parts[34] or 0) if len(parts) > 34 else 0,
            'time': parts[30] if len(parts) > 30 else '',
        }
    except (ValueError, IndexError):
        return None


def parse_tencent_commodity(raw):
    """解析腾讯商品期货 hf_GC/hf_SI/hf_CL/hf_HSI"""
    m = re.search(r'"([^"]+)"', raw)
    if not m:
        return None
    parts = m.group(1).split(',')
    if len(parts) < 14:
        return None
    try:
        return {
            'price': float(parts[0] or 0), 'change_pct': float(parts[1] or 0),
            'open': float(parts[2] or 0), 'prev_close': float(parts[3] or 0),
            'high': float(parts[4] or 0), 'low': float(parts[5] or 0),
            'time': parts[6], 'name_cn': parts[13] if len(parts) > 13 else '',
        }
    except (ValueError, IndexError):
        return None


def parse_sina_futures(raw):
    """解析新浪期货数据 hf_OIL/hf_NK/hf_BTC"""
    m = re.search(r'"([^"]+)"', raw)
    if not m:
        return None
    parts = m.group(1).split(',')
    if len(parts) < 14:
        return None
    try:
        current = float(parts[0] or 0)
        prev_close = float(parts[7] or 0) if parts[7] else float(parts[2] or 0)
        change_pct = ((current - prev_close) / prev_close * 100) if prev_close else 0
        return {
            'price': current, 'change_pct': round(change_pct, 2),
            'open': float(parts[2] or 0), 'prev_close': prev_close,
            'high': float(parts[4] or 0), 'low': float(parts[5] or 0),
            'time': parts[6], 'name_cn': parts[13] if len(parts) > 13 else '',
        }
    except (ValueError, IndexError):
        return None


# ============================================================
# 数据采集函数
# ============================================================

def get_a_share_indices():
    """A股主要指数 via 腾讯API"""
    codes = 'sh000001,sz399001,sz399006,sh000688,sh000016,sh000300'
    url = f'https://qt.gtimg.cn/q={codes}'
    data = http_get(url, referer='https://finance.qq.com/', encoding='gbk')
    return [r for line in data.split(';') if line.strip() and 'none_match' not in line
            for r in [parse_tencent_index(line.strip())] if r]


def get_us_indices():
    """美股三大指数 via 腾讯API"""
    codes = 'usDJI,us.IXIC,us.INX,us.NDX'
    url = f'https://qt.gtimg.cn/q={codes}'
    data = http_get(url, referer='https://finance.qq.com/', encoding='gbk')
    return [r for line in data.split(';') if line.strip() and 'none_match' not in line
            for r in [parse_tencent_us(line.strip())] if r]


def get_us_stocks():
    """美股权重股 via 腾讯API"""
    codes = 'usNVDA,usTSLA,usAAPL,usMSFT,usGOOG,usAMZN,usMETA'
    url = f'https://qt.gtimg.cn/q={codes}'
    data = http_get(url, referer='https://finance.qq.com/', encoding='gbk')
    return [r for line in data.split(';') if line.strip() and 'none_match' not in line
            for r in [parse_tencent_us(line.strip())] if r]


def get_commodities_tencent():
    """纽约金/银/原油 + 恒生期货 via 腾讯API"""
    codes = 'hf_GC,hf_SI,hf_CL,hf_HSI'
    url = f'https://qt.gtimg.cn/q={codes}'
    data = http_get(url, referer='https://finance.qq.com/', encoding='gbk')
    results = {}
    key_map = {'hf_GC': 'gold', 'hf_SI': 'silver', 'hf_CL': 'wti_oil', 'hf_HSI': 'hsi_futures'}
    for line in data.split(';'):
        line = line.strip()
        if not line or 'none_match' in line:
            continue
        for code, key in key_map.items():
            if code in line:
                com = parse_tencent_commodity(line)
                if com:
                    results[key] = com
    return results


def get_sina_futures():
    """布伦特原油 + 日经225 + 比特币 via 新浪API"""
    codes = 'hf_OIL,hf_NK,hf_BTC'
    url = f'https://hq.sinajs.cn/list={codes}'
    data = http_get(url, referer='https://finance.sina.com.cn/', encoding='gbk')
    results = {}
    key_map = {'hf_OIL': 'brent_oil', 'hf_NK': 'nikkei', 'hf_BTC': 'bitcoin'}
    for line in data.split(';'):
        line = line.strip()
        if not line or '=""' in line:
            continue
        for code, key in key_map.items():
            if code in line:
                com = parse_sina_futures(line)
                if com:
                    results[key] = com
    return results


def get_cls_news(limit=20):
    """财联社电报/快讯"""
    results = []
    try:
        url = 'https://www.cls.cn/nodeapi/updateTelegraphList?app=CailianpressWeb&os=web&sv=7.7.5&sign=1'
        data = fetch_json(url, referer='https://www.cls.cn/')
        if data.get('data') and data['data'].get('roll_data'):
            for item in data['data']['roll_data'][:limit]:
                content = item.get('content', item.get('brief', ''))
                if not content:
                    continue
                ctime = item.get('ctime', 0)
                time_str = ''
                if ctime:
                    try:
                        time_str = datetime.fromtimestamp(int(ctime)).strftime('%H:%M')
                    except:
                        pass
                results.append({
                    'time': time_str,
                    'title': str(content)[:150],
                    'content': str(content),
                    'keywords': extract_keywords(content),
                })
    except Exception as e:
        print(f"    ⚠ 财联社获取失败: {e}")
    return results


def extract_keywords(text):
    keywords = []
    patterns = {
        '政策': r'国务院|证监会|央行|发改委|财政部|工信部|国常会',
        'AI': r'人工智能|AI|算力|芯片|半导体|大模型|GPT|GPU',
        '新能源': r'新能源|锂电池|碳酸锂|光伏|风电|储能',
        '地产': r'房地产|地产|楼市|住建部',
        '医药': r'医药|药品|疫苗|医疗|创新药',
        '军工': r'军工|国防|军备|导弹',
        '消费': r'消费|零售|白酒|食品饮料',
        '汽车': r'汽车|新能源车|电动车|自动驾驶',
        '机器人': r'机器人|人形机器人|具身智能',
    }
    for name, pattern in patterns.items():
        if re.search(pattern, text):
            keywords.append(name)
    return keywords


def get_exchange_rates():
    """汇率数据"""
    try:
        url = 'https://api.exchangerate-api.com/v4/latest/USD'
        data = fetch_json(url)
        rates = data.get('rates', {})
        return {
            'usd_cny': rates.get('CNY', 0),
            'usd_jpy': rates.get('JPY', 0),
            'usd_hkd': rates.get('HKD', 0),
            'usd_krw': rates.get('KRW', 0),
            'date': data.get('date', ''),
        }
    except Exception as e:
        print(f"    ⚠ 汇率获取失败: {e}")
        return {}


def get_dragon_tiger_list(days=1):
    """龙虎榜数据 via 东方财富数据中心"""
    try:
        date_limit = (datetime.now() - timedelta(days=days*3)).strftime('%Y-%m-%d')
        url = (f'https://datacenter-web.eastmoney.com/api/data/v1/get?'
               f'sortColumns=TRADE_DATE,BILLBOARD_NET_AMT&sortTypes=-1,-1&pageSize=30&pageNumber=1'
               f'&reportName=RPT_DAILYBILLBOARD_DETAILSNEW'
               f'&columns=SECURITY_CODE,SECURITY_NAME_ABBR,TRADE_DATE,CLOSE_PRICE,CHANGE_RATE,'
               f'BILLBOARD_NET_AMT,BILLBOARD_BUY_AMT,BILLBOARD_SELL_AMT,BILLBOARD_DEAL_AMT,'
               f'EXPLANATION,BUY_SEAT_NEW,SELL_SEAT_NEW,TURNOVERRATE,ACCUM_AMOUNT'
               f'&source=WEB&client=WEB'
               f'&filter=(TRADE_DATE%3E%27{date_limit}%27)')
        data = fetch_json(url, referer='https://data.eastmoney.com/')
        results = []
        if data.get('result') and data['result'].get('data'):
            for item in data['result']['data']:
                results.append({
                    'code': item.get('SECURITY_CODE', ''),
                    'name': item.get('SECURITY_NAME_ABBR', ''),
                    'date': item.get('TRADE_DATE', '')[:10],
                    'close': item.get('CLOSE_PRICE', 0),
                    'change_pct': item.get('CHANGE_RATE', 0),
                    'net_amount': (item.get('BILLBOARD_NET_AMT', 0) or 0) / 1e8,
                    'buy_amount': (item.get('BILLBOARD_BUY_AMT', 0) or 0) / 1e8,
                    'sell_amount': (item.get('BILLBOARD_SELL_AMT', 0) or 0) / 1e8,
                    'reason': item.get('EXPLANATION', ''),
                    'turnover': item.get('TURNOVERRATE', 0),
                })
        return results
    except Exception as e:
        print(f"    ⚠ 龙虎榜获取失败: {e}")
        return []


def get_north_flow(limit=5):
    """北向资金 via 东方财富数据中心"""
    try:
        url = (f'https://datacenter-web.eastmoney.com/api/data/v1/get?'
               f'sortColumns=TRADE_DATE&sortTypes=-1&pageSize={limit}&pageNumber=1'
               f'&reportName=RPT_MUTUAL_DEAL_HISTORY'
               f'&columns=TRADE_DATE,MUTUAL_TYPE,NET_DEAL_AMT,FUND_INFLOW,'
               f'BUY_AMT,SELL_AMT,DEAL_AMT,INDEX_CLOSE_PRICE,INDEX_CHANGE_RATE'
               f'&source=WEB&client=WEB'
               f'&filter=(MUTUAL_TYPE=%22001%22)')
        data = fetch_json(url, referer='https://data.eastmoney.com/')
        results = []
        if data.get('result') and data['result'].get('data'):
            for item in data['result']['data']:
                results.append({
                    'date': item.get('TRADE_DATE', '')[:10],
                    'net_amount': item.get('NET_DEAL_AMT'),
                    'buy_amount': item.get('BUY_AMT'),
                    'sell_amount': item.get('SELL_AMT'),
                })
        return results
    except Exception as e:
        print(f"    ⚠ 北向资金获取失败: {e}")
        return []


# ============================================================
# 报告生成 - 盘前速递
# ============================================================

def generate_premarket(date_str, data):
    us_indices = data.get('us_indices', [])
    us_stocks = data.get('us_stocks', [])
    commodities = data.get('commodities', {})
    sina = data.get('sina_futures', {})
    news = data.get('news', [])
    rates = data.get('exchange_rates', {})

    lines = [f'## ☀️ A股盘前速递 | {date_str}', '']

    # ── 美股大盘 ──
    lines += ['### 🇺🇸 隔夜美股', '']
    for idx in us_indices:
        arrow = '🔴' if idx['change_pct'] < 0 else '🟢' if idx['change_pct'] > 0 else '⚪'
        lines.append(f"- {arrow} **{idx['name']}**: {idx['price']:,.2f} ({idx['change_pct']:+.2f}%)")
    if not us_indices:
        lines.append('- （数据暂未更新）')

    # 分析
    if us_indices:
        gains = [i for i in us_indices if i['change_pct'] > 0]
        losses = [i for i in us_indices if i['change_pct'] < 0]
        if len(gains) > len(losses):
            lines.append(f'\n> 📊 **分析**: 美股整体偏多，{len(gains)}涨{len(losses)}跌。对A股开盘情绪偏正面。')
        elif len(losses) > len(gains):
            lines.append(f'\n> 📊 **分析**: 美股整体偏弱，{len(gains)}涨{len(losses)}跌。注意对A股开盘的压制。')
        else:
            lines.append(f'\n> 📊 **分析**: 美股涨跌互现，对A股影响中性。')

    # ── 美股权重股 ──
    lines += ['', '**权重股表现:**', '']
    for stock in us_stocks:
        arrow = '🔴' if stock['change_pct'] < 0 else '🟢' if stock['change_pct'] > 0 else '⚪'
        code = stock['code'].replace('.OQ', '').replace('.', '')
        lines.append(f"- {arrow} **{stock['name']}**({code}): ${stock['price']:.2f} ({stock['change_pct']:+.2f}%)")
    if us_stocks:
        # 分析权重股趋势
        tech_gains = [s for s in us_stocks if s['change_pct'] > 1]
        tech_losses = [s for s in us_stocks if s['change_pct'] < -1]
        if tech_gains:
            names = '、'.join(s['name'] for s in tech_gains)
            lines.append(f'\n> 📊 **分析**: {names}涨幅较大，利好A股相关板块情绪。')
        if tech_losses:
            names = '、'.join(s['name'] for s in tech_losses)
            lines.append(f'\n> 📊 **分析**: {names}走弱，关注对A股同类板块的影响。')

    # ── 亚太股市 ──
    lines += ['', '### 🌏 亚太市场', '']

    # 日经225 (Sina)
    nikkei = sina.get('nikkei')
    if nikkei:
        arrow = '🔴' if nikkei['change_pct'] < 0 else '🟢' if nikkei['change_pct'] > 0 else '⚪'
        lines.append(f"- {arrow} **日经225期货**: {nikkei['price']:,.0f} ({nikkei['change_pct']:+.2f}%)")

    # 恒生指数期货 (Tencent)
    hsi = commodities.get('hsi_futures')
    if hsi:
        arrow = '🔴' if hsi['change_pct'] < 0 else '🟢' if hsi['change_pct'] > 0 else '⚪'
        lines.append(f"- {arrow} **恒生指数期货**: {hsi['price']:,.2f} ({hsi['change_pct']:+.2f}%)")

    # KOSPI - 需要mimo_web_search补充
    lines.append('- **韩国KOSPI**: {{mimo_web_search: "韩国KOSPI指数 今日行情"}}')

    if nikkei or hsi:
        analysis_parts = []
        if nikkei and nikkei['change_pct'] > 0.5:
            analysis_parts.append('日经走强')
        elif nikkei and nikkei['change_pct'] < -0.5:
            analysis_parts.append('日经偏弱')
        if hsi and hsi['change_pct'] > 0.5:
            analysis_parts.append('恒生期货偏多')
        elif hsi and hsi['change_pct'] < -0.5:
            analysis_parts.append('恒生期货偏弱')
        if analysis_parts:
            lines.append(f'\n> 📊 **分析**: {", ".join(analysis_parts)}，亚太市场情绪对A股开盘有指引作用。')
    lines.append('')

    # ── 大宗商品 ──
    lines += ['### 💰 大宗商品', '']
    com_display = [
        ('gold', '纽约金(XAU)', '伦敦金价格走势基本与纽约金一致'),
        ('silver', '纽约银(XAG)', ''),
        ('wti_oil', 'WTI原油', ''),
    ]
    for key, label, note in com_display:
        com = commodities.get(key)
        if com:
            arrow = '🔴' if com['change_pct'] < 0 else '🟢' if com['change_pct'] > 0 else '⚪'
            suffix = f' — {note}' if note else ''
            lines.append(f"- {arrow} **{label}**: ${com['price']:,.2f} ({com['change_pct']:+.2f}%){suffix}")

    # 布伦特原油 (Sina)
    brent = sina.get('brent_oil')
    if brent:
        arrow = '🔴' if brent['change_pct'] < 0 else '🟢' if brent['change_pct'] > 0 else '⚪'
        lines.append(f"- {arrow} **布伦特原油**: ${brent['price']:,.2f} ({brent['change_pct']:+.2f}%)")

    # 碳酸锂 - 需要mimo_web_search
    lines.append('- **碳酸锂**: {{mimo_web_search: "碳酸锂期货 最新价格 走势"}}')

    # 分析
    if commodities:
        gold = commodities.get('gold')
        oil = commodities.get('wti_oil')
        analysis_parts = []
        if gold and gold['change_pct'] > 1:
            analysis_parts.append('黄金大涨，利好避险+黄金板块')
        elif gold and gold['change_pct'] < -1:
            analysis_parts.append('黄金回落，避险情绪降温')
        if oil and oil['change_pct'] > 2:
            analysis_parts.append('原油大涨，利好石化板块但利空交运')
        elif oil and oil['change_pct'] < -2:
            analysis_parts.append('原油大跌，利空石化板块但利好交运航空')
        if brent and brent['change_pct'] > 2:
            analysis_parts.append('布伦特同步走高，国际油价趋势确认')
        if analysis_parts:
            lines.append(f'\n> 📊 **分析**: {"; ".join(analysis_parts)}。')
    lines.append('')

    # ── 加密货币 ──
    lines += ['### ₿ 加密货币', '']
    btc = sina.get('bitcoin')
    if btc:
        arrow = '🔴' if btc['change_pct'] < 0 else '🟢' if btc['change_pct'] > 0 else '⚪'
        lines.append(f"- {arrow} **比特币(BTC)**: ${btc['price']:,.0f} ({btc['change_pct']:+.2f}%)")
    lines.append('- **以太坊(ETH)**: {{mimo_web_search: "以太坊 最新价格"}}')

    if btc:
        if btc['change_pct'] > 3:
            lines.append(f'\n> 📊 **分析**: 比特币大涨，关注A股区块链/数字货币板块异动。')
        elif btc['change_pct'] < -3:
            lines.append(f'\n> 📊 **分析**: 比特币大跌，区块链板块可能承压。')
        else:
            lines.append(f'\n> 📊 **分析**: 比特币走势平稳，对A股相关板块影响有限。')
    lines.append('')

    # ── 马斯克 & 特朗普 ──
    lines += [
        '### 🐦 马斯克 & 特朗普最新', '',
        '- **马斯克**: {{mimo_web_search: "马斯克 Elon Musk 最新推特 言论 今天"}}',
        '- **特朗普**: {{mimo_web_search: "特朗普 Trump 最新政策 言论 今天"}}', '',
    ]

    # ── 汇率 ──
    if rates:
        lines += ['### 💱 汇率', '']
        if rates.get('usd_cny'):
            lines.append(f"- 美元/人民币: {rates['usd_cny']:.4f}")
        if rates.get('usd_jpy'):
            lines.append(f"- 美元/日元: {rates['usd_jpy']:.2f}")
        if rates.get('usd_krw'):
            lines.append(f"- 美元/韩元: {rates['usd_krw']:.2f}")
        lines.append('')

    # ── 财联社 ──
    if news:
        lines += ['### 📰 财联社精选', '']
        important = [n for n in news if n.get('keywords')]
        normal = [n for n in news if not n.get('keywords')]
        shown_titles = set()
        for n in important[:8]:
            tag = f"🔴 [{n.get('time','')}]"
            lines.append(f"- {tag} {n.get('title','')}")
            shown_titles.add(n.get('title','')[:30])
        for n in normal[:8]:
            if n.get('title','')[:30] not in shown_titles:
                lines.append(f"- [{n.get('time','')}] {n.get('title','')}")
        # 分析
        if important:
            all_kw = []
            for n in important[:8]:
                all_kw.extend(n.get('keywords', []))
            if all_kw:
                from collections import Counter
                top = Counter(all_kw).most_common(3)
                kw_str = '、'.join(k[0] for k in top)
                lines.append(f'\n> 📊 **分析**: 财联社重点关注方向: {kw_str}。相关板块开盘后值得密切关注。')
        lines.append('')

    # ── A50期货 ──
    lines += [
        '### 📊 期货信号', '',
        '- **A50期货**: {{mimo_web_search: "富时A50期货 最新行情 走势"}}', '',
    ]

    # ── 盘前总结 ──
    lines += [
        '### 🎯 盘前判断', '',
        generate_premarket_summary(us_indices, us_stocks, commodities, sina, news),
        '',
        '**风险提示:**',
        '- 关注开盘后量能是否配合，谨防高开低走',
        '- 注意外盘盘中变化对A股情绪的传导',
        '',
    ]

    return '\n'.join(lines)


def generate_premarket_summary(us_indices, us_stocks, commodities, sina, news):
    parts = []

    # 美股
    if us_indices:
        gains = [i for i in us_indices if i['change_pct'] > 0]
        losses = [i for i in us_indices if i['change_pct'] < 0]
        if len(gains) > len(losses):
            parts.append('美股整体偏多，')
        elif len(losses) > len(gains):
            parts.append('美股整体偏弱，')
        else:
            parts.append('美股涨跌互现，')

    # 亚太
    nikkei = sina.get('nikkei')
    hsi = commodities.get('hsi_futures')
    if nikkei and nikkei['change_pct'] > 0:
        parts.append('日经走强，')
    if hsi and hsi['change_pct'] > 0:
        parts.append('恒生期货偏多利好港股情绪，')

    # 商品
    gold = commodities.get('gold')
    oil_wti = commodities.get('wti_oil')
    brent = sina.get('brent_oil')
    if gold and abs(gold['change_pct']) > 1:
        direction = '大涨' if gold['change_pct'] > 0 else '大跌'
        parts.append(f'黄金{direction}需关注避险板块，')
    if (oil_wti and oil_wti['change_pct'] > 2) or (brent and brent['change_pct'] > 2):
        parts.append('原油大涨利好石化板块，')

    # BTC
    btc = sina.get('bitcoin')
    if btc and btc['change_pct'] > 3:
        parts.append('比特币大涨关注区块链板块，')

    # 新闻热点
    if news:
        all_kw = []
        for n in news[:10]:
            all_kw.extend(n.get('keywords', []))
        if all_kw:
            from collections import Counter
            top = Counter(all_kw).most_common(3)
            parts.append(f"今日热点: {', '.join(k[0] for k in top)}。")

    if not parts:
        parts.append('数据有限，建议开盘后观察15分钟再做判断。')

    return ''.join(parts)


# ============================================================
# 报告生成 - 午盘策略
# ============================================================

def generate_midday(date_str, data):
    a_indices = data.get('a_indices', [])
    news = data.get('news', [])
    dragon_tiger = data.get('dragon_tiger', [])

    lines = [f'## 🍜 A股午盘策略 | {date_str}', '']

    # ── 上午行情 ──
    lines += ['### 📊 上午行情回顾', '']
    total_amount = 0
    main_indices = [i for i in a_indices if i['code'] in ('000001', '399001', '399006', '000688')]
    for idx in main_indices:
        arrow = '🔴' if idx['change_pct'] < 0 else '🟢' if idx['change_pct'] > 0 else '⚪'
        amt_yi = idx['amount'] / 1e4 if idx['amount'] > 100 else idx['amount']
        lines.append(f"- {arrow} **{idx['name']}**: {idx['price']:.2f} ({idx['change_pct']:+.2f}%) 成交{amt_yi:.0f}亿")
        if idx['code'] in ('000001', '399001'):
            total_amount += amt_yi

    if total_amount > 0:
        lines.append(f'\n**两市半日成交: 约{total_amount:.0f}亿**')

    # 行情分析
    if main_indices:
        lines.append('')
        bullish = sum(1 for i in main_indices if i['change_pct'] > 0.3)
        bearish = sum(1 for i in main_indices if i['change_pct'] < -0.3)
        if bullish > bearish:
            style = '成长' if any(i['code'] == '399006' and i['change_pct'] > [x for x in main_indices if x['code']=='000001'][0]['change_pct'] for i in main_indices if i['code']=='399006') else '均衡'
            lines.append(f'> 📊 **分析**: 上午整体偏多，{style}风格占优。')
        elif bearish > bullish:
            lines.append('> 📊 **分析**: 上午整体偏弱，注意午后能否企稳。')
        else:
            lines.append('> 📊 **分析**: 上午震荡整理，方向不明朗。')

    # 量能分析
    if total_amount > 0:
        if total_amount > 6000:
            lines.append(f'> 📊 **量能**: 半日{total_amount:.0f}亿属于显著放量，资金进场意愿强。')
        elif total_amount > 4500:
            lines.append(f'> 📊 **量能**: 半日{total_amount:.0f}亿属于温和放量。')
        else:
            lines.append(f'> 📊 **量能**: 半日{total_amount:.0f}亿量能偏弱，关注午后能否补量。')
    lines.append('')

    # ── 财联社上午新闻 ──
    if news:
        lines += ['### 📰 上午要闻', '']
        for n in news[:8]:
            lines.append(f"- [{n.get('time','')}] {n.get('title','')}")
        lines.append('')

    # ── 龙虎榜 ──
    if dragon_tiger:
        lines += ['### 🐉 龙虎榜亮点', '']
        today_str = datetime.now().strftime('%Y-%m-%d')
        today_dt = [d for d in dragon_tiger if d['date'] == today_str] or dragon_tiger[:8]
        for dt in today_dt[:8]:
            net = dt['net_amount']
            arrow = '🟢' if net > 0 else '🔴'
            lines.append(f"- {arrow} **{dt['name']}**({dt['code']}): 净{'买入' if net > 0 else '卖出'}{abs(net):.2f}亿, {dt['change_pct']:+.1f}%")
        if today_dt:
            total_net = sum(d['net_amount'] for d in today_dt)
            if total_net > 2:
                lines.append(f'\n> 📊 **分析**: 龙虎榜整体净买入{total_net:.1f}亿，机构偏积极。关注净买入额较大且涨停的标的。')
            elif total_net < -2:
                lines.append(f'\n> 📊 **分析**: 龙虎榜整体净卖出{abs(total_net):.1f}亿，机构偏谨慎。')
        lines.append('')

    # ── 下午策略 ──
    lines += ['### 🎯 下午操作建议', '']
    lines.append(generate_midday_strategy_detailed(a_indices, news, dragon_tiger))
    lines.append('')

    return '\n'.join(lines)


def generate_midday_strategy_detailed(a_indices, news, dragon_tiger):
    parts = []

    # 行情判断
    main = [i for i in a_indices if i['code'] in ('000001', '399001', '399006')]
    if main:
        if all(i['change_pct'] > 0.3 for i in main):
            parts.append('**行情判断:** 上午整体偏多，可积极参与。')
        elif all(i['change_pct'] < -0.3 for i in main):
            parts.append('**行情判断:** 上午整体偏弱，建议观望或轻仓。')
        else:
            parts.append('**行情判断:** 上午震荡，方向未明，谨慎操作。')

    # 风格判断
    if len(main) == 3:
        sh = next((i for i in main if i['code'] == '000001'), None)
        cy = next((i for i in main if i['code'] == '399006'), None)
        if sh and cy:
            if cy['change_pct'] > sh['change_pct'] + 0.3:
                parts.append('**风格:** 创业板强于主板，成长风格占优。')
            elif sh['change_pct'] > cy['change_pct'] + 0.3:
                parts.append('**风格:** 主板强于创业板，价值/蓝筹风格占优。')
            else:
                parts.append('**风格:** 大小盘均衡。')

    # 热点方向
    if news:
        all_kw = []
        for n in news[:10]:
            all_kw.extend(n.get('keywords', []))
        if all_kw:
            from collections import Counter
            top = Counter(all_kw).most_common(3)
            parts.append(f"**热点方向:** {', '.join(k[0] for k in top)}。")

    # 操作建议
    parts.append('')
    parts.append('**操作建议:**')
    parts.append('- 关注午后量能变化，如持续放量可适当加仓')
    parts.append('- 如午后缩量或跳水，优先减仓弱势股')
    parts.append('- 尾盘30分钟注意资金动向，决定次日仓位')
    parts.append('- 任何买入设-3%止损')

    # 关注方向
    if dragon_tiger:
        strong = [d for d in dragon_tiger if d['net_amount'] > 1 and d['change_pct'] > 5]
        if strong:
            parts.append('')
            parts.append('**龙虎榜重点关注:**')
            for s in strong[:3]:
                parts.append(f"- **{s['name']}**({s['code']}): 净买入{s['net_amount']:.2f}亿, {s['change_pct']:+.1f}%, 机构资金介入明显")

    return '\n'.join(parts)


# ============================================================
# 报告生成 - 收盘复盘
# ============================================================

def generate_closing(date_str, data):
    a_indices = data.get('a_indices', [])
    us_indices = data.get('us_indices', [])
    us_stocks = data.get('us_stocks', [])
    commodities = data.get('commodities', {})
    sina = data.get('sina_futures', {})
    news = data.get('news', [])
    dragon_tiger = data.get('dragon_tiger', [])
    north_flow = data.get('north_flow', [])
    rates = data.get('exchange_rates', {})

    lines = [f'## 📊 A股收盘复盘 | {date_str}', '']

    # ── 大盘 & 量能 ──
    lines += ['### 📈 大盘 & 量能', '']
    total_amount = 0
    for idx in a_indices:
        if idx['code'] in ('000001', '399001', '399006', '000688'):
            arrow = '🔴' if idx['change_pct'] < 0 else '🟢' if idx['change_pct'] > 0 else '⚪'
            amt_yi = idx['amount'] / 1e4 if idx['amount'] > 100 else idx['amount']
            lines.append(f"- {arrow} **{idx['name']}**: {idx['price']:.2f} ({idx['change_pct']:+.2f}%) 成交{amt_yi:.0f}亿")
            if idx['code'] in ('000001', '399001', '399006'):
                total_amount += amt_yi
    if total_amount > 0:
        lines.append(f'\n**全天成交: 约{total_amount:.0f}亿**')
        if total_amount > 12000:
            lines.append('> 📊 **分析**: 全天成交超1.2万亿，显著放量，增量资金入场。量价齐升趋势可信。')
        elif total_amount > 9000:
            lines.append('> 📊 **分析**: 全天成交温和，量能配合尚可。')
        else:
            lines.append('> 📊 **分析**: 全天成交偏低，量能不足需警惕。')
    lines.append('')

    # ── 美股盘前/走势 ──
    if us_indices or us_stocks:
        lines += ['### 🇺🇸 美股最新', '']
        for idx in us_indices:
            arrow = '🔴' if idx['change_pct'] < 0 else '🟢' if idx['change_pct'] > 0 else '⚪'
            lines.append(f"- {arrow} **{idx['name']}**: {idx['price']:,.2f} ({idx['change_pct']:+.2f}%)")
        for stock in us_stocks[:4]:
            arrow = '🔴' if stock['change_pct'] < 0 else '🟢' if stock['change_pct'] > 0 else '⚪'
            code = stock['code'].replace('.OQ', '').replace('.', '')
            lines.append(f"- {arrow} **{stock['name']}**({code}): ${stock['price']:.2f} ({stock['change_pct']:+.2f}%)")
        lines.append('')

    # ── 龙虎榜 ──
    if dragon_tiger:
        lines += ['### 🐉 龙虎榜亮点', '']
        for dt in dragon_tiger[:10]:
            net = dt['net_amount']
            arrow = '🟢' if net > 0 else '🔴'
            direction = '买入' if net > 0 else '卖出'
            lines.append(f"- {arrow} **{dt['name']}**({dt['code']}): 净{direction}{abs(net):.2f}亿, {dt['change_pct']:+.1f}%, {dt['reason'][:30]}")

        # 分析
        buy_stocks = [d for d in dragon_tiger if d['net_amount'] > 0]
        sell_stocks = [d for d in dragon_tiger if d['net_amount'] < 0]
        total_net = sum(d['net_amount'] for d in dragon_tiger)
        lines.append(f'\n> 📊 **分析**: 净买入{len(buy_stocks)}只，净卖出{len(sell_stocks)}只，整体净{"流入" if total_net > 0 else "流出"}{abs(total_net):.1f}亿。')
        if total_net > 3:
            lines.append('> 📊 **分析**: 机构整体积极，市场风险偏好较高。')
        elif total_net < -3:
            lines.append('> 📊 **分析**: 机构整体谨慎，注意防御。')

        # 量化席位分析
        big_buys = [d for d in dragon_tiger if d['net_amount'] > 1.5]
        if big_buys:
            lines.append('\n**重点标的:**')
            for b in big_buys[:3]:
                lines.append(f"- **{b['name']}**: 净买入{b['net_amount']:.2f}亿，资金介入力度大，次日值得跟踪。")
        lines.append('')

    # ── 北向资金 ──
    if north_flow:
        lines += ['### 🌊 北向资金(近5日)', '']
        for nf in north_flow[:5]:
            amt = nf.get('net_amount')
            if amt is not None:
                arrow = '🟢' if amt > 0 else '🔴'
                lines.append(f"- {arrow} {nf['date']}: {amt:+.2f}亿")
            else:
                lines.append(f"- {nf['date']}: 数据更新中")

        # 分析
        valid = [n for n in north_flow[:5] if n.get('net_amount') is not None]
        if len(valid) >= 2:
            consecutive = 0
            for n in valid:
                if n.get('net_amount', 0) > 0:
                    consecutive += 1
                else:
                    break
            if consecutive >= 3:
                lines.append(f'\n> 📊 **分析**: 北向资金连续{consecutive}日净流入，外资回流信号积极。历史上连续流入后5日上涨概率较高。')
            elif consecutive == 0 and valid[0].get('net_amount', 0) < 0:
                lines.append('\n> 📊 **分析**: 北向资金转为流出，注意外资态度变化。')
        lines.append('')

    # ── 大宗商品 ──
    if commodities or sina:
        lines += ['### 💰 大宗商品收盘', '']
        for key, label in [('gold', '纽约金'), ('silver', '纽约银'), ('wti_oil', 'WTI原油')]:
            com = commodities.get(key)
            if com:
                arrow = '🔴' if com['change_pct'] < 0 else '🟢' if com['change_pct'] > 0 else '⚪'
                lines.append(f"- {arrow} **{label}**: ${com['price']:,.2f} ({com['change_pct']:+.2f}%)")
        brent = sina.get('brent_oil')
        if brent:
            arrow = '🔴' if brent['change_pct'] < 0 else '🟢' if brent['change_pct'] > 0 else '⚪'
            lines.append(f"- {arrow} **布伦特原油**: ${brent['price']:,.2f} ({brent['change_pct']:+.2f}%)")
        btc = sina.get('bitcoin')
        if btc:
            arrow = '🔴' if btc['change_pct'] < 0 else '🟢' if btc['change_pct'] > 0 else '⚪'
            lines.append(f"- {arrow} **比特币**: ${btc['price']:,.0f} ({btc['change_pct']:+.2f}%)")
        lines.append('')

    # ── 财联社今日要闻 ──
    if news:
        lines += ['### 📰 财联社今日要闻', '']
        for n in news[:12]:
            lines.append(f"- [{n.get('time','')}] {n.get('title','')}")
        lines.append('')

    # ── 复盘分析 ──
    lines += ['### 🧠 复盘分析', '', generate_closing_analysis(a_indices, dragon_tiger, north_flow, news), '']

    # ── 明日预判 ──
    lines += ['### 🔮 明日关注', '', generate_next_day_watch(a_indices, dragon_tiger, commodities, sina), '']

    # ── 风险提示 ──
    lines += [
        '### ⚠️ 风险提示', '',
        '- 关注晚间外盘走势变化',
        '- 关注明日财经日历和政策动态',
        '- 回顾盘前/午盘预判与实际偏差',
        '',
    ]

    return '\n'.join(lines)


def generate_closing_analysis(a_indices, dragon_tiger, north_flow, news):
    parts = []

    main = [i for i in a_indices if i['code'] == '000001']
    if main:
        pct = main[0]['change_pct']
        if pct > 1:
            parts.append(f'**大盘:** 上证涨{pct:+.2f}%，表现强势。')
        elif pct > 0:
            parts.append(f'**大盘:** 上证微涨{pct:+.2f}%，温和上行。')
        elif pct > -1:
            parts.append(f'**大盘:** 上证微跌{pct:+.2f}%，小幅调整。')
        else:
            parts.append(f'**大盘:** 上证跌{pct:+.2f}%，表现偏弱。')

    # 量价关系
    total = sum(i['amount'] / 1e4 for i in a_indices if i['code'] in ('000001', '399001', '399006'))
    if total > 0:
        if total > 12000:
            parts.append(f'**量能:** 全天{total:.0f}亿，显著放量，趋势可信。')
        elif total < 7000:
            parts.append(f'**量能:** 全天{total:.0f}亿，缩量明显，需谨慎。')
        else:
            parts.append(f'**量能:** 全天{total:.0f}亿，量能正常。')

    # 板块轮动
    if dragon_tiger:
        buy_stocks = [d for d in dragon_tiger if d['net_amount'] > 0]
        if buy_stocks:
            names = '、'.join(d['name'] for d in buy_stocks[:3])
            parts.append(f'**资金方向:** 龙虎榜机构重点买入{names}等。')

    # 北向
    if north_flow and north_flow[0].get('net_amount') is not None:
        amt = north_flow[0]['net_amount']
        if amt > 30:
            parts.append(f'**北向:** 大幅流入{amt:.1f}亿，信号积极。')
        elif amt < -30:
            parts.append(f'**北向:** 大幅流出{abs(amt):.1f}亿，信号偏空。')

    return '\n'.join(parts) if parts else '数据有限，建议结合其他渠道综合判断。'


def generate_next_day_watch(a_indices, dragon_tiger, commodities, sina):
    parts = []

    # 从龙虎榜找强势标的
    if dragon_tiger:
        strong = [d for d in dragon_tiger if d['net_amount'] > 1 and d['change_pct'] > 5]
        if strong:
            parts.append('**龙虎榜重点关注:**')
            for s in strong[:3]:
                parts.append(f"- **{s['name']}**({s['code']}): 净买入{s['net_amount']:.2f}亿, {s['change_pct']:+.1f}%")

    # 商品趋势
    gold = commodities.get('gold')
    btc = sina.get('bitcoin')
    if gold and abs(gold['change_pct']) > 1:
        direction = '上涨' if gold['change_pct'] > 0 else '下跌'
        parts.append(f"\n**黄金:** 纽约金{direction}{abs(gold['change_pct']):.1f}%，关注A股黄金板块。")
    if btc and abs(btc['change_pct']) > 3:
        direction = '大涨' if btc['change_pct'] > 0 else '大跌'
        parts.append(f"**比特币:** {direction}{abs(btc['change_pct']):.1f}%，关注区块链板块。")

    parts.append('\n**操作建议:** 开盘后观察15-30分钟再做决定，不追高开。')
    return '\n'.join(parts) if parts else '综合判断后关注外盘变化和消息面。'


# ============================================================
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='A股数据采集 v7 混合API版')
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

    print(f'📊 A股数据采集 v7 [混合API版] [{args.mode}] - {date_fmt}')

    data = {}
    errors = []

    # 1. A股指数
    print('  [指数] A股大盘...')
    try:
        data['a_indices'] = get_a_share_indices()
        for idx in data['a_indices'][:4]:
            print(f'    ✅ {idx["name"]}: {idx["price"]:.2f} ({idx["change_pct"]:+.2f}%)')
    except Exception as e:
        errors.append(f'A股指数: {e}')
        data['a_indices'] = []

    # 2. 美股指数+个股（盘前和收盘）
    if args.mode in ('premarket', 'closing', 'full'):
        print('  [美股] 指数+个股...')
        try:
            data['us_indices'] = get_us_indices()
            for idx in data['us_indices'][:3]:
                print(f'    ✅ {idx["name"]}: {idx["price"]:,.2f} ({idx["change_pct"]:+.2f}%)')
        except Exception as e:
            errors.append(f'美股指数: {e}')
            data['us_indices'] = []

        try:
            data['us_stocks'] = get_us_stocks()
            for s in data['us_stocks'][:3]:
                print(f'    ✅ {s["name"]}: ${s["price"]:.2f} ({s["change_pct"]:+.2f}%)')
        except Exception as e:
            errors.append(f'美股个股: {e}')
            data['us_stocks'] = []

    # 3. 商品期货（盘前和收盘）
    if args.mode in ('premarket', 'closing', 'full'):
        print('  [商品] 腾讯期货...')
        try:
            data['commodities'] = get_commodities_tencent()
            for key, com in data['commodities'].items():
                print(f'    ✅ {key}: {com["price"]} ({com["change_pct"]:+.2f}%)')
        except Exception as e:
            errors.append(f'商品期货: {e}')
            data['commodities'] = {}

    # 4. 新浪期货（布伦特/日经/比特币）
    if args.mode in ('premarket', 'closing', 'full'):
        print('  [期货] 新浪期货(布伦特/日经/比特币)...')
        try:
            data['sina_futures'] = get_sina_futures()
            for key, com in data['sina_futures'].items():
                print(f'    ✅ {key}: {com["price"]} ({com["change_pct"]:+.2f}%)')
        except Exception as e:
            errors.append(f'新浪期货: {e}')
            data['sina_futures'] = {}

    # 5. 汇率
    if args.mode in ('premarket', 'full'):
        print('  [汇率] 汇率...')
        try:
            data['exchange_rates'] = get_exchange_rates()
            if data['exchange_rates']:
                print(f'    ✅ USD/CNY: {data["exchange_rates"].get("usd_cny", "N/A")}')
        except Exception as e:
            errors.append(f'汇率: {e}')
            data['exchange_rates'] = {}

    # 6. 财联社新闻
    if args.mode in ('premarket', 'midday', 'closing', 'full'):
        print('  [新闻] 财联社...')
        try:
            data['news'] = get_cls_news()
            print(f'    ✅ {len(data["news"])} 条')
        except Exception as e:
            errors.append(f'新闻: {e}')
            data['news'] = []

    # 7. 龙虎榜
    if args.mode in ('midday', 'closing', 'full'):
        print('  [龙虎榜] 数据中心...')
        try:
            data['dragon_tiger'] = get_dragon_tiger_list()
            print(f'    ✅ {len(data["dragon_tiger"])} 条')
        except Exception as e:
            errors.append(f'龙虎榜: {e}')
            data['dragon_tiger'] = []

    # 8. 北向资金
    if args.mode in ('closing', 'full'):
        print('  [北向] 资金...')
        try:
            data['north_flow'] = get_north_flow()
            print(f'    ✅ {len(data["north_flow"])} 条')
        except Exception as e:
            errors.append(f'北向: {e}')
            data['north_flow'] = []

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
