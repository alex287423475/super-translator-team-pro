优秀译文范例

本文档通过具体的“错误”与“正确”对比，直观展示本翻译工作流所追求的质量标准。请翻译官与审校官在处理类似语境时，以此为参照，确保译文不仅准确，而且符合中文技术文档的阅读习惯。

术语一致性

场景：涉及 API 开发与配置。

原文：
"You need to configure the endpoint in your .env file. If the instance fails to connect, check the logs."

错误译文：
“你需要在你的 .env 文件中配置端点。如果实例连接失败，检查日志。”

正确译文：
“你需要在 .env 文件中配置 endpoint（端点）。如果 instance（实例）连接失败，请检查 logs（日志）。”

解析：
行内代码保护：.env、endpoint、instance、logs 均作为代码或变量处理，保留了反引号。
术语准确：endpoint 译为“端点”，instance 译为“实例”。
处理策略：对于关键术语，采用“英文+中文”的格式（如 endpoint（端点）），既保留了代码的准确性，又提供了中文解释，方便读者理解。

句式优化与去翻译腔

场景：解释复杂的功能逻辑。

原文：
"The library, which is designed to handle complex data structures, provides a robust interface that allows developers to easily manipulate arrays without worrying about memory management."

错误译文：
“这个库，它是被设计用来处理复杂的数据结构的，提供了一个强大的接口，允许开发者去轻松地操作数组，而不用担心内存管理。”

正确译文：
“该库专为处理复杂数据结构而设计，提供了强大的接口。开发者可以轻松操作数组，无需担心内存管理问题。”

解析：
拆分长句：原文是一个典型的英文长句，包含定语从句。译文将其拆分为两个短句，逻辑更清晰。
去除冗余：删除了“它是被”、“去”、“而”等典型的翻译腔词汇。
主动语态：将“allows developers to...”转化为“开发者可以...”，更符合中文表达习惯。

语气与指令

场景：用户操作指南。

原文：
"To get started, you should first install the dependency. Then, run the build script."

错误译文：
“为了开始，你应该首先安装依赖。然后，运行构建脚本。”

正确译文：
“开始之前，请先安装依赖。随后，运行构建脚本。”

解析：
自然流畅：“To get started” 译为“开始之前”或直接省略，比“为了开始”更自然。
指令清晰：去掉了“你应该”，直接使用祈使句“请先安装...”，在技术文档中更显专业且高效。

格式与标点

场景：包含链接和特殊符号。

原文：
"For more details, visit our Documentation. Note: This feature is currently in Beta."

错误译文：
“为了更多细节，访问我们的 文档 。注意：这个功能当前在 Beta 。”

正确译文：
“如需了解更多详情，请访问文档。注意：该功能目前处于 Beta 阶段。”

解析：
链接处理：保留了 Markdown 链接格式，且链接文本翻译准确。
标点规范：使用了中文全角标点（如句号、冒号），但在代码 Beta 周围保留了适当的间距。
强调：将“Note”译为加粗的注意，提升了可读性。

代码与注释保护

场景：代码块中的内容。

原文：
Calculate the sum
def add(a, b):
    return a + b

错误译文：
计算总和
def 加(a, b):
    return a + b

正确译文：
Calculate the sum
def add(a, b):
    return a + b

解析：
绝对保护：代码块内的任何内容（包括注释 #、函数名 add、变量名 a、b）都严禁修改。这是不可逾越的红线。