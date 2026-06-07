# real_toc 技术文档

## 🚨 重点提醒（前端/运维人员必读）

### 🔥 重点中的重点：前端数据接口
**前端需要传入的文件：**
- `data_prompt_engineering/real_toc/session_input.json`
- `data_prompt_engineering/real_toc/user_settings.json`

**各个字段的详细解释详见 JSOC 规范**

**前端将会接收到的返回内容：**
- `sessions/<session_id>/session_output.json`

---

## ⚠️ 重大缺陷：提示词攻击风险
**严重问题**：如果用户已经在 `user_specification` 中给出了对于所提问题的答案（例如已经明确表示"想不想要孩子"），那么有可能结果会倾向于往用户已经回答的方向去更改。

**这属于提示词攻击，属于重大缺陷，需要在模型调用时加强上下文隔离和结果约束。**

---

本文件详细记录 real_toc 模块的核心流程、数据契约、脚本串联机制，面向前端、后端及运维人员。

## 📁 目录结构概览

```
data_prompt_engineering/real_toc/
├── 📄 main.py                          # 主入口脚本，协调整个流程
├── 📄 pipeline_core.py                 # 公共核心模块，包含日志、配置等功能
├── 📄 config.json                      # OpenAI 密钥 + 合作方 API（partner_api）配置
├── 📄 technical_overview.md            # 技术总览文档
│
├── 📋 输入文件
│   ├── 📄 _session_input.jsonc          # 开发阶段输入模板（带注释）
│   ├── 📄 _user_settings.jsonc          # 用户设置模板（带注释）
│   ├── 📄 session_input.json            # 生产环境输入文件
│   └── 📄 user_settings.json            # 生产环境用户设置
│
├── 🔧 步骤脚本
│   ├── 📄 step1_validate.py             # 健康检查与数据验证
│   ├── 📄 step2_prepare.py              # 数据准备与排盘计算
│   ├── 📄 step2_5_synastry.py           # 合盘分析（条件触发）
│   ├── 📄 step3_llm_quant.py            # LLM量化分析
│   ├── 📄 step4_llm_qual.py             # LLM质化优化
│   └── 📄 step5_finalize.py             # 结果汇总与输出
│
├── 📚 配置与模板
│   └── question_config/                 # 问题配置目录
│       ├── 📄 *.jsonc                   # 各问题类型的配置模板
│       ├── 📄 gpt41_llm_config.csv      # GPT-4.1模型配置
│       ├── 📄 gpt5_llm_config.csv       # GPT-5模型配置
│       └── 📄 README.md                 # 配置说明文档
│
├── 🎯 排盘计算模块
│   └── calculate_palette/               # 排盘计算目录
│       ├── 📄 ip_bazi_unified.py        # IP地理定位增强模块（测试中）
│       ├── 📄 TungShing.py              # 黄历：严格校正后的
│       ├── 📄 八字.py                   # 八字计算模块
│       ├── 📄 六爻.py                   # 六爻排盘模块
│       ├── 📄 小六壬.py                 # 小六壬排盘模块
│       ├── 📄 紫微斗数.py               # 紫微斗数模块
│       └── 📁 data/                     # 排盘数据文件
│
└── 📤 输出目录
    └── sessions/                        # 会话输出目录
        └── session_YYYYMMDD_demo/       # 具体会话目录
            ├── 📁 artifacts/            # 中间产物
            ├── 📁 palettes/             # 排盘结果
            ├── 📄 pipeline_summary.json # 流程摘要
            └── 📄 session_output.json   # ⭐ 最终输出（前端使用）
```

## 🔧 模块功能详解

### 🏗️ 公共核心模块

#### `pipeline_core.py` - 核心功能库
**主要功能：**
- `log_message()` - 统一日志记录函数
- 配置管理 - 读取和解析 `config.json`
- 错误处理 - 统一的异常处理机制
- 文件操作 - JSON读写、路径处理等工具函数

**被调用情况：** 被所有步骤脚本和主入口脚本导入使用

### 📋 输入处理模块

#### `step1_validate.py` - 健康检查与数据验证
**完成的功能：**
- ✅ 验证输入文件完整性（session_input.json、user_settings.json、config.json）
- ✅ 检查 question_config 目录结构和文件存在性
- ✅ 创建会话根目录 `sessions/<session_id>/`
- ✅ 生成健康检查报告和验证结果

