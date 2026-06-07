# -*- coding: utf-8 -*-
import os
import sys
import json
import argparse
import shutil
import time
import re


from pipeline_core import ensure_dir, load_json, save_json, remove_jsonc_comments, parse_question_config, log_message


def main():
    parser = argparse.ArgumentParser(description='Step2 准备：加载JSONC与拷贝排盘数据 + 实际排盘 + 条件触发合盘(2.5)')
    parser.add_argument('--session-id')
    parser.add_argument('--sessions-root', default='sessions')
    parser.add_argument('--question-config-dir', default='question_config')
    parser.add_argument('--session-input', default='session_input.json')
    parser.add_argument('--config-path', default='config.json')
    parser.add_argument('--user-settings', default='user_settings.json')
    parser.add_argument('--model-set', choices=['gpt-4.1', 'gpt-5'], help='LLM模型集选择', default='gpt-4.1')
    args = parser.parse_args()


    si_all = load_json(args.session_input)
    session_id = args.session_id or si_all.get('session_metadata', {}).get('session_id')
    if not session_id:
        log_message("ERROR", "无法解析 session_id", "STEP2")
        sys.exit(1)
    sess_dir = args.sessions_root
    if not os.path.exists(sess_dir):
        log_message("ERROR", "会话目录不存在，请先执行step1", "STEP2")
        sys.exit(1)
    artifacts_dir = os.path.join(sess_dir, 'artifacts')
    ensure_dir(artifacts_dir)

    si = si_all
    qp = si.get('question_parameters', {})
    qid = qp['question_metadata']['question_id']

    # 加载 question JSONC/JSON
    cfg_path_jsonc = os.path.join(args.question_config_dir, f'{qid}.jsonc')
    # cfg_path_json = os.path.join(args.question_config_dir, f'{qid}.json')
    if os.path.exists(cfg_path_jsonc):
        with open(cfg_path_jsonc, 'r', encoding='utf-8') as f:
            content = remove_jsonc_comments(f.read())
        config = json.loads(content)
        src_cfg = cfg_path_jsonc
    else:
        log_message("ERROR", f"未找到问题配置 {qid}.jsonc/.json", "STEP2")
        sys.exit(1)
    '''
    elif os.path.exists(cfg_path_json):
        with open(cfg_path_json, 'r', encoding='utf-8') as f:
            config = json.load(f)
        src_cfg = cfg_path_json
    '''


    # 复制 JSONC/JSON 到 session 目录的 artifacts/
    shutil.copy2(src_cfg, os.path.join(artifacts_dir, os.path.basename(src_cfg)))

    # 传入 palette_data（保存副本） （初步用户数据）
    palette_data = si.get('palette_data', {}) or {}
    save_json(os.path.join(artifacts_dir, 'palette_data.json'), palette_data)

    # 保存解析后的规范结构，供后续步骤使用（同时drop空输入项）
    llm_cfg_dir = args.question_config_dir
    parsed = parse_question_config(config, llm_cfg_dir, args.model_set)
    # drop 空 user_spec in parsed（由下游重新注入会话输入）
    if isinstance(qp, dict):
        parsed['user_specification'] = qp.get('user_specification', parsed.get('user_specification', {}))
    save_json(os.path.join(artifacts_dir, 'parsed_question.json'), parsed)

    # === 排盘：严格依据 JSONC 的方法启用状态（include），并根据 session_input 的资料完备度决定是否 exclude ===
    # 四种方法：八字、紫微斗数（需要 birth），六爻、小六壬（不需要 birth）
    start_ts = time.time()
    executed = []
    methods = parsed.get('methods', []) or []
    # birth keys 允许多样化
    BIRTH_KEYS = ('birth_time', 'birthTime', 'birth_string', 'birthString')
    # palette_data 写回使用
    pd_write = palette_data
    for m in methods:
        if not bool(m.get('enabled', False)):
            continue
        name = m.get('method_name', '')
        # 检查是否已由外部提供原始盘（palette_data里已有）
        if isinstance(pd_write, dict) and name in pd_write and pd_write.get(name):
            executed.append({'method': name, 'action': 'provided', 'status': 'skip-generate'})
            continue
        # 需要出生信息与性别：八字、紫微斗数（两者必须同时具备）
        requires_birth = name in ('八字', '紫微斗数')
        birth_value = ''
        gender_value = None
        if requires_birth:
            # 优先从 palette_data.<method> 下查找 birth 与 gender
            method_pd = palette_data.get(name, {}) if isinstance(palette_data, dict) else {}
            if isinstance(method_pd, dict):
                for k in BIRTH_KEYS:
                    val = str(method_pd.get(k, '') or '').strip()
                    if val:
                        birth_array = re.findall(r'\d', str(val))
                        birth_value = ''.join(birth_array)
                        break
                if method_pd.get('gender')== '男':
                    gender_value = 'male'
                else:
                    gender_value = 'female'
            # 回退从 person_a/personA 等来源查找（必须同时拿到 birth & gender）
            if (not birth_value) or (not gender_value):
                fallback_sources = ['person_a', 'personA', 'user_birth', 'birth_info']
                for source in fallback_sources:
                    person_data = palette_data.get(source)
                    if isinstance(person_data, dict):
                        if not birth_value:
                            for k in BIRTH_KEYS:
                                val = str(person_data.get(k, '') or '').strip()
                                if val:
                                    birth_array = re.findall(r'\d', str(val))
                                    birth_value = ''.join(birth_array)
                                    break
                        if gender_value is None:
                            candidate_gender = person_data.get('gender')
                            if candidate_gender:
                                if candidate_gender == '男':
                                    gender_value = 'male'
                                else:
                                    gender_value = 'female'
                    if birth_value and gender_value:
                        break
        # 排盘执行
        try:
            if name == '八字' and requires_birth:
                # 强制要求 birth 与 gender 同时具备
                if (not birth_value) or (not gender_value):
                    executed.append({'method': name, 'action': 'generate', 'status': 'skipped-no-birth'})
                else:
                    # 调用八字程序：python calculate_palette/八字.py --session-id sid --birth-string YYYYMMDDHHMM --gender [male|female] --current-time NOW --output-path sessions/sid/palettes/八字.json
                    out_dir = os.path.join(sess_dir, 'palettes')
                    ensure_dir(out_dir)
                    out_path = os.path.join(out_dir, f'{name}.json')
                    gender = gender_value
                    now = (si.get('palette_data', {}) or {}).get('current_time', '') or '202501010000'
                    now = ''.join(now)[:12]
                    cmd = f"{sys.executable} \"{os.path.join(os.path.dirname(__file__), 'calculate_palette', '八字.py')}\" --session-id {session_id} --birth-string {birth_value} --gender {gender} --current-time {now} --output-path \"{out_path}\""
                    os.system(cmd)
                    # 读取结果写回 palette_data
                    if os.path.exists(out_path):
                        pd_write[name] = load_json(out_path)
                        executed.append({'method': name, 'action': 'generate', 'status': 'ok'})
                    else:
                        executed.append({'method': name, 'action': 'generate', 'status': 'failed'})
            elif name == '紫微斗数' and requires_birth:
                # 强制要求 birth 与 gender 同时具备
                if (not birth_value) or (not gender_value):
                    executed.append({'method': name, 'action': 'generate', 'status': 'skipped-no-birth'})
                else:
                    out_dir = os.path.join(sess_dir, 'palettes')
                    ensure_dir(out_dir)
                    out_path = os.path.join(out_dir, f'{name}.json')
                    gender = gender_value
                    now = (si.get('palette_data', {}) or {}).get('current_time', '') or '202501010000'
                    now = ''.join(now)[:12]
                    cmd = f"{sys.executable} \"{os.path.join(os.path.dirname(__file__), 'calculate_palette', '紫微斗数.py')}\" --session-id {session_id} --birth-string {birth_value} --gender {gender} --current-time {now} --output-path \"{out_path}\""
                    os.system(cmd)
                    if os.path.exists(out_path):
                        pd_write[name] = load_json(out_path)
                        executed.append({'method': name, 'action': 'generate', 'status': 'ok'})
                    else:
                        executed.append({'method': name, 'action': 'generate', 'status': 'failed'})
            elif name == '六爻':
                out_dir = os.path.join(sess_dir, 'palettes')
                ensure_dir(out_dir)
                out_path = os.path.join(out_dir, f'{name}.json')
                now = (si.get('palette_data', {}) or {}).get('current_time', '') or '202501010000'
                now = ''.join(now)[:12]
                method = (palette_data.get(name, {}) or {}).get('method', 'coin')
                seed = (palette_data.get(name, {}) or {}).get('seed')
                seed_arg = f" --seed {seed}" if seed is not None else ""
                cmd = f"{sys.executable} \"{os.path.join(os.path.dirname(__file__), 'calculate_palette', '六爻.py')}\" --session-id {session_id} --current-time {now} --output-path \"{out_path}\" --method {method}{seed_arg}"
                os.system(cmd)
                if os.path.exists(out_path):
                    pd_write[name] = load_json(out_path)
                    executed.append({'method': name, 'action': 'generate', 'status': 'ok'})
                else:
                    executed.append({'method': name, 'action': 'generate', 'status': 'failed'})
            elif name == '小六壬':
                out_dir = os.path.join(sess_dir, 'palettes')
                ensure_dir(out_dir)
                out_path = os.path.join(out_dir, f'{name}.json')
                now = (si.get('palette_data', {}) or {}).get('current_time', '') or '202501010000'
                now = ''.join(now)[:12]
                cmd = f"{sys.executable} \"{os.path.join(os.path.dirname(__file__), 'calculate_palette', '小六壬.py')}\" --session-id {session_id} --current-time {now} --output-path \"{out_path}\""
                os.system(cmd)
                if os.path.exists(out_path):
                    pd_write[name] = load_json(out_path)
                    executed.append({'method': name, 'action': 'generate', 'status': 'ok'})
                else:
                    executed.append({'method': name, 'action': 'generate', 'status': 'failed'})
        except Exception as e:
            executed.append({'method': name, 'action': 'generate', 'status': f'exception: {e}'})

    # === 若启用合盘：尝试为 A/B 生成 八字/紫微斗数 盘（需在 palette_data 中提供 personA/personB 的出生信息与性别）===
    syn_cfg = (parsed.get('synastry') or {})
    # JSONC 必须显式 true
    jsonc_syn_true = (syn_cfg.get('required', False) is True)
    # session_input.palette_data.synastry 必须为真（支持字符串 'true'）
    def _to_bool(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ('1', 'true', 'yes', 'y')
        if isinstance(v, (int, float)):
            return v != 0
        return False
    si_pd = si.get('palette_data', {}) or {}
    si_syn_true = _to_bool(si_pd.get('synastry'))
    def _get_person_pd(label: str) -> dict:
        syn_pd = palette_data.get('合盘', {}) if isinstance(palette_data, dict) else {}
        # 允许多种命名：personA/personB 或 person_a/person_b
        alt_label = 'personA' if label == 'personA' else 'personB'
        alt_label2 = 'person_a' if label == 'personA' else 'person_b'
        return (syn_pd.get(label, {}) or syn_pd.get(alt_label, {}) or syn_pd.get(alt_label2, {}) or
                palette_data.get(label, {}) or palette_data.get(alt_label, {}) or palette_data.get(alt_label2, {}) or {})
    # 需要：JSONC=true 且 session_input=true
    need_syn = bool(jsonc_syn_true and si_syn_true)
    if need_syn:
        for person_label in ('personA', 'personB'):
            p = _get_person_pd(person_label)
            # 如果 palette_data 中未提供 A/B 的八字/紫微斗数盘，则尝试生成（严格要求 birth+gender）
            birth_value = ''
            for k in BIRTH_KEYS:
                val = str(p.get(k, '') or '').strip()
                if val:
                    birth_value = val
                    break
            gender_value = p.get('gender')

            if birth_value and gender_value:
                now = (si.get('palette_data', {}) or {}).get('current_time', '') or '202501010000'
                out_dir = os.path.join(sess_dir, 'palettes')
                ensure_dir(out_dir)

                # 生成 八字
                try:
                    out_path_bz = os.path.join(out_dir, f'合盘_{person_label}_八字.json')
                    need_gen_bz = not (((pd_write or {}).get('合盘') or {}).get(person_label) or {}).get('八字')
                    if need_gen_bz:
                        cmd_bz = f"{sys.executable} \"{os.path.join(os.path.dirname(__file__), 'calculate_palette', '八字.py')}\" --session-id {session_id} --birth-string {birth_value} --gender {gender_value} --current-time {now} --output-path \"{out_path_bz}\""
                        os.system(cmd_bz)
                        if os.path.exists(out_path_bz):
                            pd_write.setdefault('合盘', {})
                            pd_write['合盘'].setdefault(person_label, {})
                            pd_write['合盘'][person_label]['八字'] = load_json(out_path_bz)
                            executed.append({'method': f'合盘_{person_label}_八字', 'action': 'generate', 'status': 'ok'})
                        else:
                            executed.append({'method': f'合盘_{person_label}_八字', 'action': 'generate', 'status': 'failed'})
                    else:
                        executed.append({'method': f'合盘_{person_label}_八字', 'action': 'generate', 'status': 'skip-exists'})
                except Exception as e:
                    executed.append({'method': f'合盘_{person_label}_八字', 'action': 'generate', 'status': f'exception: {e}'})

                # 生成 紫微斗数
                try:
                    out_path_zw = os.path.join(out_dir, f'合盘_{person_label}_紫微斗数.json')
                    need_gen_zw = not (((pd_write or {}).get('合盘') or {}).get(person_label) or {}).get('紫微斗数')
                    if need_gen_zw:
                        cmd_zw = f"{sys.executable} \"{os.path.join(os.path.dirname(__file__), 'calculate_palette', '紫微斗数.py')}\" --session-id {session_id} --birth-string {birth_value} --gender {gender_value} --current-time {now} --output-path \"{out_path_zw}\""
                        os.system(cmd_zw)
                        if os.path.exists(out_path_zw):
                            pd_write.setdefault('合盘', {})
                            pd_write['合盘'].setdefault(person_label, {})
                            pd_write['合盘'][person_label]['紫微斗数'] = load_json(out_path_zw)
                            executed.append({'method': f'合盘_{person_label}_紫微斗数', 'action': 'generate', 'status': 'ok'})
                        else:
                            executed.append({'method': f'合盘_{person_label}_紫微斗数', 'action': 'generate', 'status': 'failed'})
                    else:
                        executed.append({'method': f'合盘_{person_label}_紫微斗数', 'action': 'generate', 'status': 'skip-exists'})
                except Exception as e:
                    executed.append({'method': f'合盘_{person_label}_紫微斗数', 'action': 'generate', 'status': f'exception: {e}'})
            else:
                executed.append({'method': f'合盘_{person_label}_生成', 'action': 'generate', 'status': 'skipped-no-birth-or-gender'})

    # 写回 palette_data.json 与步骤日志
    save_json(os.path.join(artifacts_dir, 'palette_data.json'), pd_write)
    step_log = {
        'step': 'prepare',
        'started_at': start_ts,
        'finished_at': time.time(),
        'executed': executed
    }
    save_json(os.path.join(artifacts_dir, 'step2_prepare_log.json'), step_log)

    # === 条件触发合盘 Step2.5：仅当 JSONC 启用 + 提供关系对 + 已有 A/B 八字盘时 ===
    def _has_ab_bazi(pd: dict) -> bool:
        try:
            a_bz = (((pd or {}).get('合盘') or {}).get('personA') or {}).get('八字')
            b_bz = (((pd or {}).get('合盘') or {}).get('personB') or {}).get('八字')
            a_zw = (((pd or {}).get('合盘') or {}).get('personA') or {}).get('紫微斗数')
            b_zw = (((pd or {}).get('合盘') or {}).get('personB') or {}).get('紫微斗数')
            return bool(a_bz) and bool(b_bz) and bool(a_zw) and bool(b_zw)
        except Exception:
            return False

    if need_syn and _has_ab_bazi(pd_write):
        cmd = f"{sys.executable} \"{os.path.join(os.path.dirname(__file__), 'step2_5_synastry.py')}\" --sessions-root {args.sessions_root} --config-path {args.config_path} --user-settings {args.user_settings} --session-input {args.session_input} --question-config-dir {args.question_config_dir} --session-id {session_id}"
        if args.model_set:
            cmd += f" --model-set {args.model_set}"
        os.system(cmd)

    log_message("SUCCESS", f"已准备完成：复制配置并排盘。", "STEP2")



if __name__ == '__main__':
    main()


# 调用示例:
# python step2_prepare.py --session-id <sid> --sessions-root sessions --question-config-dir question_config --session-input session_input.json')