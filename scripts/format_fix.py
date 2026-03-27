import re
import sys
import json

def write_stdout(text):
    sys.stdout.buffer.write(text.encode('utf-8'))

def restore_placeholders(text, mapping_file):
    """
    将文本中的占位符（如 {{PH_001}}）还原为原始内容。
    """
    with open(mapping_file, 'r', encoding='utf-8-sig') as f:
        mapping = json.load(f)

    if not isinstance(mapping, dict):
        raise ValueError("mapping file must contain a JSON object")

    # 按照 ID 排序，确保还原顺序正确（虽然 JSON 字典通常有序，但保险起见）
    # 这里其实不需要排序，因为我们是根据 key 查找 value
    for ph_id, original_content in mapping.items():
        # 使用 re.escape 确保占位符中的特殊字符（如 {}）被正确转义
        # 替换时确保完全匹配
        text = text.replace(ph_id, original_content)

    return text

def fix_markdown_formatting(text):
    """
    修复 AI 常见的 Markdown 格式错误。
    """
    # 1. 修复加粗/斜体周围的空格问题
    # 将 "** 文本 **" 修复为 "**文本**" (中文语境下通常不需要空格，或者保留一个空格)
    # 这里采用更通用的策略：确保 ** 和文字之间没有多余的空格，但 ** 和中文之间保持自然
    # 规则：去除 ** 内部首尾的空格
    text = re.sub(r'\*\*([ \t]+)(.*?)\*\*', lambda m: f"**{m.group(2)}**", text)
    text = re.sub(r'\*\*(.*?)[ \t]+\*\*', lambda m: f"**{m.group(1)}**", text)
    
    # 2. 修复列表符号后的空格
    # 将 "-文本" 修复为 "- 文本"
    text = re.sub(r'^(\s*)([-*+])(\S)', r'\1\2 \3', text, flags=re.MULTILINE)
    
    # 3. 规范化代码围栏行，去掉围栏行尾多余空白
    text = re.sub(r'(?m)^[ \t]*```([^\n`]*)[ \t]+$', lambda m: f"```{m.group(1).rstrip()}", text)
    
    # 4. 修复链接格式
    # 防止 AI 在 ] 和 ( 之间加入空格，导致链接失效
    text = re.sub(r'\]([ \t]+)\(', r'](', text)

    # 5. 统一占位符附近的多余空格，减少还原失败概率
    text = re.sub(r'[ \t]+(\{\{PH_[A-Z_0-9]+\}\})', r'\1', text)
    text = re.sub(r'(\{\{PH_[A-Z_0-9]+\}\})[ \t]+', r'\1', text)

    return text

def main():
    if len(sys.argv) < 3:
        print("Usage: python format_fix.py <input_file> <mapping_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    mapping_file = sys.argv[2]

    # 1. 读取经过审校的文本
    try:
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            content = f.read().lstrip('\ufeff')
    except FileNotFoundError:
        print(f"ERROR: file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    # 2. 还原占位符
    print("INFO: restoring placeholders...", file=sys.stderr)
    try:
        restored_content = restore_placeholders(content, mapping_file)
    except Exception as e:
        print(f"ERROR: failed to restore placeholders: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. 修复 Markdown 格式
    print("INFO: fixing markdown formatting...", file=sys.stderr)
    final_content = fix_markdown_formatting(restored_content)

    # 4. 输出结果 (直接打印到 stdout，由调用者重定向或捕获)
    write_stdout(final_content.lstrip('\ufeff'))

if __name__ == "__main__":
    main()
