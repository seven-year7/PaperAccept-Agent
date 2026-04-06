---

## RAG 召回实录

- **UTC**: 2026-04-06T05:15:59.704840+00:00
- **request_id**: 15bbe33638724fce89b718fb10d28f36
- **session_id**: session_l3vjai9s9_1775451754846
- **tenant_id**: test
- **retrieve_query**: openclaw 相关论文
- **below_threshold**（低置信门控）: True
- **RAG_HYBRID_ENABLED**: False
- **RAG_HIERARCHICAL_CHUNKS_ENABLED**: True

### 模型侧上下文（format_docs，融合后 top_k）

```text
【参考资料 1】
标题: OpenClaw 相关论文调研报告 > OpenClaw 框架概述 > OpenClaw 的核心功能与架构
来源: report.md
距离(L2): 0.7270452976226807
内容:
# OpenClaw 相关论文调研报告  
## OpenClaw 框架概述  
### OpenClaw 的核心功能与架构  
OpenClaw 作为一个开源本地 AI 代理框架，由大型语言模型（LLM）驱动，支持代理自主执行复杂任务，包括 shell 命令调用、工具链交互、内存检索和技能生态扩展。其架构强调高权限执行和紧耦合即时消息交互，赋予代理 OS 级权限，实现个性化场景下的长时程交互和真实工具链支持。例如，在个性化代理安全评估中，OpenClaw 被用于处理用户提示、工具使用和内存检索等阶段，展示其在真实部署中的端到端能力（[From Assistant to Double Agent](http://arxiv.org/abs/2602.08412v2)）。

【参考资料 2】
标题: OpenClaw 相关论文调研报告 > OpenClaw 框架概述 > 研究热点与挑战
来源: report.md
距离(L2): 0.7427380084991455
内容:
### 研究热点与挑战  
当前研究热点聚焦 OpenClaw 的安全漏洞和防御策略，多篇工作揭示其在初始化、输入、推理、决策和执行生命周期的复合威胁，如提示注入、工具调用链攻击、sandbox 逃逸和供应链污染，平均原生防御率仅 17%（[Don't Let the Claw Grip Your Hand](http://arxiv.org/abs/2603.10387v1)；[Taming OpenClaw](http://arxiv.org/abs/2603.11619v1)；[Uncovering Security Threats](http://arxiv.org/abs/2603.12644v1)）。创新防御包括五层生命周期框架、三层风险分类法、HITL 层和 MITM-based 红队评估，提升防御率至 92%，并开源工具如 ClawGuard 和 PASB（[ClawTrap](http://arxiv.org/abs/2603.18762v1)；[Defensible Design](http://arxiv.org/abs/2603.13151v1)）。用户行为研究则通过 CAC 框架分析隐私担忧对采用意图的影响，强调心理机制优化（[Examining Users' Behavioural Intention](http://arxiv.org/abs/2603.11455v2)）。  
尽管 OpenClaw 在功能和应用上表现出色，但其高权限执行特性也引入了显著的安全风险。以下章节将系统剖析这些漏洞及其攻击机制。

【参考资料 3】
标题: OpenClaw 相关论文调研报告 > 结论与展望 > 关键发现总结
来源: report.md
距离(L2): 0.7588655948638916
内容:
## 结论与展望  
### 关键发现总结  
OpenClaw作为开源本地AI代理框架，在个性化任务处理、工具调用链和自主执行方面展现潜力，但多项研究揭示其安全风险显著高于预期。如PASB基准评估显示，OpenClaw在用户提示处理、工具使用和内存检索阶段存在关键漏洞，支持黑盒端到端攻击测试（2602.08412）。Clawdrain攻击利用技能注入实现6-7倍token耗尽放大，暴露工具链生产向量（2603.00902）。此外，安全分析暴露sandbox逃逸、prompt注入、意图漂移和供应链污染等复合威胁，原生防御率仅17%（2603.10387、2603.11619）。用户行为研究通过CAC框架证实，隐私担忧和感知风险抑制采用意图（2603.11455）。正面应用包括OpenClaw-RL的实时学习机制和计算化学自动化（2603.10165、2603.25522），但均需安全强化。

【参考资料 4】
标题: OpenClaw 相关论文调研报告 > OpenClaw 的安全漏洞与攻击 > OpenClaw的安全风险概述
来源: report.md
距离(L2): 0.7761808633804321
内容:
## OpenClaw 的安全漏洞与攻击  
### OpenClaw的安全风险概述  
多篇论文系统揭示了OpenClaw作为开源本地AI代理框架的固有安全漏洞，这些漏洞源于其高权限执行（如shell命令）、工具调用链、个性化交互和真实工具链集成。在真实部署中，OpenClaw易受复合攻击影响，包括提示注入驱动的远程代码执行（RCE）、token耗尽、内存中毒和供应链污染，现有点防御（如内容过滤）往往失效，导致严重风险传播（2602.08412；2603.10387；2603.11619；2603.12644）。

【参考资料 5】
标题: OpenClaw 相关论文调研报告 > OpenClaw 的防御策略与框架 > OpenClaw 防御策略概述
来源: report.md
距离(L2): 0.8315394520759583
内容:
## OpenClaw 的防御策略与框架  
### OpenClaw 防御策略概述  
OpenClaw作为开源本地AI代理框架，在赋予代理高权限工具调用能力的同时，暴露了显著的安全漏洞，包括提示注入、工具链攻击和内存污染等多阶段威胁。现有研究提出多种防御策略，如人机协作机制、生命周期框架和零信任架构，旨在从架构、执行和验证层面缓解风险。这些方法通过系统评估和实证验证，揭示了原生防御的不足（如平均防御率仅17%），并提升整体鲁棒性，但仍面临跨阶段复合威胁的挑战。

```

