## 基于 ATT&amp;CK 框架的技术关联分析方法综述

钟睿 1 ，冯文英 2 ，李若南 2 ，甘隆罡 1, 2 ，于浩泽 1 ，顾钊铨 1, 2*

（ 1. 哈尔滨工业大学（深圳）计算机科学与技术学院，深圳 518055 ；

2. 鹏城实验室新型网络研究部，深圳 518000 ）

摘要： 随着网络攻防对抗的日益激烈，深入理解攻击者行为模式对主动防御至关重要。依托 MITRE ATT&amp;CK 框 架，本文系统界定了 ' 技术关联分析 ' 的研究范式，其核心目标是将离散的行为观测转化为连续的意图推理。以 ' 对上 下文及时间序列依赖的建模深度 ' 为核心划分标准，将现有技术关联挖掘方法归纳为 3 个递进层次：基于统计共现与 关联规则的静态模式挖掘、基于概率图与时序模型的动态演进分析，以及融合图计算与大语言模型的高阶语义挖掘。 在此基础上，对各类方法进行了系统性横向对比，并深入分析了其在攻击链补全、攻击意图预测以及防御与检测优化 三大下游任务中的适配性与实战价值。最后，剖析了现有方法在动态上下文感知与多模态数据对齐等方面的局限，并 展望了以大语言模型与知识图谱深度融合为代表的智能化发展方向，以期为自动化威胁捕获与网络安全运营提供系统 性的理论参考。

关键词： MITRE ATT&amp;CK ；技术关联分析；意图预测；大语言模型；知识图谱

中图分类号：

TP393

文献标志码： A

DOI:

10.20172/j.issn.2097-3136.250501

## Survey of technique association analysis methods based on the ATT&amp;CK framework

Zhong Rui 1 , Feng Wenying 2 , Li Ruonan 2 , Gan Longgang 1, 2 , Yu Haoze 1 , Gu Zhaoquan 1, 2*

（ 1. School of Computer Science and Technology, Harbin Institute of

Technology (Shenzhen), Shenzhen 518055, China ；

2. Department of New Network Research, Peng Cheng Laboratory, Shenzhen 518000, China ）

Abstract: As  cyber  offense  and  defense  grows  increasingly  sophisticated,  understanding  adversary  behaviors  is  essential  for proactive defense. Based on the MITRE ATT&amp;CK framework, we systematically define the paradigm of "Technique Association Analysis," which aims to transform discrete behavioral observations into continuous intent reasoning. Using the core modeling depth of contextual and temporal dependencies as a classification criterion, we categorize current technique association mining methods into three progressive levels: static pattern mining based on statistical co-occurrence and association rules, dynamic evolution analysis using probabilistic graphs and time-series models, and high-level semantic mining that integrates graph computing with large language models. Furthermore, we provide a systematic horizontal comparison and analyze the applicability of these methods in key downstream tasks, including attack chain completion, intent prediction, and defense and detection optimization. Finally, we discuss the limitations of existing methods in dynamic context awareness and cross-modal data alignment, and outline future directions. In particular, we highlight the indepth integration between large language models and knowledge graphs as a promising avenue, aiming to provide a comprehensive reference for research in automated threat hunting and network security operations.

* 通信作者： E-mail ： guzhaoquan@hit.edu.cn

基金项目： 国家自然科学基金（ No.  62372137 ）；鹏城实验室重点项目（ No.  PCL2024A05 ）；深圳市科技计划（ No. KJZD20231023094701003 ）

引用格式： 钟睿，冯文英，李若南，等 . 基于 ATT&amp;CK 框架的技术关联分析方法综述 [J]. 网络空间安全科学学报， 2025 ， 3 （ 5 ）： 2 - 13.

Citation Format ： Zhong R ， Feng W Y ， LI R N ， et al. Survey of technique association analysis methods based on the ATT&amp;CK framework[J]. Journal of Cybersecurity ， 2025 ， 3 （ 5 ）： 2 - 13.

Keywords: MITRE ATT&amp;CK; technique association analysis; intent prediction; large language models; knowledge graphs

## 0 引言

随着网络攻防对抗日益激烈，高级持续性威胁 （ Advanced Persistent Threat ， APT ）等复杂多步攻击已 成为关键信息基础设施面临的核心风险。现代网络攻 击通常横跨初始访问、横向移动与数据渗出等多个阶 段，使得防守方面临着严峻的 ' 告警疲劳 ' 与 ' 溯源断 链 ' 的双重困境。长期以来，威胁检测与溯源高度依赖 失陷指标（ Indicators of Compromise ， IOC ）。然而，根 据 ' 痛苦金字塔 ' 模型， IOC 处于金字塔底层，攻击者 可低成本动态更改，使传统防御手段难以持续有效。 为应对这一挑战，防御视角正向金字塔顶层的战术、 技术和过程（ Tactics ， Techniques ， and  Procedures ， TTP ）演进。在此背景下， MITRE ATT&amp;CK （ Adversarial  Tactics ， Techniques ， and  Common  Knowledge ） 框架通过对实战攻击行为的 TTP 进行标准化建模， 为学术界与工业界提供了系统化的先验知识库。

然而， ATT&amp;CK 框架本质上提供的是一套描述 攻击者单步行为的原子化静态 ' 词汇表 ' ，而非揭示 攻击逻辑演进的 ' 语法规则 ' 。在真实的威胁情报分 析与应急响应中，安全系统往往只能捕获到离散的 技术标签观测值。如何将孤立的单点技术观测有效 地转化为连续的攻击意图推理，是从被动响应走向 主动防御的关键。近年来，业界涌现出大量旨在挖 掘技战术深层关系的研究，但这些工作分布于底层 告警因果分析、攻击链预测或知识图谱构建等分支 领域，尚未形成统一的理论共识。鉴于此，为了系 统梳理这些跨领域的研究工作，本文尝试在理论层 面对其进行归纳与抽象，界定 ' 技术关联分析 ' （ Technique Association Analysis ， TAA ）这一统一概 念，并将其定义为：挖掘并建模攻击技术之间（如 先后依赖、共现协同），以及技术与多维上下文要素（如 组织偏好、资产特征）之间内在语义逻辑与时序映 射关系的系统性过程。

伴随数据挖掘、图计算以及大语言模型（ Large Language Models ， LLM ）的飞速发展，技术关联分析 方法在攻击链补全、意图预测等下游任务中取得显 著进展。然而，面对该领域研究范式的快速迭代， 现有综述文献大多聚焦于传统的统计共现与浅层机 器学习方法。近年来，复杂图模型、多模型集成、 大语言模型等前沿技术的引入，为技术关联的高阶 语义推理与智能化发展注入了新动能，但目前学术

界尚缺乏以 ' 上下文感知与时序建模深度 ' 为核心维 度的统一系统性梳理与横向对比。

为弥补这一综述空白并进一步完善该领域的理 论体系，本文对 ATT&amp;CK 框架下的技术关联分析前 沿研究进行了全面梳理。

## 1 技术关联的背景

技术关联分析的研究目标是基于 MITRE ATT&amp; CK 框架，将威胁情报中与技术相关的离散信息进 行结构化提取与建模，以支撑下游的攻击链补全等 任务。

## 1.1    ATT&amp;CK 技战术框架

