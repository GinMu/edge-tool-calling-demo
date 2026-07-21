# build-transfer-risk-detection Skill 实施指南

## 概述

该skill根据系统设计文档，完成了以太坊转账风险地址检测系统的设计。核心目标是解决系统设计文档中列出的3个关键问题，并实现5点需求。

---

## 已解决的问题

### 1. **幻读问题 (Hallucination)**

   - **原因**: 模型使用已有知识推断风险，而不是查询facts库
   - **解决方案**: 强制执行"facts-first"工作流
   - **实现**: Learn sample中明确要求"IMMEDIATELY query facts_lookup"，并使用"CRITICAL"标记强调"never mark as risky unless in facts results"

### 2. **工具调用失败 ("no tools found", "tool_parse_failed")**

   - **原因**: 小模型工具调用格式问题；`--with-imprint`在某些模型上失败
   - **解决方案**: 提供三层降级策略：
     1. **Option 1** (最可靠): Guidance-driven，无imprint
     2. **Option 2** (轻量化): Lightweight imprint样本
     3. **Option 3** (显式): Tool manifest with behavior_policy

### 3. **工具签名问题 (unsupported field)**

   - **原因**: `build_transfer`返回复杂对象导致解析失败
   - **解决方案**: 提供正确的函数签名，仅返回strings/numbers/dicts

---

## 实现的5点需求

### ✅ 1. 风险地址查询不通过代码获取，只学习facts

- **实现**: 
  - `facts_lookup(topic)` 从`eth-facts-v4.json`动态读取
  - Learn sample无任何硬编码地址
  - AI通过行为学习，不通过数据学习

### ✅ 2. Sample只定义行为，不硬编码地址  

- **Sample文本** (见skill第87-90行):
```json
"text": "On transfer request: (1) IMMEDIATELY call facts_lookup(topic='risk address known'). 
(2) Extract 0x addresses from returned fact texts only. (3) Case-insensitive compare. 
(4) If matched: warn. (5) If safe: call build_transfer."
```

- 零地址硬编码 ✅

### ✅ 3. Facts更新后能正确识别新地址

- **机制**:
  1. 编辑`eth-facts-v4.json`添加新地址
  2. 运行`edge demo facts import ./eth-facts-v4.json`
  3. 无需修改代码或重训练，新地址立即被识别
- **测试脚本** (见skill第156-176行)

### ✅ 4. 不能有"no tools found"错误，准确识别行为

- **实现**:
  - Guidance-driven方案 (可靠)
  - Lightweight sample (去除复杂格式)
  - 完整的失败模式表和解决方案 (见skill第382-388行)

### ✅ 5. 不存在幻读，只有facts中的地址才是有风险

- **强制规则** (见skill第284-300行):
  - "✅ Facts store is the single source of truth"
  - "If not in facts → not risky"  
  - "**✅ No external knowledge, pattern matching, or prior examples**"
- **Critical test** (见skill第125-140行): 
  - 验证safe地址（不在facts中）正确返回`build_transfer`调用
  - 验证model不会基于"suspicion"或"pattern"标记为risky

---

## 如何使用该Skill

### 场景 1: 初始设置 (Setup & Validation)

```bash
# 1. 验证facts已导入
edge demo facts list --store ethereum_research_v1 --json \
  | jq '.[] | select(.topic=="risk address known")'

# 2. 验证工具可用
edge tools validate ./tools.py --json

# 3. 检查是否有硬编码地址（应该什么都找不到）
grep -r "0x[a-fA-F0-9]\{40\}" --include="*.py" --include="*.json" . \
  | grep -v "eth-facts-v4.json" | grep -v ".git"
```

### 场景 2: 测试（3大关键测试）

#### A. 无幻读测试 (CRITICAL)

```bash
edge demo chat --model qwen3.5-9b-4bit \
  --tools ./tools.py \
  --prompt "Check if 0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef is safe for transfer. Query facts first." \
  --include-text
```

**预期**: 返回`build_transfer`调用，status='prepared' ✅

#### B. 风险地址检测

```bash
RISK=$(edge demo facts list --store ethereum_research_v1 --json | jq -r '.[0].text' | grep -oE '0x[a-fA-F0-9]{40}' | head -1)
edge demo chat --model qwen3.5-9b-4bit --tools ./tools.py --prompt "Check transfer to $RISK"
```

