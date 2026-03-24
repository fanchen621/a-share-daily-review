# A 股复盘钉钉消息格式化技能

这是一个专门用于将 A 股复盘数据格式化为钉钉消息的辅助技能/模块。

## 技能描述

当应用开发技能创建 A 股复盘应用时，可以附加此技能以确保生成的消息完美适配钉钉的消息格式。

## 核心能力

### 1. 数据格式化

将原始股票数据转换为钉钉 Markdown 兼容格式：

```python
def format_market_data(data):
    """格式化大盘数据为钉钉 Markdown"""
    return f"""# 📊 A 股复盘报告 | {data['date']}

---

## 🎯 大盘速览
- **上证指数**: {data['sh_index']} ({data['sh_change']}%), 成交{data['sh_volume']}亿
- **深证成指**: {data['sz_index']} ({data['sz_change']}%), 成交{data['sz_volume']}亿
- **创业板指**: {data['cyb_index']} ({data['cyb_change']}%), 成交{data['cyb_volume']}亿
"""

def format_lianban_tier(data):
    """格式化连板天梯"""
    lines = ["---", "", "## 🏆 连板天梯"]
    for tier in sorted(data.keys(), reverse=True):
        stocks = ", ".join(data[tier])
        lines.append(f"- **{tier}连板**: {stocks}")
    return "\n".join(lines)

def format_longhubang(data):
    """格式化龙虎榜数据"""
    return f"""
---

## 💰 龙虎榜亮点
- **净买入 Top1**: {data['top1_stock']} ({data['top1_amount']})
- **机构加持**: {data['institution_stock']} ({data['institution_amount']})
- **游资动向**: {data['youzi_description']}
"""
```

### 2. 图片处理策略

由于钉钉 Markdown 不支持内联图片，提供以下方案：

```python
class DingTalkImageStrategy:
    """钉钉图片发送策略"""
    
    @staticmethod
    def send_image_first(image_url, title, robot_code, group_id):
        """方案 A：先发送图片"""
        cmd = f'''dws chat message send-by-bot --robot-code "{robot_code}" \\
  --group "{group_id}" \\
  --title "{title}" \\
  --text "{image_url}"'''
        return cmd
    
    @staticmethod
    def send_doc_link(doc_url, text):
        """方案 B：使用钉钉文档链接"""
        return f"""👉 **查看详细图文报告**: {doc_url}\n\n{text}"""
```

### 3. 完整消息组装

```python
def assemble_full_message(review_data, image_urls=None):
    """组装完整的钉钉消息"""
    
    header = f"# 📊 A 股复盘报告 | {review_data['date']}\n\n"
    
    market_section = format_market_data(review_data['market'])
    lianban_section = format_lianban_tier(review_data['lianban'])
    longhubang_section = format_longhubang(review_data['longhubang'])
    
    # 图片提示（如果有多图）
    image_note = ""
    if image_urls:
        image_note = """
---

## 📈 技术图表
> 图片已通过单独消息发送，请向上滑动查看
"""
    
    strategy_section = f"""
---

## 📝 明日策略
{review_data['strategy']}
"""
    
    footer = f"""
---

> 生成时间：{review_data['timestamp']}  
> 完整报告：[点击查看]({review_data['doc_url']})
"""
    
    full_message = (
        header + 
        market_section + 
        lianban_section + 
        longhubang_section +
        image_note +
        strategy_section +
        footer
    )
    
    # 检查长度（钉钉限制 4096 字符）
    if len(full_message) > 4096:
        # 简化版本
        full_message = simplify_message(full_message)
    
    return full_message
```

### 4. 发送命令生成器

```python
class DingTalkMessageSender:
    """钉钉消息发送器"""
    
    def __init__(self, robot_code, group_id):
        self.robot_code = robot_code
        self.group_id = group_id
    
    def send_image(self, image_url, title="图表"):
        """发送图片消息"""
        return f'''dws chat message send-by-bot --robot-code "{self.robot_code}" \\
  --group "{self.group_id}" \\
  --title "{title}" \\
  --text "{image_url}" \\
  --format json'''
    
    def send_text(self, markdown_text, title="A 股复盘报告"):
        """发送文字消息（Markdown）"""
        # 转义特殊字符
        escaped_text = markdown_text.replace('"', '\\"').replace('\n', '\\n')
        return f'''dws chat message send-by-bot --robot-code "{self.robot_code}" \\
  --group "{self.group_id}" \\
  --title "{title}" \\
  --text "{escaped_text}" \\
  --format json'''
    
    def send_batch(self, image_urls, markdown_text):
        """批量发送（图片 + 文字）"""
        commands = []
        
        # 发送图片
        for i, url in enumerate(image_urls):
            title = f"图表{i+1}"
            commands.append(self.send_image(url, title))
        
        # 发送文字
        commands.append(self.send_text(markdown_text))
        
        return commands
```

