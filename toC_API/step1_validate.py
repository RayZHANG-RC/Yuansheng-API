# -*- coding: utf-8 -*-
import os
import sys
import json
import argparse
from datetime import datetime
from pipeline_core import ensure_dir, load_json, save_json, log_message, remove_jsonc_comments, parse_question_config


def main():
    parser = argparse.ArgumentParser(description='Step1 校验与建立会话目录（包含主流程健康检查）')
    parser.add_argument('--config-path', default='config.json')
    parser.add_argument('--user-settings', default='user_settings.json')
    parser.add_argument('--session-input', default='session_input.json')
    parser.add_argument('--sessions-root', default='sessions')
    parser.add_argument('--question-config-dir', default='question_config')
    # todo：需添加支持新模型
    parser.add_argument('--model-set', choices=['gpt-4.1', 'gpt-5'], help='LLM模型集选择：gpt-4.1 或 gpt-5')
    args = parser.parse_args()

    # 0）检查所有执行文件脚本是否齐全
    required_files = [
        'config.json',
        'step1_validate.py', 'step2_prepare.py', 'step2_5_synastry.py',
        'step3_llm_quant.py', 'step4_llm_qual.py', 'step5_finalize.py',
        'pipeline_core.py'
    ]
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        log_message("ERROR", f"缺少必需文件: {', '.join(missing_files)}", "STEP1")
        sys.exit(1)

    # 0.1）检查问题参数文件夹是否存在
    qcfg_dir = args.question_config_dir
    if not os.path.exists(qcfg_dir) or not os.path.isdir(qcfg_dir):
        log_message("ERROR", "缺少 question_config 目录", "STEP1")
        sys.exit(1)
    #todo：可能需要加入新模型的config
    for csv_file in ('gpt41_llm_config.csv', 'gpt5_llm_config.csv'):
        csv_path = os.path.join(qcfg_dir, csv_file)
        if not os.path.exists(csv_path):
            log_message("ERROR", f"缺少 CSV 配置文件: {csv_path}", "STEP1")
            sys.exit(1)

    # 1) config.json
    #todo: 新增其他模型判断逻辑，并引入判断模型机制
    if not os.path.exists(args.config_path):
        log_message("ERROR", "缺少 config.json", "STEP1")
        sys.exit(1)
    cfg = load_json(args.config_path)
    openai_cfg = cfg.get('openai', {})
    if not openai_cfg.get('api_key'):
        log_message("ERROR", "config.json 缺少 OpenAI api_key", "STEP1")
        sys.exit(1)
    if not openai_cfg.get('organization_id'):
        log_message("ERROR", "config.json 缺少 OpenAI organization_id", "STEP1")
        sys.exit(1)

    # 2) user_settings
    if not os.path.exists(args.user_settings):
        log_message("ERROR", "缺少 user_settings.json", "STEP1")
        sys.exit(1)
    us = load_json(args.user_settings)
    if 'user_metadata' not in us or 'user_sensitivity_setting' not in us:
        log_message("ERROR", "user_settings.json 缺少 user_metadata", "STEP1")
        sys.exit(1)
    if 'user_sensitivity_setting' not in us:
        log_message("ERROR", "user_settings.json 缺少 user_sensitivity_setting", "STEP1")
        sys.exit(1)

    # 3) session_input
    if not os.path.exists(args.session_input):
        log_message("ERROR", "缺少 session_input.json", "STEP1")
        sys.exit(1)
    si = load_json(args.session_input)
    if 'session_metadata' not in si:
        log_message("ERROR", "session_input.json 缺少 session_metadata", "STEP1")
        sys.exit(1)
    sm = si['session_metadata']
    session_id = sm.get('session_id')
    if not session_id:
        log_message("ERROR", "session_metadata 缺少 session_id", "STEP1")
        sys.exit(1)
    if 'question_parameters' not in si:
        log_message("ERROR", "session_input.json 缺少 question_parameters", "STEP1")
        sys.exit(1)
    qp = si['question_parameters']
    qmeta = (qp.get('question_metadata') or {})
    if not qmeta.get('question_id'):
        log_message("ERROR", "question_parameters.question_metadata 缺少 question_id", "STEP1")
        sys.exit(1)
    uspec = (qp.get('user_specification') or {})
    if 'required_inputs' not in uspec or 'optional_inputs' not in uspec:
        log_message("ERROR", "user_specification 需包含 required_inputs 与 optional_inputs", "STEP1")
        sys.exit(1)
    if 'palette_data' not in si:
        log_message("ERROR", "session_input.json 缺少 palette_data", "STEP1")
        sys.exit(1)


    # 4）确认单个问题配置文件存在
    qid = qmeta.get('question_id')
    cfg_path_jsonc = os.path.join(qcfg_dir, f'{qid}.jsonc')
    # cfg_path_json = os.path.join(qcfg_dir, f'{qid}.json')
    if os.path.exists(cfg_path_jsonc):
        with open(cfg_path_jsonc, 'r', encoding='utf-8') as f:
            content = remove_jsonc_comments(f.read())
        try:
            config = json.loads(content)
        except Exception as e:
            log_message("ERROR", f"JSONC 解析失败: {e}", "STEP1")
            sys.exit(1)
    else:
        log_message("ERROR", f"无法找到问题配置文件: {qid}.jsonc / {qid}.json", "STEP1")
        sys.exit(1)

    """
    elif os.path.exists(cfg_path_json):
        try:
            with open(cfg_path_json, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            log_message("ERROR", f"JSON 解析失败: {e}", "STEP1")
            sys.exit(1)
    """


    # todo：有可能可以删除（TBC）
    try:
        # 在step1中只做基本验证，不加载LLM配置（传None避免触发LLM加载）
        _ = parse_question_config(config, qcfg_dir, None)
        #log_message("SUCCESS", "问题配置解析正常", "STEP1")
    except Exception as e:
        log_message("ERROR", f"问题配置解析失败: {e}", "STEP1")
        sys.exit(1)

    # 5) 建立 session 目录
    root = args.sessions_root
    ensure_dir(root)
    artifacts_dir = os.path.join(root, 'artifacts')
    ensure_dir(artifacts_dir)

    # 记录元数据
    meta = {
        'session_id': session_id,
        'created_at': datetime.now().isoformat(),
        'config_path': os.path.abspath(args.config_path),
        'user_settings': os.path.abspath(args.user_settings),
        'session_input': os.path.abspath(args.session_input)
    }
    # 同步保存一份 session_id 供 main 使用
    meta_path = os.path.join(artifacts_dir, 'step1_validation.json')
    save_json(meta_path, meta)
    log_message("SUCCESS", f"健康检查通过", "STEP1")


if __name__ == '__main__':
    main()


