import os
import json


def extract_fields_from_jsonc(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
        # 移除注释（简单的处理方式）
        content = '\n'.join([line for line in content.split('\n') if not line.strip().startswith('//')])
        data = json.loads(content)

        question_metadata = data.get("question_metadata", {})
        return {
            "question_id": question_metadata.get("question_id", ""),
            "question_text": question_metadata.get("question_text", ""),
            "question_domain": question_metadata.get("question_domain", ""),
            "question_theme": question_metadata.get("question_theme", "")
        }


def process_jsonc_files(directory):
    result = {}
    for filename in os.listdir(directory):
        if filename.endswith(".jsonc"):
            file_path = os.path.join(directory, filename)
            try:
                fields = extract_fields_from_jsonc(file_path)
                file_name_without_ext = os.path.splitext(filename)[0]
                result[file_name_without_ext] = fields
            except Exception as e:
                print(f"Error processing file {filename}: {e}")
    return result


# 指定目录路径
directory_path = r"C:\Users\x1gen9\Documents\Elephenotype-master - Copy\Elephenotype-master - Copy\data_prompt_engineering\real_toc\question_config"

# 处理文件并生成结果
output = process_jsonc_files(directory_path)

# 输出为JSON对象
print(json.dumps(output, ensure_ascii=False, indent=2))
