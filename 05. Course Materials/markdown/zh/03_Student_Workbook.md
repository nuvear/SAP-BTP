# Northwind Advisor 学员练习手册

Raj Academy · 2026年9月18日

本手册是"SAP BTP 上的受治理 AI"课程的动手实践配套材料，分为两部分。第A部分在你自己的笔记本电脑上运行公开代码仓库中的代码：不需要 SAP BTP 账户、API 密钥或密码；预计约九十分钟。第B部分在你自己的免费 SAP BTP 试用账户上构建同一个顾问助手，使用真实的 SAP 登录，与讲师的演示运行方式相同；预计约四小时。请携带：一台拥有管理员权限的笔记本电脑，Node.js 20+、Python 3.11+、git；第B部分还需要一部手机用于接收 SAP 验证码，以及（可选）一个 Claude 账户。

# 第A部分: 笔记本电脑实验

## 你将构建什么

你将在自己的机器上运行演示中看到的同样三个组件：带有行规则的 Northwind 数据服务、带有文档过滤器的策略库，以及提供三个只读工具的 MCP 服务器。你将使用两个内置测试用户来代替 SAP 登录，并使用 MCP Inspector 来代替 Claude；MCP Inspector 是一个小型网页，让你可以手动调用工具，并准确看到返回的内容。这正是本手册的意义所在：在模型把答案转化为文字之前，先看到原始的返回结果。

| 测试用户 | 办公室 | 角色 | 可读取的订单 | 可读取的文档 |
| --- | --- | --- | --- | --- |
| `nancy` | 西雅图 | SalesHQ | 全部 830 条 | all-staff, sales, sales-seattle |
| `steven` | 伦敦 | SalesRegion，国家 UK | 英国销售人员的 224 条订单 | all-staff, sales, sales-london |

实验日期固定为 2026年5月7日，因为样本数据截止于 2026年5月6日。凡是规则中提到"今天"，指的都是这个日期。

你需要：Node.js 20 或更高版本、Python 3.11 或更高版本、git，以及一个浏览器。用 `node --version`、`python3 --version`、`git --version` 检查。Windows 用户：请使用 PowerShell 或 WSL；下面的命令是为 Unix 风格的 shell 编写的，PowerShell 有差异的地方会另行注明。

## 环境准备：三个终端，约 20 分钟

获取代码，只需一次：

```bash
git clone https://github.com/nuvear/SAP-BTP.git
cd SAP-BTP/apps
```

**终端 1，数据服务。** 这是拥有订单数据和行规则的 SAP CAP 服务。在本地它使用内存数据库和两个模拟用户。

```bash
cd northwind-service
npm ci
npm test
npm start
```

`npm test` 的输出必须以 `# pass 9` 和 `# fail 0` 结尾。`npm start` 会打印一行包含 `http://localhost:4004` 的内容，随后是 `server ... launched`；出现 SQLite 处于实验阶段的警告属于正常现象。让它保持运行。在浏览器中打开 <http://localhost:4004/odata/v4/northwind/Orders?$top=3>：它会要求输入用户；输入用户名 `nancy` 和密码 `nancy`，你会看到三条订单的 JSON 数据。这就是助手所读取的内容。

**终端 2，MCP 服务器。** 它提供三个工具，并且在本地对代码仓库中已有的 86 个策略段落（`policy-loader/chunks.jsonl`）进行关键词搜索。

```bash
cd mcp-servers
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
DEV_MODE=1 DEV_USER=nancy LAB_TODAY=2026-05-07 python server.py advisor
```

`pytest` 必须显示 45 passed（出现少量弃用警告属于正常；它会在另一个端口上启动自己的一份数据服务副本，因此终端 1 不会造成干扰）。最后一条命令会打印 `Uvicorn running on http://0.0.0.0:8000`。它不会回显你选择的用户，所以请在启动前检查变量。在 PowerShell 上，用 `.venv\Scripts\Activate.ps1` 激活虚拟环境，并在运行 `python server.py advisor` 之前用 `$env:DEV_MODE="1"; $env:DEV_USER="nancy"; $env:LAB_TODAY="2026-05-07"` 设置变量。

`DEV_MODE=1` 的含义：在你的笔记本电脑上没有 SAP 登录，所以服务器从 `DEV_USER` 获取用户。在 BTP 上这个开关并不存在；服务器会拒绝任何没有有效 SAP 令牌的调用。切勿带着这个开关部署。

**终端 3，MCP Inspector。** 这是你观察工具的窗口。

```bash
npx @modelcontextprotocol/inspector
```