MITRE ATT&amp;CK 是由 MITRE 公司 [1] 维护的开源 对抗知识库。它通过战术（ Tactics ）、技术（ Techniques ）和过程（ Procedures ） 3 个层级，构建了攻击 行为的标准化描述语言。战术代表攻击者的阶段性 目标，技术描述实现目标的具体手段，过程记录了 攻击者操作的上下文细节 [2] 。自 2015 年发布以来， ATT&amp;CK 已演进至 v17 版本（截至 2025 年 4 月）， 公开覆盖 38 种战术、 369 种技术及子技术。其核心 价值在于提供了通用的底层语义框架，使得跨组织、 跨平台的攻击行为比对成为可能。然而， ATT&amp;CK 矩阵本身是原子化的静态知识集合，缺乏对技术间 动态演进逻辑的显式表达，这构成了本文提出 ' 技术 关联分析 ' 的现实动力。

## 1.2 技术关联的定义与边界辨析

基于 ATT&amp;CK 框架 [2] 如图 1 所示，本文界定 ' 技术关联分析 ' 的研究范式，其定义为：利用计算 模型挖掘、量化并表征 ATT&amp;CK 技术项之间（如时 序依赖、协同共现），以及技术与多维上下文要素（如 组织、资产、环境）之间语义逻辑与映射关系的过 程。为明确该研究范式的独特性，需将其与网络安 全领域的相关成熟概念进行核心边界区分。

与攻击图的异同：攻击图侧重于底层物理网络 拓扑、资产漏洞分布以及节点间的 ' 物理可达性 ' 分 析，而技术关联则抽象于具体的物理资产之外，不 关注特定服务器的 IP 或具体 CVE 漏洞，聚焦于攻击 者战术意图与技术组合的 ' 语义逻辑映射 ' 。简言之， 攻击图解答 ' 攻击者能否到达该节点 ' ，技术关联解 答 ' 攻击者惯用何种战术组合 ' 。

与威胁情报关联分析的异同：传统的威胁情报关 联分析多停留在金字塔底层，侧重于失陷指标（如

图 1    ATT&amp;CK 框架：战术按列排布，技术按行排布

<!-- image -->

Fig. 1    ATT&amp;CK matrix: tactics are organized by columns while techniques by rows

恶意 IP 、域名、文件哈希）与特定恶意软件或黑客 组织之间的映射。由于 IOC 易被攻击者低成本更改， 这类关联的半衰期较短。技术关联则关注痛苦金字 塔顶层的 TTP ，挖掘的是超越易变指标的 ' 行为模式 关联 ' ，具有较好的稳定性和对抗价值。

与 TTP 提取的异同： TTP 提取本质上是自然语 言处理中的信息抽取任务，其目标是将非结构化文 本转化为孤立的 ATT&amp;CK 技术标签。而技术关联则 是建立在 TTP 提取基础上的 ' 知识发现与推理 ' 任 务 -前者解决 ' 是什么 ' 的问题，后者解决标签间的 ' 因果、时序与程序化关系 ' 。

现有研究多将底层告警分析与高层意图推测相 割裂，或仅停留在孤立的技术标签识别上。界定 ' 技 术关联分析 ' ，旨在将离散的行为观测（孤立标签） 转化为连续的意图推理（攻击链条），为整合静态 规则挖掘、动态时序预测及大语言模型高阶推理提 供了统一的研究框架，是实现自动化威胁捕获与主 动防御的关键支撑。

在实际应用中，技术关联分析需从多源数据（如 攻击报告、告警日志、 APT 组织行为模式等）中提 取相关信息，并经标准化处理形成结构化表征。由 于多步攻击发生于特定上下文，技术关联分析不仅 需关注技术本身的演进规律，还需结合上下文要素 对其转移关系进行多维映射。

## 1.3 技术关联分析的方法体系与应用范畴

技术关联分析作为本文探讨的研究范式，旨在 通过建模 ATT&amp;CK 技战术之间的内在逻辑、演进规 律与上下文约束，将离散的行为观测转化为具备推

理能力的关联模型。该范式的核心价值在于实现底 层原子化技术标签向高层结构化意图表示的转化， 为后续威胁捕获与应急响应提供标准化的知识支撑。

根据对攻击上下文及时间序列建模深度的差异， 本文将现有的技术关联分析方法归纳为 3 个递进层 次：①静态模式挖掘，侧重于利用统计共现、聚类 或关联规则发现技术间的频繁组合模式，适用于挖 掘宏观、稳定的技术关联；②动态演进分析，引入 概率转移矩阵或深度时序网络，捕捉攻击行为在时 间维度上的转移规律与动态变化；③高阶语义挖掘， 融合图计算、知识图谱与大语言模型，通过建模异 构实体关系与复杂语义上下文，实现高维度的关联 预测与因果推理。

技术关联模型的输出形式与其承载的下游任务 高度互补。目前，技术关联分析主要服务于以下三 类安全运营场景：①攻击链路补全，针对观测视角 残缺导致的 ' 断链 ' 问题，利用关联规则或语义补全 模型预测缺失的技术节点或演进路径；②攻击意图 预测，基于已观测到的早期攻击片段，实时推演 攻击者后续最可能的技战术动向，实现主动防御； ③防御与检测优化，通过对关联模型进行结构化分 析，辅助安全团队识别资产暴露面中的核心威胁节 点，从而实现防御资源的精准调度与检测策略的针 对性优化。

## 2 技术关联的主要方法分析

自 MITRE ATT&amp;CK 框架公开发布以来，挖掘技 术间隐含关系的研究不断涌现。然而，这些散落在

告警分析、意图推测等方向的工作，其切入视角往 往较为分散。为了建立更为系统和统一的理论框架， 本文将这些探索性研究纳入 ' 技术关联分析 ' 的语境 中，以 ' 对攻击上下文及时间序列依赖的建模深度 ' 为核心划分标准，将现有的分析方法归纳为 3 个递 进层次：①基于统计共现与关联规则的静态模式挖 掘，侧重于从宏观历史频次中提取浅层的条件关联； ②基于概率图与时序模型的动态演进分析，旨在弥 补静态方法的不足，重点捕捉多步攻击的状态转移 与时间依赖；③基于图计算与大模型的高阶语义挖 掘，致力于突破异构拓扑与非结构化情报的融合瓶 颈，实现深层语义推理。

本节将沿着这一演进脉络，对三类代表性方法 的核心思想、适用场景及局限性进行详细阐述与系 统对比。

## 2.1 基于统计共现与关联规则的静态模式挖掘

在技术关联研究的早期阶段，基于统计共现、 聚类与关联规则的无监督挖掘是最直观且广泛采用 的方法。这类方法的核心逻辑是提取历史安全数据 中技术标签之间的共现频次与浅层条件关联，即重 点关注技术在攻击事件中 ' 是否一起出现 ' 或 ' A 的出 现是否往往伴随 B ' 的静态模式，而不严格深究其背 后的时间演进顺序。由于此类算法对数据维度要求 较低、计算开销适中，常被用作技术特征探索的先 导手段或复杂模型的预处理步骤。

