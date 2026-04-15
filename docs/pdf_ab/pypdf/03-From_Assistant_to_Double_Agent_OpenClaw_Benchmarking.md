FROMASSISTANT TODOUBLEAGENT:FORMALIZING
AND BENCHMARKING ATTACKS ON OPENCLAW FOR
PERSONALIZEDLOCALAI AGENT.
Yuhang Wang1 Feiming Xu1 Zheng Lin1 Guangyu He1 Yuzhe Huang1
Haichang Gao1∗ Zhenxing Niu1 Shiguo Lian2 Zhaoxiang Liu2
1 Xidian University 2 Data Science & Artificial Intelligence Research Institute, China Unicom
ABSTRACT
Although large language model (LLM)-based agents, exemplified by OpenClaw,
are increasingly evolving from task-oriented systems into personalized AI assistants
for solving complex real-world tasks, their practical deployment also introduces
severe security risks. However, existing agent security research and evaluation
frameworks primarily focus on synthetic or task-centric settings, and thus fail
to accurately capture the attack surface and risk propagation mechanisms of per-
sonalized agents in real-world deployments. To address this gap, we propose
Personalized Agent Security Bench (PASB), an end-to-end security evaluation
framework tailored for real-world personalized agents. Building upon existing
agent attack paradigms, PASB incorporates personalized usage scenarios, realistic
toolchains, and long-horizon interactions, enabling black-box, end-to-end security
evaluation on real systems. Using OpenClaw as a representative case study, we
systematically evaluate its security across multiple personalized scenarios, tool
capabilities, and attack types. Our results indicate that OpenClaw exhibits critical
vulnerabilities at different execution stages, including user prompt processing, tool
usage, and memory retrieval, highlighting substantial security risks in personalized
agent deployments. The code is available at https://github.com/AstorYH/PASB.
1 INTRODUCTION
Large language model (LLM)-based agents have demonstrated remarkable capabilities in autonomous
reasoning, task planning, and interacting with external tools and environments to solve complex multi-
step tasks Wang et al. (2024); Yao et al. (2022); Schick et al. (2023). With rapid advances in model
capacity, inference efficiency, and deployment infrastructure, the application landscape of agents is
undergoing a notable shift. On the one hand, agents are increasingly being explored and piloted in
safety-critical domains such as financial services, healthcare, and autonomous driving to improve
automation and decision-making efficiency Wu et al. (2023); Singhal et al. (2025); Xu et al. (2024).
On the other hand, more notably, agents are increasingly evolving from task-oriented systems into
personalized AI assistantsthat operate continuously on behalf of individual users. Such personalized
agents typically integrate long-term interaction histories, private user context, and high-privilege
toolchains, enabling them to undertake longer-horizon and more complex real-world tasks in personal
communication, information management, and daily automation. Representative systems, exemplified
by the recently popular OpenClaw Steinberger (2025), indicate that real-world personalized agents
are transitioning from “demo-ready task agents” to “always-on personal assistants,” substantially
expanding the scope and impact of security failures.
However, this shift toward personalization fundamentally changes the security landscape of agentic
systems. While substantial progress has been made in improving agent capabilities, existing research
∗Corresponding author.
arXiv:2602.08412v2  [cs.AI]  11 Feb 2026