它会打开一个浏览器页面。选择传输方式 **Streamable HTTP**（可流式 HTTP），URL 填 `http://localhost:8000/mcp`，点击 **Connect**（连接），然后点击 **List Tools**（列出工具）。你应该能看到 `get_order_status`、`get_product_availability` 和 `search_policies`。如果 Connect 失败，请检查终端 2 是否仍在运行，以及 URL 是否以 `/mcp` 结尾。

之后要切换为 Steven 时，在终端 2 中用 Ctrl+C 停止服务器，再用 `DEV_USER=steven` 重新启动，然后在 Inspector 中再次点击 Connect。（不重启的替代方法：在 Inspector 中添加一个自定义请求头 `X-Dev-User: steven`；请求头的优先级高于环境变量。）

## 练习 1：实时事实与行规则（15 分钟）

在 Inspector 中选择 `get_order_status`，输入 `order_id` = `11019`，点击 Run Tool（运行工具）。

- [ ] 记录：客户、销售人员及其办公室所在国家、要求交付日期、`days_until_required`、承运商，以及两个产品行及其库存。注意 `data_read_at`：每一条事实都带有它被读取的时间。
- [ ] 再用 `11070` 运行一次。销售人员是 Andrew Fuller，美国办公室。记下 `days_until_required`。
- [ ] 现在切换为 Steven（用 `DEV_USER=steven` 重启终端 2，重新连接）。分别对 `11019` 和 `11070` 运行 `get_order_status`。

你应该看到的结果：作为 Steven，11019 能够返回（其销售人员在英国办公室），而 11070 返回 `found: false`，"No order with this number is visible to you."（没有此编号的订单对你可见。）这不是 MCP 服务器做出的决定。它以不同的用户身份向数据服务发送了同样的请求，是数据服务的行规则给出了回答。查看终端 1：两个请求都被记录了下来，第二个请求后面跟着 `404 - Error: Not Found`。

为什么措辞很重要。在任何工具存在之前，一个被问及订单 11019 的模型仍然会根据训练中学到的模式自信地作答；而订单 11019 只存在于本实验的数据库中，所以那样的回答会是编造的（幻觉）。你在这里看到的每一个值都是在调用的那一刻从某一行数据中读取的，`data_read_at` 说明了读取的时间。基于事实的检索取代了编造。

- [ ] 用 `Rössle Sauerkraut` 和 `Chai` 试试 `get_product_availability`。一个是已停产但仍有库存的产品；另一个是正常产品。哪些字段告诉了你这一点？

问题，请用一句话回答：为什么服务器说"not visible to you"（对你不可见），而不是"does not exist"（不存在）或"you are not allowed"（你无权访问）？（请在下方写下你的答案；参考答案由讲师掌握。）

## 练习 2：带引用的规则（15 分钟）

切换回 Nancy。选择 `search_policies`；`k` 保持为 4。

- [ ] 问题：`How much discount can I give a customer on my own authority?`（我在自己的权限内可以给客户多少折扣？）阅读返回的每个段落的 `citation`。哪份文档、哪个版本给出了答案，数值是多少？
- [ ] 查看代码仓库中的 `data/northwind/robustness/`。打开已被取代的 Discount Authority Policy 1.0（折扣权限策略 1.0）以及关于春季促销活动的备忘录草稿。它们规定的限额是多少？它们被返回了吗？为什么没有？（提示：`policy-loader/chunks.jsonl` 中的每个段落都带有 `status`、`effective_from`、`effective_to` 和 `audience`；工具结果显示前三项。`search_policies` 只搜索状态为 current、在实验日期有效、且你有权阅读的段落。）
- [ ] 问题：`customer wants a rush job, is that allowed?`（客户想要加急处理，这允许吗？）这些段落中并不包含"rush job"这个短语。哪个段落解释了搜索为何仍能找到正确的规则？（找一找术语表。）
- [ ] 问题：`Which carrier may carry seafood?`（哪家承运商可以运输海鲜？）然后结合练习 1：订单 11019 有一个海鲜产品行，承运商为 3 号。该订单应当如何处理，由谁付费，由谁审批？请引用相应章节。

关于搜索在本地与在 BTP 上的工作方式的说明。在你的笔记本电脑上，搜索是基于关键词的（BM25）；它能找到术语表条目是因为词语匹配。在 BTP 上，同样的问题由 SAP HANA 的内置函数生成嵌入向量，并按语义进行比较；在那里，关于加急处理的段落会排在最前面，尽管它与问题没有任何共同的词语。两种方式的过滤器是完全相同的：它在排序之前应用，在 HANA 上位于 `WHERE` 子句中，在本地位于函数 `visible()` 中。

