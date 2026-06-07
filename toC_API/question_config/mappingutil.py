import os
import json
import re

def read_jsonc(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 移除注释
    content = re.sub(r'//.*?\n', '\n', content)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    return json.loads(content)

# 获取当前目录下所有 .jsonc 文件，按字典序排序
files = sorted(f for f in os.listdir(".") if f.endswith(".jsonc"))

for filename in files:
    try:
        data = read_jsonc(filename)
        methods = data.get("quantitative_stage", {}).get("methods", [])
        synastry = data.get("synastry", {})
        require_synastry = synastry.get("required", False)  # 默认 False

        method_names = [m["method_name"] for m in methods if m.get("method_name")]

        # 优先级 1: synastry.require = true
        if require_synastry is True:
            print(f"{filename},true,006")
        # 优先级 2: synastry.require = false 且 含有紫微斗数/八字
        elif require_synastry is False and ("紫微斗数" in method_names or "八字" in method_names):
            print(f"{filename},false,003")
        # 优先级 3: synastry.require = false 且 含有六爻/小六壬
        elif require_synastry is False and ("六爻" in method_names or "小六壬" in method_names):
            print(f"{filename},六爻,001")
        # 优先级 4: 都不满足
        else:
            print(f"{filename},unknown,xxx")

    except Exception as e:
        print(f"{filename},unknown,xxx")