### BM25 / ES 全量候选（Elasticsearch 融合前，按相关度排名）

*当前 `RAG_HYBRID_ENABLED=false`，未执行独立 ES 召回列表。*

### 融合后条目（含向量 / BM25 来源标注）

#### 融合后条目 1

- **_chunk_id**: d7bee46c-b69a-417f-8b14-7e2d9219d2a4
- **_retrieve_source**: 
- **L2**: 0.7270452976226807
- **_file_name**: report.md

**正文**:

```
# OpenClaw 相关论文调研报告  
## OpenClaw 框架概述  
### OpenClaw 的核心功能与架构  
OpenClaw 作为一个开源本地 AI 代理框架，由大型语言模型（LLM）驱动，支持代理自主执行复杂任务，包括 shell 命令调用、工具链交互、内存检索和技能生态扩展。其架构强调高权限执行和紧耦合即时消息交互，赋予代理 OS 级权限，实现个性化场景下的长时程交互和真实工具链支持。例如，在个性化代理安全评估中，OpenClaw 被用于处理用户提示、工具使用和内存检索等阶段，展示其在真实部署中的端到端能力（[From Assistant to Double Agent](http://arxiv.org/abs/2602.08412v2)）。
```

#### 融合后条目 2

- **_chunk_id**: 65859384-e832-40d9-9f86-495ae6818ac8
- **_retrieve_source**: 
- **L2**: 0.7427380084991455
- **_file_name**: report.md

**正文**:

```
### 研究热点与挑战  
当前研究热点聚焦 OpenClaw 的安全漏洞和防御策略，多篇工作揭示其在初始化、输入、推理、决策和执行生命周期的复合威胁，如提示注入、工具调用链攻击、sandbox 逃逸和供应链污染，平均原生防御率仅 17%（[Don't Let the Claw Grip Your Hand](http://arxiv.org/abs/2603.10387v1)；[Taming OpenClaw](http://arxiv.org/abs/2603.11619v1)；[Uncovering Security Threats](http://arxiv.org/abs/2603.12644v1)）。创新防御包括五层生命周期框架、三层风险分类法、HITL 层和 MITM-based 红队评估，提升防御率至 92%，并开源工具如 ClawGuard 和 PASB（[ClawTrap](http://arxiv.org/abs/2603.18762v1)；[Defensible Design](http://arxiv.org/abs/2603.13151v1)）。用户行为研究则通过 CAC 框架分析隐私担忧对采用意图的影响，强调心理机制优化（[Examining Users' Behavioural Intention](http://arxiv.org/abs/2603.11455v2)）。  
尽管 OpenClaw 在功能和应用上表现出色，但其高权限执行特性也引入了显著的安全风险。以下章节将系统剖析这些漏洞及其攻击机制。
```

#### 融合后条目 3

- **_chunk_id**: e2d00e48-ab11-4e46-8afc-32beec483612
- **_retrieve_source**: 
- **L2**: 0.7588655948638916
- **_file_name**: report.md

**正文**:

```
## 结论与展望  
### 关键发现总结  
OpenClaw作为开源本地AI代理框架，在个性化任务处理、工具调用链和自主执行方面展现潜力，但多项研究揭示其安全风险显著高于预期。如PASB基准评估显示，OpenClaw在用户提示处理、工具使用和内存检索阶段存在关键漏洞，支持黑盒端到端攻击测试（2602.08412）。Clawdrain攻击利用技能注入实现6-7倍token耗尽放大，暴露工具链生产向量（2603.00902）。此外，安全分析暴露sandbox逃逸、prompt注入、意图漂移和供应链污染等复合威胁，原生防御率仅17%（2603.10387、2603.11619）。用户行为研究通过CAC框架证实，隐私担忧和感知风险抑制采用意图（2603.11455）。正面应用包括OpenClaw-RL的实时学习机制和计算化学自动化（2603.10165、2603.25522），但均需安全强化。
```

#### 融合后条目 4

- **_chunk_id**: bb8cb9cd-d9a3-4579-b89f-ca1c4f46d39f
- **_retrieve_source**: 
- **L2**: 0.7761808633804321
- **_file_name**: report.md

**正文**:

```
## OpenClaw 的安全漏洞与攻击  
### OpenClaw的安全风险概述  
多篇论文系统揭示了OpenClaw作为开源本地AI代理框架的固有安全漏洞，这些漏洞源于其高权限执行（如shell命令）、工具调用链、个性化交互和真实工具链集成。在真实部署中，OpenClaw易受复合攻击影响，包括提示注入驱动的远程代码执行（RCE）、token耗尽、内存中毒和供应链污染，现有点防御（如内容过滤）往往失效，导致严重风险传播（2602.08412；2603.10387；2603.11619；2603.12644）。
```

#### 融合后条目 5

- **_chunk_id**: 0e5e17b5-52d7-4ca4-8da8-aebd525400f2
- **_retrieve_source**: 
- **L2**: 0.8315394520759583
- **_file_name**: report.md

**正文**:

```
## OpenClaw 的防御策略与框架  
### OpenClaw 防御策略概述  
OpenClaw作为开源本地AI代理框架，在赋予代理高权限工具调用能力的同时，暴露了显著的安全漏洞，包括提示注入、工具链攻击和内存污染等多阶段威胁。现有研究提出多种防御策略，如人机协作机制、生命周期框架和零信任架构，旨在从架构、执行和验证层面缓解风险。这些方法通过系统评估和实证验证，揭示了原生防御的不足（如平均防御率仅17%），并提升整体鲁棒性，但仍面临跨阶段复合威胁的挑战。
```

---

## RAG 召回实录

- **UTC**: 2026-04-06T05:16:55.189088+00:00
- **request_id**: af3b469cb7ed4925bc4ee6a7831237ca
- **session_id**: session_1gnt1ap7m_1775452583668
- **tenant_id**: test
- **retrieve_query**: openclaw related papers
- **below_threshold**（低置信门控）: True
- **RAG_HYBRID_ENABLED**: False
- **RAG_HIERARCHICAL_CHUNKS_ENABLED**: True

### 模型侧上下文（format_docs，融合后 top_k）

