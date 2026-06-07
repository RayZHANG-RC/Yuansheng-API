\*\*“面向易学专家的 LLM 配置调优思路”\*\*（不含代码）

专讲如何把 GPT-5-nano 的生成参数调成更贴合命理工作流。要点是：把“温度/采样/惩罚/长度/结构化输出”这些通用拨盘，翻译成你熟悉的卦气、格局与断语风格的可控旋钮。文末附上相关官方文档依据。([OpenAI平台][1])

# 你要调的，究竟在“管”什么

* **temperature（温度）**：相当于“放胆说话”的刻度。越低越谨慎复现既有口径；越高越敢联想发散。用于控制“金口直断 vs. 机锋开示”的气口。([OpenAI平台][2])
* **top\_p（核采样）**：像“拣最可能的几条卦象来断”。p 越小，越只取头部常见说法；越大，允许小众但可能有启发的表达。与 temperature 联动，通常二者择一侧重。([OpenAI平台][2])
* **frequency\_penalty / presence\_penalty（重复/存在惩罚）**：抑制“同一句口诀反复掰扯”。前者按出现频率扣，后者更鼓励引入新点。对**避免同义赘述**很有效。([OpenAI平台][2])
* **输出长度上限**：

  * Chat Completions 用 **max\_tokens**；
  * Responses 用 **max\_output\_tokens**。
    这决定一篇“详批/总批”的最长铺陈篇幅。([OpenAI平台][2])
* **response\_format（结构化输出）**：要求模型严格按照你给的 JSON Schema 吐结果，适合“固定栏位的合盘审阅单/风控矩阵”。设置为 **json\_schema** 并 **strict**，稳定性最高。([OpenAI平台][1])

---

# 典型命理场景 → 推荐拨盘

把工作拆成 5 种“出活儿”的形态，每种给一套直观的调参口径（区间可微调）：

1. **金口直断（要稳要准）**
   适用：四柱核对、格局判断、刑冲合害定性

   * temperature：**0.2–0.4**（降低偶然性）
   * top\_p：**0.85–0.95**（保主流表达）
   * frequency\_penalty：**0.2–0.5**（压重复断语）
   * presence\_penalty：**0.0–0.2**
   * 长度：中等（避免跑题）
   * 若要落表：启用 **response\_format=json\_schema + strict**，把结论写进固定字段。([OpenAI平台][1])

2. **叙事开示（要通达人心）**
   适用：命理解读、择日建议的“因果说明”

   * temperature：**0.7–1.0**（允许更自然的语言流）
   * top\_p：**0.9**
   * frequency\_penalty：**0.2**（避免啰嗦）
   * presence\_penalty：**0.3–0.6**（鼓励补充视角）
   * 长度：适中到偏长（保完整论证链）

3. **合盘风控矩阵（要可比可算）**
   适用：B2B/B2C 中台的评分、阈值与建议卡片

   * temperature：**0.4–0.6**（稳）
   * top\_p：**0.85–0.9**
   * frequency\_penalty：**0.3–0.6**（压模板化复述）
   * presence\_penalty：**0.0–0.3**
   * 长度：**足够覆盖各分支理由**；
   * **强烈建议**用 **response\_format=json\_schema + strict** 产出结构化字段，方便前端/报表聚合。([OpenAI平台][1])

4. **术语校勘 & 格式复核（要一致可复现）**
   适用：专家审稿、统一术语与格式

   * temperature：**0.3–0.5**
   * top\_p：**0.8–0.9**
   * frequency\_penalty：**0.4–0.8**（强压同句回流）
   * presence\_penalty：**0–0.2**
   * 如需要严格一致：在调用端配合固定 **seed**（同输入重跑更一致）。([OpenAI平台][2])

5. **长篇“总批”与多分支比对（要覆盖全面）**
   适用：年运/大运+流年+刑冲合害大综述

   * 选择“接口决定的长度参数”：

     * Chat：调 **max\_tokens**；
     * Responses：调 **max\_output\_tokens**；
   * temperature：**0.5–0.8**
   * top\_p：**0.9**
   * 辅以适度 **frequency\_penalty**，避免“同理路换说法”的冗长。([OpenAI平台][2])

---

# 易学语境下的三条“总诀”

1. **“格局定，温度稳”**
   如果你已知格局（如“官印相生、三刑成立”），就把 temperature 压低，让模型更像“按谱断事”；若还在探路期，再适度上调 temperature/top\_p 让它冒出可比较的备选论证。([OpenAI平台][2])

2. **“定栏位，用结构化”**
   只要落到表单/卡片（例如你给的 riskDecisionMatrix、branchInteractions 等），就用 **response\_format=json\_schema + strict**，模型会**强制**按 schema 产出，极大降低“字段缺漏/拼写跑偏”。([OpenAI平台][1])

3. **“避赘述，调惩罚”**
   出现“同一句口诀不同说法反复出现”，优先加 **frequency\_penalty**；若想引入全新切口，再加一点 **presence\_penalty**。两者合用，比一味拉低 temperature 更不伤内容密度。([OpenAI平台][2])

---

# 诊断式调参：像校盘一样排错

* **现象：论证老在同一句绕** → 升 **frequency\_penalty**（0.3 → 0.7）。
* **现象：话题不展开** → 升 **presence\_penalty**（0.2 → 0.5）或小幅升 **temperature**。
* **现象：结论飘** → 降 **temperature**（≤0.5），并缩小 **top\_p**（≤0.9）。
* **现象：字段缺/类型偏** → 开 **json\_schema + strict**（结构化输出）。([OpenAI平台][1])
* **现象：同样输入不同口风** → 固定 **seed**（可复现），并保持 messages 与参数完全一致。([OpenAI平台][2])

---

# 接口选择与长度预算（务实）

* 你若走 **Chat Completions**，请用 **max\_tokens** 管控篇幅；
* 你若走 **Responses**，请用 **max\_output\_tokens**。
  二者只取其一，跟随你接的具体 API 端点；别混用名词。([OpenAI平台][2])

---

# 为什么“结构化输出”对合盘场景是神助攻

合盘报告常要产出 **可比、可检索、可回归** 的字段（总分、阈值、分项建议、刑冲合害清单等）。使用 **response\_format: { type: "json\_schema", strict: true }** 时，模型会以你提供的 schema 为“模板”，严格填空，能显著减少后处理复杂度与“字段跑偏”的人工返工。([OpenAI平台][1])

---

## 参考（官方文档）

* OpenAI **Structured Outputs**（含 `response_format: { type: "json_schema", strict: true }` 的说明）。([OpenAI平台][1])
* OpenAI **API 参考**（Chat/Responses 的生成参数：temperature、top\_p、penalties、以及 Chat 的 `max_tokens` 与 Responses 的 `max_output_tokens` 等字段定义）。([OpenAI平台][2])

> 小结：把“温度/核采样/惩罚/长度/结构化”当作五套旋钮。先按场景定“准还是活”，再通过结构化把结论落进固定栏位。这样既保你“按书立断”的专业气口，又能在需要时展开成贴心的叙事开示。

[1]: https://platform.openai.com/docs/guides/structured-outputs?utm_source=chatgpt.com "Structured model outputs - OpenAI API"
[2]: https://platform.openai.com/docs/api-reference/chat/create?utm_source=chatgpt.com "API Reference"
