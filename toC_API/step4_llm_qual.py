# -*- coding: utf-8 -*-
import os
import sys
import json
import argparse
import time
from pipeline_core import load_json, save_json, load_openai_client, call_frontend_llm, build_frontend_prompt_from_backend, log_message


def _extract_llm_qual_params(parsed: dict) -> dict:
    llm_cfg = parsed.get('llm_config', {}).get('qualitative', {})
    return {
        'model': llm_cfg.get('model', 'gpt-4.1-nano'),
        'temperature': llm_cfg.get('temperature', 0.3),
        'top_p': llm_cfg.get('top_p', 1),
        'frequency_penalty': llm_cfg.get('frequency_penalty', 0),
        'presence_penalty': llm_cfg.get('presence_penalty', 0),
        'max_tokens': llm_cfg.get('max_tokens', 32768)
    }


def main():
    parser = argparse.ArgumentParser(description='Step4 提交质化 LLM')
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--sessions-root', default='sessions')
    parser.add_argument('--config-path', default='config.json')
    parser.add_argument('--user-settings', default='user_settings.json')
    args = parser.parse_args()

    sess_dir = args.sessions_root
    if not os.path.exists(sess_dir):
        log_message("ERROR", "会话目录不存在，请先执行前置步骤", "STEP4")
        sys.exit(1)
    artifacts_dir = os.path.join(sess_dir, 'artifacts')
    os.makedirs(artifacts_dir, exist_ok=True)

    parsed = load_json(os.path.join(artifacts_dir, 'parsed_question.json'))
    backend_result = load_json(os.path.join(artifacts_dir, 'step3_backend.json'))
    validated = load_json(os.path.join(artifacts_dir, 'validated_data.json'))

    params = _extract_llm_qual_params(parsed)
    prompt = build_frontend_prompt_from_backend(backend_result, validated)
    client, _ = load_openai_client(args.config_path)
    t0 = time.time()
    frontend_result, usage = call_frontend_llm(client, params['model'], params['temperature'], prompt, params['top_p'], params['frequency_penalty'], params['presence_penalty'], params['max_tokens'])
    elapsed = time.time() - t0

    save_json(os.path.join(artifacts_dir, 'step4_frontend.json'), frontend_result)
    save_json(os.path.join(artifacts_dir, 'step4_usage.json'), {'elapsed_s': elapsed, **usage})
    # 追加：保存质化阶段完整 Prompt
    try:
        with open(os.path.join(artifacts_dir, 'step4_prompt.txt'), 'w', encoding='utf-8') as f:
            f.write(prompt)
    except Exception:
        pass
    log_message("SUCCESS", "质化阶段完成", "STEP4")


if __name__ == '__main__':
    main()


# 调用示例:
# python step4_llm_qual.py --session-id <sid> --sessions-root sessions --config-path config.json --user-settings user_settings.json')