has largely emphasized effectiveness, generalization, and task completion performance Hong et al.
(2023); Wei et al. (2022), whereas security discussions and systematic evaluations for real-world
deployments remain relatively limited Zhan et al. (2024). Compared to traditional task-centric
agents Mialon et al. (2023), personalized agents exhibit three key properties:(i) persistent operation
and long-horizon interactions, where the agent works continuously across turns and sessions Park
et al. (2023);(ii) accumulation of private context, where the system holds or can access user-
sensitive assets such as interaction histories, files, contacts, and preferences; and(iii) high-privilege
tools and actionable capabilities, where the agent can invoke high-impact tools such as message
sending, file access, and account-level operations Schick et al. (2023). Together, these properties
significantly amplify the potential consequences of security failures: malicious inputs or abnormal
behaviors introduced at one stage of execution may persist over multiple interactions and propagate
along the agent action chain, ultimately causing unauthorized information disclosure, unsafe tool
invocation, or even long-term behavioral manipulation Greshake et al. (2023). Importantly, risks in
personalized settings are no longer limited to “undesired text generation” but may instead manifest as
“unsafe actions being executed” or “private assets being exfiltrated through end-to-end interactions,”
requiring security evaluation to go beyond output-level analysis toward action-chain and system-level
assessment.
Although a growing body of work has investigated agent security and proposed benchmark frame-
works,e.g., Agent Security Bench (ASB) systematically categorizes and evaluates attack paradigms
such as prompt injection, indirect injection, tool misuse, and memory poisoning Zhang et al. (2025),
existing efforts are often built on controlled, white-box, or synthetic environments, typically re-
lying on custom agent implementations and custom tool interfaces to enable instrumented exper-
iments Debenedetti et al. (2024). While such designs offer important methodological value, a
significant gap remains when evaluatingreal-world deployed personalized agents. First, existing
benchmarks often lack explicit modeling of personalized usage scenarios, private assets, and high-
privilege toolchains, making it difficult to reflect the practical attack surface of personalized agents Liu
& Jabbarvand (2025). Second, prior evaluations commonly omit long-horizon interactions and cross-
stage propagation effects, failing to characterize how attacks persist and propagate across stages such
as prompt processing, external content access, tool invocation, and memory-related behaviors Feng
et al. (2026). Third, many benchmarks depend on instrumentable white-box implementations or sim-
plified tool environments, limiting the transferability of their findings to real deployed systems Deng
et al. (2023). These limitations prevent us from answering a critical question: under real deployment
conditions, what systematic security vulnerabilities do personalized agents like OpenClaw expose
during end-to-end execution, and how do these risks manifest and propagate along the action chain?
To bridge this gap, we proposePersonalized Agent Security Bench (PASB), an end-to-end security
evaluation framework for real-world personalized agents. PASB follows and extends the core ideas
of existing agent attack paradigms, and introduces three key enhancements in evaluation design:(i)
modeling personalized scenarios and private assets, by constructing representative usage scenarios
spanning personal communication, information management, and long-horizon task coordination, and
by providing auditable private assets under controlled settings (e.g., honey tokens and confidential
files Staab et al. (2023)) to enable measurable leakage criteria;(ii) realistic toolchains and a
controllable testbed environment, by simulating practical tool interactions via self-hosted web
testbeds and controllable tool services without relying on real production platforms or real users,
thereby covering typical risk sources such as observation-level malicious content, untrusted external
content, tool response manipulation, and memory-related poisoning Chen et al. (2024); and(iii) black-
box end-to-end evaluation with automated adjudicationZheng et al. (2023), by designing an
end-to-end testing harness that automatically drives inputs, records outputs and tool-invocation traces,
and quantifies system-level risks (including information leakage, unsafe actions, and persistence)
based on explicit harm criteria. In contrast to prior work that emphasizes controllable settings for
evaluating synthetic agents Liu et al. (2023); Mialon et al. (2023), PASB aims to assess the security
behavior of real deployed personalized agents in realistic operating conditions and to characterize
how risks propagate along the agent action chain.
We conduct a case study on OpenClaw by applying PASB to systematically evaluate its security
across multiple personalized scenarios, tool capabilities, and attack types. Our evaluation covers key
execution stages, including user prompt processing, external content access, tool invocation, and
memory-related behaviors, and analyzes the propagation and persistence of attacks under long-horizon
interactions. Experimental results (to be presented in Section 3) indicate that OpenClaw exhibits

Figure 1: Threat landscape of the Personalized LLM Agent. The agent interacts with an External
Environment (content hubs and tools) and maintains a Private Memory.
critical security vulnerabilities across multiple execution stages; attack behaviors can propagate
across stages and accumulate over extended interactions, posing tangible threats to the security
of personalized agent deployments. These findings suggest that relying solely on prompt-level
protections or security conclusions drawn from synthetic benchmarks may be insufficient to cover the
risks faced by real-world personalized agent systems.
Overall, our contributions can be summarized as follows:
• We propose PASB, an end-to-end security evaluation framework tailored for real-world
personalized AI assistants, enabling black-box and systematic evaluation under realistic
system configurations.
• We conduct a personalization-oriented security evaluation of OpenClaw, covering repre-
sentative scenarios, realistic toolchains, and long-horizon interactions, and reveal critical
vulnerabilities across multiple execution stages.
• We build a realistic evaluation environment and an automated evaluation pipeline, providing
a reproducible foundation and reference baseline for future research on the security of
personalized agent systems.
2 METHODS
2.1 PERSONALIZEDAGENTS
Personalized agent as a persistent, tool-using system.We model a personalized LLM-based agent
as a persistent system that repeatedly interacts with a single user, maintains evolving private context,
and executes actions through external tools on the user’s behalf. Letπu denote the distribution of user
requests for a user u. A personalized agent A is instantiated by a backbone language model L with
a system prompt psys, a tool set T={τ 1, . . . , τN } with privilege levels priv(τ) , and a long-term
memory store D. At step t, the agent receives an observation ot and produces an action at according
to the induced policy
πA(at |o t)≜L(a t |p sys, o t,T), a t ∈ Atext ∪ Atool,(1)
where Atext denotes natural-language responses and Atool denotes structured tool invocations.
The resulting interaction trajectory is τ= (o 1, a1, . . . , oT , aT ), with ot aggregating mixed-trust
information available at step t, including the user input, untrusted external content accessible to the
agent, tool outputs from previous steps, and memory items retrieved from long-term storage. We
model memory retrieval as
mt =R(o t,D),(2)
where R denotes the retrieval module and mt is incorporated into ot as in-context evidence for
decision making. Tools τ∈ T expose interfaces with varying privilege levels, enabling the agent

