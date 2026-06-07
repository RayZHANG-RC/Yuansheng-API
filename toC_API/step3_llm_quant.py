# -*- coding: utf-8 -*-
import os
import sys
import json
import argparse
import time
from pipeline_core import load_json, save_json, load_openai_client, call_backend_llm, build_validated_data, build_backend_prompt_from_validated, log_message


def _extract_llm_quant_params(parsed: dict) -> dict:
    llm_cfg = parsed.get('llm_config', {}).get('quantitative', {})
    return {
        'model': llm_cfg.get('model', 'gpt-4.1-nano'),
        'temperature': llm_cfg.get('temperature', 0.1),
        'top_p': llm_cfg.get('top_p', 1),
        'frequency_penalty': llm_cfg.get('frequency_penalty', 0),
        'presence_penalty': llm_cfg.get('presence_penalty', 0),
        'max_tokens': llm_cfg.get('max_tokens', 32768)
    }


def main():
    parser = argparse.ArgumentParser(description='Step3 提交量化 LLM')
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--sessions-root', default='sessions')
    parser.add_argument('--config-path', default='config.json')
    parser.add_argument('--user-settings', default='user_settings.json')
    parser.add_argument('--session-input', default='session_input.json')
    parser.add_argument('--question-config-dir', default='question_config')
    args = parser.parse_args()

    sess_dir = args.sessions_root
    if not os.path.exists(sess_dir):
        log_message("ERROR", "会话目录不存在，请先执行step1/step2", "STEP3")
        sys.exit(1)
    artifacts_dir = os.path.join(sess_dir, 'artifacts')
    os.makedirs(artifacts_dir, exist_ok=True)

    parsed = load_json(os.path.join(artifacts_dir, 'parsed_question.json'))
    palette_data = load_json(os.path.join(artifacts_dir, 'palette_data.json')) if os.path.exists(os.path.join(artifacts_dir, 'palette_data.json')) else {}
    user_settings = load_json(args.user_settings)
    session_input = load_json(args.session_input)
    # 用 Step2 生成/更新的 palette_data 覆盖 session_input 中的 palette_data，以保证使用最新排盘
    try:
        if palette_data:
            base_pd = session_input.get('palette_data', {}) or {}
            if isinstance(base_pd, dict) and isinstance(palette_data, dict):
                merged = {**base_pd, **palette_data}
            else:
                merged = palette_data or base_pd
            session_input['palette_data'] = merged
    except Exception:
        pass

    # 构建与 toC 一致的 validated_data 与 prompt
    validated = build_validated_data(parsed, user_settings, session_input)
    # 若 JSONC 开启了 synastry（不为 false 或缺省）且存在 Step2.5 结果，则注入
    syn_required_field = (parsed.get('synastry') or {}).get('required', None)
    syn_enabled = (syn_required_field is not False)  # True 或 None 均视为可启用，但需实际结果存在
    syn_path = os.path.join(artifacts_dir, 'step2_5_synastry_analysis.json')
    if syn_enabled and os.path.exists(syn_path):
        try:
            validated['_synastry_full_analysis'] = load_json(syn_path)
        except Exception:
            pass
    prompt = build_backend_prompt_from_validated(validated)
    params = _extract_llm_quant_params(parsed)
    client, _ = load_openai_client(args.config_path)
    t0 = time.time()
    backend_result, usage = call_backend_llm(client, params['model'], params['temperature'], prompt, params['top_p'], params['frequency_penalty'], params['presence_penalty'], params['max_tokens'])
    elapsed = time.time() - t0

    # 保存与 toC 一致命名
    save_json(os.path.join(artifacts_dir, 'step3_backend.json'), backend_result)
    save_json(os.path.join(artifacts_dir, 'validated_data.json'), validated)
    save_json(os.path.join(artifacts_dir, 'step3_usage.json'), {'elapsed_s': elapsed, **usage})
    # 追加：保存量化阶段完整 Prompt
    try:
        with open(os.path.join(artifacts_dir, 'step3_prompt.txt'), 'w', encoding='utf-8') as f:
            f.write(prompt)
    except Exception:
        pass
    log_message("SUCCESS", "量化阶段完成", "STEP3")


if __name__ == '__main__':
    main()

# 调用示例:
# python step3_llm_quant.py --session-id <sid> --sessions-root sessions --config-path config.json --user-settings user_settings.json --session-input session_input.json --question-config-dir question_config