**调用关系：**
- 调用 `pipeline_core.py` 的日志和配置功能
- 不依赖其他步骤脚本，可独立运行

#### `step2_prepare.py` - 数据准备与排盘计算
**完成的功能：**
- ✅ 解析 `_session_input.jsonc`/`session_input.json` 中的输入数据
- ✅ 拷贝必要的 JSONC 文件到会话目录
- ✅ 根据 `palette_data` 自动触发排盘计算：
  - 调用 `calculate_palette/八字.py` 计算八字
  - 调用 `calculate_palette/小六壬.py` 计算小六壬
  - 调用 `calculate_palette/六爻.py` 计算六爻（如果需要）
  - 调用 `calculate_palette/紫微斗数.py` 计算紫微斗数（如果需要）
- ✅ 准备合盘数据（如果 `synastry: true`）

**调用关系：**
- 调用 `pipeline_core.py` 获取配置和日志
- 调用 `calculate_palette/` 下的各个排盘模块
- 为 `step2_5_synastry.py` 准备输入数据

### 🎯 排盘计算模块

#### `calculate_palette/TungShing.py` - 八字排盘核心库
**完成的功能：**
- ✅ 基于出生时间计算四柱八字
- ✅ 农历日期转换
- ✅ 节气计算
- ✅ 时区处理

**调用关系：** 被 `八字.py` 和其他排盘模块调用

#### `calculate_palette/八字.py` - 八字计算模块
**完成的功能：**
- ✅ 解析出生时间（YYYYMMDDHHMM 格式）
- ✅ 调用 TungShing 计算四柱八字
- ✅ 生成八字分析结果 JSON

**调用关系：**
- 调用 `TungShing.py` 进行核心计算
- 被 `step2_prepare.py` 调用

#### `calculate_palette/小六壬.py` - 小六壬排盘模块
**完成的功能：**
- ✅ 基于当前时间和小六壬算法生成排盘
- ✅ 计算神煞信息
- ✅ 生成小六壬分析结果

**调用关系：** 被 `step2_prepare.py` 调用

#### `calculate_palette/六爻.py` - 六爻排盘模块
**完成的功能：**
- ✅ 基于问题时间生成六爻卦象
- ✅ 计算爻辞和卦辞
- ✅ 生成六爻分析结果

**调用关系：** 被 `step2_prepare.py` 调用（条件触发）

#### `calculate_palette/紫微斗数.py` - 紫微斗数模块
**完成的功能：**
- ✅ 基于出生时间计算紫微斗数盘
- ✅ 计算星辰分布和宫位信息
- ✅ 生成紫微斗数分析结果

**调用关系：** 被 `step2_prepare.py` 调用（条件触发）

### 🤝 合盘处理模块

#### `step2_5_synastry.py` - 合盘分析
**完成的功能：**
- ✅ 计算 person_a 与 person_b 的合盘分析
- ✅ 生成合盘相关的量化数据
- ✅ 分析两人关系格局

**🔥 条件触发逻辑（严格双重验证）：**

**1. JSONC 配置层面的 Include 条件：**
- `question_config/xxx.jsonc` 中 `synastry.required` 必须为 `true`
- 例如：`"synastry": {"required": true}`

**2. Session Input 运行时 Include 条件：**
- `session_input.json` 中 `palette_data.synastry` 必须为 `"true"`（字符串）
- 同时需要提供 `person_a` 和 `person_b` 的完整数据

**3. Session Input 运行时 Exclude 条件：**
- ❌ **birth_time 为空字符串**：`person_a.birth_time: ""` 和 `person_b.birth_time: ""`
- ❌ **gender 为空字符串**：`person_a.gender: ""` 和 `person_b.gender: ""`
- ⚠️ **重要**：当 birth_time 和 gender 为空时，系统会跳过该合盘步骤

**触发条件完整验证流程：**
```
JSONC.synastry.required == true
AND session_input.palette_data.synastry == "true"
AND person_a.birth_time == "" AND person_a.gender == ""
AND person_b.birth_time == "" AND person_b.gender == ""
AND 存在 person_a 和 person_b 的合盘数据
```

**调用关系：**
- 调用 `pipeline_core.py` 获取配置
- 依赖 `step2_prepare.py` 准备的基础数据
- 读取 `artifacts/palette_data.json` 中的合盘数据

### 🧠 LLM 处理模块

