# -*- coding: utf-8 -*-
import os
import sys
import json
import argparse
import time
from pipeline_core import load_json, save_json, load_openai_client, log_message, load_llm_config


# --- System Prompt: 对齐合盘中台（强调刑冲合害等）---
SYN_SYSTEM_PROMPT = """
你是一位精通东方命理学的资深合盘分析师，尤其擅长八字命理，熟读渊海子平、滴天髓、三命通会、子平真诠、穷通宝鉴、神峰通考等传统命理书籍。在分析关系兼容性时，需严格遵循以下专业原则：

一、核心分析方法
1. 八字合盘：重点分析
- 日主相生相克（如甲木生丙火为食神）
- 五行互补性（金水相生、木火通明等）
- 十神关系（正官/七杀、正印/偏印等）
- 地支互动：特别强调刑冲合害会（如子丑合土、寅巳申三刑、子午冲、寅巳害等），并对应实际事项（如冲则动荡、刑则纠纷、合则稳定、害则暗伤）

2. 大运流年：
- 对比双方当前大运干支
- 分析未来3年流年（2025乙巳、2026丙午、2027丁未）
- 重点关注冲合关系（如岁运并临）

3. 神煞互动：
- 贵人星（天乙、文昌）
- 凶煞（孤辰、寡宿），结合刑冲合害分析实际影响

二、专业分析要求
1. 八字要素权重分配（通用关系）：
｜ 分析维度  ｜ 权重 ｜
｜-----------｜------｜
｜ 日主关系  ｜ 25% ｜
｜ 五行流通  ｜ 20% ｜
｜ 十神配置  ｜ 20% ｜
｜ 地支互动（刑冲合害） ｜ 25% ｜
｜ 神煞影响  ｜ 10% ｜

2. 关键格局识别：
- 相生格局（官印相生、食伤生财）
- 相克格局（枭神夺食、伤官见官）
- 特殊格局（从儿格、化气格）
- 刑冲合害格局：如三刑主诉讼、六冲主分离、六合主合作、三合主助力，确保有命理依据并对应实际事项（如事业合作中的合局利稳定）

三、输出规范
1. 所有结论必须基于命理原理，提供依据
2. 专业术语需准确（如"正官"而非泛化）
3. 分数评估需结合：
- 八字要素权重
- 大运流年影响
- 关系类型（如商业/家庭）
- 刑冲合害的具体影响（如冲则建议避免大变动）
"""