现有的聚类与相似度计算方法常将技术视作 ' 点 ' 或多维特征向量，通过衡量其在共现空间或嵌 入空间中的距离，将彼此相近的技术划归为同一簇。 相较于简单的两两共现，聚类能够识别出 ' 多对多 ' 的技术组合，并可灵活融合攻击阶段、组织 ID 等上 下文要素。例如， Al-Shaer 等 [3] 使用层次聚类分析了 ATT&amp;CK 中的 66 个 APT 组织和 204 个软件攻击实例， 有效识别出细粒度的技术关联；结合信息论 [4] 和专 家验证表明，这些关联具有较高的预测价值。类似 地， Wang 等 [5] 虽未直接处理底层 TTP ，但将 TTP 映 射至 ' 目标 -行为 -能力 ' 三层模型后，利用 GirvanNewman 算法揭示了不同 APT 组织在技战术使用习 惯上的聚类差异。此外， Ding 等 [6] 提出基于层次聚 类的隐藏模式挖掘方法，利用安全知识图谱识别了 黑客群体共用的技术簇。

然而，单纯的聚类难以揭示技术实施的先后顺 序。为此，基于频繁项集与关联规则挖掘的方法被 引入，用于进一步量化 ' 前提技术 → 结果技术 ' 的条 件概率。典型算法（如 Apriori 与 FP-Growth ）能够从

大量 ATT&amp;CK 标签数据中提取高置信度的关联规则， 弥补简单聚类所忽略的因果方向性。在这一方向的 探索中， Abu 等 [7] 较早尝试用 Apriori 算法从底层 IOC 数据中挖掘关联规则，揭示了恶意 IP 、软件家 族与受感染设备之间的内在联系。受此启发，后续 研究逐渐将关联规则的挖掘层级提升至 TTP 维度。 例如， Mckee 等 [8] 提出使用活动组创建（ AGC ）函 数生成技术关联组，以指导威胁行动方案的生成。 Wang 等 [9] 针对特定领域改造了 ATT&amp;CK 框架，利用 改进的 PDFP-Growth 算法挖掘车联网入侵检测系统 （ Intrusion Detection System ， IDS ）事件关联，提取 基础攻击链路。 Zang 等 [10] 则在 DARPA 2000 等数据 集中构建语义关联图，利用社区发现和加权语义挖 掘攻击场景内的技术依赖。

在实际应用中，共现统计与规则挖掘往往是相 辅相成的。例如， Rahman 等 [11] 受频繁项集 [12] 与关 联规则挖掘 [13] 启发，对收集的 115 个网络犯罪集团 和 484 个恶意软件相关数据进行了综合分析。该工 作不仅提炼了高频技术的组合模式，还量化了技 术间的因果关联，为制定针对性的缓解策略提供了 依据。

静态模式挖掘算法依赖常见工具库，部署较为 便捷、开销较低，且提取的规则直观易懂，便于安 全团队快速进行探索和原型验证。然而，这类方法 仅关注静态频率，标准挖掘算法忽视了技术使用的 时间顺序，缺乏对动态上下文的深入建模。在面对 高动态 APT 行为或数据稀疏场景时，这类方法容易 遭遇簇边界模糊和罕见模式漏检等瓶颈。表 1 给出 基于静态模式挖掘的技术关联方法总结。

## 2.2 基于概率图与时序模型的动态演进分析

静态模式挖掘虽能有效筛选高频技术组合，但 难以刻画多步攻击中技术之间流转的时间顺序与动 态演进规律。为捕捉这种时序依赖与因果链条，研 究者开始引入概率转移图与时序模型，重点挖掘攻 击行为在时间维度上的转移概率与长程依赖。

基于概率图的转移与动态更新方法通常假设攻 击行为遵循某种特定的状态转移过程或条件概率分 布。 Zhang 等 [14] 融合 ATT&amp;CK 与 Mandiant 情报数据， 构建了技术关联概率图和战术转移矩阵，利用马尔 可夫链对攻击者在不同战术阶段的转移进行建模， 实现了零信任网络环境下 APT 威胁风险传播的量化 评估。 Choi 等 [15] 针对工业控制系统，在假设战术阶 段具有某种严格顺序的前提下，构建隐马尔可夫模 型以生成战术依赖与关联技术序列。此外，贝叶斯

## 表 1 基于静态模式挖掘的技术关联方法总结

Table 1    Methods for technique association research using statistical co-occurrence ID clustering

| 方法                     |   年份 | 方法描述                                            | 输出形式                                              | 使用数据                         | 评估策略                                              | 优点                                                                | 局限性                                                                                 |
|--------------------------|--------|-----------------------------------------------------|-------------------------------------------------------|----------------------------------|-------------------------------------------------------|---------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| 分区聚类、 层次聚类 [3]  |   2020 | 使用分区聚类与层次 聚类发掘技术关联                 | 聚类层次树、技 术转移关系图                           | MITRE ATT&CK                     | 信息论方法 [4] 、专 家评估                            | 方法简单，能分级 排列技术间的关联                                   | 对上下文内容综合 较少，处理复杂 APT 攻击的能力较弱                                     |
| Girvan- Newman [5]       |   2020 | 提出一个三层模型量 化 APT 群组的相似性              | 共现表、技术关 联网络                                 | MITRE ATT&CK                     | 观察网络图与专家 经验                                 | 分离出了不同组 织偏好使用的技术 群组                                | 数据量较少，且评 估方式过于主观                                                        |
| Ward 联结 法 [6]         |   2021 | 从已有的网络安全知 识图中提取 ' 技术 - 组 织 ' 关系 | 聚类层次树                                            | 已有网络安全知识图               | 观察 ESS 增量和例 子验证隐含模式                      | 仅依赖已有的 ' 技 术 - 组织 ' 关联，无 需额外特征工程               | 不考虑技术之间更 细粒度的上下文或 语义关系；缺乏定 量评价指标，无法 客观评估聚类效果   |
| Apriori 算 法 [7]        |   2020 | 基于关联规则挖掘进 行网络攻击归因                   | 挖掘出的关联规 则集、散点图、分 组矩阵图、规则 统计表 | Shadowserver 抓取 数据           | 无量化指标，仅提 取支持度与置信度 排名靠前的关联 规则 | 使用真实 CTI 数据； Apriori 算法实现简 单、规则可视化               | 缺乏时序或流量上 下文分析、阈值需 人工调节、缺乏定 量评价指标                          |
| AGC [8]                  |   2023 | 提出 AGC 活动组， 以此为基础进行关联 规则挖掘       | 活动组关联、攻 击路径                                 | 部分公开数据集                   | 结合真实 APT 攻 击场景分析                            | 多层次粒度，支持 子技术级与父级技 术抽象；有一定的 上下文关联       | 阈值选择主观、无 时序因果关系、对 上下文关系的提取 过于简单                            |
| PDFP- Growth [9]         |   2024 | 基于改进 PDFP- Growth 算法挖掘关联 规则             | PDFP-Growth 规 则集、复杂攻击 路径                    | MITRE ATT&CK 、 模拟安全事件数据 | 真实攻击场景测试、 对比分析                           | 支持多维度攻击路 径挖掘，规则提取 高效                              | 缺乏灵活的上下文 适配能力，处理大 规模数据时效率 受限                                  |
| 语义关联图、 Leiden [10] |   2025 | 构建语义关联图，并 将其视为社交网络挖 掘攻击场景    | 语义关联图、关 联规则集、攻击 场景子图                | DARPA 2000 、 CICIDS 2017        | 攻击路径对比、指 标计算                               | 使用序列模式挖掘 语义捕获关联，无 需依赖位置或时序 模板             | 关联权重设置较为 主观、不同攻击场 景下社区规模与连 通性差异大，可能 产生过大或过小子图 |
| FIM 、 ARM [11]          |   2022 | 频繁项集挖掘、关联 规则挖掘、构建共现 网络          | 频繁个体技术、 频繁共现技术组 合、关联规则、 共现网络 | MITRE ATT&CK                     | 中心性度量、介数 中心度                               | 结合频繁项集挖掘、 关联规则挖掘和图 网络分析揭示技术 共现与相互依赖 | 不考虑时序、忽略 上下文深度、阈值 选择主观、中心性 解释有局限                          |