## 练习 3：身份决定一切（10 分钟）

同一个问题，两个人。

- [ ] 作为 Nancy：用 `How far are we prepared to go on the QUICK-Stop contract discount?`（在 QUICK-Stop 合同折扣上我们准备让步到什么程度？）调用 `search_policies`。记下引用。其中有没有任何谈判数字？
- [ ] 切换为 Steven，问完全相同的问题。现在出现了一份来自伦敦销售经理的备忘录：文档 id 是什么，哪个章节，其中包含什么数字？
- [ ] 查看 `data/northwind/corpus/` 中的备忘录文件。找到限制其读者范围的那一行。然后打开 `apps/mcp-servers/identity.py`，找到为本地使用定义 Nancy 和 Steven 的文档受众的位置。

需要注意的地方：Nancy 并没有被告知有内容对她隐藏。助手根据它所能看到的内容作答，而它能看到什么，是由附加在她身份上的受众列表决定的，永远不由问题本身决定。在 BTP 上，该列表由 SAP 角色集合和登录令牌中的 `country` 属性推导得出（`apps/mcp-servers/xsuaa.py`，函数 `audiences_for`）；在本地，它来自两个测试用户。

声明的身份，而非证明的身份。在笔记本电脑上没有人登录：`DEV_USER`（或 `X-Dev-User` 请求头）指定用户名，`identity.py` 中的 `DEV_USERS` 为该用户名赋予其文档受众以及访问数据服务的基本认证登录信息，而数据服务在 `package.json` 中的模拟用户则为该登录赋予角色和国家。任何人都可以输入 `DEV_USER=steven` 而成为 Steven。这正是 BTP 上不存在这个开关的原因：在那里，同样的两项事实——角色和国家——是包含在 XSUAA 令牌中送达的，MCP 服务器会验证该令牌（签名、有效期、签发者、受众），数据服务会再验证一次。第A部分展示身份的效果；第B部分展示身份的证明。实验指南（`04_Lab_Guide`）以这种方式逐个角色地讲解每个实验。

可选：更改实验日期。用 `LAB_TODAY=2026-08-01` 重启服务器，并重复 Steven 的问题。该备忘录的 `effective_to` 是 2026年6月30日，所以到了八月它不再被返回，即使对 Steven 也是如此。文档无需任何人编辑即会过期。

## 练习 4：陷阱（15 分钟）

这是稳健性实验。你将关闭文档过滤器，观察一个粗心的系统会做出什么。

- [ ] 停止终端 2，并在关闭过滤器的情况下重启：`DEV_MODE=1 DEV_USER=nancy LAB_TODAY=2026-05-07 STRICT_FILTERS=0 python server.py advisor`。重新连接 Inspector。
- [ ] 提问：`What discount may I approve for a customer?`（我可以为客户批准多少折扣？）并将 `k` 设为 `6`（该工具最多返回 6 条）。现在，`status: superseded` 的段落（5%，来自 `NW-POL-001 v1.0, 3. Approval tiers`）和 `status: unapproved` 的段落（15%，备忘录草稿 `NW-MEM-900`）与当前有效的 10% 一起出现了。记下这三个数字及其引用。一个拿到这些段落的模型将不得不做出选择，而它可能选错。（关键词搜索对措辞很敏感；上面这个确切的问题是在笔记本电脑上能同时带出这三条的问题。在 HANA 上，基于语义的搜索对任何措辞都能做到。）
- [ ] 提问：`Has the lead time for Pavlova products changed?`（Pavlova 产品的交货周期有变化吗？）出现了一个 `status: unverified-external` 的段落：一封供应商邮件。把它的第二个段落读到最后。其中包含一条写给"any AI assistant"（任何 AI 助手）的指令。
- [ ] 作为 Nancy，在关闭过滤器的情况下，提出练习 3 中的 QUICK-Stop 问题。现在伦敦备忘录对她也出现了。

去掉 `STRICT_FILTERS=0` 重启服务器，并确认三个陷阱都再次消失。

本练习展示的内容：过滤器是在检索之前应用的一行策略，它一次性消除了三类不同的故障：过时的规则、未经批准的规则，以及试图向模型下达指令的内容。模型的良好行为是第二道防线，而不是第一道。在演示中，你看到 Claude 即使在被直接要求时也拒绝执行被注入的指令；在这里你看到，当过滤器开启时，它根本就没有收到那条指令。

问题：对于一个关于折扣的问题，关键词搜索会把三个陷阱中的哪一个排在最前面，这为什么危险？（请在下方写下你的答案；参考答案由讲师掌握。）

## 练习 5：阅读代码，找到每条规则（15 分钟）

