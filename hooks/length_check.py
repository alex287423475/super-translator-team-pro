import sys
import os

def count_tokens_and_chars(text):
    """
    估算文本的长度。
    注意：这是一个轻量级估算。
    对于中文，1个汉字 ≈ 1-1.5个token。
    对于英文，1个单词 ≈ 1.3个token。
    这里简单使用字符数作为主要参考，辅以单词数。
    """
    char_count = len(text)
    # 简单的单词分割（基于空格），对中文不准确，但可作为参考
    word_count = len(text.split())
    
    # 粗略的 Token 估算公式 (经验值)
    # 英文: chars / 4.5
    # 中文: chars * 0.6 (因为中文信息密度大)
    # 这里取一个折中值，或者直接返回字符数供脚本判断
    estimated_tokens = int(char_count / 3) 
    
    return char_count, word_count, estimated_tokens

def main():
    if len(sys.argv) < 2:
        print("Usage: python length_check.py <input_file> [max_length]")
        sys.exit(1)

    input_file = sys.argv[1]
    
    # 可选参数：最大长度阈值
    max_length = int(sys.argv[2]) if len(sys.argv) > 2 else 5000

    # 1. 读取文件
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ 文件不存在: {input_file}")
        sys.exit(1)

    # 2. 计算长度
    chars, words, tokens = count_tokens_and_chars(content)

    # 3. 输出报告到 stderr (不干扰 stdout)
    print(f"📊 文件分析报告: {os.path.basename(input_file)}", file=sys.stderr)
    print(f"   - 字符数: {chars}", file=sys.stderr)
    print(f"   - 估算 Token: ~{tokens}", file=sys.stderr)
    
    # 4. 决策逻辑
    if chars > max_length:
        print(f"⚠️  状态: 超长 (>{max_length} 字符)，建议切分", file=sys.stderr)
        # 输出 "SPLIT" 到 stdout，供 Shell 脚本捕获
        print("SPLIT")
    else:
        print(f"✅  状态: 长度正常", file=sys.stderr)
        # 输出 "OK" 到 stdout
        print("OK")

if __name__ == "__main__":
    main()