## 使用示例

### 在 AI应用创建时使用

```bash
dws aiapp create \
  --prompt "创建 A 股复盘应用，集成钉钉消息格式化技能" \
  --skills a-share-dingtalk-formatter \
  --format json
```

### 在代码中调用

```python
# 初始化发送器
sender = DingTalkMessageSender(
    robot_code="a-share-review-bot",
    group_id="openconv_market_group_123"
)

# 准备数据
review_data = {
    'date': '2026-03-24',
    'market': {
        'sh_index': '3245.67',
        'sh_change': '+1.23',
        'sh_volume': '4567',
        # ...
    },
    'lianban': {
        '5': ['龙头股份', '凤凰光学'],
        '4': ['东方明珠'],
        # ...
    },
    # ...
}

# 生成消息
message = assemble_full_message(review_data)

# 发送
commands = sender.send_batch(
    image_urls=['https://.../chart1.png'],
    markdown_text=message
)

# 执行命令
for cmd in commands:
    subprocess.run(cmd, shell=True)
```

## 注意事项

1. **字符限制**：单条消息不超过 4096 字符
2. **频率限制**：机器人发送频率不超过 20 条/分钟
3. **图片 URL**：必须使用可公开访问的链接（推荐钉盘）
4. **特殊字符转义**：双引号、换行符需要正确转义
5. **@功能**：如需@用户，添加 `--at-users userId` 参数

## 错误处理

```python
def handle_send_error(error):
    """处理发送错误"""
    if "robot-code" in error:
        return "❌ 机器人 Code 错误，请检查配置"
    elif "group" in error:
        return "❌ 群 ID 错误，请确认机器人已加入该群"
    elif "rate limit" in error:
        return "⚠️ 发送频率超限，请稍后重试"
    else:
        return f"❌ 发送失败：{error}"
```

## 配置文件示例

```yaml
# config.yaml
dingtalk:
  robot_code: "a-share-review-bot"
  group_id: "openconv_market_group_xxx"
  
  # 可选：@特定用户
  at_users:
    - "userId1"
    - "userId2"
  
  # 发送时间（每个交易日）
  schedule:
    cron: "0 18 * * 1-5"  # 工作日 18:00
  
data_source:
  tushare_token: "your_token_here"
  akshare_proxy: ""  # 可选代理
```

## 与其他技能配合

- **数据采集技能**：提供原始股票数据
- **图表生成技能**：生成 K 线图、资金流向图等
- **文档生成技能**：创建完整的钉钉文档报告
- **定时任务技能**：设置每日自动推送

## 测试验证

创建测试数据验证消息格式：

```python
test_data = {
    'date': '2026-03-24',
    'market': {
        'sh_index': '3245.67',
        'sh_change': '+1.23',
        'sh_volume': '4567',
        'sz_index': '11234.56',
        'sz_change': '+0.89',
        'sz_volume': '5678',
        'cyb_index': '2345.67',
        'cyb_change': '+1.56',
        'cyb_volume': '2345'
    },
    'lianban': {
        '5': ['龙头股份', '凤凰光学'],
        '4': ['东方明珠'],
        '3': ['科技先锋', '创新电子', '智能制造']
    },
    'longhubang': {
        'top1_stock': '龙头股份',
        'top1_amount': '1.23 亿',
        'institution_stock': '凤凰光学',
        'institution_amount': '5678 万',
        'youzi_description': '知名游资"XX 路"大举买入智能制造'
    },
    'strategy': '市场情绪回暖，建议关注低位补涨机会，谨慎追高。',
    'timestamp': '2026-03-24 18:00',
    'doc_url': 'https://doc.dingtalk.com/doc/abc123'
}

# 生成并打印测试消息
message = assemble_full_message(test_data)
print(message)
```

这样可以预览最终发送到钉钉的消息效果。
