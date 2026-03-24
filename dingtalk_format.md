# 钉钉消息格式参考

## Markdown 语法限制

钉钉机器人支持的 Markdown 子集：
- **粗体**: `**文本**`
- *斜体*: `*文本*`
- 链接: `[文本](URL)`
- 图片: `![替代文本](图片URL)`
- 有序列表: `1. item`
- 无序列表: `- item` 或 `* item`
- 标题: `#` (仅一级) 或 `##` (二级)
- 引用: `> 文本`

**不支持**: 表格、代码块、删除线

## 最佳实践

1. **标题用二级 `##`**: 一级标题在手机端太大
2. **用 emoji 增加可读性**: 🔥📈💰⚠️🔮
3. **关键数字加粗**: 如 `**涨跌比: 1.5:1**`
4. **分隔线用 `---`**: 分隔不同分析模块
5. **避免表格**: 用列表代替
6. **控制长度**: 钉钉消息建议不超过 4000 字符

## 发送示例

```python
import requests
import hmac
import hashlib
import base64
import urllib.parse
import time

def send_dingtalk(webhook, secret, title, text):
    timestamp = str(round(time.time() * 1000))
    secret_enc = secret.encode('utf-8')
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

    url = f'{webhook}&timestamp={timestamp}&sign={sign}'
    data = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
        "at": {"isAtAll": True}
    }
    r = requests.post(url, json=data, timeout=10)
    return r.json()
```