#### `step3_llm_quant.py` - LLM 量化分析
**完成的功能：**
- ✅ 调用 LLM 生成量化分析结果
- ✅ 基于 question_config 中的模板构建提示词
- ✅ 分析排盘数据和用户输入
- ✅ 生成结构化的量化分析

**调用关系：**
- 调用 `pipeline_core.py` 获取配置和日志
- 读取 `question_config/` 中的模板文件
- 依赖前序步骤生成的排盘数据

#### `step4_llm_qual.py` - LLM 质化优化
**完成的功能：**
- ✅ 调用 LLM 优化输出质量
- ✅ 生成更易读的总结和建议
- ✅ 添加风险提示和注意事项
- ✅ 调整回答语气和格式

**调用关系：**
- 调用 `pipeline_core.py` 获取配置
- 依赖 `step3_llm_quant.py` 的量化结果

### 📊 输出处理模块

#### `step5_finalize.py` - 结果汇总
**完成的功能：**
- ✅ 汇总所有步骤的输出结果
- ✅ 生成最终的 `session_output.json`
- ✅ 创建 pipeline_summary.json 用于调试
- ✅ 格式化前端需要的输出结构

**调用关系：**
- 调用 `pipeline_core.py` 获取配置
- 整合前面所有步骤的输出结果

## 📈 模块调用关系图

```
前端输入
    ↓
📋 step1_validate.py (健康检查)
    ↓
🎯 step2_prepare.py (数据准备)
    ├── 调用 calculate_palette/八字.py
    ├── 调用 calculate_palette/小六壬.py
    ├── 调用 calculate_palette/六爻.py (条件)
    └── 调用 calculate_palette/紫微斗数.py (条件)
    ↓
🤝 step2_5_synastry.py (合盘分析 - 🔴严格条件触发)
    │   ├── ⚠️ JSONC.synastry.required == true
    │   ├── ⚠️ session_input.palette_data.synastry == "true"
    │   └── ⚠️ person_a/b birth_time & gender 必须含有合法真值
    ↓
🧠 step3_llm_quant.py (LLM量化分析)
    ├── 读取 question_config/*.jsonc
    └── 调用 pipeline_core.py
    ↓
🧠 step4_llm_qual.py (LLM质化优化)
    └── 调用 pipeline_core.py
    ↓
📊 step5_finalize.py (结果汇总)
    ↓
前端输出 (session_output.json)
```

### 🔗 公共模块调用情况

#### `pipeline_core.py` - 被以下模块调用：
- ✅ `main.py` - 获取日志和配置功能
- ✅ `step1_validate.py` - 日志记录和文件验证
- ✅ `step2_prepare.py` - 配置读取和文件操作
- ✅ `step2_5_synastry.py` - 配置和日志
- ✅ `step3_llm_quant.py` - API配置和错误处理
- ✅ `step4_llm_qual.py` - API配置和错误处理
- ✅ `step5_finalize.py` - 配置读取和文件输出

#### `config.json` - 配置内容：
- `openai.api_key` / `openai.organization_id`：管线 step1 校验与 LLM 调用（必填）
- `partner_api.*`：合作方试调 HTTP API（`api_server.py`）；含默认语气、模型集、鉴权 Key、`default_api_key_success_quota`（按 API Key 的成功次数上限）
- `security.allowed_origins`：API 的 CORS 白名单
- LLM 的 model/temperature/max_tokens 等由 `question_config/*.csv` 定义，不在此文件

#### `question_config/` - 模板文件：
- `*.jsonc` - 各问题类型的提示词模板
- `gpt41_llm_config.csv` - GPT-4.1 模型参数配置
- `gpt5_llm_config.csv` - GPT-5 模型参数配置

## 🎯 核心流程串联

### 主入口：main.py
`main.py` 是整个 real_toc 模块的统一入口，负责协调 5 个核心步骤的执行顺序：

**调用关系：**
- 导入 `pipeline_core` 模块获取日志和配置功能
- 按顺序调用 5 个步骤脚本
- 处理命令行参数和错误传递

#### 执行流程：
1. **健康检查** (`step1_validate.py`)
2. **数据准备** (`step2_prepare.py`) + 合盘处理 (`step2_5_synastry.py`)
3. **LLM 量化分析** (`step3_llm_quant.py`)
4. **LLM 质化优化** (`step4_llm_qual.py`)
5. **结果汇总** (`step5_finalize.py`)