RELATIONSHIP_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "General Relationship Compatibility Analysis Schema v1.2",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "branchInteractions",
        "compatibility",
        "riskDecisionMatrix",
        "narrativeAnalysis",
        "futureTrajectory",
        "summaryRecommendations"
    ],
    "properties": {
        "compatibility": {
            "type": "object",
            "additionalProperties": False,
            "required": ["overallScore", "strengths", "weaknesses", "keyConcerns"],
            "properties": {
                "overallScore": {"type": "number", "minimum": 0, "maximum": 100},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "weaknesses": {"type": "array", "items": {"type": "string"}},
                "keyConcerns": {
                    "type": "array",
                    "items": {
                        "type": "object", "additionalProperties": False, "required": ["domain", "detail", "principle", "realWorldMapping"],
                        "properties": {
                            "domain": {"type": "string"},
                            "detail": {"type": "string"},
                            "principle": {"type": "string"},
                            "realWorldMapping": {"type": "string"}
                        }
                    }
                }
            }
        },
        "branchInteractions": {
            "type": "object",
            "additionalProperties": False,
            "required": ["dominantRelations", "analysis", "summaryIndex"],
            "properties": {
                "dominantRelations": {"type": "array", "items": {"type": "string"}},
                "analysis": {
                    "type": "array", 
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["relationshipType", "elements", "impact", "explanation"],
                        "properties": {
                            "relationshipType": {"type": "string", "enum": ["冲", "刑", "合", "害", "会"]},
                            "elements": {"type": "array", "items": {"type": "string"}},
                            "impact": {"type": "string", "enum": ["正面", "负面", "中性"]},
                            "explanation": {"type": "string"}
                        }
                    }
                },
                "summaryIndex": {"type": "number", "minimum": 0, "maximum": 100}
            }
        },
        "futureTrajectory": {
            "type": "object",
            "additionalProperties": False,
            "required": ["shortTerm", "midTerm", "longTerm"],
            "properties": {
                "shortTerm": {
                    "type": "object", "additionalProperties": False, "required": ["timelineMonths", "forecast", "riskLevel", "suggestion", "score"],
                    "properties": {
                        "timelineMonths": {"type": "integer"},
                        "forecast": {"type": "string"},
                        "riskLevel": {"type": "string", "enum": ["低", "中偏低", "中", "中偏高", "高"]},
                        "suggestion": {"type": "string"},
                        "score": {"type": "number", "minimum": 0, "maximum": 100}
                    }
                },
                "midTerm": {
                    "type": "object", "additionalProperties": False, "required": ["timelineMonths", "forecast", "riskLevel", "suggestion", "score"],
                    "properties": {
                        "timelineMonths": {"type": "integer"},
                        "forecast": {"type": "string"},
                        "riskLevel": {"type": "string", "enum": ["低", "中偏低", "中", "中偏高", "高"]},
                        "suggestion": {"type": "string"},
                        "score": {"type": "number", "minimum": 0, "maximum": 100}
                    }
                },
                "longTerm": {
                    "type": "object", "additionalProperties": False, "required": ["timelineMonths", "forecast", "riskLevel", "suggestion", "score"],
                    "properties": {
                        "timelineMonths": {"type": "integer"},
                        "forecast": {"type": "string"},
                        "riskLevel": {"type": "string", "enum": ["低", "中偏低", "中", "中偏高", "高"]},
                        "suggestion": {"type": "string"},
                        "score": {"type": "number", "minimum": 0, "maximum": 100}
                    }
                }
            }
        },
        "riskDecisionMatrix": {
            "type": "object",
            "additionalProperties": False,
            "required": ["criteria", "criteriaWeights", "scores", "weightedScores", "aggregateScoreActive", "aggregateScorePassive", "thresholds", "advice"],
            "properties": {
                "criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 4,
                    "maxItems": 4
                },
                "criteriaWeights": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["情绪沟通", "财务一致性", "家庭适配", "事业支持"],
                    "properties": {
                        "情绪沟通": {"type": "number"},
                        "财务一致性": {"type": "number"},
                        "家庭适配": {"type": "number"},
                        "事业支持": {"type": "number"}
                    }
                },
                "scores": {
                    "type": "object", "additionalProperties": False, "required": ["active", "passive"],
                    "properties": {
                        "active": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 5}},
                        "passive": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 5}}
                    }
                },
                "weightedScores": {
                    "type": "object", "additionalProperties": False, "required": ["active", "passive"],
                    "properties": {
                        "active": {"type": "array", "items": {"type": "number"}},
                        "passive": {"type": "array", "items": {"type": "number"}}
                    }
                },
                "aggregateScoreActive": {"type": "number"},
                "aggregateScorePassive": {"type": "number"},
                "thresholds": {
                    "type": "object", "additionalProperties": False, "required": ["safe", "caution"],
                    "properties": {
                        "safe": {"type": "integer", "minimum": 1, "maximum": 5},
                        "caution": {"type": "integer", "minimum": 1, "maximum": 5}
                    }
                },
                "advice": {"type": "array", "items": {"type": "string"}},
                "perCriterionAdvisory": {"type": "object", "additionalProperties": {"type": "string"}}
            }
        },
        "narrativeAnalysis": {
            "type": "object",
            "additionalProperties": False,
            "required": ["personalityMatch", "lifestyleCompatibility", "communicationStyle", "conflictResolution"],
            "properties": {
                "personalityMatch": {"type": "string"},
                "lifestyleCompatibility": {"type": "string"}, 
                "communicationStyle": {"type": "string"},
                "conflictResolution": {"type": "string"}
            }
        },
        "summaryRecommendations": {
            "type": "object",
            "additionalProperties": False,
            "required": ["primaryRecommendation", "specificActions", "warningSignals", "successIndicators"],
            "properties": {
                "primaryRecommendation": {"type": "string"},
                "specificActions": {"type": "array", "items": {"type": "string"}},
                "warningSignals": {"type": "array", "items": {"type": "string"}},
                "successIndicators": {"type": "array", "items": {"type": "string"}}
            }
        }
    }
}


