<!-- translation of docs/faq.md, sha256 9014b36abf2b6d1e57c85e163f530c2b14450f44eaa327e0997a59b389ccb4c6 -->
<!-- en: frequently-asked-questions -->
# 常见问题

对实际会遇到的问题给出简短回答。每个问题都链接到完整讲解它的页面。

你需要哪一页？

- **本页**回答“它能不能、会不会、在哪里、出了事会怎样”。
- [`troubleshooting.md`](troubleshooting.md) 回答“它坏了”。
- [`user-guide.md`](user-guide.md) 说明每个界面和每个功能如何工作，是行为的权威描述。

用户指南以及从这里链接到的其它文档，除「故障排查」外，都在浏览器中打开且为英文；引用
其章节时使用原文标题。

如果你想找从全新安装到能用的最短路径，那就是[下面的五步答案](#im-installed-now-what-do-i-actually-press)。

<!-- en: contents -->
## 目录

- [安装与选择模型](#installing-and-choosing-a-model)
- [哪些数据会离开设备，哪些不会](#what-leaves-the-device-and-what-does-not)
- [流程与编辑器](#pipelines-and-the-editor)
- [触发器与后台工作](#triggers-and-background-work)
- [工具、MCP 与确认](#tools-mcp-and-confirmations)
- [外部自动化（Tasker、MacroDroid、adb）](#external-automation-tasker-macrodroid-adb)
- [运行上限与停止运行](#run-limits-and-stopping-a-run)
- [记忆](#memory)
- [已知限制](#known-limitations)

---

<!-- en: installing-and-choosing-a-model -->
## 安装与选择模型

<!-- en: what-do-i-need-to-run-this -->
### 运行它需要什么？

Android 14 或更新版本，以及约 2 GB 可用内存供模型使用。限制运行的是内存；没有可用
GPU 的手机照样能运行，只是更慢。完整清单见 [README § 环境要求](../README.md#requirements)。

<!-- en: do-i-have-to-download-a-model-at-all -->
### 到底需要下载模型吗？

要在设备端得到回答，是的——模型是一个存放在你手机上的文件。另一种做法是用你自己的
API 密钥连接云端服务商，无需下载。两者必须有一个，答案才会产生；全新安装时两者都没
有。见 [入门](user-guide.md#getting-started)。

<!-- en: which-model-should-i-start-with -->
### 该从哪个模型开始？

初始设置会替你选：每个场景都写明了它需要的模型，并只下载那一个。手动选择时，两个预
设是 **Gemma 4 E2B** 和 **Gemma 4 E4B**；存储或内存紧张就选 E2B。见
[入门](user-guide.md#getting-started)。

<!-- en: which-cloud-providers-are-supported -->
### 支持哪些云端服务商？

托管服务：OpenAI、Anthropic、Google Gemini、DeepSeek、OpenRouter 和 Groq，每个都用
你自己的密钥。自建服务器：**Ollama**，或任何兼容 OpenAI API 的服务器。这些全部由你
主动开启。它们位于**设置 → 模型 → 外部服务商**下，每个服务商页面上的**测试连接**会在
不发送提示词的情况下检查密钥和地址。

<!-- en: can-i-point-it-at-my-own-openai-compatible-endpoint -->
### 可以指向我自己的 OpenAI 兼容端点吗？

可以——添加一个**兼容 OpenAI 的服务器**，按服务器文档的写法填写地址，包括 `/v1`（vLLM、
LM Studio 和 llama.cpp 都在该路径提供 API）。密钥可选；不填就不会发送 `Authorization`
头。等**测试连接**取回服务器的模型列表后再选模型，或直接输入模型 id。

<!-- en: my-ollama-server-is-not-on-my-home-network-will-it-work -->
### 我的 Ollama 服务器不在家庭网络里，能连上吗？

走 `https` 可以——**设置 → 模型 → 外部服务商**下的 Ollama 一行会带上它的 base URL。
走明文 `http` 会被拒绝，除非地址位于私有网络，或者你批准了那个特定来源——因为应用不会
在开放的互联网上发送未加密流量。

<!-- en: what-is-custom-model-url-and-can-it-use-authentication -->
### “自定义模型 URL”是什么，能用身份验证吗？

它会把一个 `.litertlm` **文件**从直链下载到手机上——它不是让应用指向留在服务器上的远
端模型的方式。它可以做身份验证，但只支持 bearer token，且只在 `huggingface.co` 上：
在模型界面填写 Hugging Face 访问令牌字段后，从该主机发起的下载会把它作为
`Authorization` 头带上；指向其他任何主机的链接都不会带。没有 OAuth 流程，也没有其他
认证方式。见 [下载模型](user-guide.md#2-download-a-model)。

<!-- en: does-the-app-check-a-downloaded-model -->
### 应用会校验下载的模型吗？

当 Hugging Face 在下载响应里给出文件的 SHA-256 时——对于它存放在 LFS 中的大文件（模
型文件通常如此）会给出——会校验：不匹配的文件会被删除，而不是安装。指向其他主机的链
接不给哈希，因此其文件未经校验就会被安装。模型界面会把每个模型标为**已校验**或
**未校验**。校验只能证明文件就是 Hugging Face 发布的那一个，不能证明发布者可信。见
[下载模型](user-guide.md#2-download-a-model)。

<!-- en: can-i-browse-and-install-models-from-hugging-face -->
### 能浏览并安装 Hugging Face 上的模型吗？

可以，包括受访问限制的仓库——前提是你已保存访问令牌。见 [从 Hugging Face 发现模型](user-guide.md#discovering-models-from-hugging-face)。

<!-- en: what-is-the-foss-build-and-how-does-it-differ -->
### FOSS 版本是什么，有何不同？

即 F-Droid 分发的那个版本：没有崩溃报告，没有分析统计，也没有为它们准备的同意开关。
其他一切——本地模型、云端服务商、MCP、触发器——都相同。见
[README § 安装](../README.md#install)。

---

<!-- en: what-leaves-the-device-and-what-does-not -->
## 哪些数据会离开设备，哪些不会

<!-- en: does-a-normal-conversation-leave-my-phone -->
### 普通对话会离开我的手机吗？

不会。设备端推理意味着消息、回答，以及其间的运行都留在本地。没有账号，没有登录，也
没有维护者运营的服务器。见
[PRIVACY § 哪些数据永不离开你的设备](../PRIVACY.md#4-what-never-leaves-your-device)。

<!-- en: so-what-can-go-out -->
### 那什么*可能*会外发？

六条路径。其中五条是你主动开启的：使用你自己密钥的**云端模型**——在云端节点里、通过
`delegate_task` 工具，或作为记忆的**嵌入模型**；你添加的**MCP 服务器**；**模型下载**；
对允许列表中主机的 **`http_request` 工具调用**；以及你同意过的**崩溃报告**。

第六条从首次启动起就开着，也是最该了解的一条：内置的 **`search_tool`** 会在 Wikipedia
上查主题，而应用默认启动的流程在判断问题属于事实类时会调用它。搜索词由模型写出，因此
可能带上你对话中的措辞；该工具是只读的，所以不会先询问。可在**工具**界面用它的开关关
掉，或使用**禁止本地模型访问网络**，后者会连同云端路径一起不提供它。

除此之外没有别的出路——除了你自己导出的文件，比如聊天、日志、运行轨迹或备份，它们会
去你发送的地方。关于工具路径上的分层限制，见
[PRIVACY § 哪些数据可能离开设备](../PRIVACY.md#3-what-can-leave-your-device)，以及
[SECURITY § 出站 HTTP 与数据外泄链路](../SECURITY.md#outbound-http-and-the-exfiltration-chain)。

<!-- en: where-are-my-api-keys-stored -->
### 我的 API 密钥存在哪里？

位于一个加密存储中，由不可导出的 Android Keystore 密钥封存——绝不在明文设置里，绝不
在导出的流程里，绝不在日志里，备份中也只有当你勾选**包含 API 密钥与登录信息**时才会
包含。MCP 凭据和 Hugging Face token 同理。见
[SECURITY § 云端服务商的 API 密钥](../SECURITY.md#api-keys-for-cloud-providers)。

<!-- en: can-i-back-up-everything -->
### 能备份全部数据吗？

可以，备份成一个用你自选密码锁定的文件：设置 → 隐私 → **备份与恢复** → **备份…**。
它包含聊天、记忆、流程、运行历史、触发器、设置和文件——不含模型文件，也不含你的 API
密钥，除非你勾选那个框（写进服务器地址的 token 会随地址一起走）。文件只会去你保存它的
地方。**从文件恢复…**会把它放回去——在本机或新手机上——并替换应用在那里的数据；模型文件
会保留，手机自己的密钥也会保留，但备份携带的密钥除外。见
[备份与恢复](user-guide.md#backup--restore)。

<!-- en: is-there-telemetry -->
### 有遥测吗？

使用统计确实存在，但它们留在设备上，从不传输——如果有任何网络依赖触达那段代码，构建
时的检查会让构建失败。崩溃报告是另一回事，默认关闭，仅在 `full` 构建中提供，且在收
集任何东西之前会询问。记忆搜索背后的设备端库（MediaPipe）带有自己的使用情况报告器；
发布构建会移除它，只有从源码构建的调试版本会保留它。见
[SECURITY § 收集了什么](../SECURITY.md#what-is-collected-crash-reporting)。

<!-- en: is-my-chat-history-encrypted-on-the-phone -->
### 手机上的聊天记录是加密的吗？

是——聊天、长期记忆和运行轨迹存放在一个经 SQLCipher 加密的数据库中。见
[SECURITY § 本地数据库](../SECURITY.md#local-database-at-rest-encryption)。

---

<!-- en: pipelines-and-the-editor -->
## 流程与编辑器

<!-- en: why-is-everything-a-pipeline-instead-of-just-a-chat-box -->
### 为什么一切都是流程，而不是一个聊天框？

因为这个应用的重点就是你能看见并改变消息和回答之间发生的事——用哪个模型、哪些工具、
什么会被确认。首次启动时就有现成流程在生效，所以你可以完全忽略这一切，直到你想改点
什么。见 [流程库](user-guide.md#pipeline-library)。

<!-- en: im-installed-now-what-do-i-actually-press -->
### 装好了，现在实际该点哪里？

五步，从头到尾：

1. **在初始设置里选一个场景**——它会安装一个可用的流程，*同时*下载该场景需要的模型。
2. **模型到位后，聊天 → 输入一条消息。** 整个循环就是这样；下面的一切都是可选的。
   （选了*从零开始*？先打开**模型**，下载一个预设并点**启用**——[做法](user-guide.md#2-download-a-model)。）
3. **流程 → 打开标记为“默认”的那个**，看看产出那条回答的图
   （[做法](user-guide.md#visual-editor)）。
4. **工具**用来打开某个工具，或添加一个 MCP 服务器
   （[做法](user-guide.md#adding-an-mcp-server)）。
5. **更多 → 自动化 → 触发器**，让流程自己运行
   （[做法](user-guide.md#creating-or-editing-a-trigger)）。

<!-- en: settings-has-a-run-limits--structured-output-section--where-are-the-actual-pipelines -->
### 设置里有“运行限制与结构化输出”分区——实际的流程在哪里？

在**流程**下的流程库里。那个设置分类装着适用于运行的上限和护栏，而不是流程本身；它过去
的命名让人以为不是这样。见 [流程库](user-guide.md#pipeline-library)。

<!-- en: what-does-this-node-actually-do -->
### 这个节点到底做什么？

每种节点类型都在[流程手册](cookbook.md)里有说明，包括它如何处理输入、哪些配置字段会
改变运行、哪些只是存着不用，以及五份可导入的现成配方。

<!-- en: can-i-edit-a-pipeline-on-a-computer -->
### 能在电脑上编辑流程吗？

可以——有一个独立的浏览器编辑器，读写同一份 JSON，所以你可以用真键盘搭建，再导入文
件。见 [浏览器流程编辑器](user-guide.md#browser-pipeline-editor)。

<!-- en: can-i-share-a-pipeline-with-someone-else -->
### 能把流程分享给别人吗？

你可以导出一个流程（或把整个组合导出成文件包），对方可以导入。要注意文件格式在 1.0
之前**不构成兼容承诺**：导入时会按名称告诉你哪些读不了，但这不等于没丢东西。保留原
始文件。见
[分享流程文件](user-guide.md#sharing-pipeline-files-what-compatibility-you-can-count-on)。

---

<!-- en: triggers-and-background-work -->
## 触发器与后台工作

<!-- en: where-are-the-triggers -->
### 触发器在哪里？

**更多 → 自动化 → 触发器**——第一个分区的第一行。见
[触发器](user-guide.md#triggers) 和 [“更多”标签页](user-guide.md#more-tab)。

<!-- en: does-the-agent-run-when-the-app-is-closed -->
### 应用关闭时智能体还会运行吗？

会——触发器、计划任务和已经在进行的运行会在应用离开后继续，欠你的确认会以通知形式送
达。这完全取决于下面的电池设置，而它默认不开。见
[运行中关闭应用会发生什么](user-guide.md#what-happens-when-you-close-the-app-during-a-run)。

<!-- en: why-does-nothing-happen-in-the-background-on-my-phone -->
### 为什么在我的手机上后台什么都不发生？

几乎总是电池设置，而这不是应用能自己授予的。
[电池设置决定这些功能是否会发生](user-guide.md#battery-settings-decide-whether-any-of-this-happens)
是权威解释；[一离开应用后台运行就中断](troubleshooting.md#a-background-run-dies-the-moment-i-leave-the-app)
和[触发器没有触发](troubleshooting.md#a-trigger-didnt-fire)是两个具体故障。

<!-- en: how-soon-after-the-condition-does-a-trigger-actually-fire -->
### 条件满足后，触发器多久才真正触发？

不是立即。每个非充电触发器都跑在可延迟的后台计划上，所以晚一点是正常的，而晚到触发
器自身节奏的许多倍就不正常。见
[触发器多久后触发](user-guide.md#how-soon-a-trigger-fires)。

<!-- en: does-the-model-stay-in-memory-between-runs -->
### 两次运行之间模型会留在内存里吗？

不会——它空闲五分钟后会被卸载，系统要回收内存时也会卸载（除非正在生成，生成从不因此
被打断）。所以没有运行任务时，它既不占内存也不耗电。

<!-- en: how-do-i-get-the-background-journal-off-my-phone -->
### 怎么把后台日志从手机里取出来？

触发器顶栏有两个操作：把评估日志**分享**为 JSON 文件，或**保存**到你选的文件夹。它覆盖
所有触发器，而不只是你正在看的那个，因为通常有用的问题是“中间断了”而不是某一行。设置
→ 后台与触发器 → 外部自动化里的请求日志对入站请求提供同样的一对操作。

把任意一个附在关于后台可靠性的 bug 报告里：它显示了应用在你没看着时做了什么。文件里
是日志行：失败运行的错误消息，但不含运行收到的消息，也不含它产出的回答。两个操作都
不触网。见
[查看触发器最近做了什么](user-guide.md#checking-what-a-trigger-has-been-doing)。

---

<!-- en: tools-mcp-and-confirmations -->
## 工具、MCP 与确认

<!-- en: what-address-does-my-mcp-server-need -->
### 我的 MCP 服务器需要什么地址？

你服务器启动时打印的端点，含路径——表单自带的示例是
`https://mcp.example.com/mcp`。没有单独的端口字段：非默认端口要写进 URL，字段下方的
传输方式选择器必须与端点匹配：新服务器选 **Streamable HTTP**，只支持旧传输方式的服
务器选 **SSE**。见 [添加 MCP 服务器](user-guide.md#adding-an-mcp-server)。

<!-- en: which-authentication-methods-do-mcp-servers-support -->
### MCP 服务器支持哪些身份验证方式？

Bearer token、HTTP Basic 或自定义 API-key 头——你选哪种，就按服务器加密存储哪种。
**不支持 OAuth。** 见 [已知限制](#known-limitations)。

<!-- en: is-there-a-test-connection-button -->
### 有“测试连接”按钮吗？

有。服务器表单上的**测试连接**会用你填的值连接、列出服务器的工具然后断开，这一切都发
生在保存之前。它回答工具数量，或说明哪里出了问题。见
[添加 MCP 服务器](user-guide.md#adding-an-mcp-server)。

<!-- en: my-server-publishes-16-tools-but-the-app-shows-13 -->
### 我的服务器发布了 16 个工具，但应用只显示 13 个。

那是服务器在决定，不是应用——见
[MCP 服务器已连接，但预期的工具不在](troubleshooting.md#an-mcp-server-is-connected-but-a-tool-i-expect-isnt-there)，
它解释了原因以及缺少的工具有什么影响。

<!-- en: why-does-it-ask-me-before-every-tool-call -->
### 为什么每次调用工具前都要问我？

因为该工具被归为敏感或破坏性，而这道关卡在工具执行处强制执行，而不是向模型建议。有
两个设置能一次性放宽或收紧所有工具——**批准工具调用**可以设为对*每一次*调用都询问，
**禁止破坏性工具**会直接拒绝破坏性工具，而不是提供批准——两者都在
**设置 → 工具与工作区**中。

要关掉**某一个**工具的提示，从**工具**界面打开它，把**风险等级**设为*只读*。这对 MCP 工
具和在设备上发现的工具有效，后者一开始就是*敏感*，因为应用分不清它们做什么；内置工具的
等级则由代码解析得出，会自己声明。见
[风险等级与人工介入](user-guide.md#risk-levels-and-human-in-the-loop)。

<!-- en: can-other-apps-on-my-phone-expose-tools-to-the-agent -->
### 手机上其他应用能向智能体提供工具吗？

Android 允许任何应用发布 AppFunctions，但运行另一个应用的 AppFunctions 需要一个权限
（`EXECUTE_APP_FUNCTIONS`），而 Android 16 只把它交给特权系统应用，你自己安装的应用
不属于此类。所以你能得到的，就是内置目录加上你通过 MCP 接入的东西。见
[内置工具](user-guide.md#built-in-tools)。

---

<!-- en: external-automation-tasker-macrodroid-adb -->
## 外部自动化（Tasker、MacroDroid、adb）

<!-- en: can-tasker-start-a-run -->
### Tasker 能启动运行吗？

能——这是一份受支持的约定，Tasker、MacroDroid 和 `adb` 都有可用的示例。见
[external-automation.md](external-automation.md)。

<!-- en: does-it-work-out-of-the-box -->
### 开箱就能用吗？

不能，而且是刻意如此。入口**默认关闭**，即使打开，在你恰好绑定一个允许外部应用运行
的流程之前，它也保持无效。指名其他任何东西的请求都会被拒绝，而不会被重定向。见
[开启它](external-automation.md#switching-it-on)。

<!-- en: how-do-i-get-the-result-back -->
### 怎么拿回结果？

请求可以指定一个回调广播，它携带运行的状态——但从不携带输出：让流程把结果放到你能读
取的地方。状态和拒绝原因都有枚举。见
[接收回调](external-automation.md#receiving-the-callback)。

<!-- en: does-calling-from-outside-skip-the-confirmations -->
### 从外部调用会跳过确认吗？

不会。外部调用不是一种批准：人工介入的确认和破坏性工具拦截与应用自己的后台运行完全
一样地生效，批准会以通知形式到达。见
[安全模型](external-automation.md#the-safety-model-in-one-paragraph)。

---

<!-- en: run-limits-and-stopping-a-run -->
## 运行上限与停止运行

<!-- en: what-stops-a-runaway-pipeline -->
### 什么能拦住失控的流程？

四个数字和一个重复检测器。每次运行的步数和 token 数，各自对不是你发起的运行有单独的
额度；另外还有一个监视器，盯住运行是否用同样的输入重复同一步骤，它会先提醒运行，然
后结束它。见 [运行上限](user-guide.md#run-limits) 和
[运行陷入循环时](user-guide.md#when-a-run-goes-in-circles)。

<!-- en: a-run-hit-its-limit-is-the-work-lost -->
### 运行碰到上限了，工作会白费吗？

不会——它在等你。达到上限会让运行暂停，而不是结束，聊天里会给出**继续（+N）**或
**停止运行**。继续会让它再获得同一额度的一份，并从停下的地方接着跑，因此没有任何东西被
重跑。暂停会被记录下来，所以它能经受应用关闭，你回来时它还在。见
[运行达到上限时](user-guide.md#when-a-run-reaches-a-limit)。

<!-- en: does-continuing-past-a-limit-turn-the-limit-off -->
### 超过上限后继续，会把上限关掉吗？

不会。它买到的只是**多一份**——同样的额度再来一遍，也就是按钮上的那个数字——用完时运
行会再次询问。

<!-- en: can-i-cap-what-a-run-costs-me -->
### 能限制一次运行花我多少钱吗？

不能。应用用你自己的 API 密钥运行，从来看不到你的账单，也不会给你一个只能靠猜的数
字。token 上限是最接近的控制手段。

<!-- en: how-do-i-stop-a-run-that-is-already-going -->
### 怎么停止一个已经在进行的运行？

点聊天输入框里的**停止生成**。它会结束运行，而不只是屏幕上的显示：工作停下，对话里会加
一句说运行在回答前被停止了。仍在另一个运行后面排队的消息也会以同样方式取消。切换到另一
个聊天**不会**停止任何东西——运行会继续，这正是你能回来找它的原因。

还有两个控件能结束运行：上限暂停时的**停止运行**，以及——对于智能体为自己安排的一串
任务——**更多 → 任务 → 停止全部计划任务**，它也会取消正在执行的那个。

<!-- en: my-run-stopped-by-itself-which-limit-was-it -->
### 我的运行自己停了，是哪个上限？

消息里会写明，而且不是每次中途停止都是上限——存在三种不同的结局，对应不同的处理。见
[智能体在运行中途停止](troubleshooting.md#the-agent-stopped-mid-run)。

---

<!-- en: memory -->
## 记忆

<!-- en: what-does-the-agent-remember-and-when -->
### 智能体记得什么，什么时候记？

它从对话中提取的持久事实——偏好、事件、关系——在节点被设为读取记忆时按语义检索。闲聊
和它已经知道的事实会被跳过；事实发生变化时，它会更新该条目，并把旧文本保留在该条目
的历史中。见 [智能体记得什么、何时记起](user-guide.md#what-the-agent-recalls-and-when)。

<!-- en: can-i-add-or-delete-a-memory-myself -->
### 我能自己添加或删除记忆吗？

能，两者都可以手动做——还有**压缩**可以把冗余条目合并到一起，它在删除前会先核实。见
[浏览长期记忆](user-guide.md#browsing-long-term-memory)。

<!-- en: does-memory-move-to-a-new-phone -->
### 记忆会迁移到新手机吗？

会，和其他一切一起，放在你恢复到那里的备份里：**设置 → 隐私 → 备份与恢复**。仅记忆本身
也可以通过导出和导入迁移，导出的是你手上的一个文件。见
[备份与恢复](user-guide.md#backup--restore) 和
[把记忆迁移到另一台设备（导出/导入）](user-guide.md#moving-memory-to-another-device-export--import)。

<!-- en: why-doesnt-a-memory-i-know-exists-come-back -->
### 我明明知道存在的记忆，为什么检索不出来？

原因有好几个，互不相同，是哪一个决定了怎么修。见
[记忆搜索找不到明显存在的条目](troubleshooting.md#memory-search-isnt-finding-an-obvious-entry)。

---

<!-- en: known-limitations -->
## 已知限制

应用今天不做的事。每一项都说明什么会改变它。

- **任何地方都不支持 OAuth。** MCP 服务器没有，模型下载也没有。现有的只有 Bearer、
  Basic 和 API-key 头。等出现第一份真实服务器的外部报告、且它确实无法用其他方式访
  问时再议。
- **内置工具的等级无法更改。** MCP 工具和在设备上发现的工具现在在详情页上有**风险等级**
  控件；写进应用里的工具没有，因为它的等级在任何你的设置被读取之前就已经从代码解析出
  来。如果某个内置工具的分类在真实流程中被证明是错的（而非理论上），再议。
- **每条消息只能带一张图片。** 附第二张会替换第一张，发生时应用会说明。拼图和多图对比
  都不提供。
- **MCP 客户端功能已搁置**——`roots`、`sampling` 和 `elicitation` 均未实现，这就是服务
  器向本应用发布的工具可能比它拥有的更少的原因。每一项都是带着自己风险模型的新界面，
  而不是快速添加。等出现第一份关于真实服务器缺少工具的外部报告时再议；`elicitation`
  会最先做，因为它是唯一能复用现有确认路径的一项。
- **其他应用提供的工具不会被接入。** 发布 AppFunctions 对任何应用开放；调用一个则需要
  Android 保留给特权系统应用的权限，而路线图上没有任何东西会为普通安装改变这一点。
- **记忆搜索只在英文下正常工作。** 设备端嵌入模型会把用俄语写成的不相关事实看作彼此
  的近似副本，因此一次记忆搜索每次运行只保留其中一条，把其余当作重复项丢弃。置顶事
  实绝不会以这种方式被丢弃。其他语言尚未测量。以 OpenAI 作为**嵌入模型**时，按其厂商的
  说法是多语言的——此处未测量——并会把你的记忆文本发送给 OpenAI。更换设备端模型意味
  着要发布一个多语言模型，这尚未决定。
- **流程文件在 1.0 之前不是兼容性承诺。** 版本戳是标记，不是承诺，也不存在导入时迁
  移。见 [README § 预发布说明](../README.md#pre-release-notice)。
- **可靠性数字来自一台设备和一个操作者。** 一个排程流程在无人打开的情况下运行了 7.14
  天，55 次触发全部完成，没有无法解释的漏触发。这是一次真实测量，不是外部验证。
- **没有休闲模式，以后也不会有。** 这个应用是为想看见并改变这套机制的人构建的。一个只
  回答问题的手机助手已经随系统提供，应用不打算与它竞争。见
  [README § 面向谁](../README.md#who-its-for)。
- **一位维护者，没有公司。** 响应时间由此而来。

---

<!-- en: see-also -->
## 相关阅读

- [`user-guide.md`](user-guide.md) — 每个界面和功能如何工作。
- [`cookbook.md`](cookbook.md) — 每种节点类型做什么，以及可导入的配方。
- [`troubleshooting.md`](troubleshooting.md) — 出问题时怎么办。
- [`external-automation.md`](external-automation.md) — 其他应用调用的约定。
- [`../PRIVACY.md`](../PRIVACY.md) — 存储了什么，什么可能离开。
- [`../SECURITY.md`](../SECURITY.md) — 威胁模型与漏洞报告。