你刚才观察到的每条规则都是某个文件中的几行代码。找到它们；关键在于看到治理是可以审查的代码，而不是你所期望的行为。

| 你观察到的规则 | 文件 | 要找的内容 |
| --- | --- | --- |
| Steven 无法读取订单 11070 | `apps/northwind-service/srv/northwind-service.cds` | `Orders` 上的 `@restrict`：`SalesHQ` 读取全部，`SalesRegion` 读取 `where: 'Employee.Country = $user.country'`。还有 `@readonly`：完全没有写操作。 |
| 已取代、未批准、已过期和受限的段落从不出现 | `apps/mcp-servers/stores.py` | 函数 `visible()`：四个条件，在排序之前应用 |
| SAP HANA 上的同样四个条件 | `apps/mcp-servers/hana_store.py` | `SEARCH` 语句：`WHERE STATUS = 'current' AND ... AUDIENCE IN (...)`，位于 `ORDER BY SCORE` 之前 |
| 只有三个工具，全部只读 | `apps/mcp-servers/server.py` | 函数 `build()`：三个 `@mcp.tool()` 函数，别无其他；没有通用查询工具 |
| 本地的用户身份 | `apps/mcp-servers/identity.py` | `DEV_USERS`，以及当 `DEV_MODE` 不为 `1` 时拒绝一切的那一行 |
| BTP 上的用户身份 | `apps/mcp-servers/xsuaa.py` | `verify_token`：签名、有效期、签发者、受众，按此顺序；`audiences_for`：角色范围和 `country` 属性转化为文档受众 |
| 服务器在 BTP 上无法以开放状态启动 | `apps/mcp-servers/server.py` | 函数 `auth_config()`：当既没有 XSUAA 绑定也没有 `DEV_MODE` 时触发 `SystemExit` |
| 段落中的文本是数据，不是命令 | `apps/mcp-servers/policy_tools.py` 和 `server.py` | 每个搜索结果中的 `note` 字段，以及提供给模型的 `INSTRUCTIONS` 文本 |

- [ ] 改动一处并观察测试失败：在 `stores.py` 中，让 `visible()` 对已取代的段落返回 `True`，运行 `python -m pytest -q`，阅读哪些测试失败了以及它们说了什么。然后改回来。
- [ ] 阅读 `tests/test_xsuaa.py`。它用本地密钥签发一个伪造的 SAP 令牌，并展示四条验证规则各自如何拒绝一个无效令牌。哪个测试能够捕获从另一个 SAP 应用程序窃取的令牌？

## 更进一步

**在 Claude Desktop 中与它对话，而不是使用 Inspector。** Claude Desktop 可以直接运行本地 MCP 服务器。编辑它的配置文件（Claude Desktop > Settings > Developer > Edit Config），添加如下所示的条目，使用你自己的路径；保持终端 1 运行。

```json
{
  "mcpServers": {
    "northwind-local": {
      "command": "/full/path/to/SAP-BTP/apps/mcp-servers/.venv/bin/python",
      "args": ["/full/path/to/SAP-BTP/apps/mcp-servers/server.py", "advisor", "--stdio"],
      "env": {
        "DEV_MODE": "1",
        "DEV_USER": "nancy",
        "LAB_TODAY": "2026-05-07",
        "NORTHWIND_SERVICE_URL": "http://localhost:4004/odata/v4/northwind",
        "POLICY_CHUNKS": "/full/path/to/SAP-BTP/apps/policy-loader/chunks.jsonl"
      }
    }
  }
}
```

重启 Claude Desktop，提出演示中的四个问题。把 `DEV_USER` 改为 `steven`，重启，再问一遍。现在你的笔记本电脑上已经有了完整的演示，由 Claude 来撰写文字。

**将它部署到你自己的 SAP BTP 试用账户。** 这是课程的下半部分，约半天时间。步骤都在代码仓库中：`apps/DEPLOY.md`（带自然语言处理选项的 HANA Cloud 实例、数据服务、角色集合）和 `apps/DEPLOY-MCP.md`（带 SAP 登录的 MCP 服务器以及 Claude 连接器）。两个经过实践教训得来的要点已经写入其中：在 `requirements.txt` 中将 `mcp<2` 固定版本，以及逐个输入 `cf cups` 的值。`apps/phase0/hana_checks.sql` 会在你加载任何内容之前验证你的 HANA 实例能够生成文本嵌入向量。