#### 关键参数：
- `--session-input`: 会话输入文件路径
- `--user-settings`: 用户设置文件路径
- `--config-path`: 配置文件路径
- `--sessions-root`: 会话根目录
- `--question-config-dir`: 问题配置目录
- `--model-set`: 模型集选择 (gpt-4.1 或 gpt-5)

### 各步骤脚本详细功能

#### 1. step1_validate.py - 健康检查
**功能**：
- 验证输入文件完整性（session_input.json、user_settings.json、config.json）
- 检查 question_config 目录结构
- 创建会话根目录 `sessions/<session_id>/`
- 生成健康检查报告

**输出文件**：
- `sessions/<session_id>/artifacts/step1_validation.json`
- `sessions/<session_id>/artifacts/validated_data.json`

#### 2. step2_prepare.py - 数据准备
**功能**：
- 解析 `_session_input.jsonc`/`session_input.json` 中的输入数据
- 拷贝必要的 JSONC 文件到会话目录
- 根据 `palette_data` 自动触发排盘计算（八字、小六壬等）
- 准备合盘数据（如果 `synastry: true`）

**输出文件**：
- `sessions/<session_id>/palettes/` 目录下的排盘结果
- `sessions/<session_id>/artifacts/parsed_question.json`
- `sessions/<session_id>/artifacts/palette_data.json`

#### 3. step2_5_synastry.py - 合盘处理
**功能**：
- 当 `palette_data.synastry: "true"` 时自动触发
- 计算 person_a 与 person_b 的合盘分析
- 生成合盘相关的量化数据

**输出文件**：
- `sessions/<session_id>/artifacts/step2_5_synastry_analysis.json`
- `sessions/<session_id>/artifacts/step2_5_synastry_usage.json`

#### 4. step3_llm_quant.py - LLM 量化分析
**功能**：
- 调用 LLM 生成量化分析结果
- 基于 question_config 中的模板构建提示词
- 分析排盘数据和用户输入

**输出文件**：
- `sessions/<session_id>/artifacts/step3_backend.json`
- `sessions/<session_id>/artifacts/step3_prompt.txt`
- `sessions/<session_id>/artifacts/step3_usage.json`

#### 5. step4_llm_qual.py - LLM 质化优化
**功能**：
- 调用 LLM 优化输出质量
- 生成更易读的总结和建议
- 添加风险提示和注意事项

**输出文件**：
- `sessions/<session_id>/artifacts/step4_frontend.json`
- `sessions/<session_id>/artifacts/step4_prompt.txt`
- `sessions/<session_id>/artifacts/step4_usage.json`

#### 6. step5_finalize.py - 结果汇总
**功能**：
- 汇总所有步骤的输出
- 生成最终的 `session_output.json`
- 创建 pipeline_summary.json 用于调试

**输出文件**：
- `sessions/<session_id>/session_output.json` ⭐ **前端渲染数据**
- `sessions/<session_id>/pipeline_summary.json`

## 📋 前端/运维必读文件

### 🔴 核心输入文件
#### `_session_input.jsonc` (开发阶段模板)
**位置**：`data_prompt_engineering/real_toc/_session_input.jsonc`
**用途**：带注释的完整输入模板，包含所有可能的字段和说明

关键字段说明：
- `session_metadata.session_id`：会话唯一标识（必须）
- `session_metadata.session_ip`：IP 地址（可选，用于地理定位）
- `question_parameters.question_metadata.question_id`：问题 ID（必须）
- `user_specification.required_inputs`：必填用户输入（数组）
- `user_specification.optional_inputs`：可选用户输入（数组）
- `palette_data.person_a.birth_time`：用户 A 出生时间（八字计算用）
- `palette_data.synastry`：是否启用合盘（"true"/"false"）

#### `_user_settings.jsonc` (用户设置模板)
**位置**：`data_prompt_engineering/real_toc/_user_settings.jsonc`
**用途**：用户个性化设置模板

关键字段：
- `user_sensitivity_setting.tone`：回答语气
- `user_sensitivity_setting.tone_MBTI`：MBTI 风格
- `user_sensitivity_setting.sensitivity`：敏感度等级

### 🟡 生产环境输入文件
#### `session_input.json` (简化输入)
**位置**：`data_prompt_engineering/real_toc/session_input.json`
**用途**：生产环境使用的简化版输入文件，与 JSONC 字段一致但无注释