统计分析也被应用于动态威胁概率的持续更新。例 如，近期研究 [16] 提出了一种网络风险评估量化框架， 将系统级危害映射至 ATT&amp;CK 战术，并通过贝叶斯 定理融合新接入的威胁情报。相较于传统的静态漏 洞评分，该概率模型能够根据活跃的攻击证据动态 计算后验概率，更敏锐地捕捉威胁态势的演变，为 技术关联提供了量化依据。

基于深度时序网络的预测与混合建模。为克服 传统概率模型在处理长程序列依赖上的局限，部分 研究开始引入长短期记忆网络（ Long Short-Term Memory ， LSTM ）等深度学习模型。依托此类模型对

序列历史特征的较强表征能力，安全系统能够基于 历史日志高效提取多步攻击的演进规律。例如，文 献 [17] 构建了基于高并发架构的企业内网资产暴露 面风险检测系统，该系统将 ATT&amp;CK 框架与 LSTM 时序预测算法相融合，用于主动检测潜在攻击路径。 实测表明，万级 IP 规模的复杂环境中，该系统在保 持高资产识别准确率的同时，显著缩短了风险响应 时间。此外，为探究不同动态模型在攻击链预测中 的适用边界，文献 [18] 提出了一种混合建模系统， 将一阶马尔可夫链与 LSTM 神经网络进行结合：前 者用于捕捉相邻技术间的局部转移概率，后者则基

于全局历史序列学习深层时序上下文。为缓解多步 预测中所产生的累积噪声并提升结果的可解释性， 该研究引入了 ' 链收缩 ' 算法，对语义冗余的攻击步 骤进行压缩。通过在 APT29 行动数据集上的验证， 该工作证实了生成式动态建模在威胁捕获场景中的 应用潜力。

基于概率图与时序模型的方法显著提升了关联 分析对动态演进过程的捕捉能力，为多步攻击的早 期预警与路径预测提供了有效的工具。然而，无论 是传统的转移矩阵还是深度时序网络，在直接处理 海量非结构化威胁情报文本以及复杂的异构网络拓 扑方面，仍面临语义特征提取能力有限、跨模态对 齐不足的瓶颈。这一局限性促使技术关联研究向融 合图计算与大语言模型的高阶语义挖掘方向迈进。 表 2 给出了基于动态时序演进的技术关联方法总结。

## 2.3 基于图计算与大模型的高阶语义挖掘

尽管前述的时序模型能够有效捕捉攻击的动态 演进规律，但其本质多聚焦于离散技术标签之间在 时间轴上的转移概率。在直接处理海量非结构化威 胁情报文本，以及刻画高度复杂的异构网络资产拓

扑时，传统模型往往面临特征提取能力受限与深层 语义理解不足的瓶颈。为突破这一局限，实现更深 层次的因果推理与全局上下文感知，技术关联研究 正逐步向融合图计算与大语言模型的高阶语义挖掘 阶段拓展。

需要指出的是，本文将 Transformer 及其衍生的 大语言模型归入此高阶阶段，其核心划分依据并非 底层神经网络架构的差异，而是此类模型凭借自注 意力机制，突破了纯结构化序列标签的限制，实现 了对非结构化文本细粒度上下文的深度解析与跨模 态因果映射。

基于图网络与深度学习的复杂拓扑建模：早期 的研究通过构建攻击图或威胁知识图谱，将网络资 产与 ATT&amp;CK 技战术进行结构化映射 [19-21] ，从而计 算攻击路径的物理可达性。然而，为克服单一图谱 在泛化预测上的局限，近期的前沿研究逐渐转向图 计算与深度神经网络的混合架构。例如， DeepOP 框 架 [22] 结合了本体推理与 Transformer 模型。该框架首 先利用本体论从非结构化情报中提取具备因果关联 的攻击事件，有效缓解了细粒度挖掘中的数据稀疏

表 2 基于动态时序演进的技术关联方法总结

Table 2    Summary of technique association methods based on dynamic time-series evolution

| 方法                          |   年份 | 方法描述                                                                  | 输出形式                                                | 使用数据                          | 评估策略                                                | 优点                                                              | 局限性                                                                                 |
|-------------------------------|--------|---------------------------------------------------------------------------|---------------------------------------------------------|-----------------------------------|---------------------------------------------------------|-------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| HMM [15]                      |   2021 | 假设 ATT&CK 框架 中的战术遵循严格 顺序，通过战术映 射技术生成攻击序列     | 生成的技术序列列 表、序列概率分数                       | MITRE ATT&CK 、 HAI 测试平台      | 前向算法评估、在 HAI 测试台执行测试                     | 能够快速生成大量 的攻击序列                                       | 模型过于简化，且 带有较强假设；转 移与发射概率基于 有限公开报告计算， 生成序列可能失真 |
| 马尔可夫 链 [14]              |   2024 | 基于 ATT&CK 威胁 度量体系构建战术 转换图，建模 APT 威胁风险模型           | 技术转移图、战术 转移图、单技术威 胁值表、战术转移 矩阵 | MITRE ATT&CK 、 Mandiant 情报数据 | 攻击路径对比、指 标计算                                 | 在技术转移图基础 上提升至战术转移 图，构建马尔可夫 链预测攻击意图 | 忽略上下文，仅以 技术序列与频率驱 动；威胁系数依赖 专家打分，偏主观                    |
| 贝叶斯统 计 [16]              |   2025 | 将系统危害映射至 ATT&CK 战术，利 用贝叶斯方法挖掘 技术关联                | 动态风险评估结果、 攻击路径预测                         | 开源 ATT&CK 数据、 CVSS 评分数据  | 真实攻击场景测试、 对比分析                             | 融合多种攻击路径 分析方法，精准定 位技术关联点                    | 依赖大量 ATT&CK 标准数据，小数据 集场景下泛化能力 弱                                   |
| LSTM 时 序预测 [17]           |   2025 | 集成 ATT&CK 与 LSTM 时序预测算 法，构建高并发企 业内网资产暴露面 检测系统 | 潜在攻击路径预测、 风险警报                             | 企业内网环境资产 与时序日志       | 真实内网环境（万 级 IP ）实测，对比 扫描效率与响应时 间 | 工程落地能力极强， 利用深度模型精准 预测攻击路径                  | 主要针对结构化日 志定制，非结构化 情报自动处理能力 不足                                |
| Markov 与 LSTM 混 合模型 [18] |   2025 | 结合一阶马尔可夫 链与 LSTM 进行多 路径攻击预测，引 入链收缩算法降噪       | 攻击路径预测结果、 风险评分、概率表 与图                | MITRE ATT&CK 、 STIX 结构化数据   | 与真实 APT 攻击路 径比对计算                            | 融合时序与语义分 析优势，攻击路径 预测准确率高                    | 依赖 STIX 结构化数 据输入，非结构化 数据解析能力有限                                   |

