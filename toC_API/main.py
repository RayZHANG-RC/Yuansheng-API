# -*- coding: utf-8 -*-
import os
import sys
import argparse
import subprocess
import json
from datetime import datetime
from pipeline_core import log_message

def run(cmd: list):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        sys.exit(proc.returncode)

def main():
    parser = argparse.ArgumentParser(description='toC 多步主程序')
    parser.add_argument('--session-id')
    parser.add_argument('--sessions-root', default='sessions')
    parser.add_argument('--config-path', default='config.json')
    '''
    真实环境下仅会传参以下两个文件路径
    '''
    parser.add_argument('--user-settings', default='user_settings.json')
    parser.add_argument('--session-input', default='session_input.json')


    parser.add_argument('--question-config-dir', default='question_config')
    parser.add_argument('--skip-validation', action='store_true', help='跳过启动前的健康检查')
    # todo：需添加支持新模型
    parser.add_argument('--model-set', choices=['gpt-4.1', 'gpt-5'], help='LLM模型集选择：gpt-4.1 或 gpt-5', default='gpt-4.1')
    args = parser.parse_args()


    base = os.path.dirname(os.path.abspath(__file__))

    # 从 user_settings.json 路径中提取输出目录
    user_settings_path = os.path.abspath(args.user_settings)
    args.sessions_root = os.path.dirname(user_settings_path)
    

    # 0. 校验是否已经建立问题的sessionID
    log_message("INFO", "健康检查完成，开始主流程", "MAIN")
    # 读取 session-id
    with open(args.session_input, 'r', encoding='utf-8') as f:
        _si = json.load(f)
    session_id = _si.get('session_metadata', {}).get('session_id')
    if not session_id:
        log_message("ERROR", "无法解析 session_id", "MAIN")
        sys.exit(1)

    # 1. 校验与建立会话目录
    run([sys.executable, os.path.join(base, 'step1_validate.py'),
         '--config-path', args.config_path,
         '--user-settings', args.user_settings,
         '--session-input', args.session_input,
         '--sessions-root', args.sessions_root,
         '--question-config-dir', args.question_config_dir,
         '--model-set', args.model_set])
    # 调用示例：
    # python step1_validate.py --config-path config.json --user-settings user_settings.json --session-input session_input.json --sessions-root sessions


    # 2. 准备 JSONC 与排盘数据（拷贝）
    step2_cmd = [sys.executable, os.path.join(base, 'step2_prepare.py'),
                 '--session-id', session_id,
                 '--sessions-root', args.sessions_root,
                 '--question-config-dir', args.question_config_dir,
                 '--session-input', args.session_input,
                 '--config-path', args.config_path,
                 '--user-settings', args.user_settings]
    if args.model_set:
        step2_cmd.extend(['--model-set', args.model_set])
    run(step2_cmd)
    # 调用示例：
    # python step2_prepare.py --session-id <sid> --sessions-root sessions --question-config-dir question_config --session-input session_input.json

    # 2.5 合盘由 step2_prepare 内部根据 JSONC + session_input 条件触发（不可跳步）。
    # 如需单独调试，可直接运行 step2_5_synastry.py（见其内注释示例）。

    # 3. 量化 LLM
    run([sys.executable, os.path.join(base, 'step3_llm_quant.py'),
         '--session-id', session_id,
         '--sessions-root', args.sessions_root,
         '--config-path', args.config_path,
         '--user-settings', args.user_settings,
         '--session-input', args.session_input,
         '--question-config-dir', args.question_config_dir])
    # 调用示例：
    # python step3_llm_quant.py --session-id <sid> --sessions-root sessions --config-path config.json --user-settings user_settings.json --session-input session_input.json --question-config-dir question_config

    # 4. 质化 LLM
    run([sys.executable, os.path.join(base, 'step4_llm_qual.py'),
         '--session-id', session_id,
         '--sessions-root', args.sessions_root,
         '--config-path', args.config_path,
         '--user-settings', args.user_settings])
    # 调用示例：
    # python step4_llm_qual.py --session-id <sid> --sessions-root sessions --config-path config.json --user-settings user_settings.json

    # 5. 汇总输出（产出 timestamp_o.json）
    run([sys.executable, os.path.join(base, 'step5_finalize.py'),
         '--session-id', session_id,
         '--sessions-root', args.sessions_root])
    # 调用示例：
    # python step5_finalize.py --session-id <sid> --sessions-root sessions


if __name__ == '__main__':
    main()
