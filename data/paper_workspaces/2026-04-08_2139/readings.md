# 论文阅读摘要

## 1807.10875 — TensorFuzz: Debugging Neural Networks with Coverage-Guided Fuzzing

- 链接: http://arxiv.org/abs/1807.10875v1

### 核心问题
机器学习模型尤其是神经网络难以解释和调试，特别是发现仅在稀有输入上发生的错误。

### 关键方法
引入覆盖引导模糊测试（CGF），通过随机变异输入并使用快速近似最近邻算法提供的覆盖度量引导测试，以满足用户指定约束。应用于发现训练神经网络的数值错误、神经网络与量化版本的分歧，以及字符级语言模型的不良行为。

### 创新点
为神经网络开发CGF方法，并使用快速近似最近邻算法实现覆盖度量。

### 局限性
摘要未涉及

### 贡献
实现CGF用于发现神经网络数值错误、网络与量化版本分歧及语言模型不良行为；开源TensorFuzz库。

---

## 1808.09700 — Evaluating Fuzz Testing

- 链接: http://arxiv.org/abs/1808.09700v2

### 核心问题
摘要未涉及

### 关键方法
摘要未涉及

### 创新点
摘要未涉及

### 局限性
摘要未涉及

### 贡献
摘要未涉及

---

## 2103.05118 — Efficient Fuzz Testing for Apache Spark Using Framework Abstraction

- 链接: http://arxiv.org/abs/2103.05118v1

### 核心问题
数据密集型可扩展计算(DISC)系统如Apache Spark的应用难以测试，传统模糊测试(fuzz testing)不适用，因为DISC系统延迟长且常规分支覆盖难以区分应用逻辑与框架实现。

### 关键方法
开发BigFuzz工具，自动为Apache Spark程序生成具体数据；通过可执行规范抽象DISC框架数据流行为，并基于DISC应用常见错误类型设计schema-aware mutations。

### 创新点
框架抽象与schema-aware mutations，提升模糊测试效率。

### 局限性
摘要未涉及

### 贡献
BigFuzz比随机模糊测试快1477倍，应用代码覆盖提高271%，应用错误检测提高157%。

---

## 2203.06910 — Investigating Coverage Guided Fuzzing with Mutation Testing

- 链接: http://arxiv.org/abs/2203.06910v2

### 核心问题
覆盖引导模糊测试（CGF）有效检测bug，但更高代码覆盖不一定意味着更好故障检测能力；触发bug需不仅执行特定路径，还需达到有趣程序状态。

### 关键方法
使用变异测试改进CGF，以变异分数作为反馈引导模糊测试优先检测bug而非仅覆盖代码；在5个基准上实验，对比Zest基线及两个基于该方法的修改版本。

### 创新点
引入变异分数作为反馈，指导模糊测试向检测bug方向优化，而非仅最大化代码覆盖。

### 局限性
摘要未涉及

### 贡献
实验结果显示该方法能提升CGF在代码覆盖和bug检测方面的性能。

---

## 2302.08664 — Socialz: Multi-Feature Social Fuzz Testing

- 链接: http://arxiv.org/abs/2302.08664v4

### 核心问题
在线社交网络bug和glitches可能导致挫败问题至严重数据泄露；传统fuzz testing对社交网络外部开发者难以实现。

### 关键方法
Socialz方法：(1)表征真实用户；(2)使用进化计算多样化多特征交互；(3)执行交互并收集性能数据。

### 创新点
提出新型social fuzz testing工具Socialz，使人人可用，提升社交网络可靠性和安全性。

### 局限性
摘要未涉及

### 贡献
开发Socialz工具；在研究中发现GitLab CE一已知限制及6907个错误（40.16%超出调试技能）

---

## 2307.11247 — Formal-Guided Fuzz Testing: Targeting Security Assurance from Specification to Implementation for 5G and Beyond

- 链接: http://arxiv.org/abs/2307.11247v1

### 核心问题
5G及Beyond的软硬件化和虚拟化需彻底测试，确保关键基础设施和网络安全，识别从协议设计到软件栈实现的漏洞及意外行为。

### 关键方法
设计形式验证检测关键协议攻击轨迹，指导后续模糊测试，并从模糊测试反馈扩展形式验证；在srsRAN平台上实现，指导下发现61个漏洞。

### 创新点
首次连接形式验证与模糊测试，按层次高效检测协议逻辑至实现栈漏洞；形式指导模糊并反之，提高效率，将计算复杂度从指数转为线性。

### 局限性
摘要未涉及

### 贡献
发现1个标识符泄漏模型、1个DoS攻击模型、2个窃听攻击模型；指导下在srsRAN上利用61个漏洞；相比SOTA，系统发现漏洞并降低计算复杂度。