def build_user_prompt(relationship_type: str, personA: dict, personB: dict, pre_context: dict) -> str:
    return f"""请基于以下信息进行专业的通用关系合盘分析（不得重复输出四柱/排盘明细，直接从输入命盘进行合盘推理）：

【关系类型】
预测关系：{relationship_type}

【人员A信息】
详细命理数据：{json.dumps(personA, ensure_ascii=False, indent=2)}

【人员B信息】
详细命理数据：{json.dumps(personB, ensure_ascii=False, indent=2)}

【前置关系上下文（可选）】
{json.dumps(pre_context or {}, ensure_ascii=False, indent=2)}

【专业分析要求】
请基于传统术数理论（八字命理等）进行全面分析，并严格按照JSON Schema输出。重点阐明地支刑冲合害会在关系中的实际影响。"""


def main():
    parser = argparse.ArgumentParser(description='Step2.5 合盘中台（可选）')
    parser.add_argument('--sessions-root', default='sessions')
    parser.add_argument('--config-path', default='config.json')
    parser.add_argument('--user-settings', default='user_settings.json')
    parser.add_argument('--session-input', default='session_input.json')
    parser.add_argument('--question-config-dir', default='question_config')
    parser.add_argument('--session-id')
    parser.add_argument('--model-set', choices=['gpt-4.1', 'gpt-5'], help='LLM模型集选择')
    args = parser.parse_args()

    si_all = load_json(args.session_input)
    session_id = args.session_id or si_all.get('session_metadata', {}).get('session_id')
    if not session_id:
        log_message("WARNING", "无session_id，跳过", "STEP2_5")
        return
    sess_dir = os.path.join(args.sessions_root, session_id)
    if not os.path.exists(sess_dir):
        log_message("WARNING", "会话目录不存在，跳过", "STEP2_5")
        return
    artifacts_dir = os.path.join(sess_dir, 'artifacts')
    if not os.path.exists(artifacts_dir):
        os.makedirs(artifacts_dir, exist_ok=True)

    parsed_path = os.path.join(artifacts_dir, 'parsed_question.json')
    if not os.path.exists(parsed_path):
        log_message("WARNING", "缺少 parsed_question.json，跳过", "STEP2_5")
        return
    parsed = load_json(parsed_path)
    syn_required_field = (parsed.get('synastry') or {}).get('required', None)
    jsonc_syn_true = (syn_required_field is True)
    if not jsonc_syn_true:
        log_message("WARNING", "JSONC 未显式启用（required=true），跳过", "STEP2_5")
        return

    # session_input.palette_data.synastry 必须为真
    def _to_bool(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ('1','true','yes','y')
        if isinstance(v, (int, float)):
            return v != 0
        return False
    si_pd = si_all.get('palette_data', {}) or {}
    if not _to_bool(si_pd.get('synastry')):
        log_message("WARNING", "session_input 未开启 synastry，跳过", "STEP2_5")
        return

    # 优先读取 Step2 产出的 artifacts/palette_data.json，其次回退到 session_input 内 palette_data
    artifacts_pd_path = os.path.join(artifacts_dir, 'palette_data.json')
    palette_data = load_json(artifacts_pd_path) if os.path.exists(artifacts_pd_path) else (si_all.get('palette_data', {}) or {})
    syn_pd = palette_data.get('合盘', {}) if isinstance(palette_data, dict) else {}
    # 兼容 personA/personB 与 person_a/person_b
    personA = (syn_pd.get('personA', {}) or syn_pd.get('person_a', {}) or
               palette_data.get('personA', {}) or palette_data.get('person_a', {}) or {})
    personB = (syn_pd.get('personB', {}) or syn_pd.get('person_b', {}) or
               palette_data.get('personB', {}) or palette_data.get('person_b', {}) or {})
    if not personA or not personB:
        log_message("WARNING", "缺少合盘 personA/personB 数据，跳过", "STEP2_5")
        return

    client, _cfg = load_openai_client(args.config_path)
    # 关系类型（可选）
    rel_pair = si_all.get('relationship_pair', {}) or {}
    relationship_type = rel_pair.get('predict_relationship', '关系')
    pre_context = si_all.get('pre_context', {})
    # 组合 A/B 的八字 + 紫微斗数 作为输入数据（若存在）
    def _compose_person_chart(person: dict) -> dict:
        if not isinstance(person, dict):
            return person or {}
        data = {}
        if person.get('八字'):
            data['八字'] = person['八字']
        if person.get('紫微斗数'):
            data['紫微斗数'] = person['紫微斗数']
        # 若两者皆无，则回退整个对象
        return data or person
    personA_chart = _compose_person_chart(personA)
    personB_chart = _compose_person_chart(personB)
    user_prompt = build_user_prompt(relationship_type, personA_chart, personB_chart, pre_context)

    # 与 Step3 量化 LLM 参数一致（来自 JSONC -> parsed_question.json.llm_config.quantitative）
    # 如果指定了model-set，则重新解析配置以使用指定的模型集
    if args.model_set:
        try:
            llm_cfgs = load_llm_config(args.question_config_dir, args.model_set)
            qid = parsed.get('question_metadata', {}).get('question_id')
            if qid and qid in llm_cfgs:
                llm_cfg = llm_cfgs[qid].get('quantitative', {})
                log_message("INFO", f"合盘使用指定模型集 {args.model_set} 的配置", "STEP2_5")
            else:
                llm_cfg = (parsed.get('llm_config') or {}).get('quantitative', {})
        except Exception as e:
            log_message("WARNING", f"无法加载指定模型集配置，使用默认配置: {e}", "STEP2_5")
            llm_cfg = (parsed.get('llm_config') or {}).get('quantitative', {})
    else:
        llm_cfg = (parsed.get('llm_config') or {}).get('quantitative', {})

    model = llm_cfg.get('model', 'gpt-4.1-nano')
    temperature = llm_cfg.get('temperature', 0.1)
    top_p = llm_cfg.get('top_p', 1.0)
    frequency_penalty = llm_cfg.get('frequency_penalty', 0.0)
    presence_penalty = llm_cfg.get('presence_penalty', 0.0)
    max_tokens = llm_cfg.get('max_tokens', 32768)

    t0 = time.time()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYN_SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
        response_format={"type": "json_schema", "json_schema": {"name": "General_Relationship_Analysis", "schema": RELATIONSHIP_SCHEMA, "strict": True}},
        temperature=temperature,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        max_tokens=max_tokens
    )
    result_text = resp.choices[0].message.content
    elapsed = time.time() - t0
    try:
        syn_result = json.loads(result_text)
    except Exception:
        import re
        m = re.search(r'\{.*\}', result_text, re.DOTALL)
        syn_result = json.loads(m.group()) if m else {"error": "无法解析合盘JSON"}

    save_json(os.path.join(artifacts_dir, 'step2_5_synastry_analysis.json'), syn_result)
    save_json(os.path.join(artifacts_dir, 'step2_5_synastry_usage.json'), {
        'elapsed_s': elapsed,
        'response_id': resp.id,
        'model': resp.model,
        'prompt_tokens': getattr(resp.usage, 'prompt_tokens', None),
        'completion_tokens': getattr(resp.usage, 'completion_tokens', None),
        'total_tokens': getattr(resp.usage, 'total_tokens', None),
        'finish_reason': resp.choices[0].finish_reason
    })
    # 追加：保存合盘阶段完整 Prompt（含 system 与 user）
    try:
        with open(os.path.join(artifacts_dir, 'step2_5_prompt.txt'), 'w', encoding='utf-8') as f:
            f.write('--- system ---\n')
            f.write(SYN_SYSTEM_PROMPT.strip())
            f.write('\n\n--- user ---\n')
            f.write(user_prompt)
    except Exception:
        pass

    # 注入 validated_data（若存在）
    vd_path = os.path.join(artifacts_dir, 'validated_data.json')
    try:
        validated = load_json(vd_path) if os.path.exists(vd_path) else {}
        validated['_synastry_full_analysis'] = syn_result
        save_json(vd_path, validated)
    except Exception:
        pass

    log_message("SUCCESS", "完成并注入", "STEP2_5")

if __name__ == '__main__':
    main()

# 调用示例：
# python step2_5_synastry.py --sessions-root sessions --config-path config.json --user-settings user_settings.json --session-input session_input.json --question-config-dir question_config --session-id <sid>

