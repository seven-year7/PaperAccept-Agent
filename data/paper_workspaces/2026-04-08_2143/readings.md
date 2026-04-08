# 论文阅读摘要

## 1807.10875 — TensorFuzz: Debugging Neural Networks with Coverage-Guided Fuzzing

- 链接: http://arxiv.org/abs/1807.10875v1

### 核心问题
机器学习模型尤其是神经网络难以解释和调试，特别是针对稀有输入的错误。

### 关键方法
开发覆盖引导模糊测试（CGF）方法，通过随机变异输入并由覆盖率度量指导，目标满足用户指定约束；使用快速近似最近邻算法提供覆盖率度量。

### 创新点
将覆盖引导模糊测试引入神经网络调试，并用近似最近邻算法实现覆盖率度量。

### 局限性
摘要未涉及

### 贡献
应用于发现训练神经网络数值错误、生成神经网络与量化版本不一致、揭示字符级语言模型不良行为；发布开源库TensorFuzz实现所述技术。

---

## 1808.09700 — Evaluating Fuzz Testing

- 链接: http://arxiv.org/abs/1808.09700v2

### 核心问题
Fuzz testing新技术和算法的实验评估设置是否能产生可信结果，现有的32篇fuzzing论文实验评估均存在问题，可能导致错误或误导性评估。

### 关键方法
调研32篇fuzzing论文的实验评估，发现普遍问题；使用现有fuzzer进行广泛实验评估，验证这些问题确实导致错误评估。

### 创新点
系统评估fuzzing研究文献的实验方法，并通过自身实验验证其影响。

### 局限性
摘要未涉及

### 贡献
识别现有实验评估的普遍问题，提供改进fuzz testing算法实验评估的指导方针，使结果更robust。

---

## 2103.05118 — Efficient Fuzz Testing for Apache Spark Using Framework Abstraction

- 链接: http://arxiv.org/abs/2103.05118v1

### 核心问题
数据密集型应用依赖DISC系统如Apache Spark处理大数据，但DISC应用难测试。传统fuzzing不适用，因DISC系统长延迟及常规分支覆盖难以区分应用逻辑与框架实现。

### 关键方法
BigFuzz工具自动为Apache Spark程序生成具体数据，通过抽象DISC框架数据流行为（executable specifications）并设计基于DISC应用常见错误类型的schema-aware mutations。

### 创新点
框架抽象与schema-aware mutations，实现高效Spark fuzz testing。

### 局限性
摘要未涉及

### 贡献
BigFuzz比随机fuzzing快1477X、应用代码覆盖率提高271%、检测应用错误提高157%

---

## 2203.06910 — Investigating Coverage Guided Fuzzing with Mutation Testing

- 链接: http://arxiv.org/abs/2203.06910v2

### 核心问题
覆盖引导模糊测试（CGF）虽有效检测大量bug，但更高代码覆盖率不一定意味着更好故障检测能力；触发bug需不仅执行特定路径，还需达到有趣程序状态。

### 关键方法
使用变异测试改进CGF，以变异分数作为反馈引导模糊测试针对bug检测；在5个基准上实验，以Zest为基准，构建两个修改技术。

### 创新点
将变异分数作为反馈指导模糊测试，聚焦bug检测而非仅代码覆盖。

### 局限性
摘要未涉及

### 贡献
实验结果显示，该方法提升CGF在代码覆盖和bug检测方面的性能。

---

## 2302.08664 — Socialz: Multi-Feature Social Fuzz Testing

- 链接: http://arxiv.org/abs/2302.08664v4

### 核心问题
在线社交网络易受bug和glitches影响，可能导致挫败问题或严重数据泄露；传统fuzz testing对社交网络开发团队外程序员实施困难或不实际。

### 关键方法
Socialz：(1)表征真实用户；(2)使用进化计算多样化用户交互，跨越多个非平凡特征；(3)执行交互时收集性能数据。

### 创新点
提出新型social fuzz testing方法Socialz，使人人可使用社交测试工具，提高全球社交网络可靠性和安全性。

### 局限性
研究发现当前GitLab CE的一个已知限制；6907个错误中40.16%超出调试技能。

### 贡献
引入Socialz工具；发现GitLab CE限制及大量错误，提升社交网络测试可及性。

---

## 2307.11247 — Formal-Guided Fuzz Testing: Targeting Security Assurance from Specification to Implementation for 5G and Beyond

- 链接: http://arxiv.org/abs/2307.11247v1

### 核心问题
5G及Beyond的软硬件化和虚拟化需彻底测试确保关键基础设施和网络安全，识别从协议设计到软件栈实现的漏洞及意外新兴行为。

### 关键方法
设计形式验证检测关键协议攻击轨迹，用于指导后续模糊测试，并融入模糊测试反馈扩展形式验证；在srsRAN平台上实现，按层次检测协议逻辑和实现栈漏洞。