to perform actions beyond text generation, including high-impact operations over personal commu-
nication and private assets. This combination of persistent execution, private contextual state, and
high-privilege tool access fundamentally distinguishes personalized agents from task-centric agents
instantiated for isolated problem instances, and substantially expands the security attack surface of
deployed systems.
Backbone language model and long-horizon execution.Let L denote the backbone language
model parameterized by a system prompt. At each step t, the agent maps the current observation
ot to an action distribution according to a policy πA(at |o t) induced by L and the available tools.
The selected action is executed in the environment, producing new observations and potentially
updating the agent’s internal state and memory. Crucially, personalized agents maintain persistent
state across interaction steps and sessions, allowing information written at earlier stages to influence
future behavior. This long-horizon execution property enables personalized agents to adapt over time,
but also allows adversarial effects introduced at a single stage to propagate across actions, tools, and
memory, resulting in system-level security risks that cannot be captured by single-turn or resettable
agent formulations.
Attack Task Definition.PASB evaluates a deployed personalized agent A via a set of end-to-end
attack tasksthat aim to induce verifiable system-level harms during execution. An attack task is
defined as
Γ =⟨C,I,B,G,P⟩,
where C specifies the personalized scenario and initial context, including the available tool set T and
the long-term memory store D; I specifies the adversary-controllable inputs and injection channels
that can affect the agent’s observationsot; B specifies the interaction budget and constraints, including
the maximum horizon T ; G specifies the adversarial goal class; andP is a success predicate evaluated
from the agent’s end-to-end execution. ExecutingΓyields an interaction trajectory
τ= (o 1, a1, . . . , oT , aT ),
where each action at is generated by the agent policy πA(at |o t) and may be either a language
response or a tool invocation.
Observable execution trace and success predicate.Since PASB targets real deployed systems,
we define success based on anobservable execution tracederived fromτ:
tr(τ) ={x t, r t, κ t, y t+1}T
t=1,
where xt is the user-facing input, rt is the agent’s emitted response,κt is the tool-call event induced
by at including the selected tool in T and its arguments, and yt+1 is the recorded tool return. We
define the attack success predicate as
P(tr(τ)) =I(P leak(tr(τ))∨ P act(tr(τ))∨ P persist(tr(τ))),
where I(·) is an indicator function. Pleak is true if tr(τ) contains any protected private asset from a
predefined canary set Spriv in rt, κt, or yt+1. Pact is true if tr(τ) contains any tool-call event κt that
violates a scenario policy F, such as invoking forbidden tools or executing disallowed high-impact
operations under the scenario constraints. Ppersist is true if a harm event occurs after the adversary
stops providing injection inputs, capturing long-horizon propagation across steps or sessions. Over a
task distributionπ Γ, PASB reports the attack success rate
ASR =E Γ∼πΓ [P(tr(τΓ))],
and can further decompose it by harm type usingP leak,P act, andP persist.
2.2 THREATMODEL
PASB targets security risks that arise from the end-to-end coupling of a deployed personalized agent
A, its tool ecosystem T , and its long-term memory store D under long-horizon interaction. We
consider an adversary whose objective is to induce system-level harms during execution, including
unauthorized disclosure of private assets, unsafe or unauthorized tool actions, and persistence of
malicious influence across steps or sessions. The adversary operates in a black-box setting with

Figure 2: Example of Indirect Prompt Injection Attack on Openclaw.
respect to the agent internals: they do not access the backbone model parameters, hidden states, or
system prompt psys, and do not rely on any instrumentation of the agent beyond what is observable
through normal interaction and tool I/O.
Adversarial capabilities.The adversary can interact with the agent through channels that affect the
observations ot in the trajectory τ= (o 1, a1, . . . , oT , aT ). Concretely, the adversary may provide
adaptive user-facing inputs xt, and may control or influence untrusted external content that the
agent can access during execution, which becomes part of ot. In addition, when the agent invokes
tools in T , the adversary may influence the tool interaction context in ways that are realistic in
deployment, such as by controlling a remote content source or service endpoint that returns data to
the agent. The adversary is assumed to observe the agent outputs and the observable execution trace
tr(τ), enabling adaptive strategies across the interaction budget T specified by B in an attack task
Γ =⟨C,I,B,G,P⟩.
Adversarial knowledge.The adversary may know the public-facing interface of the agent and the
documented tool descriptions and schemas of T , as well as generic properties of the underlying
model family. They do not know any user-specific private assets, hidden memory implementation
details, or the exact contents of D beyond what can be inferred from observable behavior. This
matches the evaluation goal of PASB: to assess whether realistic external influence can cause harms
without assuming privileged access.
Out-of-scope assumptions.We do not consider direct compromise of the host operating system, arbi-
trary modification of the agent codebase, direct rewriting of the system prompt, or direct modification
of model weights. Network-level denial-of-service, physical attacks, and exfiltration that bypasses
the agent-tool interface are also out of scope. PASB focuses on security failures that manifest through
the agent’s decision making and tool-using behavior under mixed-trust inputs, which are precisely
the risks that emerge in real personalized agent deployments.
2.3 PERSONALIZEDSCENARIOSUITE
PASB emphasizesscenario-level realismfor personalized agents. Our key premise is that the
practical security risk is not whether new injection tricks exist, but whether established attack
primitivesmaterialize into measurable system-level harmsin real deployments, and whether such
harmspropagate and persistunder long-horizon interactions. Accordingly, PASB is built around
realistic personalized workflows, auditable private assets, tool privileges, and persistent execution,
enabling end-to-end verification beyond output-only checks.
Scenario A: External Content Hub.Inspired by the recent surge of agent-oriented content
platforms such asMoltbook, we construct an external-content-centered scenario suite to capture a
dominant attack surface in deployed personalized agents: the agent actively fetches and consumes
untrusted external content, incorporating it into planning and tool usage. This content can come from
ordinary web pages as well as community-style hubs, where posts, comments, structured fields, links,