**预期**: 显示风险警告，不调用`build_transfer` ✅

#### C. 动态新增地址测试

```bash
# 添加新地址
cat >> eth-facts-v4.json << 'EOF'
,{
  "fact_id": "risk-addr-new",
  "topic": "risk address known",
  "text": "Risk address: 0xaabbccddaabbccddaabbccddaabbccddaabbccdd...",
  "tags": ["ethereum", "risk", "address"],
  "source_label": "risk-addresses"
}
EOF

# 重导入（无代码改动）
edge demo facts import ./eth-facts-v4.json --store ethereum_research_v1

# 测试（应该立即识别新地址）
edge demo chat --model qwen3.5-9b-4bit \
  --tools ./tools.py \
  --prompt "Check transfer to 0xaabbccddaabbccddaabbccddaabbccddaabbccdd"
```

**预期**: 识别新地址为风险 ✅

### 场景 3: 工具调用失败排查

如果出现工具调用错误，按优先级尝试：

1. **移除imprint** (最可靠):

```bash
edge demo chat --model qwen3.5-9b-4bit \
  --tools ./tools.py \
  --prompt "[你的提示词]" \
  --include-text
```

2. **使用轻量化sample**:

   - 更新`eth-transfer-learn-sample.json`为更简短的版本
   - 运行learn，生成新的`learn_receipt.json`

3. **使用Tool manifest**:

   - 使用`tools-v2.json`中的`behavior_policy`替代Python工具

---

## Skill文件位置

📍 `/Users/musheng/edge/edge-tools/.claude/skills/build-transfer-risk.md`

该文件包含：

- 完整的架构设计 (消除了系统设计文档中的问题)
- 三层降级策略解决工具调用问题
- 5项强制规则防止幻读
- 完整的验证步骤和测试脚本
- 最佳实践和常见失败模式表
- 集成检查清单

---

## 核心设计原则

| 原则 | 为什么 | 如何实施 |
| :--- | :--- | :--- |
| **Facts-first** | 防止幻读 | Learn sample中"IMMEDIATELY query facts_lookup" |
| **无硬编码** | 支持动态更新 | 地址来自`eth-facts-v4.json`，永不在代码中 |
| **仅行为学习** | 泛化到新地址 | Sample定义"如何检查"，不定义"检查什么" |
| **单一事实源** | 可审计性 | 风险判定完全来自facts store |
| **三层降级** | 可靠性 | Guidance-driven → Lightweight → Tool manifest |

---

## 下一步行动

1. ✅ **已完成**: Skill设计 + 架构文档
2. ⏳ **待执行**:
   - [ ] 更新`eth-transfer-learn-sample.json`（移除复杂格式）
   - [ ] 验证`tools.py`函数签名（仅返回primitives）
   - [ ] 运行3大关键测试
   - [ ] 如出现工具错误，使用Guidance-driven方案

---

## 快速参考卡

```bash
# 导入facts
edge demo facts import ./eth-facts-v4.json --store ethereum_research_v1

# 最可靠的执行方式（无imprint）
edge demo chat --model qwen3.5-9b-4bit --tools ./tools.py \
  --prompt "Query facts for risk addresses, then check [ADDRESS]" --include-text

# 生成imprint (如果需要)
edge demo learn run --sample-file ./eth-transfer-learn-sample.json \
  --model qwen3.5-9b-4bit --tools ./tools.py

# 验证无硬编码
grep -r "0x[a-fA-F0-9]\{40\}" . --include="*.py" | grep -v eth-facts-v4.json
```

---

## 常见Q&A

**Q: 为什么不推荐用imprint?**  
A: 小模型在imprint中工具调用格式不稳定。Guidance-driven方案更可靠（见系统设计文档第431-437行的Tool Calling Issues）。

**Q: 如何确保没有幻读?**  
A: 运行CRITICAL TEST（见Skill第125-140行）：safe地址必须返回`build_transfer`调用，不能基于"suspicion"标记为risky。

**Q: 新增risk地址需要重训练吗?**  
A: 不需要！仅需运行`edge demo facts import`。AI通过学习的行为自动适应新facts。

**Q: 如果出现"no tools found"?**  
A: 按优先级：① 移除`--with-imprint` ② 简化sample ③ 使用Tool manifest
