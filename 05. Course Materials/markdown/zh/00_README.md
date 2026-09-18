# 课程材料：SAP BTP 上的受治理 AI

Raj Academy 面向 SAP 工程师的动手实践课程。本文件夹中的所有内容都有英文、日文和简体中文版本；代码、命令、文件名和引用在三种语言中完全相同。

## 面向学员

| 页面 | 是什么 |
|---|---|
| `03_Student_Workbook.html` | 动手实践练习册：第A部分为笔记本电脑实验（无需 SAP 账户），第B部分为你自己的 SAP BTP 试用租户。勾选任务，输入你的答案和笔记，然后点击“Save my copy”（保存我的副本）下载填写好的文件。 |
| `04_Lab_Guide.html` | 每个实验一节：每个角色问了什么、返回了什么、是否正确以及为什么。请在课后阅读。 |

用你的语言打开页面：`English/`、`Japanese/`、`Chinese/`。每个页面顶部都有语言切换；你的勾选和答案按浏览器保存，并在语言之间保留。

代码位于 <https://github.com/nuvear/SAP-BTP>：`apps/`（数据服务、策略加载器、MCP 服务器、部署指南、实验引导器）和 `data/northwind/`（11 份策略文档和 3 份健壮性文档）。

## 面向讲师

每个语言文件夹中的 `instructor/` 存放课程运行手册（映射到幻灯片的一日议程）、演示脚本（逐个问题的现场演示）和参考答案。这些文件夹通过 `.gitignore` 排除在公共仓库之外。幻灯片为 `../04. Governed_AI_on_SAP_BTP.pptx`；课程中使用的 Stage 页面（一次一步，含实验图表和记录的证据）是一个私有的 Claude artifact。

## 文件是如何生成的

`markdown/en`、`markdown/ja` 和 `markdown/zh` 存放源文件。英文源文件是在线 Claude Docs（运行手册、演示脚本、练习册和实验指南）的快照；翻译由这些快照制作而成。`tools/build_package.py` 使用 `tools/build_handbook.py` 从源文件构建每个 HTML 页面。编辑在线文档之后，请重新导出并重新构建。