问题；随后，通过因果窗口自注意力机制，实现局 部因果与全局时序依赖的联合建模。此外，多模型 集成与图神经网络的结合也正成为提升关联预测精 度的重要手段。 KillChainGraph 框架 [23] 利用预训练语 言模型将 ATT&amp;CK 技术语义映射至宏观的网络攻击 链，并采用有向图建模不同阶段间的技术依赖关系。 通过集成图神经网络（ Graph Neural Network ， GNN ）、 Transformer 与 LightGBM 的预测结果，该方法在有效 捕捉攻击者横向移动特征的同时，提供了具有较高 可解释性的攻击路径推演。

基于大语言模型的深层语义关联：在探索底层 行为与高层语义映射的初期，引入注意力机制的深度 神经网络起到了关键的过渡作用。例如， Huang 等 [24] 提出了 MAMBA 系统，利用门控循环单元（ Gated Recurrent Unit ， GRU ）与双级注意力机制，将沙箱提 取的底层应用程序接口（ Application Programming Interface ， API ）调用序列多标签映射至 ATT&amp;CK 技术。 该工作在提升恶意行为发现效能的同时，提供了一 定程度的映射可解释性。然而，这类传统的深度学习 模型（如 MAMBA 、早期的多层感知机（ Multi-Layer Perceptron ， MLP ） [21] 或 Transformer [25] ）往往高度依 赖沙箱日志等结构化数据的完整性，且在处理非结 构化威胁情报时受限于繁重的人工特征工程。随着 大语言模型零样本与少样本推理能力的不断演进， 这一现状得到了显著改善。针对底层结构化告警难 以解读的问题，文献 [26] 提出整合大语言模型与检 索增强生成技术，将 Snort 入侵检测系统规则自动转 译并多标签映射至 ATT&amp;CK 战术与技术。这种降维 解析旨在降低特征工程开销，为防御端提供具备实 战价值的上下文语义。而在处理顶层非结构化威胁 情报时，文献 [27] 提出的 TTParser 双阶段解析框架 提供了一种新思路。该框架针对传统句子级分类方 法在 ' 细粒度上下文感知 ' 与 ' 动态攻击过程捕捉 ' 上 的局限，结合深度网络与 LLM 验证器进行 TTP 识别， 并利用少样本提示显式建模技术之间的程序化关系。 该方法尝试将孤立识别的技术节点按步骤重构为连 贯的攻击叙事，以期将孤立的技术预测转化为连续 的攻击意图推理。

基于图计算与大模型的方法代表了技术关联挖 掘的前沿方向。知识图谱与 GNN 提供了严密的拓扑 逻辑与宏观阶段约束，而 LLM 则赋予了系统极强的 细粒度语义理解与跨模态映射能力。这两者的融合 不仅能够应对最复杂的 APT 攻击场景的需求，也为 实现完全自动化的威胁捕获与高可解释性的攻击链

重构指明了未来的研究方向。表 3 给出了基于高阶 语义挖掘的技术关联方法总结。

## 2.4 各类方法的横向对比与适用边界分析

通过对上述三类技术关联分析方法的梳理可以 看出，随着网络攻击复杂度的提升，技术关联建模 的范式正经历从 ' 浅层静态统计 ' 向 ' 高阶动态语义 ' 的演进。为了更直观地揭示各方法的内在联系与适 用边界，本节将从时序感知能力、上下文建模深度、 数据依赖约束以及可解释性 4 个维度进行横向对比， 并探讨不同方法在实际应用中的边界条件。

1 ）时序与上下文建模的演进。静态模式挖掘（共 现分析、聚类与关联规则挖掘）本质上是一种降维 统计方法，其将攻击行为从时间轴上剥离，重点关 注技术特征的共现概率。这种方法计算开销极小， 但在面对具有强阶段依赖的高级持续性威胁时，时 序感知能力的缺失是其显著局限。动态时序模型（马 尔可夫链、贝叶斯模型、 LSTM 在一定程度上缓解了 这一缺陷，将技术关联从 ' 无向图 ' 升级为 ' 有向序 列 ' ，能够有效捕捉多步攻击的转移概率。然而，传 统时序模型依然停留在标签层面的流转；直至知识 图谱与大语言模型的引入，技术关联才真正具备高 维度上下文感知能力，如区分同一技术在不同网络 拓扑或不同组织背景下的微观语义差异。

2 ）数据依赖与适用边界条件。各种方法的适用 边界高度依赖于输入数据的类型、规模与结构化程 度。底层结构化日志 / 告警（如 IDS 规则）适合采用 关联规则或深度时序网络，因为这类数据格式统一、 并发量大，时序模型在此边界条件下能发挥较高的 计算效率。对于多源异构安全实体（如资产、漏洞、 用户），适用边界须转向知识图谱与图神经网络， 图模型在容纳多模态拓扑关系方面具有天然优势， 有助于缓解孤立标签难以映射宏观攻击链的问题。 而顶层非结构化文本（如 CTI （ Cyber Threat Intelligence ）报告）是传统算法的 ' 盲区 ' ；在此边界条件 下，大语言模型结合检索增强生成或少样本提示， 为将孤立的非结构化文本转化为结构化技术关联链 路提供了有效方案。

3 ）解释性与自动化程度的博弈。在网络安全领 域，预测结果的专家可解释性至关重要。基于关联 规则和本体推理（ Ontological Reasoning ）的方法具有 较强的 ' 白盒 ' 属性，其输出的规则或图谱逻辑清晰， 但往往需要极高的人工特征工程开销。深度神经网 络虽提升了特征提取的自动化水平，但其 ' 黑盒 ' 属 性导致预测路径难以被安全运营人员追溯。前沿的

表 3 基于高阶语义挖掘的技术关联方法总结

Table 3    Summary of technique association methods based on high-level semantic mining