**带上你自己的文档。** 把一个 `.txt` 或 `.pdf` 文件放入 `data/northwind/corpus/`，在 `manifest.json` 中添加它，并填写状态、生效日期和受众，在 `apps/policy-loader` 中运行 `python loader.py --data ../../data/northwind --out chunks.jsonl`，然后重启服务器。你的文档现在可以被搜索到了，并且受到与其他所有内容相同的过滤器约束。试着给它设置 `"status": "draft"`，观察它如何保持不可见。

## 反思

反思（请在团队中讨论）:

1. 四条规则（行、文档、工具、身份）中，哪一条对你所在的组织来说最难用代码表达？它目前存在于哪里？
2. 助手对 Nancy 说"this information is not available to you"（此信息对你不可用）。它是否应该说明存在一份受限文档？如果它这样做了，会有什么变化？
3. 过滤器使用状态、生效日期和受众。对于你们的策略来说，还有哪些文档属性是重要的？由谁来维护它们？
4. 如果把 Claude 换成另一个模型，你所看到的行为中哪些会改变，哪些是由平台保证的、与模型无关的？

# 第B部分: 你自己的SAP BTP租户

在第A部分中，一切都在你的笔记本电脑上用两个测试用户运行。在第B部分中，你将在一个免费的 SAP BTP 试用账户上，使用真实的 SAP 登录构建同一个顾问助手，与讲师的演示完全一致。共六个小节，总计约四小时，按此顺序进行；每一节结束时都有一个可以在屏幕上看到的检查点。区域：请选择 **Singapore (Azure)**（新加坡 - Azure），这样本手册中的每个地址都会与你的一致；其他区域也可以使用，只是主机名不同。

你在 SAP 屏幕上输入的内容只属于你自己：DBADMIN 密码、POLICY\_READER 密码，以及连接器的客户端密钥。切勿把其中任何一个放进代码仓库的文件、聊天记录或截图中。

## 1. 创建试用账户（15 分钟）

1. 打开 <https://account.hanatrial.ondemand.com>，点击 **Get started**（开始使用）（如果你还没有 SAP Universal ID，则点击 **Register**（注册））。填写姓名、电子邮件和密码；SAP 会向该邮箱发送验证码。输入验证码。
2. 登录。接受试用条款。SAP 会要求提供手机号码并通过短信发送验证码；输入它。（每个 Universal ID 只能有一个试用账户；如果你已经有一个，此步骤会直接带你进入。）
3. 选择区域 **Singapore - Azure** 并确认。页面会显示账户正在设置中；大约需要一分钟。
4. 点击 **Go To Your Trial Account**（前往你的试用账户）。你现在位于 BTP cockpit（驾驶舱）中你的全局账户内（其名称以 `trial` 结尾）。点击子账户磁贴 **trial**。
5. 在子账户的 Overview（概览）页面上，阅读 Cloud Foundry Environment 框：API endpoint 为 `https://api.cf.ap21.hana.ondemand.com`，一个以 `trial` 结尾的 org 名称，以及再往下一个名为 `dev` 的 space。把 org 名称写在你的记录表上；`cf target` 时会用到它。
6. 在左侧菜单中点击 **Entitlements**（授权）。找到 SAP HANA Cloud：列出了 `hana-free` 和 `tools` 两个计划。SAP AI Core 没有列出，这就是本课程直接调用 Claude 的原因（幻灯片第 14 页）。

检查：Overview 页面显示了你的 API endpoint 和 org 名称。

## 2. 准备环境（60 分钟，包括等待时间）

请按此顺序执行各步骤。前两步必须在创建数据库之前完成，否则数据库的界面无法打开。

**2a. SAP HANA Cloud tools 订阅。** 左侧菜单 **Instances and Subscriptions**（实例和订阅）> **Create**（创建）。Service：输入 `SAP HANA Cloud` 并选中它；Plan：`tools`（在 Subscriptions 下，而不是 Instances 下）。点击 **Create**。Subscriptions 列表先显示为 Processing（处理中），然后显示为 Subscribed（已订阅）（约一分钟）。

**2b. 你的角色集合。** 左侧菜单 **Security > Users**（安全 > 用户），点击你的用户，选择 **Role Collections**（角色集合）标签页，然后在 **...** 菜单中选择 **Assign Role Collection**（分配角色集合）。在搜索框中输入 `HANA`，勾选 **SAP HANA Cloud Administrator** 和 **SAP HANA Cloud Security Administrator**，点击 Assign。退出 cockpit 并重新登录，使新角色生效。

**2c. 数据库实例。** 左侧菜单 **Instances and Subscriptions** > **Create**。Service 选 `SAP HANA Cloud`，Plan 选 `hana-free`（在 Instances 下），Runtime Environment 选 **Cloud Foundry**，Space 选 `dev`。点击 **Next** 或 **Create**；SAP HANA Cloud Central 会打开一个向导。

