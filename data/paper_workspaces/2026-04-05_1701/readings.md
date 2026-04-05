# 论文阅读摘要

## 2602.08412 — From Assistant to Double Agent: Formalizing and Benchmarking Attacks on OpenClaw for Personalized Local AI Agent

- 链接: http://arxiv.org/abs/2602.08412v2

### 核心问题
现有代理安全研究和评估框架主要关注合成或任务中心设置，无法准确捕捉个性化代理（如OpenClaw）在真实世界部署中的攻击面和风险传播机制，这些代理引入严重安全风险。

### 关键方法
提出Personalized Agent Security Bench (PASB)，端到端安全评估框架，融入个性化使用场景、真实工具链和长时程交互，支持黑盒端到端评估。以OpenClaw为案例，系统评估多个个性化场景、工具能力和攻击类型。

### 创新点
PASB框架针对真实世界个性化代理，基于现有攻击范式扩展个性化场景、真实工具链和长时程交互，实现OpenClaw不同执行阶段的安全评估。

### 局限性
摘要未涉及

### 贡献
揭示OpenClaw在用户提示处理、工具使用和内存检索等阶段的严重漏洞，强调个性化代理部署的安全风险；开源PASB框架代码。

---

## 2603.00902 — Clawdrain: Exploiting Tool-Calling Chains for Stealthy Token Exhaustion in OpenClaw Agents

- 链接: http://arxiv.org/abs/2603.00902v1

### 核心问题
现代生成代理如OpenClaw的开放性和社区技能生态快速增长，超过系统安全评估，导致token耗尽攻击风险。

### 关键方法
设计Clawdrain木马技能，通过注入SKILL.md指令和伴侣脚本诱导多轮‘分段验证协议’，返回PROGRESS/REPAIR/TERMINAL信号；在生产-like OpenClaw实例中使用真实API计费和Gemini 2.5 Pro模型部署测试，测量6-7x token放大（最高9x）。

### 创新点
利用工具调用链实现隐秘token耗尽；观察代理自主组合通用工具（如shell/Python）绕过协议，减少放大并改变攻击动态；识别SKILL.md提示膨胀、持久工具输出污染、cron/heartbeat频率放大、行为指令注入等生产向量。

### 局限性
攻击幅度和可观察性受工具组合、恢复行为和接口设计影响，代理可自主绕过协议步骤降低放大。

### 贡献
证明token-drain攻击在真实OpenClaw部署中可行，但受多种因素塑造；揭示架构启用的安全向量。

---

## 2603.10165 — OpenClaw-RL: Train Any Agent Simply by Talking

- 链接: http://arxiv.org/abs/2603.10165v1

### 核心问题
现有代理RL系统未将每个交互产生的下一个状态信号（如用户回复、工具输出、终端或GUI状态变化）作为实时在线学习来源。

### 关键方法
OpenClaw-RL框架：从下一个状态信号提取评估信号（PRM judge转为标量奖励）和指令信号（Hindsight-Guided On-Policy Distillation (OPD)，提取文本提示构建增强教师上下文，提供token-level directional advantage监督）；异步设计同时服务请求、判断交互和更新策略，无协调开销。

### 创新点
下一个状态信号通用性，所有交互（对话、终端、GUI、SWE、工具调用）统一训练同一策略；OPD提供比标量奖励更丰富的token-level监督；异步设计零开销并发。

### 局限性
摘要未涉及

### 贡献
代理通过使用即改进，恢复用户反馈信号；支持跨终端、GUI、SWE、工具调用等可扩展RL，并展示过程奖励效用；开源代码。

---

## 2603.10387 — Don't Let the Claw Grip Your Hand: A Security Analysis and Defense Framework for OpenClaw

- 链接: http://arxiv.org/abs/2603.10387v1

### 核心问题
由大语言模型驱动的代码代理可代表用户执行shell命令，引入严重安全漏洞。OpenClaw作为开源本地AI代理框架，缺乏内置安全约束，主要依赖后端LLM安全能力，易受sandbox逃逸攻击，平均防御率仅17%。

### 关键方法
两阶段安全分析：第一阶段系统评估OpenClaw对恶意指令的原生弹性，测试47个对抗场景跨越MITRE ATLAS和ATT&CK的六大攻击类别；第二阶段提出并实现Human-in-the-Loop (HITL)防御层，使用双模式测试框架评估干预效果。

### 创新点
新型HITL防御层，显著强化系统，拦截多达8个原生完全绕过的严重攻击，结合原生能力后整体防御率提升至19%至92%。

### 局限性
摘要未涉及

### 贡献
暴露当前代码代理的固有安全局限，证明人-代理协作防御策略的有效性，并提供针对OpenClaw的安全分析与防御框架。

---

## 2603.11455 — Examining Users' Behavioural Intention to Use OpenClaw Through the Cognition--Affect--Conation Framework

- 链接: http://arxiv.org/abs/2603.11455v2

### 核心问题
考察用户使用OpenClaw的行为意图，通过Cognition--Affect--Conation (CAC)框架分析认知感知（个性化感知、智能感知、相对优势）如何影响情感响应及行为意图，启用因素与抑制因素（隐私担忧、算法不透明、感知风险）的作用。

### 关键方法
对436名OpenClaw用户进行调查，使用结构方程模型分析数据。

### 创新点
摘要未涉及

### 局限性
摘要未涉及

### 贡献
揭示正面感知增强态度并增加行为意图，负面感知增加不信任并降低使用意图；为自主AI代理采用提供心理机制洞见。