| 方法                                      | 年份   | 方法描述                                                                                                            | 输出的形式                      | 使用数据                                                                  | 评估策略                                               | 优点                                                                                     | 局限性                                                                     |
|-------------------------------------------|--------|---------------------------------------------------------------------------------------------------------------------|---------------------------------|---------------------------------------------------------------------------|--------------------------------------------------------|------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| Bhadra 威胁 建模 [19]                     | 2021   | 将技术作为节点，相邻 技术间若共现则连边， 边权为出现次数；                                                          | 高频技术子序 列、可视化攻 击图  | 60 个手工建模的移 动通信多阶段攻击 案例、 Bhadra 框架 中定义的战术与技 术 | 定性与定量图 论分析                                    | 利用 Bhadra 框架将 多源攻击系统化建 模、通过图论提取 共子路径、重要性 与多样性           | 攻击图无环境上下 文，忽略实际网络 影响；建模过程高 度依赖专家判断          |
| 基于知识图谱的 攻击链检测与补 全系统 [20] | 2023   | 基于五元组与 MDATA 模 型构建网络安全知识图 谱，实现攻击链检测、 补全与剪枝                                          | 攻击知识图谱                    | 流式攻击日志数据                                                          | 实验模拟、攻 击链覆盖率与 错误状态识别 精度            | 将技术关联构建成 高度结构化的图谱， 具有较高的攻击链 识别的准确性与实 时性               | 构建与维护知识图 谱与规则库成本高， 攻击规则泛化能力 有限                  |
| EFI ：端点攻击预 测与解释系统 [21]        | 2024   | 提出 EFI 系统，通过图结 构方法实现对 EDR 告警 的实时后渗透攻击预测 与解释                                           | 攻击场景图、 攻击溯源图         | DARPA Engagement 数据集                                                   | 图预测准确率、 AFG 与真实攻 击图对齐得分、 预测时间    | 对潜在攻击行为有 较精准的预测与解 释                                                     | 模型训练复杂；对 EDR 系统能力有前 置依赖                                   |
| MAMBA [24]                                | 2022   | 构建 MLP 学习 ATT&CK 中（资产，技术）对的 隐向量、计算资源嵌入 与当前 API 隐向量的相关 度                           | TTP 预测列表                    | MITRE ATT&CK 、 MalShare 数据集                                           | P/R/F1/FPR/F NR 评估、消融 实验                        | 适配大规模样本， 远优于传统机器学 习与规则方法；多 标签输出，同一样 本可识别多个并发 TTP | 注意力解释非严格 推理、稀有 TTP 标签 样本不足时，模型 Recall 下降          |
| Transformer [25]                          | 2024   | 基于 MITRE ATT&CK 战 术框架对网络流量按战 术阶段建模，并利用 Transformer 提取时序相 关性，实现网络安全态 势分类评估 | 安全态势等级                    | UNSW - NB15 、 NSL - KDD                                                  | Precision 、 Recall 、 F 1 、 Accuracy                 | 利用 ATT&CK 精细 分类， Transformer 并行效率高                                           | 依赖 ATT&CK 标签 映射质量；对新兴 攻击技术泛化能力 有限                    |
| DeepOP 混合 框架 [22]                     | 2025   | 结合本体推理提取因果 事件，并嵌入 Transformer 架构进行多步预测                                                      | 攻击序列预测、 结构化事件图     | CTI 报告、 MITRE ATT&CK                                                   | 在真实 APT 数 据集上的多步 攻击预测精度 对比           | 本体论有效缓解了 数据稀疏问题， Transformer 捕捉了 全局时序依赖                          | 框架的本体构建阶 段仍有一定的人工 开销，未完全实现 端到端自动化            |
| KillChainGraph [23]                       | 2025   | 将 ATT&CK 映射至攻击 链，利用有向图与多模 型集成学习                                                                | 攻击路径预测、 可解释关系图     | MITRE 数据集                                                              | 对比多模型及 其集成框架在 各攻击阶段的 F 1             | 融合了攻击链的宏 观约束，预测结果 具备极高的可解释 性与准确率                            | 预训练语言模型与 图神经网络的集成 计算开销较大，实 时性可能受限            |
| Snort RAG 映射 [26]                       | 2025   | 整合 LLM 与 RAG 技术， 将底层 Snort 入侵规则翻 译并多标签映射至 ATT&CK 技术                                         | 威胁摘要、 ATT&CK 多标 签映射表 | Snort 规则、 CISA 咨 询报告                                               | 专家评分（准 确度 / 清晰度）， 单标签分类准 确率达 80% | 极大降低了一线安 全运营的认知负担， 实现底层告警到高 层语义的转译                        | LLM 的上下文窗口 限制可能影响超长 规则的解析，且存 在轻微的 ' 幻觉 ' 风 险 |
| TTParser 框架 [27]                        |        | 结合深度网络与 LLM 验 证器，利用少样本提示 重构孤立技术为连贯攻 击链                                                | TTP 识别结果、 分步攻击叙事     | 非结构化 CTI 报告                                                         | 与现有主流 NLP 模型对比 TTP 提取和攻 击链重建的准 确性 | 突破了孤立节点预 测的局限，显式建 模了程序化关系， 填补了语义鸿沟                        | 对 LLM 提示词的质 量和少样本设计高 度敏感；大模型调 用成本较高             |

混合架构（如 DeepOP 、 KillChainGraph ，）以及引入 大模型验证器的方案（如 TTParser ），旨在探索模型

自动化预测精度与安全专家逻辑可解释性之间的最 优平衡，代表了该领域极具潜力的演进方向。

表 4 对上述技术关联分析方法在核心机制、适 用边界、性能瓶颈及典型下游任务等方面进行了全 面的量化与定性对比。该表的横向映射，可为后续 针对特定安全运营场景选择最优技术路线提供理论 参考。

## 2.5 评估基准的缺失与标准化挑战

在对上述三类方法进行横向对比时，不可忽视 的一个现状是：当前技术关联分析领域仍缺乏统一 的标准化评估基准与量化指标体系。正如本文表 1~ 表 3 所梳理的评估策略所示，各类研究在验证手段 上存在显著分歧：静态模式挖掘往往依赖专家经验 进行定性评估或图论分析；动态时序模型多采用特 定企业内网或封闭测试床数据进行验证；而基于大 语言模型的研究则多依赖独立收集的开源威胁情报 进行小规模准确率测试。

统一评估基准的缺失，导致不同方法在召回率、 准确率以及计算开销等核心性能表现上，难以进行 绝对的横向量化对比。这种评估标准的碎片化现状， 很大程度上制约了技术关联模型在工业界的泛化与 落地应用。因此，构建包含多模态异构数据、覆盖 真实且多样化 APT 组织演进轨迹的大规模开源基准 数据集，并建立统一的性能评价量纲，不仅是客观 评估现有技术优劣的基础，亦是该领域未来亟待突 破的重要研究方向。

## 3 技术关联的应用场景

本文界定 ' 技术关联分析 ' 这一研究范式的核 心目的，不仅在于发现历史攻击规律，更在于将挖 掘出的技战术演进规律服务于真实的网络安全运营 实战。正如第 3 节所述，不同维度的关联分析方法 因其上下文建模深度与数据依赖的差异，在实际应 用中展现出对不同运营场景的适配性。在本文所界 定的语境下，技术关联的主要下游任务可归纳为三 大核心场景：攻击链路补全、攻击意图预测以及防 御与检测优化。

## 3.1 攻击链路补全

在真实的网络安全应急响应中，受限于日志留 存策略、审计盲区或攻击者的反取证操作，安全团 队往往只能观测到攻击链中的零星片段。攻击链路 补全的核心诉求在于回答 ' 在当前观测到的行为之 前，最有可能发生了什么前置操作？ ' 。早期的自动 化链路补全多依赖专家规则匹配，难以应对高级威 胁的复杂变形。针对这一痛点，部分研究开发了自 动化技术关联框架 [28] ，尝试将安全专家的语义先验 知识与数据驱动方法相结合，为孤立的告警片段提 供了初步的上下文回溯能力。

然而，面对海量的非结构化威胁情报与极度残 缺的观测视角，传统方法在特征提取上依然面临瓶

表 4 各类技术关联分析方法的横向对比与适用边界

Table 4    Comparative analysis of different technique association analysis methods

