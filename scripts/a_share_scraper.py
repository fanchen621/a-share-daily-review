#!/usr/bin/env python3
"""
A股全时段数据采集脚本 v6 - 纯API版
完全不依赖 mimo_web_search，使用可靠的公共API获取数据。

数据源:
  1. 腾讯行情API (qt.gtimg.cn) → A股指数、美股指数、个股、商品期货
  2. 财联社API (cls.cn) → 电报/快讯新闻
  3. 东方财富数据中心 (datacenter-web) → 龙虎榜、北向资金
  4. 汇率API (exchangerate-api) → 汇率
  5. web_fetch辅助 → 加密货币、亚太指数

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
# 腾讯行情API解析器
# ============================================================

def parse_tencent_us_index(raw):
    """解析腾讯美股指数: usDJI, us.IXIC, us.INX"""
    try:
        # format: v_usDJI="200~道琼斯~.DJI~46294.23~46208.47~..."
        m = re.search(r'"([^"]+)"', raw)
        if not m:
            return None
        parts = m.group(1).split('~')
        if len(parts) < 32:
            return None
        return {
            'name': parts[1],
            'code': parts[2],
            'price': float(parts[3]) if parts[3] else 0,
            'prev_close': float(parts[4]) if parts[4] else 0,
            'open': float(parts[5]) if parts[5] else 0,
            'change': float(parts[31]) if parts[31] else 0,
            'change_pct': float(parts[32]) if len(parts) > 32 and parts[32] else 0,
            'high': float(parts[33]) if len(parts) > 33 and parts[33] else 0,
            'low': float(parts[34]) if len(parts) > 34 and parts[34] else 0,
            'time': parts[30] if len(parts) > 30 else '',
        }
    except Exception:
        return None


def parse_tencent_us_stock(raw):
    """解析腾讯美股个股: usAAPL, usNVDA, usTSLA, usMSFT"""
    try:
        m = re.search(r'"([^"]+)"', raw)
        if not m:
            return None
        parts = m.group(1).split('~')
        if len(parts) < 32:
            return None
        return {
            'name': parts[1],
            'code': parts[2],
            'price': float(parts[3]) if parts[3] else 0,
            'prev_close': float(parts[4]) if parts[4] else 0,
            'open': float(parts[5]) if parts[5] else 0,
            'change': float(parts[31]) if parts[31] else 0,
            'change_pct': float(parts[32]) if len(parts) > 32 and parts[32] else 0,
            'high': float(parts[33]) if len(parts) > 33 and parts[33] else 0,
            'low': float(parts[34]) if len(parts) > 34 and parts[34] else 0,
            'time': parts[30] if len(parts) > 30 else '',
            'volume': float(parts[6]) if parts[6] else 0,
        }
    except Exception:
        return None


def parse_tencent_commodity(raw):
    """解析腾讯商品期货: hf_GC, hf_SI, hf_CL"""
    try:
        m = re.search(r'"([^"]+)"', raw)
        if not m:
            return None
        # format: "4449.27,0.22,4446.20,4446.90,4482.30,4337.70,23:16:05,..."
        parts = m.group(1).split(',')
        if len(parts) < 14:
            return None
        return {
            'price': float(parts[0]) if parts[0] else 0,
            'change_pct': float(parts[1]) if parts[1] else 0,
            'open': float(parts[2]) if parts[2] else 0,
            'prev_close': float(parts[3]) if parts[3] else 0,
            'high': float(parts[4]) if parts[4] else 0,
            'low': float(parts[5]) if parts[5] else 0,
            'time': parts[6] if len(parts) > 6 else '',
            'name': parts[13] if len(parts) > 13 else '',
        }
    except Exception:
        return None


def parse_tencent_index(raw):
    """解析腾讯A股指数: sh000001, sz399001, etc."""
    try:
        m = re.search(r'"([^"]+)"', raw)
        if not m:
            return None
        parts = m.group(1).split('~')
        if len(parts) < 45:
            return None
        return {
            'market': parts[0],
            'name': parts[1],
            'code': parts[2],
            'price': float(parts[3]) if parts[3] else 0,
            'prev_close': float(parts[4]) if parts[4] else 0,
            'open': float(parts[5]) if parts[5] else 0,
            'volume': float(parts[6]) if parts[6] else 0,
            'change': float(parts[31]) if len(parts) > 31 and parts[31] else 0,
            'change_pct': float(parts[32]) if len(parts) > 32 and parts[32] else 0,
            'high': float(parts[33]) if len(parts) > 33 and parts[33] else 0,
            'low': float(parts[34]) if len(parts) > 34 and parts[34] else 0,
            'amount': float(parts[37]) if len(parts) > 37 and parts[37] else 0,  # 成交额(万)
            'time': parts[30] if len(parts) > 30 else '',
        }
    except Exception:
        return None


# ============================================================
# 1. A股大盘指数 — 腾讯行情API
# ============================================================

def get_a_share_indices():
    """通过腾讯API获取A股主要指数"""
    codes = 'sh000001,sz399001,sz399006,sh000688,sh000016,sh000300'
    try:
        url = f'https://qt.gtimg.cn/q={codes}'
        data = http_get(url, referer='https://finance.qq.com/', encoding='gbk')
        results = []
        for line in data.split(';'):
            line = line.strip()
            if not line or 'none_match' in line:
                continue
            idx = parse_tencent_index(line)
            if idx:
                results.append(idx)
        return results
    except Exception as e:
        print(f"    ⚠ A股指数获取失败: {e}")
        return []


# ============================================================
# 2. 美股指数 — 腾讯行情API
# ============================================================

def get_us_indices():
    """美股三大指数 + 纳斯达克100"""
    codes = 'usDJI,us.IXIC,us.INX,us.NDX'
    try:
        url = f'https://qt.gtimg.cn/q={codes}'
        data = http_get(url, referer='https://finance.qq.com/', encoding='gbk')
        results = []
        for line in data.split(';'):
            line = line.strip()
            if not line or 'none_match' in line:
                continue
            idx = parse_tencent_us_index(line)
            if idx:
                results.append(idx)
        return results
    except Exception as e:
        print(f"    ⚠ 美股指数获取失败: {e}")
        return []


# ============================================================
# 3. 美股权重股 — 腾讯行情API
# ============================================================

def get_us_stocks():
    """英伟达、特斯拉、苹果、微软"""
    codes = 'usNVDA,usTSLA,usAAPL,usMSFT'
    try:
        url = f'https://qt.gtimg.cn/q={codes}'
        data = http_get(url, referer='https://finance.qq.com/', encoding='gbk')
        results = []
        for line in data.split(';'):
            line = line.strip()
            if not line or 'none_match' in line:
                continue
            stock = parse_tencent_us_stock(line)
            if stock:
                results.append(stock)
        return results
    except Exception as e:
        print(f"    ⚠ 美股个股获取失败: {e}")
        return []


# ============================================================
# 4. 商品期货 — 腾讯行情API
# ============================================================

def get_commodities():
    """黄金、白银、WTI原油"""
    codes = 'hf_GC,hf_SI,hf_CL'
    try:
        url = f'https://qt.gtimg.cn/q={codes}'
        data = http_get(url, referer='https://finance.qq.com/', encoding='gbk')
        results = {}
        name_map = {'hf_GC': 'gold', 'hf_SI': 'silver', 'hf_CL': 'oil'}
        for line in data.split(';'):
            line = line.strip()
            if not line or 'none_match' in line:
                continue
            for code, key in name_map.items():
                if code in line:
                    com = parse_tencent_commodity(line)
                    if com:
                        com['name'] = key
                        results[key] = com
        return results
    except Exception as e:
        print(f"    ⚠ 商品期货获取失败: {e}")
        return {}


# ============================================================
# 5. 恒生指数期货 — 腾讯行情API
# ============================================================

def get_hk_futures():
    """恒生指数期货"""
    try:
        url = 'https://qt.gtimg.cn/q=hf_HSI'
        data = http_get(url, referer='https://finance.qq.com/')
        for line in data.split(';'):
            line = line.strip()
            if not line or 'none_match' in line:
                continue
            com = parse_tencent_commodity(line)
            if com:
                com['name'] = '恒生指数期货'
                return com
        return None
    except Exception as e:
        print(f"    ⚠ 恒生期货获取失败: {e}")
        return None


# ============================================================
# 6. 财联社新闻
# ============================================================

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
                # 分析内容中的价格/涨跌信息
                results.append({
                    'time': time_str,
                    'title': str(content)[:150],
                    'content': str(content),
                    'source': '财联社',
                    'is_important': bool(item.get('is_important', 0) or item.get('level', 0)),
                    'keywords': extract_keywords(content),
                })
    except Exception as e:
        print(f"    ⚠ 财联社获取失败: {e}")
    return results


def extract_keywords(text):
    """从新闻中提取关键词"""
    keywords = []
    patterns = {
        '政策': r'国务院|证监会|央行|发改委|财政部|工信部',
        'AI': r'人工智能|AI|算力|芯片|半导体|大模型',
        '新能源': r'新能源|锂电池|碳酸锂|光伏|风电',
        '地产': r'房地产|地产|楼市|住建部',
        '医药': r'医药|药品|疫苗|医疗',
        '军工': r'军工|国防|军备',
        '消费': r'消费|零售|白酒|食品饮料',
    }
    for name, pattern in patterns.items():
        if re.search(pattern, text):
            keywords.append(name)
    return keywords


# ============================================================
# 7. 汇率数据
# ============================================================

def get_exchange_rates():
    """获取主要汇率"""
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


# ============================================================
# 8. 东方财富数据中心 — 龙虎榜
# ============================================================

def get_dragon_tiger_list(days=1):
    """龙虎榜数据"""
    try:
        date_limit = (datetime.now() - timedelta(days=days*2)).strftime('%Y-%m-%d')
        url = (f'https://datacenter-web.eastmoney.com/api/data/v1/get?'
               f'sortColumns=TRADE_DATE,BILLBOARD_NET_AMT&sortTypes=-1,-1&pageSize=20&pageNumber=1'
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
                    'buy_seats': item.get('BUY_SEAT_NEW', ''),
                    'turnover': item.get('TURNOVERRATE', 0),
                })
        return results
    except Exception as e:
        print(f"    ⚠ 龙虎榜获取失败: {e}")
        return []


# ============================================================
# 9. 东方财富数据中心 — 北向资金
# ============================================================

def get_north_flow(limit=5):
    """北向资金历史数据"""
    try:
        url = (f'https://datacenter-web.eastmoney.com/api/data/v1/get?'
               f'sortColumns=TRADE_DATE&sortTypes=-1&pageSize={limit}&pageNumber=1'
               f'&reportName=RPT_MUTUAL_DEAL_HISTORY'
               f'&columns=TRADE_DATE,MUTUAL_TYPE,NET_DEAL_AMT,FUND_INFLOW,QUOTA_BALANCE,'
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
                    'fund_inflow': item.get('FUND_INFLOW'),
                    'buy_amount': item.get('BUY_AMT'),
                    'sell_amount': item.get('SELL_AMT'),
                    'deal_amount': item.get('DEAL_AMT'),
                    'index_price': item.get('INDEX_CLOSE_PRICE'),
                    'index_change': item.get('INDEX_CHANGE_RATE'),
                })
        return results
    except Exception as e:
        print(f"    ⚠ 北向资金获取失败: {e}")
        return []


# ============================================================
# 报告生成器
# ============================================================

def generate_premarket(date_str, data):
    """生成盘前速递报告"""
    indices = data.get('a_indices', [])
    us_indices = data.get('us_indices', [])
    us_stocks = data.get('us_stocks', [])
    commodities = data.get('commodities', {})
    hk_futures = data.get('hk_futures')
    news = data.get('news', [])
    rates = data.get('exchange_rates', {})

    lines = [f'## ☀️ A股盘前速递 | {date_str}', '']

    # 隔夜美股
    lines += ['### 🇺🇸 隔夜美股', '']
    us_idx_map = {'DJI': '道琼斯', '.IXIC': '纳斯达克', '.INX': '标普500', '.NDX': '纳斯达克100'}
    for idx in us_indices:
        arrow = '🔴' if idx['change'] < 0 else '🟢' if idx['change'] > 0 else '⚪'
        pct = idx['change_pct']
        lines.append(f"- {arrow} **{idx['name']}**: {idx['price']:,.2f} ({pct:+.2f}%)")
    if not us_indices:
        lines.append('- （美股指数暂未更新）')

    lines.append('')
    lines.append('**权重股表现:**')
    stock_map = {'NVDA': '英伟达(NVDA)', 'TSLA': '特斯拉(TSLA)', 'AAPL': '苹果(AAPL)', 'MSFT': '微软(MSFT)'}
    for stock in us_stocks:
        code_key = stock['code'].split('.')[0] if '.' in stock['code'] else stock['code'].replace('OQ','')
        label = stock_map.get(code_key, f"{stock['name']}({code_key})")
        arrow = '🔴' if stock['change'] < 0 else '🟢' if stock['change'] > 0 else '⚪'
        lines.append(f"- {arrow} {label}: ${stock['price']:.2f} ({stock['change_pct']:+.2f}%)")
    if not us_stocks:
        lines.append('- （美股个股暂未更新）')
    lines.append('')

    # 大宗商品
    lines += ['### 💰 大宗商品', '']
    com_name_map = {
        'gold': '伦敦金(XAU)', 'silver': '伦敦银(XAG)', 'oil': 'WTI原油'
    }
    for key, label in com_name_map.items():
        com = commodities.get(key)
        if com:
            arrow = '🔴' if com['change_pct'] < 0 else '🟢' if com['change_pct'] > 0 else '⚪'
            lines.append(f"- {arrow} **{label}**: ${com['price']:,.2f} ({com['change_pct']:+.2f}%)")
    if not commodities:
        lines.append('- （商品期货暂未更新）')
    lines.append('')

    # 恒生指数期货
    if hk_futures:
        lines += ['### 🌏 亚太信号', '']
        arrow = '🔴' if hk_futures['change_pct'] < 0 else '🟢' if hk_futures['change_pct'] > 0 else '⚪'
        lines.append(f"- {arrow} **恒生指数期货**: {hk_futures['price']:,.2f} ({hk_futures['change_pct']:+.2f}%)")
        lines.append('')

    # 汇率
    if rates:
        lines += ['### 💱 汇率', '']
        if rates.get('usd_cny'):
            lines.append(f"- 美元/人民币: {rates['usd_cny']:.4f}")
        if rates.get('usd_jpy'):
            lines.append(f"- 美元/日元: {rates['usd_jpy']:.2f}")
        lines.append('')

    # 财联社
    if news:
        lines += ['', '### 📰 财联社精选', '']
        important = [n for n in news if n.get('is_important')]
        normal = [n for n in news if not n.get('is_important')]
        shown = set()
        for n in important[:10]:
            tag = f"🔴 [{n.get('time','')}]"
            lines.append(f"- {tag} {n.get('title','')}")
            shown.add(n.get('title','')[:30])
        if important and normal:
            lines.append('')
        for n in normal[:10]:
            if n.get('title','')[:30] not in shown:
                lines.append(f"- [{n.get('time','')}] {n.get('title','')}")
        lines.append('')

    # 盘前判断
    lines += [
        '',
        '### 🎯 盘前判断',
        '',
        '**综合分析:**',
        generate_premarket_analysis(us_indices, us_stocks, commodities, hk_futures, news),
        '',
        '**风险提示:**',
        '- 关注开盘后量能是否配合',
        '- 注意外盘变化对A股情绪的影响',
        '',
    ]

    return '\n'.join(lines)


def generate_premarket_analysis(us_indices, us_stocks, commodities, hk_futures, news):
    """自动生成盘前分析"""
    parts = []

    # 美股分析
    if us_indices:
        gains = [i for i in us_indices if i['change_pct'] > 0]
        losses = [i for i in us_indices if i['change_pct'] < 0]
        if len(gains) > len(losses):
            parts.append('美股整体偏多，')
        elif len(losses) > len(gains):
            parts.append('美股整体偏弱，')
        else:
            parts.append('美股涨跌互现，')

    # 商品分析
    if commodities.get('gold') and commodities['gold']['change_pct'] > 1:
        parts.append('黄金大涨利好避险板块。')
    if commodities.get('oil') and commodities['oil']['change_pct'] > 2:
        parts.append('原油大涨利好石化板块。')

    # 新闻关键词
    if news:
        keywords_count = {}
        for n in news:
            for kw in n.get('keywords', []):
                keywords_count[kw] = keywords_count.get(kw, 0) + 1
        if keywords_count:
            top = sorted(keywords_count.items(), key=lambda x: -x[1])[:3]
            parts.append(f"财联社热点: {', '.join(k[0] for k in top)}。")

    if not parts:
        parts.append('数据有限，建议开盘后观察15分钟再做判断。')

    return ''.join(parts)


def generate_midday(date_str, data):
    """生成午盘策略报告"""
    indices = data.get('a_indices', [])
    news = data.get('news', [])
    dragon_tiger = data.get('dragon_tiger', [])

    lines = [f'## 🍜 A股午盘策略 | {date_str}', '']

    # 上午行情
    lines += ['### 📊 上午行情回顾', '']
    for idx in indices:
        if idx['code'] in ('000001', '399001', '399006', '000688'):
            arrow = '🔴' if idx['change_pct'] < 0 else '🟢' if idx['change_pct'] > 0 else '⚪'
            amt = idx['amount'] / 1e4 if idx['amount'] > 100 else idx['amount']
            lines.append(f"- {arrow} **{idx['name']}**: {idx['price']:.2f} ({idx['change_pct']:+.2f}%) 成交{amt:.0f}亿")

    if not indices:
        lines.append('- （指数数据暂未更新）')

    lines += ['', '**量能分析:**']
    # 从指数数据中计算总成交额
    total_amount = 0
    for idx in indices:
        if idx['code'] in ('000001', '399001'):
            amt = idx['amount'] / 1e4 if idx['amount'] > 100 else idx['amount']
            total_amount += amt
    if total_amount > 0:
        lines.append(f"- 两市半日成交: 约{total_amount:.0f}亿")
    lines.append('')

    # 财联社新闻
    if news:
        lines += ['### 📰 上午要闻', '']
        for n in news[:8]:
            lines.append(f"- [{n.get('time','')}] {n.get('title','')}")
        lines.append('')

    # 龙虎榜（如果有）
    if dragon_tiger:
        lines += ['### 🐉 龙虎榜亮点', '']
        for dt in dragon_tiger[:8]:
            net = dt['net_amount']
            arrow = '🟢' if net > 0 else '🔴'
            lines.append(f"- {arrow} **{dt['name']}** ({dt['code']}): 净买入{abs(net):.2f}亿, 涨跌{dt['change_pct']:+.1f}%, {dt['reason'][:40]}")
        lines.append('')

    # 策略建议
    lines += [
        '### 🎯 下午策略',
        '',
        generate_midday_strategy(indices, news, dragon_tiger),
        '',
    ]

    return '\n'.join(lines)


def generate_midday_strategy(indices, news, dragon_tiger):
    """生成午盘策略建议"""
    parts = []

    # 判断行情方向
    bullish = 0
    bearish = 0
    for idx in indices:
        if idx['change_pct'] > 0.5:
            bullish += 1
        elif idx['change_pct'] < -0.5:
            bearish += 1

    if bullish > bearish:
        parts.append('**行情判断:** 上午整体偏多，')
    elif bearish > bullish:
        parts.append('**行情判断:** 上午整体偏弱，')
    else:
        parts.append('**行情判断:** 上午震荡整理，')

    # 从新闻找热点
    if news:
        keywords_count = {}
        for n in news:
            for kw in n.get('keywords', []):
                keywords_count[kw] = keywords_count.get(kw, 0) + 1
        if keywords_count:
            top = sorted(keywords_count.items(), key=lambda x: -x[1])[:3]
            parts.append(f"热点方向: {', '.join(k[0] for k in top)}。")

    parts.append('')
    parts.append('**注意事项:**')
    parts.append('- 关注下午量能变化')
    parts.append('- 如有突发消息注意应对')
    parts.append('- 尾盘注意资金动向')

    return '\n'.join(parts)


def generate_closing(date_str, data):
    """生成收盘复盘报告"""
    indices = data.get('a_indices', [])
    us_indices = data.get('us_indices', [])
    us_stocks = data.get('us_stocks', [])
    commodities = data.get('commodities', {})
    hk_futures = data.get('hk_futures')
    news = data.get('news', [])
    dragon_tiger = data.get('dragon_tiger', [])
    north_flow = data.get('north_flow', [])
    rates = data.get('exchange_rates', {})

    lines = [f'## 📊 A股收盘复盘 | {date_str}', '']

    # 今日概况
    lines += ['### 📈 大盘 & 量能', '']
    total_amount = 0
    for idx in indices:
        if idx['code'] in ('000001', '399001', '399006', '000688'):
            arrow = '🔴' if idx['change_pct'] < 0 else '🟢' if idx['change_pct'] > 0 else '⚪'
            amt = idx['amount'] / 1e4 if idx['amount'] > 100 else idx['amount']
            lines.append(f"- {arrow} **{idx['name']}**: {idx['price']:.2f} ({idx['change_pct']:+.2f}%) 成交{amt:.0f}亿")
            if idx['code'] in ('000001', '399001', '399006'):
                total_amount += amt

    if total_amount > 0:
        lines.append('')
        lines.append(f'**全天成交: 约{total_amount:.0f}亿**')
    lines.append('')

    # 龙虎榜
    if dragon_tiger:
        lines += ['### 🐉 龙虎榜亮点', '']
        for dt in dragon_tiger[:10]:
            net = dt['net_amount']
            arrow = '🟢' if net > 0 else '🔴'
            lines.append(f"- {arrow} **{dt['name']}** ({dt['code']}): 净{'买入' if net > 0 else '卖出'}{abs(net):.2f}亿, {dt['change_pct']:+.1f}%, {dt['reason'][:40]}")
        lines.append('')

    # 北向资金
    if north_flow:
        lines += ['### 🌊 北向资金(近5日)', '']
        for nf in north_flow[:5]:
            amt = nf.get('net_amount')
            if amt is not None:
                arrow = '🟢' if amt > 0 else '🔴'
                lines.append(f"- {arrow} {nf['date']}: {amt:+.2f}亿")
            else:
                lines.append(f"- {nf['date']}: 数据待更新")
        lines.append('')

    # 财联社今日要闻
    if news:
        lines += ['### 📰 财联社今日要闻', '']
        for n in news[:12]:
            lines.append(f"- [{n.get('time','')}] {n.get('title','')}")
        lines.append('')

    # 商品期货回顾
    if commodities:
        lines += ['### 💰 商品期货收盘', '']
        com_name_map = {'gold': '纽约金', 'silver': '纽约银', 'oil': 'WTI原油'}
        for key, label in com_name_map.items():
            com = commodities.get(key)
            if com:
                arrow = '🔴' if com['change_pct'] < 0 else '🟢' if com['change_pct'] > 0 else '⚪'
                lines.append(f"- {arrow} **{label}**: ${com['price']:,.2f} ({com['change_pct']:+.2f}%)")
        lines.append('')

    # 复盘分析
    lines += [
        '### 🧠 复盘分析',
        generate_closing_analysis(indices, dragon_tiger, north_flow, news),
        '',
    ]

    # 风险提示
    lines += [
        '### ⚠️ 注意事项',
        '- 关注晚间外盘走势',
        '- 关注明日财经日历',
        '- 回顾盘前预判与实际的偏差',
        '',
    ]

    return '\n'.join(lines)


def generate_closing_analysis(indices, dragon_tiger, north_flow, news):
    """生成收盘分析"""
    parts = []

    # 行情分析
    if indices:
        main_idx = [i for i in indices if i['code'] == '000001']
        if main_idx:
            pct = main_idx[0]['change_pct']
            if pct > 1:
                parts.append(f'大盘涨幅{pct:+.2f}%，表现强势。')
            elif pct > 0:
                parts.append(f'大盘微涨{pct:+.2f}%，温和上行。')
            elif pct > -1:
                parts.append(f'大盘微跌{pct:+.2f}%，小幅调整。')
            else:
                parts.append(f'大盘跌幅{pct:+.2f}%，表现偏弱。')

    # 龙虎榜分析
    if dragon_tiger:
        buy_count = len([d for d in dragon_tiger if d['net_amount'] > 0])
        sell_count = len([d for d in dragon_tiger if d['net_amount'] < 0])
        parts.append(f'龙虎榜净买入{buy_count}只，净卖出{sell_count}只。')

        # 机构动向
        total_net = sum(d['net_amount'] for d in dragon_tiger)
        if total_net > 2:
            parts.append(f'机构整体净买入{total_net:.1f}亿，偏积极。')
        elif total_net < -2:
            parts.append(f'机构整体净卖出{abs(total_net):.1f}亿，偏谨慎。')

    # 北向资金
    if north_flow and north_flow[0].get('net_amount') is not None:
        today_north = north_flow[0]['net_amount']
        if today_north > 30:
            parts.append(f'北向资金大幅流入{today_north:.1f}亿，信号积极。')
        elif today_north > 0:
            parts.append(f'北向资金小幅流入{today_north:.1f}亿。')
        elif today_north < -30:
            parts.append(f'北向资金大幅流出{abs(today_north):.1f}亿，信号偏空。')
        else:
            parts.append(f'北向资金小幅流出{abs(today_north):.1f}亿。')

    if not parts:
        parts.append('数据有限，建议结合其他渠道信息综合判断。')

    return '\n'.join(parts)


# ============================================================
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='A股数据采集 v6 纯API版')
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

    print(f'📊 A股数据采集 v6 [纯API版] [{args.mode}] - {date_fmt}')

    data = {}
    errors = []

    # 1. A股指数（所有模式）
    print('  [指数] A股大盘...')
    try:
        data['a_indices'] = get_a_share_indices()
        for idx in data['a_indices'][:3]:
            print(f'    ✅ {idx["name"]}: {idx["price"]:.2f} ({idx["change_pct"]:+.2f}%)')
    except Exception as e:
        errors.append(f'A股指数: {e}')
        data['a_indices'] = []

    # 2. 美股指数 + 个股（盘前和收盘）
    if args.mode in ('premarket', 'closing', 'full'):
        print('  [美股] 指数+个股...')
        try:
            data['us_indices'] = get_us_indices()
            data['us_stocks'] = get_us_stocks()
            for idx in data['us_indices'][:2]:
                print(f'    ✅ {idx["name"]}: {idx["price"]:,.2f} ({idx["change_pct"]:+.2f}%)')
        except Exception as e:
            errors.append(f'美股: {e}')
            data['us_indices'] = []
            data['us_stocks'] = []

    # 3. 商品期货（盘前和收盘）
    if args.mode in ('premarket', 'closing', 'full'):
        print('  [商品] 期货...')
        try:
            data['commodities'] = get_commodities()
            for key, com in data['commodities'].items():
                print(f'    ✅ {key}: {com["price"]} ({com["change_pct"]:+.2f}%)')
        except Exception as e:
            errors.append(f'商品: {e}')
            data['commodities'] = {}

    # 4. 恒生指数期货（盘前）
    if args.mode in ('premarket', 'closing', 'full'):
        print('  [亚太] 恒生期货...')
        try:
            data['hk_futures'] = get_hk_futures()
            if data['hk_futures']:
                print(f'    ✅ 恒生期货: {data["hk_futures"]["price"]} ({data["hk_futures"]["change_pct"]:+.2f}%)')
        except Exception as e:
            errors.append(f'恒生期货: {e}')
            data['hk_futures'] = None

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
    if args.mode in ('premarket', 'closing', 'full'):
        print('  [新闻] 财联社...')
        try:
            data['news'] = get_cls_news()
            print(f'    ✅ {len(data["news"])} 条')
        except Exception as e:
            errors.append(f'新闻: {e}')
            data['news'] = []

    # 7. 龙虎榜（收盘）
    if args.mode in ('closing', 'full'):
        print('  [龙虎榜] 数据中心...')
        try:
            data['dragon_tiger'] = get_dragon_tiger_list()
            print(f'    ✅ {len(data["dragon_tiger"])} 条')
        except Exception as e:
            errors.append(f'龙虎榜: {e}')
            data['dragon_tiger'] = []

    # 8. 北向资金（收盘）
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