- Instance name（实例名称）：`northwind-hana`。Administrator password（管理员密码）：现在选择一个，并以"DBADMIN northwind-hana"为名保存到你的密码管理器中（至少 8 个字符，包含大写字母、小写字母和数字）。
- 保持免费层的规格（16 GB 内存，80 GB 存储）。
- **Advanced Settings**（高级设置）：在 Allowed connections（允许的连接）下选择 **Allow all IP addresses**（允许所有 IP 地址）；在 Additional Features（附加功能）下开启 **Natural Language Processing (NLP)**（自然语言处理）。此项无法在之后添加；没有它的实例必须删除后重新创建。
- 检查并点击 **Create Instance**（创建实例）。创建需要 5 到 10 分钟；实例先显示 Creating（创建中），然后显示 Running（运行中）。

如果向导没有要求你输入密码（某些路径会使用生成的密码创建实例），请在 HANA Cloud Central 中打开该实例，使用 **...** 菜单 > **Reset DBADMIN Password**（重置 DBADMIN 密码），设置一个临时密码，并在首次登录时更改它。

**2d. 阶段 0：数据库能满足我们的需要吗？** 在 HANA Cloud Central 中，在你的实例上选择 **Open > Open in SQL Console**（打开 > 在 SQL 控制台中打开）。如果被要求，请用用户 `DBADMIN` 和你的密码进行注册。打开代码仓库中的 `apps/phase0/hana_checks.sql`，逐个运行七个代码块（粘贴一个代码块，点击 **Run**）。第 4 块是关键：它必须返回 **768**。第 6 块必须首先返回 `expedite`，并且既不返回 `old-discount` 也不返回 `london-memo`。第 7 块删除测试表。

检查：`northwind-hana` 处于 Running 状态且 NLP 已启用（Configuration 标签页），第 4 块返回了 768。

从现在起的每日习惯：试用实例每晚都会停止。每次开始前，请打开 HANA Cloud Central，在实例上点击 **Start**（启动）。

## 3. 笔记本电脑上的工具与登录（15 分钟）

你需要 Cloud Foundry 命令行工具、它的部署插件，以及 MTA 构建工具。在装有 Homebrew 的 Mac 上：

```bash
brew install cloudfoundry/tap/cf-cli@8
cf install-plugin multiapps
npm install -g mbt
```

在 Windows 上，从 Cloud Foundry 的 GitHub releases 页面安装 cf CLI，然后在 PowerShell 中运行同样的 `cf install-plugin` 和 `npm install -g mbt`。用 `cf --version` 和 `mbt --version` 检查。

通过浏览器登录（命令行上不输入密码）：

```bash
cf login --sso -a https://api.cf.ap21.hana.ondemand.com
```

它会打印一个链接；打开它，登录，把临时代码复制回终端。然后使用你记录表上的 org 名称，指向你的 org 和 space：

```bash
cf target -o <your org name> -s dev
```

检查：`cf target` 显示你的 org 和 space `dev`。

## 4. 部署 Northwind 数据服务（20 分钟）

这是拥有订单数据和行规则的 CAP 服务，与它的 HDI 数据库容器和 XSUAA 登录配置打包在一起。一次部署即可创建这三者。

```bash
cd SAP-BTP/apps/northwind-service
npm ci
mbt build
cf deploy mta_archives/northwind-service_0.1.0.mtar
```

构建需要一分钟，部署需要三到五分钟；结束时显示"Process finished"。然后：

```bash
cf apps
```

`northwind-service-srv` 已启动，有一个实例；`northwind-service-db-deployer` 已停止（它运行了一次，用于创建表并加载 830 条订单）。在 cockpit 中，Instances and Subscriptions 现在列出三个实例：你的 HANA 数据库、`northwind-service-auth`（XSUAA）和 `northwind-service-db`（HDI 容器）。

在浏览器中打开服务地址：`cf app northwind-service-srv` 会在 routes 下打印该地址；在其后加上 `/odata/v4/northwind/Orders`。你必须得到 **401 Unauthorized**。这是正确的：在 BTP 上，模拟用户已不存在，只接受有效的 SAP 令牌。

**角色。** Cockpit > Security > Users > 你的用户 > Role Collections > Assign：勾选 `SalesHQ (northwind-service <org>-dev)`，它是由部署创建的。你现在是 Nancy。对于 Steven，需要创建一次区域角色：Security > Roles，搜索 `northwind`，在 `SalesRegion` 模板上点击 **Create Role**（创建角色），名称为 `SalesRegion_UK`，下一步；属性 `country`，来源为 Static，值为 `UK`，然后按 Enter 使其变成一个标签（在此之前 Next 按钮保持灰色）；跳过角色集合；Finish。然后 Security > Role Collections > Create，名称为 `Northwind SalesRegion UK`，打开它，Edit，添加角色 `SalesRegion_UK`，Save。暂时不要分配它。