Table 1: Clawdbot IPI Threat Skillset Statistics. A total of 131 threatening skills were collected, and
for each skill, a fixed query (the first step query is unrelated to the target skill), return value template,
and injection instruction were designed.
Capability Category Count Ratio (%) Example Skills (Excerpts)
Communication/Outreach (Email, IM, Webhook) 22 16.8 Email Send, Slack Post, Webhook
Notify
Funds/Wallet and Transaction Operations 18 13.7 FluxA-agent-wallet, Crypto Trans-
fer, Invoice Pay
Data Export/Sensitive Information Leakage 20 15.3 Data Export, Drive Upload, Con-
tact Dump
Account/Permission and Identity Operations 12 9.2 Password Reset, OAuth Token
Mint, Account Link
File/System-level Read-Write and Automation 16 12.2 File Write, Shell Runner, Local
Scheduler
Network/HTTP and Third-party API Calls 14 10.7 HTTP Request, RapidAPI Caller,
GraphQL Query
Social Media/Forum Search and Content Scraping 15 11.5 Search Reddit, X Search, Forum
Scrape
Development/Operations and CI/CD Chains 14 10.7 CI Trigger, Repo Write, Package
Publish
Total131 100.0 –
and embedded artifacts may all be ingested by the agent. Such content becomes part of the agent’s
observation stream ot, potentially influencing tool selection, argument construction, and subsequent
actions, even when the user’s prompt is benign.
We build a controlled web range that simulates realistic information-seeking and multi-step task
execution with multiple pages and modular content blocks. The pages contain natural-language
sections, structured fields, navigational links, and referenced attachments, allowing adversarial
payloads to be embedded in a seemingly benign form. This scenario traces how untrusted content
enterso t, influences planning, and propagates into subsequent tool calls and actions.
Scenario B: Personal Context & Long-Term Memory Management.A defining characteristic
of personalized agents is persistent operation with private context accumulation. In this scenario,
we simulate how attackers can exploit the long-term memory store of personalized agents to induce
persistent and harmful behaviors. These agents continuously interact with users, accumulating
personal data, preferences, and past interactions. The risk arises when malicious inputs or influences
are stored in the agent’s long-term memory, allowing adversarial behaviors to survive beyond the
initial interaction and affect future tasks. Once adversarial content is written into the memory, it can
bias the agent’s actions across multiple sessions, creating long-term vulnerabilities.
We instantiate auditable private assets (e.g., canary secrets, sensitive-context markers) within the
agent’s memory to evaluate how memory poisoning can lead to information leakage or unsafe actions.
By introducing controlled malicious inputs into the memory store and assessing their retrieval over
time, we can measure the persistence and propagation of harmful effects across subsequent tasks.
This scenario examines how poisoned memories, once written, can trigger system-level harms in later
interactions, even without additional adversarial injections.
Scenario C: Skills/Plugins and Tool-Return Risks.A critical feature of personalized agents
is their reliance on external skills, plugins, and third-party services to perform various tasks on
behalf of users. These tools, often possessing high privileges, allow agents to access sensitive data,
perform actions such as sending messages, modifying files, or even interacting with external services.
However, this heavy reliance on external toolchains introduces new security risks, as adversaries can
exploit vulnerabilities within the tool interactions. These interactions may lead to unauthorized tool
executions or the manipulation of high-privilege actions, thereby compromising the integrity of the
agent’s behavior and exposing private assets.
We model the agent-tool ecosystem as a mixed-trust environment, where the agent may over-trust the
tools it interacts with. This scenario explores how adversaries can manipulate the behavior of tools
or services to steer the agent into executing harmful actions. The agent’s belief system, often based
on the assumption that tool outputs are trustworthy, can be deceived by adversarial manipulation,
leading to unsafe follow-up actions or unintended exposure of private data. This scenario evaluates