```text
【参考资料 1】
标题: OpenClaw 相关论文调研报告 > OpenClaw 框架概述 > OpenClaw 的核心功能与架构
来源: report.md
距离(L2): 0.8452922105789185
内容:
# OpenClaw 相关论文调研报告  
## OpenClaw 框架概述  
### OpenClaw 的核心功能与架构  
OpenClaw 作为一个开源本地 AI 代理框架，由大型语言模型（LLM）驱动，支持代理自主执行复杂任务，包括 shell 命令调用、工具链交互、内存检索和技能生态扩展。其架构强调高权限执行和紧耦合即时消息交互，赋予代理 OS 级权限，实现个性化场景下的长时程交互和真实工具链支持。例如，在个性化代理安全评估中，OpenClaw 被用于处理用户提示、工具使用和内存检索等阶段，展示其在真实部署中的端到端能力（[From Assistant to Double Agent](http://arxiv.org/abs/2602.08412v2)）。

【参考资料 2】
标题: OpenClaw 相关论文调研报告 > OpenClaw 框架概述 > 研究热点与挑战
来源: report.md
距离(L2): 0.879164457321167
内容:
### 研究热点与挑战  
当前研究热点聚焦 OpenClaw 的安全漏洞和防御策略，多篇工作揭示其在初始化、输入、推理、决策和执行生命周期的复合威胁，如提示注入、工具调用链攻击、sandbox 逃逸和供应链污染，平均原生防御率仅 17%（[Don't Let the Claw Grip Your Hand](http://arxiv.org/abs/2603.10387v1)；[Taming OpenClaw](http://arxiv.org/abs/2603.11619v1)；[Uncovering Security Threats](http://arxiv.org/abs/2603.12644v1)）。创新防御包括五层生命周期框架、三层风险分类法、HITL 层和 MITM-based 红队评估，提升防御率至 92%，并开源工具如 ClawGuard 和 PASB（[ClawTrap](http://arxiv.org/abs/2603.18762v1)；[Defensible Design](http://arxiv.org/abs/2603.13151v1)）。用户行为研究则通过 CAC 框架分析隐私担忧对采用意图的影响，强调心理机制优化（[Examining Users' Behavioural Intention](http://arxiv.org/abs/2603.11455v2)）。  
尽管 OpenClaw 在功能和应用上表现出色，但其高权限执行特性也引入了显著的安全风险。以下章节将系统剖析这些漏洞及其攻击机制。

【参考资料 3】
标题: OpenClaw 相关论文调研报告 > 结论与展望 > 关键发现总结
来源: report.md
距离(L2): 0.9055504202842712
内容:
## 结论与展望  
### 关键发现总结  
OpenClaw作为开源本地AI代理框架，在个性化任务处理、工具调用链和自主执行方面展现潜力，但多项研究揭示其安全风险显著高于预期。如PASB基准评估显示，OpenClaw在用户提示处理、工具使用和内存检索阶段存在关键漏洞，支持黑盒端到端攻击测试（2602.08412）。Clawdrain攻击利用技能注入实现6-7倍token耗尽放大，暴露工具链生产向量（2603.00902）。此外，安全分析暴露sandbox逃逸、prompt注入、意图漂移和供应链污染等复合威胁，原生防御率仅17%（2603.10387、2603.11619）。用户行为研究通过CAC框架证实，隐私担忧和感知风险抑制采用意图（2603.11455）。正面应用包括OpenClaw-RL的实时学习机制和计算化学自动化（2603.10165、2603.25522），但均需安全强化。

【参考资料 4】
标题: OpenClaw 相关论文调研报告 > OpenClaw 的安全漏洞与攻击 > OpenClaw的安全风险概述
来源: report.md
距离(L2): 0.9197976589202881
内容:
## OpenClaw 的安全漏洞与攻击  
### OpenClaw的安全风险概述  
多篇论文系统揭示了OpenClaw作为开源本地AI代理框架的固有安全漏洞，这些漏洞源于其高权限执行（如shell命令）、工具调用链、个性化交互和真实工具链集成。在真实部署中，OpenClaw易受复合攻击影响，包括提示注入驱动的远程代码执行（RCE）、token耗尽、内存中毒和供应链污染，现有点防御（如内容过滤）往往失效，导致严重风险传播（2602.08412；2603.10387；2603.11619；2603.12644）。

【参考资料 5】
标题: OpenClaw 相关论文调研报告 > OpenClaw 框架概述 > 发展背景与在代理领域的地位
来源: report.md
距离(L2): 0.9483280181884766
内容:
### 发展背景与在代理领域的地位  
OpenClaw 源于 LLM 代理向自主工具调用演进的趋势，其开放社区技能生态快速增长，超过传统系统安全评估，推动代理从合成任务向真实世界个性化应用转型。作为本地框架，它填补了现有 agentic RL 系统将对话、终端执行、GUI 交互和工具调用视为分离问题的空白，支持 next-state signals 的实时在线学习（[OpenClaw-RL](http://arxiv.org/abs/2603.10165v1)）。在工具调用领域，OpenClaw 地位突出，代理可组合通用工具如 shell/Python，实现多轮协议和生产-like 部署，但也暴露 token 耗尽和攻击向量风险（[Clawdrain](http://arxiv.org/abs/2603.00902v1)）。

```

### BM25 / ES 全量候选（Elasticsearch 融合前，按相关度排名）

*当前 `RAG_HYBRID_ENABLED=false`，未执行独立 ES 召回列表。*

### 融合后条目（含向量 / BM25 来源标注）

#### 融合后条目 1

- **_chunk_id**: d7bee46c-b69a-417f-8b14-7e2d9219d2a4
- **_retrieve_source**: 
- **L2**: 0.8452922105789185
- **_file_name**: report.md

**正文**:

```
# OpenClaw 相关论文调研报告  
## OpenClaw 框架概述  
### OpenClaw 的核心功能与架构  
OpenClaw 作为一个开源本地 AI 代理框架，由大型语言模型（LLM）驱动，支持代理自主执行复杂任务，包括 shell 命令调用、工具链交互、内存检索和技能生态扩展。其架构强调高权限执行和紧耦合即时消息交互，赋予代理 OS 级权限，实现个性化场景下的长时程交互和真实工具链支持。例如，在个性化代理安全评估中，OpenClaw 被用于处理用户提示、工具使用和内存检索等阶段，展示其在真实部署中的端到端能力（[From Assistant to Double Agent](http://arxiv.org/abs/2602.08412v2)）。
```