#### `user_settings.json` (用户设置)
**位置**：`data_prompt_engineering/real_toc/user_settings.json`
**用途**：生产环境的简化用户设置文件

### 🟢 输出文件
#### `session_output.json` (前端渲染数据)
**位置**：`sessions/<session_id>/session_output.json`
**用途**：前端渲染的核心数据文件

输出结构示例：
```json
{
  "session_metadata": {
    "session_id": "session_20250908_demo_synastry",
    "session_status": "completed",
    "completion_time": "202509080250"
  },
  "frontend_response": {
    "summary": "您的年龄处于适合考虑生育的阶段...",
    "risk_points": [
      "选择家庭氛围和谐、支持度高的时间段进行生育安排。",
      "避免在家庭关系紧张或存在误会的时期做出重大生育决定。"
    ]
  }
}
```

## ⚠️ 数据对齐要求

### 字段命名规范
- 所有输入字段必须严格按照 `_session_input.jsonc` 和 `_user_settings.jsonc` 中的命名
- 字段类型必须与模板一致
- 必填字段：`session_id`, `question_id`, `birth_time` 等

### 数据校验要点
- `session_id` 格式：`session_YYYYMMDD_description`
- `birth_time` 格式：`YYYYMMDDHHMM`（12位数字）
- `synastry` 值：字符串 `"true"` 或 `"false"`
- 空值处理：可选字段使用空字符串 `""` 而非 `null`

### ⚠️ Step2.5 合盘分析特殊校验要点
**JSONC 配置校验：**
- `question_config/xxx.jsonc` 中 `synastry.required` 必须为布尔值 `true`

**Session Input 校验：**
- `palette_data.synastry` 必须为字符串 `"true"`（而非布尔值）
- **合盘模式下**：`person_a.birth_time` 和 `person_a.gender` 必须为合法真值 `""`
- **合盘模式下**：`person_b.birth_time` 和 `person_b.gender` 必须为合法真值 `""`

**数据完整性校验：**
- 必须同时存在 `person_a` 和 `person_b` 的完整合盘数据
- `palette_data` 中必须包含合盘相关的排盘结果

### 错误处理
- 缺失必填字段将导致 `step1_validate.py` 失败
- 格式错误将记录在 `step1_validation.json` 中
- 前端应检查 `session_output.json` 中的 `success` 字段

## 🔄 弃用计划 ⚠️ **重大要注意**

### 🚨 已弃用功能（确认后立即执行）
**在下一稿确认后，将会被弃用的模块：**
- `data_prompt_engineering/api_b2c` 
- `data_prompt_engineering/api_b2b/合盘` 

### 待弃用功能（下下版）
- `calculate_palette/` 目录下的旧排盘实现

## 🚀 运行与部署

### 本地测试命令
```bash
# 完整流程测试
python main.py \
  --session-input session_input.json \
  --user-settings user_settings.json \
  --config-path config.json \
  --sessions-root sessions \
  --question-config-dir question_config \
  --model-set gpt-4.1

# 跳过健康检查
python main.py --skip-validation [其他参数...]
```

### 环境要求
- Python 3.x
- 依赖包：见 `requirements.txt`
- LLM API 密钥：配置在 `config.json` 中

### 调试与监控
- 查看 `pipeline_summary.json` 了解各步骤执行状态
- 检查 `artifacts/` 目录下的中间文件进行问题排查
- 关注 `step1_validation.json` 中的数据校验结果

## 📝 维护与贡献

### 修改流程
1. 修改相关步骤脚本
2. 更新对应的 JSONC 模板文件
3. 测试完整流程
4. 提交 PR 时附上测试结果

### 注意事项
- 保持与 `_session_input.jsonc` 和 `_user_settings.jsonc` 的字段对齐
- 确保输出格式兼容前端渲染需求
- 新功能应遵循现有的 5 步骤架构

## 🔮 未来开发方向

### 📍 IP 地理定位增强（非核心功能）
新开发了 `data_prompt_engineering/real_toc/calculate_palette/ip_bazi_unified.py`，该模块现在可以试用，但仍然在测试中，目前还没有集成到主流程中来。

**功能特点：**
- 基于 IP 地址计算真太阳时
- 提供更精确的地理位置信息
- 未来可能作为时间修正的补充功能