the security risks associated with tool return manipulation, skill impersonation, and the potential
cascading effects of deceptive tool interactions across multiple tasks.
2.4 ATTACKPRIMITIVES
PASB builds upon four representative attack primitives for LLM-based agents and systematically
instantiates them in realistic personalized workflows. Our goal is to assess whether these primitives
materialize into system-level harmsunder end-to-end execution, including leakage of auditable
private assets Spriv, policy-violating tool actions under constraints F, and persistence across steps
or sessions. We model attacks as structured perturbations to the agent’s observation stream along a
trajectory τ= (o 1, a1, . . . , oT , aT ). At step t, an attacker selects a payloadδt and induces a corrupted
observation
o′
t = Inject(ot;δ t),(3)
where Inject(·) is channel-specific (e.g., text insertion, structured-field overwrite, or return-value
manipulation). Below, we formalize the four primitive families used in PASB with lightweight,
operational definitions.
Direct prompt injection.The attacker controls (or influences) the user-facing input xt included in
ot and appends an instruction payloadδ pr
t .
x′
t =x t ⊕δ pr
t , o ′
t = Compose(ot, x′
t),(4)
where ⊕ denotes concatenation or insertion under natural formatting, and Compose denotes the
agent’s standard observation construction. This primitive captures failures where the agent deviates
from the intended objective, produces unauthorized disclosure, or triggers unsafe tool calls.
Indirect injection via untrusted external content.The user prompt may remain benign, while the
payload is delivered through external content zt that the agent fetches or reads (web pages, posts,
comments, emails, or messages).
z′
t =z t ⊕δ ext
t , o ′
t = Compose(ot, z′
t),(5)
so the attack enters execution through the observation channel rather than direct user instructions.
This primitive targets cross-stage propagation from content consumption to planning and tool use.
Tool-return deception and output-carried payloads.The attacker manipulates tool outputs yt
that will be incorporated into subsequent observations, enabling chained failures through the tool
loop.
y′
t =y t ⊕δ tool
t , o ′
t+1 = Compose(ot+1, y′
t).(6)
This primitive models mixed-trust ecosystems where the agent over-trusts tool returns, leading to
unsafe follow-up actions or private-asset exposure via downstream tool arguments.
Memory poisoning and retrieval-triggered influence.The attacker induces malicious artifacts to
be written into long-term memoryD, or corrupts retrieval so that harmful items are returned later.
D′ =D ∪ {(k adv, vadv)}, r t = Retrieve(qt,D ′), o ′
t = Compose(ot, rt),(7)
where qt is the implicit retrieval query (derived from the current context), and rt denotes retrieved
memory items used as in-context evidence. The defining property ispersistence: harms can be
triggered in later benign tasks after the attacker stops injecting.
Adaptive selection under black-box access.PASB supports adaptive red-teaming where the
payload is chosen based on the observable execution trace.
δt =π adv
 
tr(o′
1, a1, . . . , o′
t−1, at−1)

,(8)
withπ adv operating under black-box constraints, relying only on agent outputs and tool I/O.