---

## 2603.11619 — Taming OpenClaw: Security Analysis and Mitigation of Autonomous LLM Agent Threats

- 链接: http://arxiv.org/abs/2603.11619v1

### 核心问题
自主LLM代理如OpenClaw的紧耦合即时消息交互和高权限执行扩大攻击面，导致初始化、输入、推理、决策、执行生命周期中的复合威胁，包括间接提示注入、技能供应链污染、内存中毒和意图漂移。

### 关键方法
引入五层生命周期导向安全框架（初始化、输入、推理、决策、执行），系统分析OpenClaw威胁，通过详细案例研究展示威胁严重性，并考察各阶段防御策略如插件审查、上下文过滤、内存验证、意图验证和能力执行。

### 创新点
提出五层生命周期安全框架，系统考察跨生命周期复合威胁，揭示现有点防御在跨时间多阶段风险上的弱点，强调自主LLM代理需整体安全架构。

### 局限性
现有点防御机制无法有效应对跨时间和多阶段系统风险。

### 贡献
提供OpenClaw全面安全威胁分析、五层框架、案例研究、现有防御局限揭示及各阶段代表性防御策略考察，推动整体安全架构发展。

---

## 2603.12644 — Uncovering Security Threats and Architecting Defenses in Autonomous Agents: A Case Study of OpenClaw

- 链接: http://arxiv.org/abs/2603.12644v1

### 核心问题
大型语言模型演变为自主工具调用代理，如OpenClaw框架赋予操作系统级权限，导致前所未有安全挑战，传统内容过滤失效。主要威胁包括提示注入驱动RCE、顺序工具攻击链、上下文失忆和供应链污染。

### 关键方法
系统调查OpenClaw生态威胁景观；提出三层风险分类法（AI认知、软件执行、信息系统维度）；引入全生命周期代理安全架构FASA，倡导零信任代理执行、动态意图验证和跨层推理-行动相关性；开发Project ClawGuard工程项目实现FASA。

### 创新点
提出新型三层风险分类法；设计FASA理论防御蓝图；启动Project ClawGuard项目实现FASA范式。

### 局限性
摘要未涉及

### 贡献
全面分析OpenClaw安全威胁并突出关键漏洞；提出风险分类法和FASA架构，推动代理从高风险实验工具向可信系统转型；公开代码和数据集。

---

## 2603.13151 — Defensible Design for OpenClaw: Securing Autonomous Tool-Invoking Agents

- 链接: http://arxiv.org/abs/2603.13151v1

### 核心问题
OpenClaw-like代理提供生产力益处，但默认不安全，因结合不受信任输入、自主行动、可扩展性和特权系统访问于单一执行循环；此类代理在真实操作系统环境中交互接口、操作文件、调用工具、安装扩展，具有架构漏洞，应视为软件工程问题。

### 关键方法
提出defensible design蓝图，包括风险分类、安全工程原则和实用研究议程，以制度化代理构建中的安全。

### 创新点
将代理安全从产品特定问题转向软件工程问题，提供风险分类、安全工程原则和研究议程，推动系统性防御工程。

### 局限性
摘要未涉及

### 贡献
风险分类、安全工程原则、实用研究议程；转变社区从孤立漏洞修补向系统性防御工程和稳健部署实践。

---

## 2603.18762 — ClawTrap: A MITM-Based Red-Teaming Framework for Real-World OpenClaw Security Evaluation

- 链接: http://arxiv.org/abs/2603.18762v1

### 核心问题
自主网络代理如OpenClaw快速进入高影响真实工作流，但实时网络威胁下的安全鲁棒性评估不足。现有的基准主要聚焦静态沙箱设置和内容级提示攻击，缺少网络层安全测试的实际差距。

### 关键方法
ClawTrap，一个基于MITM的红队框架，支持多样可定制攻击形式，包括Static HTML Replacement、Iframe Popup Injection和Dynamic Content Modification，提供规则驱动的拦截、转换和审计的可重现管道。

### 创新点
提出MITM-based红队框架ClawTrap，用于真实世界OpenClaw安全评估，支持自定义攻击并为未来更丰富MITM攻击和系统性测试奠基；实证研究显示模型分层，弱模型易信任篡改观察产生不安全输出，强模型有更好异常归因和安全回退。

### 局限性
摘要未涉及

### 贡献
填补网络层安全测试空白，提供可重现框架和实证洞见，强调评估需纳入动态MITM条件而非仅静态沙箱协议。

---

## 2603.25522 — Automating Computational Chemistry Workflows via OpenClaw and Domain-Specific Skills

- 链接: http://arxiv.org/abs/2603.25522v1

### 核心问题
多步计算化学任务自动化仍具挑战性，因为推理、工作流规范、软件执行和高性能计算(HPC)执行往往紧密耦合。

### 关键方法
提出解耦的agent-skill设计，利用OpenClaw提供集中控制与监督；schema定义的规划技能将科学目标转化为可执行任务规范；领域技能封装特定计算化学过程；DPDispatcher管理异构HPC环境下的作业执行。

### 创新点
解耦agent-skill设计，结合OpenClaw实现计算化学自动化的可扩展与可维护方法。

### 局限性
摘要未涉及

### 贡献
在甲烷氧化分子动力学(MD)案例中，实现跨工具执行、运行时故障有界恢复及反应网络提取，展示多步计算化学自动化的可扩展可维护途径。

---
