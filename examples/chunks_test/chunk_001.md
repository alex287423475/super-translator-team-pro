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