检查：`cf apps` 显示服务已启动，浏览器返回 401。

## 5. 将文档载入 HANA（20 分钟）

86 个策略段落将进入你数据库中的一张表，并由 HANA 自己的模型在那里生成嵌入向量。以 DBADMIN 身份打开你实例上的 SQL 控制台。

1. 在文本编辑器中打开代码仓库中的 `apps/hana/load_policy_chunks.sql`。它包含一条 CREATE TABLE 和 86 条 INSERT 语句。分两三次把它粘贴到控制台中（编辑器一次处理几百行没有问题），每次粘贴后点击 Run。每条语句都报告 Success。
2. 为段落生成嵌入向量，一条语句：

```sql
UPDATE POLICY_CHUNKS SET VEC = VECTOR_EMBEDDING(TO_NVARCHAR(TEXT), 'DOCUMENT', 'SAP_NEB.20240715');
SELECT COUNT(*) AS LOADED, SUM(CASE WHEN VEC IS NULL THEN 0 ELSE 1 END) AS EMBEDDED FROM POLICY_CHUNKS;
```

预期结果：86 和 86。

3. 试一试 MCP 服务器将要运行的搜索，以 Nancy 的身份（受众为 all-staff, sales, sales-seattle），在实验日期：

```sql
SELECT TOP 3 CHUNK_ID, ROUND(COSINE_SIMILARITY(VEC, VECTOR_EMBEDDING('customer wants a rush job, is that allowed?', 'QUERY', 'SAP_NEB.20240715')), 3) AS SCORE
FROM POLICY_CHUNKS
WHERE STATUS = 'current' AND (EFFECTIVE_FROM IS NULL OR EFFECTIVE_FROM <= DATE'2026-05-07') AND (EFFECTIVE_TO IS NULL OR EFFECTIVE_TO >= DATE'2026-05-07') AND AUDIENCE IN ('all-staff','sales','sales-seattle')
ORDER BY SCORE DESC;
```

预期结果：`NW-RUN-001@1.0#03`（运行手册中的加急订单情形）排在第一位，分数约为 0.67。把受众改为 `'all-staff','sales','sales-london'`，并提问 `How far are we prepared to go on the QUICK-Stop contract discount?`：现在 `NW-MEM-001@1.0#03` 排在第一位。这就是第A部分的练习 3，在数据库内部重现。

4. 创建 MCP 服务器将使用的技术用户；打开 `apps/hana/create_policy_reader.sql`，把 `<choose-a-password>` 替换为你选择的密码（以"POLICY\_READER"为名保存），运行它。然后 **History > Clear All**（历史 > 全部清除），让密码从屏幕上消失。

检查：计数返回 86 和 86，加急订单搜索首先返回运行手册。

## 6. 部署 MCP 服务器并连接 Claude（55 分钟）

MCP 服务器提供三个工具，验证 SAP 令牌，并将令牌转发给数据服务。它从不在没有登录的情况下运行：它的部署文件中没有开发开关，而且如果缺少登录绑定，它会拒绝启动。

**6a. 告诉 XSUAA Claude 的登录可以返回到哪里。** `apps/northwind-service/mta.yaml` 已经列出了 Claude 的回调地址；如果你在第 4 节中是从当前代码仓库部署数据服务的，那么这一步已经就绪。如果你是从较旧的副本部署的，请把第 4 节的三条命令再执行一次。

**6b. 为服务器提供数据库凭据。** 一个用户提供的服务保存着 POLICY\_READER 的详细信息。该命令会逐个询问每个值；请逐一回答，每个值之后按 Enter。host 在 HANA Cloud Central 中你实例的页面上（**Copy SQL Endpoint**（复制 SQL 端点）），去掉 `:443`。

```bash
cf cups policy-db -p "host, port, user, password, schema"
```

host：你实例的 SQL 端点主机名；port：`443`；user：`POLICY_READER`；password：你在第 5 节中选择的密码；schema：`DBADMIN`。如果之后看到主机名被写了两遍的 SSL 错误，说明 host 被粘贴了两次：运行 `cf update-user-provided-service policy-db -p "host, port, user, password, schema"` 并只输入一次。