#### 融合后条目 2

- **_chunk_id**: 65859384-e832-40d9-9f86-495ae6818ac8
- **_retrieve_source**: 
- **L2**: 0.879164457321167
- **_file_name**: report.md

**正文**:

```
### 研究热点与挑战  
当前研究热点聚焦 OpenClaw 的安全漏洞和防御策略，多篇工作揭示其在初始化、输入、推理、决策和执行生命周期的复合威胁，如提示注入、工具调用链攻击、sandbox 逃逸和供应链污染，平均原生防御率仅 17%（[Don't Let the Claw Grip Your Hand](http://arxiv.org/abs/2603.10387v1)；[Taming OpenClaw](http://arxiv.org/abs/2603.11619v1)；[Uncovering Security Threats](http://arxiv.org/abs/2603.12644v1)）。创新防御包括五层生命周期框架、三层风险分类法、HITL 层和 MITM-based 红队评估，提升防御率至 92%，并开源工具如 ClawGuard 和 PASB（[ClawTrap](http://arxiv.org/abs/2603.18762v1)；[Defensible Design](http://arxiv.org/abs/2603.13151v1)）。用户行为研究则通过 CAC 框架分析隐私担忧对采用意图的影响，强调心理机制优化（[Examining Users' Behavioural Intention](http://arxiv.org/abs/2603.11455v2)）。  
尽管 OpenClaw 在功能和应用上表现出色，但其高权限执行特性也引入了显著的安全风险。以下章节将系统剖析这些漏洞及其攻击机制。
```

#### 融合后条目 3

- **_chunk_id**: e2d00e48-ab11-4e46-8afc-32beec483612
- **_retrieve_source**: 
- **L2**: 0.9055504202842712
- **_file_name**: report.md

**正文**:

```
## 结论与展望  
### 关键发现总结  
OpenClaw作为开源本地AI代理框架，在个性化任务处理、工具调用链和自主执行方面展现潜力，但多项研究揭示其安全风险显著高于预期。如PASB基准评估显示，OpenClaw在用户提示处理、工具使用和内存检索阶段存在关键漏洞，支持黑盒端到端攻击测试（2602.08412）。Clawdrain攻击利用技能注入实现6-7倍token耗尽放大，暴露工具链生产向量（2603.00902）。此外，安全分析暴露sandbox逃逸、prompt注入、意图漂移和供应链污染等复合威胁，原生防御率仅17%（2603.10387、2603.11619）。用户行为研究通过CAC框架证实，隐私担忧和感知风险抑制采用意图（2603.11455）。正面应用包括OpenClaw-RL的实时学习机制和计算化学自动化（2603.10165、2603.25522），但均需安全强化。
```

#### 融合后条目 4

- **_chunk_id**: bb8cb9cd-d9a3-4579-b89f-ca1c4f46d39f
- **_retrieve_source**: 
- **L2**: 0.9197976589202881
- **_file_name**: report.md

**正文**:

```
## OpenClaw 的安全漏洞与攻击  
### OpenClaw的安全风险概述  
多篇论文系统揭示了OpenClaw作为开源本地AI代理框架的固有安全漏洞，这些漏洞源于其高权限执行（如shell命令）、工具调用链、个性化交互和真实工具链集成。在真实部署中，OpenClaw易受复合攻击影响，包括提示注入驱动的远程代码执行（RCE）、token耗尽、内存中毒和供应链污染，现有点防御（如内容过滤）往往失效，导致严重风险传播（2602.08412；2603.10387；2603.11619；2603.12644）。
```

#### 融合后条目 5

- **_chunk_id**: 29750549-cbde-46c6-a3ed-29ef90587851
- **_retrieve_source**: 
- **L2**: 0.9483280181884766
- **_file_name**: report.md

**正文**:

```
### 发展背景与在代理领域的地位  
OpenClaw 源于 LLM 代理向自主工具调用演进的趋势，其开放社区技能生态快速增长，超过传统系统安全评估，推动代理从合成任务向真实世界个性化应用转型。作为本地框架，它填补了现有 agentic RL 系统将对话、终端执行、GUI 交互和工具调用视为分离问题的空白，支持 next-state signals 的实时在线学习（[OpenClaw-RL](http://arxiv.org/abs/2603.10165v1)）。在工具调用领域，OpenClaw 地位突出，代理可组合通用工具如 shell/Python，实现多轮协议和生产-like 部署，但也暴露 token 耗尽和攻击向量风险（[Clawdrain](http://arxiv.org/abs/2603.00902v1)）。
```