### 创新点
首次结合形式验证与模糊测试，按层次高效检测漏洞，实现形式指导模糊及反馈互补；自动发现3GPP协议至软件栈漏洞及新兴行为，将计算复杂度从指数转为线性。

### 局限性
摘要未涉及

### 贡献
发现1个标识符泄漏模型、1个DoS攻击模型、2个窃听攻击模型；指导下利用模糊测试发现61个漏洞，强化协议假设、精炼搜索空间，提供系统性自动保障。

---

## 2406.04517 — FOX: Coverage-guided Fuzzing as Online Stochastic Control

- 链接: http://arxiv.org/abs/2406.04517v1

### 核心问题
Fuzzing大型复杂程序发现深藏漏洞困难。现有coverage-guided fuzzers的scheduler存在信息稀疏和无法处理细粒度反馈问题；mutator忽略目标程序分支，导致计算浪费和覆盖探索缓慢。

### 关键方法
提出端到端在线随机控制公式化coverage-guided fuzzing，包括新型scheduler利用细粒度branch distance识别frontier branches，以及custom mutator利用branch distance进行高效针对性种子变异，实现FOX原型并在FuzzBench和真实程序上评估。

### 创新点
将coverage-guided fuzzing表述为在线随机控制；scheduler和mutator适应分支逻辑，最大化多阶段聚合edge coverage。

### 局限性
摘要未涉及

### 贡献
FOX在38个测试程序上优于AFL++，真实独立程序覆盖率提升26.45%，FuzzBench提升6.59%；发现20个独特bug，包括8个未知bug。

---

## 2510.10179 — LLMs are All You Need? Improving Fuzz Testing for MOJO with Large Language Models

- 链接: http://arxiv.org/abs/2510.10179v1

### 核心问题
MOJO作为新兴编程语言，缺乏全面测试框架和足够语料库，导致LLM-based fuzz testing中产生幻觉（语法正确但语义错误的代码），显著降低fuzz testing有效性。

### 关键方法
提出MOJOFuzzer，首个针对新兴语言零样本环境的适应性LLM fuzzing框架，包括多阶段过滤低质量生成输入、基于运行时反馈动态适应LLM提示进行测试用例变异，实现迭代学习。

### 创新点
首个自适应LLM-based fuzzing框架，系统消除低质量输入并动态优化提示，支持新兴语言零样本测试。

### 局限性
摘要未涉及

### 贡献
显著提升测试有效性、API覆盖和bug检测性能，优于传统及SOTA LLM fuzzing方法；首次大规模MOJO fuzz testing，发现13个未知bug；推进LLM驱动软件测试，建立新兴语言测试方法论。

---

## 2603.13411 — Human in the Loop for Fuzz Testing: Literature Review and the Road Ahead

- 链接: http://arxiv.org/abs/2603.13411v1

### 核心问题
模糊测试（fuzz testing）虽有效，但自动化启发式难以发现深层复杂漏洞，导致性能受限；缺乏将人类在环（HITL）与模糊测试结合的系统研究路线图。

### 关键方法
调研现有HITL模糊测试工作，提出研究议程，包括人类监控（human monitoring）、人类引导（human steering）和人类-LLM协作（human-LLM collaboration）。

### 创新点
强调可视化技术提升模糊过程可解释性、实时干预引导难达程序行为；探讨LLM时代人类提供知识、利用专家元知识及角色定位；呼吁向交互式人类指导模糊系统范式转变，融合专家洞见与AI自动化。

### 局限性
摘要未涉及

### 贡献
桥接研究空白，概述HITL模糊测试前瞻性路线图，调研现有工作并提出未来机会研究议程，推动下一代模糊生态发展。

---

## 2604.05289 — FLARE: Agentic Coverage-Guided Fuzzing for LLM-Based Multi-Agent Systems

- 链接: http://arxiv.org/abs/2604.05289v1

### 核心问题
Multi-Agent LLM Systems (MAS) 通过分解任务自动化复杂工作流，但LLM代理非确定性行为及代理间复杂交互导致失败，如无限循环和工具调用失败。传统测试技术无效，因缺少代理规范、行为空间大及语义正确性判断。

### 关键方法
FLARE框架输入MAS源代码，从代理定义提取规范和行为空间，构建测试预言机，进行覆盖引导模糊测试暴露失败，分析执行日志判断测试通过与否并生成失败报告。

### 创新点
提出FLARE，专为MAS设计的覆盖引导模糊测试框架，从源代码提取规范，支持inter-agent和intra-agent覆盖。

### 局限性
摘要未涉及

### 贡献
在16个开源应用上实现96.9% inter-agent覆盖和91.1% intra-agent覆盖，优于基线9.5%和1.0%，发现56个MAS特有未知失败。

---