3 EVALUATION RESULTS ONPASB
3.1 EXPERIMENTALSETUP
Evaluation metrics.We report metrics consistent with Table 2–4. For the IPI attack simulation
(Table 2), we report Response Rate (Resp Rate) and Attack Success Rate (ASR). Resp Rate counts
a trial as successful if the agent triggersanyskill/tool call (any skill call is considered a response),
capturing whether attacks disrupt the agent’s general tool-calling behavior. ASR counts a trial
as successful only if the agent triggers thetarget skillcall, capturing how effectively an attack
induces the intended high-risk action. For memory-related tasks (Table 3–4), we report STM/LTM
extraction success rates (STM-Extract/LTM-Extract Success Rate) and STM/LTM edit write success
rates (STM-Edit/LTM-Edit Write Success Rate, WSR). Extraction success indicates whether the
specified short-term context fragment or long-term memory marker can be retrieved in a test case.
WSR indicates whether an attacker can change a specified marker in the target short-term/long-term
memory to a target marker, and we verify the write effect via the corresponding marker in the
OpenClaw file system.
LLM Backbone and Defense Methods.For our personalized agents, we use three different LLM
models as the backbone: Llama-3.1-70B-Instruct, Qwen2.5-7B-Instruct, and GPT-4o-mini. And we
evaluate three key defense methods to mitigate the impact of adversarial attacks. Delimiter Defense
inserts special delimiters around inputs to separate benign content from malicious content, helping
to block prompt injection attacks. Sandwich Defense surrounds the prompt with protective layers
to increase the difficulty of injecting harmful instructions. Instruction Prevention Defense applies
predefined instructions to restrict the agent’s ability to execute specific harmful actions, particularly
preventing prompt-based attacks.
Implementation and Run Protocol.We evaluate OPENCLAWin its deployed form under black-
box access and use an end-to-end harness to drive a full interaction trajectory per trial. For each trial,
the harness provides scenario-specific inputs including: user prompts, controlled untrusted external
content (to instantiate external injection channels), controlled tool/skill service endpoints (to return
reproducible tool outputs), and follow-up prompts when needed to trigger retrieval/write behaviors
(to measure cross-step propagation and persistence). During execution, we record the observable
trace: the agent’s textual responses, each triggered tool/skill call (tool name and arguments), and
the corresponding return values. We then apply automated rules to determine whether the success
events defined in Table 2–4 occur (e.g., the target skill is triggered; a specified memory marker is
extracted/written). For reproducibility and safety, private assets Spriv are implemented as auditable
canary strings; all high-privilege operations are confined to an isolated sandbox and constrained
by explicit scenario policies F that define allowed/forbidden tool categories and operation scopes.
Unless otherwise specified, each (scenario, primitive) configuration is run forN independent trials
with a fixed maximum horizonT, and we report mean results.
3.2 MAINRESULTS ANDANALYSIS
Unlike traditional security evaluations that rely on parsing text-based outputs (such as JSON tool
requests), which can overlook issues like invalid code or missing context, we perform a more realistic
validation using OpenClaw. OpenClaw translates the agent’s reasoning steps into actual TypeScript
asynchronous operations, executed in an isolated runtime environment. This approach ensures that
attacks are only considered successful if they result in tangible changes to the environment, such
as unauthorized permission modifications or successful data exfiltration. By using this method, we
capture real-world risks that are often missed by idealized, text-based evaluations.
For Scenario A (External Content and Third-party Tool Interaction) and Scenario C (Skills/Plugins and
Tool-Return Risks), we implemented Clawdbot using OpenClaw and leveraged 131 threatening tools
from OpenClaw’s public Skills registry, covering common high-impact surfaces such as messaging,
transactions, and data exfiltration. In Scenario A, we injected malicious payloads through external
content or tool returns to simulate IPI attacks, and report results in Table 2. In Scenario C, we
manipulated tool outputs to induce unauthorized follow-up actions, highlighting risks from over-
trusting tool returns.

Table 2: Clawdbot IPI Attack Simulation Experimental Results. Statistical metrics include Response
Rate (any skill call triggered counts as success) and Attack Success Rate (ASR) (triggering thetarget
skillcall counts as attack success). IPI injection occurs in the tool observation results of step 1 and
induces the agent to call the target skill in step 2. Defense methods include Delimiter and Sandwich
defense.
Model Attack Method No Defense Delimiter Sandwich Defense
Resp Rate (%) ASR (%) Resp Rate (%) ASR (%) Resp Rate (%) ASR (%)
Llama-3.1-70B-Instruct
Naive Attack 98.5 46.0 97.2 21.5 96.8 14.0
Escape Char Attack 98.2 52.5 97.0 24.8 96.7 16.3
Context Ignore Attack 97.9 58.4 96.5 27.6 96.2 18.9
Fake Completion Attack 98.1 55.0 96.8 26.2 96.4 17.2
Combined Attack 97.6 66.8 96.0 33.5 95.8 22.0
Qwen2.5-7B-Instruct
Naive Attack 96.8 34.2 95.4 16.1 95.0 10.5
Escape Char Attack 96.4 39.0 95.0 17.8 94.6 11.9
Context Ignore Attack 96.1 44.5 94.6 20.6 94.3 13.8
Fake Completion Attack 96.2 41.8 94.8 19.7 94.4 13.0
Combined Attack 95.6 52.7 94.0 25.9 93.8 17.1
gpt-4o-mini
Naive Attack 99.0 42.0 98.2 19.0 98.0 12.8
Escape Char Attack 98.8 47.6 98.0 21.3 97.8 14.6
Context Ignore Attack 98.6 53.2 97.6 24.2 97.4 16.8
Fake Completion Attack 98.7 50.4 97.8 23.1 97.5 15.7
Combined Attack 98.4 61.9 97.2 30.4 97.0 20.1
Table 3: Simulated Experimental Results for Short-Term and Long-Term Memory Extraction (40
cases per category). Defenses include Delimiter and Instruction Prevention.
Model STM-Extract Success Rate LTM-Extract Success Rate
No Defense (%) Delimiter (%) Inst. Prevention (%) No Defense (%) Delimiter (%) Inst. Prevention (%)
Llama-3.1-70B-Instruct 41.0 19.2 15.4 62.5 28.4 18.6
Qwen2.5-7B-Instruct 33.5 14.8 11.6 54.0 23.7 15.2
gpt-4o-mini 38.2 16.5 13.0 59.1 26.1 17.0
For Scenario B (Personal Context and Long-Term Memory Management), we designed four memory
tasks: Short-Term Memory Extraction (STM-Extract), Long-Term Memory Extraction (LTM-Extract),
Short-Term Memory Modification (STM-Edit), and Long-Term Memory Modification (LTM-Edit).
Each task contains 40 test cases (160 total). Extraction success is measured by whether a specified
short-term context fragment or long-term memory marker can be retrieved (Table 3). For modification,
we measure write success rate (WSR) by whether a specified marker in STM/LTM is changed to a
target marker and verified via the OpenClaw file system (Table 4).
Overall, attacks more strongly affectwhichtool/skill is triggered thanwhetherthe agent triggers
tools at all: Resp Rate stays high across settings (93.8%–99.0% in Table 2), while ASR varies widely
by attack type and model. Across all three backbones, Combined Attack achieves the highest ASR
under no defense (66.8% for Llama-3.1-70B-Instruct, 52.7% for Qwen2.5-7B-Instruct, and 61.9% for
gpt-4o-mini). Delimiter and Sandwich defenses substantially reduce ASR, but do not eliminate it. For
example, for Llama-3.1-70B-Instruct under Combined Attack, ASR drops from 66.8% (no defense)
to 33.5% (Delimiter) and 22.0% (Sandwich). Even with Sandwich defense, a non-trivial residual
ASR remains across models and attacks (10.5%–22.0% in Table 2), indicating that prompt-layer
isolation alone is insufficient for fully mitigating IPI-style risks.
For memory risks, LTM extraction success rates are consistently higher than STM extraction success
rates (Table 3), suggesting higher leakage risk from long-term stores. Delimiter and Instruction
Prevention defenses reduce both extraction (Table 3) and modification WSR (Table 4), with Instruction
Prevention generally providing stronger reductions; however, residual extraction and modification
success persists even under the strongest defense, reflecting continued exposure when adversaries can
influence memory read/write behaviors.