| 方法子类          | 时序感知能力   | 上下文建模 深度   | 数据依赖与适用边界条件                                         | 可解释性   | 典型性能瓶颈、局限性                                                   | 优势适配的下 游任务               |
|-------------------|----------------|-------------------|----------------------------------------------------------------|------------|------------------------------------------------------------------------|-----------------------------------|
| 统计共现与 聚类   | 无             | 浅层              | 适用于具有大量历史结构化标签的 数据集，对数据维度要求低        | 高         | 数据稀疏时聚类边界模糊；无法 识别攻击步骤先后顺序                      | 基础技术概览、 初始预筛选         |
| 关联规则挖掘      | 极弱           | 浅层              | 适用于特征明确、频率分布相对集 中的底层日志与告警数据          | 极高       | 受制于最低支持度阈值，极易漏 检低频但高危的 ' 长尾 ' 技术              | 静态防御规则 生成                 |
| 概率图与 贝叶斯   | 中             | 中层              | 适用于状态转移定义清晰且能持续 摄入量化情报 ( 如 CVSS) 的场景  | 高         | 强马尔可夫假设难以处理长距离 跨阶段依赖；先验概率高度依赖 人工专家     | 动态风险量化、 基础意图预测       |
| 深度时序网络      | 极强           | 中层              | 适用于万级 IP 等高并发、海量序列 化日志的内网端点检测场景      | 极低       | 缺乏宏观拓扑感知；对非结构化 文本情报毫无处理能力                      | 自动化高速链 路补全、实时 阻断    |
| 图谱与图神经 网络 | 强             | 深层              | 适用于多源异构数据（资产、漏洞、 用户）交织的复杂 APT 捕获场景 | 高         | 知识图谱构建的人工成本极高； 大规模图卷积运算实时性较差                | 复杂 APT 溯源 补全、可解释 性预测 |
| 大语言模型        | 强             | 深层              | 专精于顶层非结构化 CTI 文本解析、 以及晦涩底层规则的语义转译   | 较高       | 上下文窗口限制影响超长报告处 理；大模型固有 ' 幻觉 ' 导致校验 成本增加 | 自动化情报解 析、防御策略 转译    |

颈。大语言模型的引入为缓解该问题提供了新路径。 例如， TTParser 框架 [27] 针对单一节点预测的局限， 其内置的过程生成模块利用少样本提示显式建模了 攻击技术的程序化关系。通过深度融合上下文语义， 该方法尝试将离散识别的 TTP 按步骤重构为连贯的 攻击叙事，为自动化攻击链溯源与补全提供了一种 兼具较高精度与可解释性的解决方案。

## 3.2 攻击意图预测

意图预测与链路补全是一体两面的任务，其核 心在于基于当前观测到的初始入侵或横向移动行为， 预测 ' 攻击者最有可能的下一步操作 ' ，从而辅助主 动防御。对于这一任务，缺乏时序感知能力的简单 统计共现方法往往难以胜任，通常需依托具备序列 建模或图推理能力的复杂模型。

针对复杂的多步高级持续性威胁，近期的前沿 研究开始采用深度序列模型与复杂图网络对意图进 行细粒度预测。例如， DeepOP 框架 [22] 引入 Transformer 架构对 ATT&amp;CK 序列进行建模，通过捕捉序 列中的局部因果关系与全局时序依赖，以期在工业 物联网等复杂场景下实现对攻击者未来技战术动向 的有效预测。同时，为了兼顾预测结果的可解释性 与阶段连贯性， KillChainGraph 框架 [23] 引入宏观攻击 链作为上下文约束，结合有向图模型追踪攻击行为 轨迹。这种图驱动的多模型集成预测方法不仅在各 攻击阶段表现出较好的预测性能，还提供了相对直 观的攻击路径推演，提升了意图预测任务在实战中 的辅助决策价值。

## 3.3 防御与检测优化

防御与检测优化的最终目标，是将技术关联与 意图预测的理论成果转化为切实可行的安全策略， 以缩短应急响应闭环并降低系统风险。在这一任务 中，各类方法的实战适配度主要体现在其实时处理 能力、自动化程度以及与高层决策的对接能力上。

在企业级防御优化中，部分技术关联模型正逐步 尝试工业级落地。例如，研究人员将 ATT&amp;CK 框架 与 LSTM 时序预测算法相融合，并依托 Go 语言构建 高并发暴露面检测系统 [17] ，该系统在万级 IP 规模的 内网实测中表现出较高的执行效能，其特定实验评 估显示，该系统可将风险响应时间大幅缩减至传统 工具的三分之一。此外，为减轻一线安全运营人员 的认知负担，文献 [26] 通过整合大语言模型与检索 增强生成技术，尝试将底层网络入侵检测（如 Snort ） 规则自动转译，并扩展为 ATT&amp;CK 框架下的多标签 攻击描述。这种自动化转译旨在提升孤立告警的可

解释性，为防御团队提供具备实战指导价值的威胁 上下文。在宏观决策层面，文献 [16] 研究表明，通 过应用贝叶斯统计方法实时处理威胁情报，防御系 统能够动态重新计算各主机的危害后验概率并生成 实时风险仪表盘，为填补底层技术风险数据与组织 级安全决策之间的信息脱节提供了量化支撑。

## 4 结束语

本文系统梳理了 ATT&amp;CK 框架下技术关联分析 的发展脉络，明确界定了该研究范式的内涵与边界。 通过建立 ' 对上下文及时间序列依赖建模深度 ' 的递 进式分类框架，本文全面对比了静态模式挖掘、动 态时序演进以及高阶语义挖掘三类方法，并深入探 讨了它们在攻击链路补全、意图预测与防御检测优 化三大下游任务中的适配性与应用价值。

尽管当前技术关联研究在算法精度与工程落地 上均取得了显著进展，但面对日益隐蔽、复杂的 APT 攻击与海量多源异构数据，现有方法在泛化能 力与语义对齐上仍显局限。基于本文对各方法瓶颈 的横向剖析，未来技术关联分析的研究可重点聚焦 于以下 3 个方向。

1 ）面向高对抗环境的动态上下文细粒度建模： 本文分析表明，当前的概率图与深度时序模型虽能 捕捉序列依赖，但其上下文特征向量往往是静态且 粗粒度的。未来的研究需要从 ' 孤立标签流转 ' 向 ' 动态上下文感知 ' 演进。例如，在预测技术转移时， 不仅要考虑时间序列，还需动态引入目标系统的实 时漏洞状态、防御策略变更以及攻击者的阶段性收 益反馈，从而构建对高对抗环境具有更强鲁棒性的 细粒度预测模型。

2 ）跨模态威胁情报与异构拓扑的深度融合：目 前的方法在数据依赖上存在明显的边界局限，图模 型专精于底层拓扑，而 NLP 技术局限于顶层文本。 真实的网络攻击往往同时遗留跨模态线索（如非结 构化的开源情报与高度结构化的内网流量告警）。 因此，未来的研究应致力于打破模态壁垒，探索多 模态表示学习架构，实现从底层物理 IP/ 资产告警到 顶层抽象 TTP 战术的无缝映射与语义对齐。

大语言模型与知识图谱的神经符号协同：针对 当前孤立节点预测在可解释性上的痛点，尽管最新 研究已初步证实了 LLM 在少样本意图重构与底层规 则转译中的巨大潜力，但纯生成式模型依然面临严 重的 ' 幻觉 ' 风险与长文本遗忘问题。未来，一个重 要的演进方向是构建 ' 大模型 + 知识图谱 ' 的神经符号

协同范式：利用 LLM 强大的泛化理解能力处理非结 构化 CTI 的冷启动抽取，同时利用知识图谱的严格 本体逻辑对 LLM 的生成推理过程进行图结构约束与 事实校验，从而实现高精度、高可解释且高度自动 化的端到端攻击链关联溯源。

## 参考文献：

