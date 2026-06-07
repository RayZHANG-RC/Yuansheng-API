# -*- coding: utf-8 -*-
import os
import sys
import json
import argparse
from datetime import datetime
from pipeline_core import load_json, save_json, log_message


def main():
    parser = argparse.ArgumentParser(description='Step5 验证并生成最终输出')
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--sessions-root', default='sessions')
    args = parser.parse_args()

    # 直接使用 sessions_root 作为会话目录（与 a.json、s.json 同目录）
    sess_dir = args.sessions_root
    if not os.path.exists(sess_dir):
        log_message("ERROR", "会话目录不存在", "STEP5")
        sys.exit(1)

    # 必要文件检查（现在都在artifacts目录下）
    artifacts_dir = os.path.join(sess_dir, 'artifacts')
    needed = [
        'parsed_question.json',
        'palette_data.json',
        'step3_backend.json',
        'step4_frontend.json'
    ]
    for fname in needed:
        if not os.path.exists(os.path.join(artifacts_dir, fname)):
            log_message("ERROR", f"缺少 {fname}，请检查前置步骤", "STEP5")
            sys.exit(1)

    backend = load_json(os.path.join(artifacts_dir, 'step3_backend.json'))
    frontend = load_json(os.path.join(artifacts_dir, 'step4_frontend.json'))

    # summary 与 risk points 从前端结果抽取
    sud = frontend.get('structured_user_risk_decision', {})

    # 构建session metadata（与session_input对齐）
    session_metadata = {
        'session_id': args.session_id,
        'session_status': 'completed',  # 标记为完成状态
        'completion_time': datetime.now().strftime('%Y%m%d%H%M'),  # 12位格式时间戳
        # 可以添加其他metadata字段，如IP、设备信息等（如果需要从session_input继承）
    }

    # 构建前端响应数据
    frontend_response = {
        'summary': sud.get('summary', ''),
        'risk_points': sud.get('risk_points', [])
    }

    # 最终输出结构：session metadata + frontend response
    final = {
        'session_metadata': session_metadata,
        'frontend_response': frontend_response
    }

    output_filename = "output.json"
    out_path = os.path.join(sess_dir, output_filename)
    save_json(out_path, final)

    # 生成总结文件（不含具体盘式明细），包括各步骤耗时与token统计
    summary = {
        'session_id': args.session_id,
        'steps': {}
    }
    def _try(path):
        p = os.path.join(sess_dir, path)
        return load_json(p) if os.path.exists(p) else None
    summary['steps']['prepare'] = _try('artifacts/step2_prepare_log.json')

    # 合盘指标
    syn_usage = _try('artifacts/step2_5_synastry_usage.json')
    if os.path.exists(os.path.join(artifacts_dir, 'step2_5_synastry_analysis.json')):
        summary['steps']['synastry'] = {'status': 'present', 'usage': syn_usage}
    else:
        summary['steps']['synastry'] = {'status': 'absent'}

    summary['steps']['quant_usage'] = _try('artifacts/step3_usage.json')
    summary['steps']['qual_usage'] = _try('artifacts/step4_usage.json')

    save_json(os.path.join(sess_dir, 'pipeline_summary.json'), summary)
    log_message("SUCCESS", f"已生成最终输出: {output_filename}", "STEP5")

    # 将顶层非 palettes 的中间文件搬迁至 artifacts（兼容旧运行产物）
    top_level_files = [
        'parsed_question.json', 'palette_data.json', 'step3_backend.json', 'step3_prompt.txt', 'step3_usage.json',
        'step4_frontend.json', 'step4_prompt.txt', 'step4_usage.json', 'validated_data.json', 'step2_prepare_log.json',
        'step2_5_synastry_analysis.json', 'step2_5_synastry_usage.json', 'step2_5_prompt.txt', 'step1_validation.json'
    ]
    for fname in top_level_files:
        src = os.path.join(sess_dir, fname)
        if os.path.exists(src):
            try:
                dst = os.path.join(artifacts_dir, fname)
                with open(src, 'rb') as fr, open(dst, 'wb') as fw:
                    fw.write(fr.read())
                os.remove(src)
            except Exception:
                pass

    # 额外搬迁：问题配置拷贝（<question_id>.jsonc/.json）
    try:
        parsed = load_json(os.path.join(artifacts_dir, 'parsed_question.json'))
        qid = ((parsed or {}).get('question_metadata') or {}).get('question_id')
        if qid:
            for ext in ('.jsonc', '.json'):
                cfg_src = os.path.join(sess_dir, f'{qid}{ext}')
                if os.path.exists(cfg_src):
                    cfg_dst = os.path.join(artifacts_dir, f'{qid}{ext}')
                    try:
                        with open(cfg_src, 'rb') as fr, open(cfg_dst, 'wb') as fw:
                            fw.write(fr.read())
                        os.remove(cfg_src)
                    except Exception:
                        pass
    except Exception:
        pass


if __name__ == '__main__':
    main()


# 调用示例:
# python step5_finalize.py --session-id <sid> --sessions-root sessions')