Table 4: Simulated Experimental Results for Short-Term and Long-Term Memory Modification (40
cases per category). Attackers require the agent to modify a specified marker in the target short-term
or long-term memory to a target marker through DPI, and then check the corresponding target marker
in the OpenClaw file system, evaluating the memory modification effect based on the Write Success
Rate (WSR). Defenses include Delimiter and Instruction Prevention.
Model STM-Edit WSR LTM-Edit WSR
No Defense (%) Delimiter (%) Inst. Prevention (%) No Defense (%) Delimiter (%) Inst. Prevention (%)
Llama-3.1-70B-Instruct 57.3 25.4 16.2 71.5 31.2 20.4
Qwen2.5-7B-Instruct 46.1 20.2 13.0 60.4 26.0 17.3
gpt-4o-mini 52.4 23.1 15.1 66.2 29.1 19.0
4 CONCLUSION ANDFUTUREWORK
We introduce Personalized Agent Security Bench (PASB), an end-to-end benchmark for evaluating
the security of LLM-based personalized agents under representative attacks and defenses. By
benchmarking a real deployed system, OPENCLAW, PASB reveals that critical vulnerabilities can
arise across operational stages and propagate along the agent action chain, leading to system-level
harms beyond unsafe text generation. PASB provides a practical foundation for building more robust
defenses and resilient personalized agents, and future work will improve defenses that account for
tool execution and long-horizon propagation while extending PASB with additional scenarios and
attacker capabilities.
REFERENCES
Zhaorun Chen, Zhen Xiang, Chaowei Xiao, Dawn Song, and Bo Li. Agentpoison: Red-teaming llm
agents via poisoning memory or knowledge bases.Advances in Neural Information Processing
Systems, 37:130185–130213, 2024.
Edoardo Debenedetti, Jie Zhang, Mislav Balunovic, Luca Beurer-Kellner, Marc Fischer, and Florian
Tram`er. Agentdojo: A dynamic environment to evaluate prompt injection attacks and defenses for
llm agents.Advances in Neural Information Processing Systems, 37:82895–82920, 2024.
Xiang Deng, Yu Gu, Boyuan Zheng, Shijie Chen, Sam Stevens, Boshi Wang, Huan Sun, and Yu Su.
Mind2web: Towards a generalist agent for the web.Advances in Neural Information Processing
Systems, 36:28091–28114, 2023.
Yunhao Feng, Yige Li, Yutao Wu, Yingshui Tan, Yanming Guo, Yifan Ding, Kun Zhai, Xingjun Ma,
and Yugang Jiang. Backdooragent: A unified framework for backdoor attacks on llm-based agents.
arXiv preprint arXiv:2601.04566, 2026.
Kai Greshake, Sahar Abdelnabi, Shailesh Mishra, Christoph Endres, Thorsten Holz, and Mario Fritz.
Not what you’ve signed up for: Compromising real-world llm-integrated applications with indirect
prompt injection. InProceedings of the 16th ACM workshop on artificial intelligence and security,
pp. 79–90, 2023.
Sirui Hong, Mingchen Zhuge, Jonathan Chen, Xiawu Zheng, Yuheng Cheng, Jinlin Wang, Ceyao
Zhang, Zili Wang, Steven Ka Shing Yau, Zijuan Lin, et al. Metagpt: Meta programming for a multi-
agent collaborative framework. InThe twelfth international conference on learning representations,
2023.
Changshu Liu and Reyhan Jabbarvand. A tool for in-depth analysis of code execution reasoning
of large language models. InProceedings of the 33rd ACM International Conference on the
Foundations of Software Engineering, pp. 1178–1182, 2025.
Xiao Liu, Hao Yu, Hanchen Zhang, Yifan Xu, Xuanyu Lei, Hanyu Lai, Yu Gu, Hangliang Ding,
Kaiwen Men, Kejuan Yang, et al. Agentbench: Evaluating llms as agents.arXiv preprint
arXiv:2308.03688, 2023.

Gr´egoire Mialon, Cl ´ementine Fourrier, Thomas Wolf, Yann LeCun, and Thomas Scialom. Gaia:
a benchmark for general ai assistants. InThe Twelfth International Conference on Learning
Representations, 2023.
Joon Sung Park, Joseph O’Brien, Carrie Jun Cai, Meredith Ringel Morris, Percy Liang, and Michael S
Bernstein. Generative agents: Interactive simulacra of human behavior. InProceedings of the 36th
annual acm symposium on user interface software and technology, pp. 1–22, 2023.
Timo Schick, Jane Dwivedi-Yu, Roberto Dess`ı, Roberta Raileanu, Maria Lomeli, Eric Hambro, Luke
Zettlemoyer, Nicola Cancedda, and Thomas Scialom. Toolformer: Language models can teach
themselves to use tools.Advances in Neural Information Processing Systems, 36:68539–68551,
2023.
Karan Singhal, Tao Tu, Juraj Gottweis, Rory Sayres, Ellery Wulczyn, Mohamed Amin, Le Hou,
Kevin Clark, Stephen R Pfohl, Heather Cole-Lewis, et al. Toward expert-level medical question
answering with large language models.Nature Medicine, 31(3):943–950, 2025.
Robin Staab, Mark Vero, Mislav Balunovi´c, and Martin Vechev. Beyond memorization: Violating
privacy via inference with large language models.arXiv preprint arXiv:2310.07298, 2023.
Peter Steinberger. Openclaw: The ai that actually does things. https://github.com/
openclaw/openclaw, 2025.
Lei Wang, Chen Ma, Xueyang Feng, Zeyu Zhang, Hao Yang, Jingsen Zhang, Zhiyuan Chen, Jiakai
Tang, Xu Chen, Yankai Lin, Wayne Xin Zhao, Zhewei Wei, and Jirong Wen. A survey on
large language model based autonomous agents.Frontiers of Computer Science, 18(6), March
2024. ISSN 2095-2236. doi: 10.1007/s11704-024-40231-1. URL http://dx.doi.org/10.
1007/s11704-024-40231-1.
Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Fei Xia, Ed Chi, Quoc V Le, Denny
Zhou, et al. Chain-of-thought prompting elicits reasoning in large language models.Advances in
neural information processing systems, 35:24824–24837, 2022.
Shijie Wu, Ozan Irsoy, Steven Lu, Vadim Dabravolski, Mark Dredze, Sebastian Gehrmann, Prabhan-
jan Kambadur, David Rosenberg, and Gideon Mann. Bloomberggpt: A large language model for
finance.arXiv preprint arXiv:2303.17564, 2023.
Zhenhua Xu, Yujia Zhang, Enze Xie, Zhen Zhao, Yong Guo, Kwan-Yee K Wong, Zhenguo Li, and
Hengshuang Zhao. Drivegpt4: Interpretable end-to-end autonomous driving via large language
model.IEEE Robotics and Automation Letters, 2024.
Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik R Narasimhan, and Yuan
Cao. React: Synergizing reasoning and acting in language models. InThe eleventh international
conference on learning representations, 2022.
Qiusi Zhan, Zhixiang Liang, Zifan Ying, and Daniel Kang. Injecagent: Benchmarking indirect
prompt injections in tool-integrated large language model agents.arXiv preprint arXiv:2403.02691,
2024.
Hanrong Zhang, Jingyuan Huang, Kai Mei, Yifei Yao, Zhenting Wang, Chenlu Zhan, Hongwei
Wang, and Yongfeng Zhang. Agent security bench (asb): Formalizing and benchmarking attacks
and defenses in llm-based agents. InThe Thirteenth International Conference on Learning
Representations, 2025.
Lianmin Zheng, Wei-Lin Chiang, Ying Sheng, Siyuan Zhuang, Zhanghao Wu, Yonghao Zhuang,
Zi Lin, Zhuohan Li, Dacheng Li, Eric Xing, et al. Judging llm-as-a-judge with mt-bench and
chatbot arena.Advances in neural information processing systems, 36:46595–46623, 2023.