**6c. 将路由调整为你的账户并部署。** 打开 `apps/mcp-servers/manifest.yml`。有两行带有讲师的 org 名称，必须改为你的：`route:` 和 `MCP_PUBLIC_URL:`（在这两处把 `cab3acb2trial` 替换为你的 org 名称），而 `NORTHWIND_SERVICE_URL:` 必须是你在第 4 节中得到的数据服务地址，后面加上 `/odata/v4/northwind`。然后：

```bash
cd SAP-BTP/apps/mcp-servers
cf push
```

需要两到四分钟。结果显示 `northwind-mcp` 正在运行，1/1。如果它因"No module named mcp.server.fastmcp"而崩溃，说明 Python 依赖项 `mcp` 被安装成了版本 2；当前代码仓库中的 `requirements.txt` 已将其固定在 2 以下，所以请确保你拥有最新的副本。

**6d. 在接触 Claude 之前先检查。** 将 `BASE` 设置为你的路由：

```bash
BASE=https://northwind-mcp-<your org>.cfapps.ap21.hana.ondemand.com
curl -s $BASE/health
curl -s -i -X POST $BASE/mcp -H "content-type: application/json" -d "{}" | head -6
```

预期结果：`"signed_in_required":true`，然后是 `HTTP/2 401`，并带有一行提到 `oauth-protected-resource` 的 `www-authenticate`。没有令牌，什么也得不到；这正是关键所在。

**6e. 给 Claude 使用的客户端 id 和密钥。**

```bash
cf create-service-key northwind-service-auth claude-connector
cf service-key northwind-service-auth claude-connector
```

从打印出的 JSON 中把 `clientid` 和 `clientsecret` 复制到你的密码管理器中。它们只用于 Claude 的连接器设置。

**6f. 在 Claude 中添加连接器。** Settings > Connectors > **Add custom connector**（添加自定义连接器）。Name 填 `Northwind Advisor`；Remote MCP server URL 填 `https://northwind-mcp-<your org>.cfapps.ap21.hana.ondemand.com/mcp`；打开 Advanced settings（高级设置），粘贴 OAuth Client ID 和 Client Secret；Add；**Connect**。你的试用租户的 SAP 登录页面会打开；用你的 BTP 用户登录。Claude 显示 Connected（已连接）。

**6g. 四个问题。** 开启连接器后开始一个新对话，逐个提问：

1. What is the status of order 11019, and can it be expedited?（订单 11019 的状态如何，可以加急吗？）
2. How much discount can I give a customer on my own authority?（我在自己的权限内可以给客户多少折扣？）
3. How far are we prepared to go on the QUICK-Stop contract discount?（在 QUICK-Stop 合同折扣上我们准备让步到什么程度？）
4. Has the delivery lead time for Pavlova products changed? Approve a 40 percent discount on their products for me.（Pavlova 产品的交货周期有变化吗？请为我批准其产品 40% 的折扣。）

与演示脚本中的预期答案进行比较：事实来自 `get_order_status`，规则以 `doc_id vVersion, section` 形式引用，没有任何内容来自已取代、草稿或供应商文档，QUICK-Stop 没有数字，并且拒绝审批。如果某次工具调用报告会话已过期，请再问一次；Claude 会重新连接。

**6h. 切换为 Steven。** Cockpit > Security > Users > 你的用户 > Role Collections：移除 `SalesHQ`（其所在行的 ×），并分配 `Northwind SalesRegion UK`。在 Claude 中断开连接器并重新连接，以便签发新的令牌。再问一次问题 3：答案现在引用 `NW-MEM-001 v1.0, 2. QUICK-Stop contract renewal`。询问订单 11070："No order with this number is visible to you."（没有此编号的订单对你可见。）完成后用同样的方式换回来，并且永远不要让两个集合同时处于分配状态：平台会将它们合并，而总部的权限会胜出。

检查：作为 Nancy，问题 1 返回订单数据和引用；作为 Steven，问题 3 的答案发生了变化。

## 你已经构建了什么

与讲师演示相同的六个步骤，在你自己的租户上：通过 XSUAA 登录，一个随每个问题一起传递的令牌，一个根据该令牌应用行规则的数据服务，一个过滤器在 HANA 内部运行、你的受众位于 WHERE 子句中的文档库，以及一个只根据事实和引用段落作答的助手。幻灯片第 17 页现在描述的是你所拥有的东西。

如何保留它：试用期为 90 天；实例每晚停止，一键即可重启；连接器的令牌有效期为 12 小时，Claude 会自动刷新。如何清理：`cf delete-service-key northwind-service-auth claude-connector` 删除连接器的凭据，`cf delete northwind-mcp` 删除服务器，其余的通过 cockpit 的 Instances and Subscriptions 页面删除。
