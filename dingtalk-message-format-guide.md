# 钉钉消息推送适配指南（A 股复盘报告）

当应用生成 A 股复盘报告并需要推送到钉钉时，必须遵循以下格式规范以确保图文并茂的消息完美适配钉钉的消息格式。

## 消息发送方式选择

| 场景 | 命令 | 身份 | 适用 |
|------|------|------|------|
| 以机器人身份发送 | `dws chat message send-by-bot` | 企业机器人 | 定时推送、自动化报告 |
| 以 Webhook 发送 | `dws chat message send-by-webhook` | 自定义机器人 | 告警、简单通知 |
| 以个人身份发送 | `dws chat message send --group` | 当前用户 | 手动推送 |

## 钉钉 Markdown 消息格式规范

**支持的 Markdown 语法：**
- 标题：`# H1`, `## H2`, `### H3`
- 粗体：`**文本**`
- 斜体：`*文本*`
- 链接：`[文本](URL)`
- 列表：`-` 或 `1.`
- 引用：`>`
- 代码块：``` ```text ```
- 换行：使用 `\n\n`（两个换行符）

**不支持的格式：**
- ❌ 表格（Markdown table）
- ❌ 复杂 HTML
- ❌ 内联图片（`![alt](url)`）

## 图文消息最佳实践

由于钉钉 Markdown **不支持直接嵌入图片**，采用以下策略实现图文并茂：

### 方案 1：图片 + 文字分开发送（推荐）

```bash
# 第 1 条：发送图片（通过钉盘或临时 URL）
dws chat message send-by-bot --robot-code <robot-code> \
  --group <openconversation_id> \
  --title "大盘走势图" \
  --text "https://drive-storage.dingtalk.com/xxx/market-chart.png" \
  --format json

# 第 2 条：发送文字分析（Markdown 格式）
dws chat message send-by-bot --robot-code <robot-code> \
  --group <openconversation_id> \
  --title "A 股复盘报告" \
  --text "# 📊 A 股复盘报告\n\n## 大盘概览\n- **上证指数**: 3245.67 (+1.23%)\n- **深证成指**: 11234.56 (+0.89%)\n- **创业板指**: 2345.67 (+1.56%)\n\n## 连板天梯\n- **5 连板**: XXXX, XXXX\n- **4 连板**: XXXX\n- **3 连板**: XXXX, XXXX, XXXX\n\n## 龙虎榜亮点\n- **净买入 Top1**: XXXX (1.23 亿)\n- **机构席位**: XXXX (5678 万)\n\n> 详细分析请查看：[完整报告](https://doc.dingtalk.com/xxx)" \
  --format json
```

### 方案 2：使用钉钉文档链接

将完整的图文报告生成钉钉文档，然后在消息中发送文档链接：

```markdown
# 📈 A 股复盘报告 - 2026 年 3 月 24 日

## 🔥 今日热点
- AI应用爆发
- 半导体反弹
- 新能源分化

## 📊 核心数据
- 涨停家数：89 家
- 跌停家数：3 家
- 连板高度：5 板

👉 **查看详细图文报告**: https://doc.dingtalk.com/doc/xxx
```

## A 股复盘报告消息模板

```markdown
# 📊 A 股复盘报告 | {日期}

---

## 🎯 大盘速览
- **上证指数**: {value} ({pct}), 成交{vol}亿
- **深证成指**: {value} ({pct}), 成交{vol}亿
- **创业板指**: {value} ({pct}), 成交{vol}亿

---

## 🏆 连板天梯
- **{height}连板**: {stocks}
- **{height-1}连板**: {stocks}
- **{height-2}连板**: {stocks}

---

## 💰 龙虎榜亮点
- **净买入 Top1**: {stock} ({amount})
- **机构加持**: {stock} ({amount})
- **游资动向**: {description}

---

## 📈 技术图表
> 提示：图片需单独发送，或通过钉钉文档承载
> - 大盘走势图：[查看图片](image-url-1)
> - 连板分布图：[查看图片](image-url-2)
> - 资金流向图：[查看图片](image-url-3)

---

## 📝 明日策略
{strategy_text}

---

> 数据来源：Wind / 同花顺  
> 生成时间：{timestamp}  
> 完整报告：[点击查看](doc-url)
```

## 实际发送示例

```bash
# 步骤 1: 生成图表并上传到钉盘
# （通过应用自动生成，获取图片 URL）

# 步骤 2: 发送第一条消息（图片）
dws chat message send-by-bot --robot-code "a-share-review-bot" \
  --group "openconv_market_group_123" \
  --title "大盘走势图" \
  --text "https://drive-storage.dingtalk.com/path/to/chart.png" \
  --format json

# 步骤 3: 发送第二条消息（文字分析）
dws chat message send-by-bot --robot-code "a-share-review-bot" \
  --group "openconv_market_group_123" \
  --title "📊 A 股复盘报告" \
  --text "# 📊 A 股复盘报告 | 2026-03-24\n\n## 🎯 大盘速览\n- **上证指数**: 3245.67 (+1.23%), 成交 4567 亿\n- **深证成指**: 11234.56 (+0.89%), 成交 5678 亿\n- **创业板指**: 2345.67 (+1.56%), 成交 2345 亿\n\n## 🏆 连板天梯\n- **5 连板**: 龙头股份，凤凰光学\n- **4 连板**: 东方明珠\n- **3 连板**: 科技先锋，创新电子，智能制造\n\n## 💰 龙虎榜亮点\n- **净买入 Top1**: 龙头股份 (1.23 亿)\n- **机构加持**: 凤凰光学 (5678 万)\n- **游资动向**: 知名游资\"XX 路\"大举买入智能制造\n\n## 📝 明日策略\n市场情绪回暖，建议关注低位补涨机会，谨慎追高。\n\n> 生成时间：2026-03-24 18:00  \n> 完整报告：[点击查看](https://doc.dingtalk.com/doc/abc123)" \
  --format json
```

## 注意事项

1. **消息长度限制**：单条 Markdown 消息不超过 4096 字符，超长内容建议拆分多条或使用文档链接
2. **发送频率限制**：机器人发消息频率不超过 20 条/分钟
3. **@提及功能**：如需@特定用户，在 text 中包含 `@userId`，并使用 `--at-users userId1,userId2`
4. **图片处理**：
   - 优先使用钉盘永久链接
   - 或使用临时 CDN URL（注意有效期）
   - 多图建议合并为长图后发送
5. **标题优化**：使用 emoji 和简洁描述，提高消息辨识度
6. **换行规范**：使用 `\n\n` 确保段落清晰，避免格式混乱

## 错误处理

| 错误场景 | 处理方式 |
|---------|---------|
| 消息发送失败 | 检查 robot-code 和 group-id 是否正确 |
| 图片无法显示 | 确认 URL 可公开访问，或改用钉盘链接 |
| Markdown 格式错乱 | 检查特殊字符转义，简化格式 |
| 频率超限 | 降低发送频率，增加间隔时间 |