---

## 2406.04517 — FOX: Coverage-guided Fuzzing as Online Stochastic Control

- 链接: http://arxiv.org/abs/2406.04517v1

### 核心问题
Fuzzing大型复杂程序发现深藏漏洞困难，现有的coverage-guided fuzzers scheduler存在信息稀疏和无法处理细粒度反馈问题，mutator忽略目标程序分支导致计算浪费和覆盖探索缓慢。

### 关键方法
提出端到端在线随机控制公式用于coverage-guided fuzzing，包括新型scheduler利用细粒度branch distance识别frontier branches，以及custom mutator利用branch distance进行高效针对性种子变异，实现FOX原型并在FuzzBench和真实程序上评估。

### 创新点
将coverage-guided fuzzing表述为在线随机控制，scheduler和mutator适应分支逻辑，最大化多阶段聚合edge coverage，使用branch distance实现高效调度和变异。

### 局限性
摘要未涉及

### 贡献
FOX在38个测试程序上优于AFL++，真实独立程序平均覆盖提升26.45%，FuzzBench提升6.59%，发现20个独特bug，包括8个未知bug。

---

## 2510.10179 — LLMs are All You Need? Improving Fuzz Testing for MOJO with Large Language Models

- 链接: http://arxiv.org/abs/2510.10179v1

### 核心问题
MOJO作为新兴编程语言，缺乏全面测试框架和足够语料库，导致LLM在零样本环境中产生幻觉，生成语法正确但语义错误的代码，显著降低fuzz testing的有效性。

### 关键方法
提出MOJOFuzzer，首个针对新兴语言零样本环境的adaptive LLM-based fuzzing框架，包括多阶段系统过滤低质量生成输入、基于运行时反馈动态适应LLM提示进行测试用例变异，实现迭代学习提升fuzzing效率。

### 创新点
首个为新兴语言零样本环境设计的adaptive LLM fuzzing框架，通过多阶段过滤和动态提示适应显著提升测试用例有效性、API覆盖和bug检测性能。

### 局限性
摘要未涉及

### 贡献
实验证明MOJOFuzzer优于传统fuzz testing和SOTA LLM fuzzing方法；首次大规模MOJO fuzz testing，发现13个未知bug；推进LLM驱动软件测试，并为新兴语言测试建立基础方法论。

---

## 2603.13411 — Human in the Loop for Fuzz Testing: Literature Review and the Road Ahead

- 链接: http://arxiv.org/abs/2603.13411v1

### 核心问题
模糊测试（fuzz testing）自动化启发式难以发现深层或复杂漏洞，导致性能有限；缺乏将人类在环（HITL）与模糊测试结合的系统研究路线图。

### 关键方法
调研现有HITL模糊测试工作，提出研究议程，包括（1）人类监控、（2）人类引导、（3）人类-LLM协作；突出可视化技术、实时干预及LLM整合。

### 创新点
概述HITL模糊测试的前瞻性研究路线图，强调可视化可解释过程、实时专家干预及LLM带来的新机会与挑战；呼吁向交互式人类指导模糊系统范式转变。

### 局限性
摘要未涉及

### 贡献
桥接研究差距，提供HITL模糊测试路线图；调研现有工作并提出未来机会议程，推动专家洞见与AI自动化的下一代模糊生态。

---

## 2604.05289 — FLARE: Agentic Coverage-Guided Fuzzing for LLM-Based Multi-Agent Systems

- 链接: http://arxiv.org/abs/2604.05289v1

### 核心问题
Multi-Agent LLM Systems (MAS) 用于自动化复杂工作流，但因 LLM agents 非确定性行为及 agents 间复杂交互，常出现无限循环和工具调用失败等故障。传统软件测试技术无效，因缺乏 LLM agent 规范、MAS 行为空间大及语义正确性判断。

### 关键方法
FLARE 框架输入 MAS 源代码，从 agent 定义提取规范和行为空间；基于规范构建测试预言机，进行覆盖引导模糊测试暴露故障；分析执行日志判断测试通过与否，并生成故障报告。

### 创新点
提出专为 MAS 设计的 FLARE 测试框架，结合规范提取、覆盖引导模糊测试及日志分析，实现高覆盖率（inter-agent 96.9%、intra-agent 91.1%，优于基线 9.5% 和 1.0%）并发现 56 个 MAS 特有未知故障。

### 局限性
摘要未涉及

### 贡献
开发 FLARE 框架；在 16 个开源应用上评估，显著提升覆盖率并发现 56 个未知 MAS 故障。

---