- MITRE. Corporate overview of the MITRE corporation[EB/OL]. [2025-05-29] https://www.mitre.org/about/corporate-overview. ［ 1 ］
- MITRE. ATT&amp;CK. [EB/OL]. [2025-05-29]. https://attack.mitre. org. ［ 2 ］
- Al-shaer  R ， Spring  J  M ， Christou E.  Learning  the   associations  of  MITRE  ATT  &amp;  CK  adversarial  techniques[C]//Proceedings of the 2020 IEEE Conference on Communications and Network Security （ CNS ） . Piscataway ： IEEE Press ， 2020 ： 1-9. ［ 3 ］
- Shannon C E. A mathematical theory of communication[J]. Bell System Technical Journal ， 1948 ， 27 （ 3 ）： 379-423. ［ 4 ］
- Wang W H ， Tang B F ， Zhu C ， et al. Clustering using a similarity measure  approach  based  on  semantic  analysis  of   adversary behaviors[C]//Proceedings of the 2020 IEEE Fifth International  Conference  on  Data  Science  in  Cyberspace （ DSC ） . Piscataway ： IEEE Press ， 2020 ： 1-7. ［ 5 ］
- Ding Z Y ， Cao D Q ， Liu L N ， et al. A method for discovering hidden patterns of cybersecurity knowledge based on hierarchical clustering[C]//Proceedings of the 2021 IEEE Sixth International Conference on Data Science in Cyberspace （ DSC ） . Piscataway ： IEEE Press ， 2021 ： 334-338. ［ 6 ］
- Abu M S ， Rahayu S ， Yusof R ， et al. An attribution of cyberattack using association rule mining （ ARM ） [J]. International  Journal  of  Advanced  Computer  Science  and  Applications ， 2020 ， 11 （ 2 ） . ［ 7 ］
- McKee C ， Edie K ， Duby A. Activity-attack graphs for intelligence-informed  threat  COA  development[C]//Proceedings  of the  2023  IEEE  13th  Annual  Computing  and  Communication Workshop  and  Conference （ CCWC ） .  Piscataway ： IEEE Press ， 2023 ： 598-604. ［ 8 ］
- Wang X Y ， Li R L ， Luo L ， et al. Construction and application of attack tactics and tactics system for intelligent connected vehicles[M]//Cyberspace Simulation and Evaluation. SingaporeSpringer Nature Singapore2025 ： 444-460. ［ 9 ］
- Zang X D ， Gong J ， Zhang X C ， et al. Attack scenario reconstruction  via  fusing  heterogeneous  threat  intelligence[J].  Computers &amp; Security ， 2023 ， 133 ： 103420. ［ 10 ］
- Rahman  M  R ， Williams  L.  Investigating  co-occurrences  of ［ 11 ］
- MITRE ATT\&amp;CK techniques[PP/OL]. V1. arXiv （ 2022-1111 ） [2025-05-29]. https://doi.org/10.48550/arXiv.2211.06495.
- Luna J M ， Fournier-viger P ， Ventura S. Frequent itemset mining ： a  25  years  review[J].  WIREs Data  Mining  and   Knowledge Discovery ， 2019 ， 9 （ 6 ）： e1329. ［ 12 ］
- Kumbhare T A ， CHOBE S V. An overview of association rule mining  algorithms[J].  International Journal  of  Computer   Science and Information Technologies ， 2014 ， 5 （ 1 ）： 927-930. ［ 13 ］
- Zhang  J  C ， Zheng  J ， Zhang  Z ， et  al.  ATT&amp;CK-based  advanced  persistent  threat  attacks  risk  propagation  assessment model for zero trust networks[J]. Computer Networks ， 2024 ， 245 ： 110376. ［ 14 ］
- Choi S ， Yun J H ， Min B G. Probabilistic attack sequence generation  and  execution  based  on  MITRE  ATT&amp;CK  for  ICS datasets[C]//Proceedings of  the  Cyber  Security   Experimentation and Test Workshop. New York ： ACM ， 2021 ： 41-48 ［ 15 ］
- Maccarone L T ， Valme R ， Anaya T R. Bayesian attack model (BAM) user story[R]. Sandia National Laboratories （ SNLNM ）， Albuquerque ， NM （ United States ）， 2025. ［ 16 ］
- Cai W X ， Shi R J ， Ye J X ， et al. Enterprise internal network asset  exposure  risk  detection  system  based  on  go  language ， ATT&amp;CK  framework  and  LSTM  time-series  prediction[C]// Proceedings of the 2025 10th International Conference on Cyber Security and Information Engineering （ ICCSIE ） . Piscataway ： IEEE Press ， 2025 ： 28-35. ［ 17 ］
- Lukade  R  R.  Attack  chain  contraction  and  prediction  using Markov model and LSTM on MITRE ATT&amp;CK data ： a thesis in  data  science[D].  University  of  Massachusetts  Dartmouth ， 2025. ［ 18 ］
- Chen H Y ， Rao S P. Adversarial trends in mobile communication systems ： from attack patterns to potential defenses strategies[M]//Secure  IT  Systems.  Cham ： Springer  International Publishing ， 2021 ： 153-171 ［ 19 ］
- Qi Y L ， Gu Z Q ， Li A P ， et al. RETRACTED ： Cybersecurity  knowledge  graph  enabled  attack  chain  detection  for  cyberphysical  systems[J].  Computers  and  Electrical  Engineering ， 2023 ， 108 ： 108660. ［ 20 ］
- Zhu T T ， Ying J ， Chen T M ， et al. Nip in the bud ： forecasting and interpreting post-exploitation attacks in real-time through cyber threat intelligence reports[J]. IEEE Transactions on  Dependable  and  Secure  Computing ， 2025 ， 22 （ 2 ）： 1431-1447. ［ 21 ］
- Zhang S Q ， Xue X H ， Su X Y. DeepOP ： a hybrid   framework for MITRE ATT&amp;CK sequence prediction via deep learning and ontology[J]. Electronics ， 2025 ， 14 （ 2 ）： 257. ［ 22 ］
- Singh C ， Dhanraj M ， Huang K. KillChainGraph ： ML frame-［ 23 ］

- work for predicting and mapping ATT&amp;CK techniques[PP/OL]. V1.  arXiv  [2025-08-19].  https://doi.org/10.48550/arXiv.2508. 18230.
- Huang Y T ， Lin C Y ， Guo Y R ， et al. Open source intelligence  for  malicious  behavior  discovery  and  interpretation[J]. IEEE  Transactions  on  Dependable  and  Secure  Computing ， 2022 ， 19 （ 2 ）： 776-789. ［ 24 ］
- Zhu Z F ， An Q ， Li S D ， et al. Network security situational assessment based on the ATT&amp;CK tactics framework and transformer model[C]//Network  Simulation  and  Evaluation.   Singapore ： Springer ， 2024 ： 106-119. ［ 25 ］
- Lee Y H ， Han C S ， Peng M C ， et al. LLM-based multi-label ［ 26 ］
- mapping  of  snort  rules  to  ATT&amp;CK[C]//Proceedings  of  the 2025 IEEE Conference on Dependable and Secure Computing （ DSC ） . Piscataway ： IEEE Press ， 2025 ： 1-6.
- Cai Y X ， Zhou H C ， Wang Z Y ， et al. TTParser ： leveraging  LLM  for  enhanced  mapping  of  ATT&amp;CK  tactics ， techniques ， and procedures  in  unstructured  cyber  threat   intelligence[C]//Proceedings of the IEEE International Conference on Big  Data  and  Smart  Computing （ BigComp ） .  Piscataway ： IEEE Press. ［ 27 ］
- Skjøtskift  G ， Eian  M ， Bromander  S.  Automated  ATT&amp;CK technique chaining[J]. Digital Threats ： Research and Practice ， 2025 ， 6 （ 1 ）： 1-11. ［ 28 ］