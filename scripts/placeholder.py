import re
import json
import sys
import os

def write_stdout(text):
    sys.stdout.buffer.write(text.encode('utf-8'))

def create_placeholders(text):
    """
    扫描文本，提取代码块、公式和特定变量，替换为占位符。
    返回：(处理后的文本, 占位符映射字典)
    """
    mapping = {}
    counter = 0

    # --- 1. 保护代码块 (``` ... ```) ---
    # 使用 re.DOTALL 让 . 也能匹配换行符
    def replace_code_block(match):
        nonlocal counter
        ph_id = f"{{{{PH_CODE_BLOCK_{counter}}}}}"
        mapping[ph_id] = match.group(0) # 保存完整的代码块（包括 ``` 语言标记）
        counter += 1
        return ph_id

    # 正则：匹配 ``` 开头和结尾的块，非贪婪匹配
    text = re.sub(r"```[\s\S]*?```", replace_code_block, text)

    # --- 2. 保护行内代码 (` ... `) ---
    def replace_inline_code(match):
        nonlocal counter
        ph_id = f"{{{{PH_INLINE_{counter}}}}}"
        mapping[ph_id] = match.group(0)
        counter += 1
        return ph_id
    
    # 正则：匹配单个反引号包裹的内容，排除反引号本身
    text = re.sub(r"`[^`]+`", replace_inline_code, text)

    # --- 3. 保护数学公式 ($$ ... $$ 和 $ ... $) ---
    # 块级公式
    def replace_block_math(match):
        nonlocal counter
        ph_id = f"{{{{PH_MATH_BLOCK_{counter}}}}}"
        mapping[ph_id] = match.group(0)
        counter += 1
        return ph_id
    
    text = re.sub(r"\$\$[\s\S]*?\$\$", replace_block_math, text)
    
    # 行内公式 (简单匹配，避免匹配到普通的货币符号，假设变量名包含字母)
    # 这里采用较安全的策略：匹配 $ 字母/数字/符号 $，但不匹配纯数字 $100
    text = re.sub(r"\$[^\s$][^\$]*[^\s$]\$", replace_block_math, text) # 简化处理，复用逻辑

    # --- 4. 保护 HTML 标签 (仅限常见安全场景) ---
    # 这里避免使用过宽的正则吞掉大段正文，只保护常见内联/块级标签。
    SAFE_HTML_TAGS = ("br", "hr", "img", "span", "div", "kbd", "sup", "sub")

    def replace_html_tag(match):
        nonlocal counter
        ph_id = f"{{{{PH_HTML_{counter}}}}}"
        mapping[ph_id] = match.group(0)
        counter += 1
        return ph_id

    tag_group = "|".join(SAFE_HTML_TAGS)
    text = re.sub(
        rf"<(?:{tag_group})(?:\s+[^<>]*?)?\s*/>",
        replace_html_tag,
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        rf"<(?P<tag>{tag_group})(?:\s+[^<>]*?)?>.*?</(?P=tag)>",
        replace_html_tag,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return text, mapping

def main():
    if len(sys.argv) < 2:
        print("Usage: python placeholder.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    
    # 读取源文件
    try:
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            content = f.read().lstrip('\ufeff')
    except FileNotFoundError:
        print(f"ERROR: file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    # 执行替换
    processed_text, mapping = create_placeholders(content)

    # 输出处理后的文本到 stdout (供管道传递)
    write_stdout(processed_text.lstrip('\ufeff'))

    # 保存映射表到文件 (供 format_fix.py 使用)
    # 文件名格式：原文件名.mapping.json
    base_name = os.path.splitext(input_file)[0]
    mapping_file = f"{base_name}.mapping.json"
    
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    
    # 将映射文件名打印到 stderr，以免干扰 stdout 的文本输出
    print(f"INFO: generated placeholder map: {mapping_file}", file=sys.stderr)

if __name__ == "__main__":
    main()
