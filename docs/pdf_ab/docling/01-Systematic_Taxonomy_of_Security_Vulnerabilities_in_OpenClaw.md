## A Systematic Taxonomy of Security Vulnerabilities in the OpenClaw AI Agent Framework

Surada Suwansathit SUCCESS Lab Texas A&amp;M University surada@tamu.edu

Yuxuan Zhang SUCCESS Lab Texas A&amp;M University yuz516@tamu.edu

February 2026

## Abstract

AI agent frameworks that connect large language model (LLM) reasoning to host execution surfaces-shell, filesystem, containers, browser automation, and messaging platforms-introduce a class of security challenges that differs structurally from those of conventional software. We present a systematic security taxonomy of 190 advisories filed against OpenClaw [1], an opensource AI agent runtime, organizing the corpus by architectural layer and trust-violation type . Our taxonomy reveals that vulnerabilities cluster along two orthogonal axes: (1) the system axis , which reflects where in the architecture a vulnerable operation occurs (exec policy, gateway, channel adapters, sandbox, browser, plugin/skill, agent/prompt layers); and (2) the attack axis , which reflects the adversarial technique applied (identity spoofing, policy bypass, crosslayer composition, prompt injection, supply-chain trust escalation). Grounding our taxonomy in patch-differential evidence, we derive three principal findings. First, three independently Moderate- or High-severity advisories [6, 7] exist within the Gateway and Node-Host subsystems. By mapping these through the Delivery, Exploitation, and Command-and-Control stages of the Cyber Kill Chain, they compose into a complete unauthenticated remote code execution path from an LLM tool call to the host process. Second, the exec allowlist [8, 9, 10], which is the framework's primary command-filtering mechanism, embeds a closed-world assumption that command identity is recoverable by lexical parsing. This assumption is invalidated by line continuation, busybox multiplexing, and GNU long-option abbreviation in independent and non-overlapping ways. Third, a malicious skill distributed through the plugin channel [13] executed a two-stage dropper entirely within the LLM context, bypassing the exec pipeline entirely and illustrating that the skill distribution surface constitutes an attack vector outside any runtime policy primitive. Across all categories, the dominant structural pattern is per-layer, per-call-site trust enforcement rather than unified policy boundaries-a design property that makes cross-layer composition attacks systematically resistant to layer-local remediation.

## 1 Introduction

AI agent frameworks as an execution surface. The deployment of large language models as autonomous agents-systems that perceive external input, reason over it, and produce actions with real-world effects-introduces a qualitatively different security problem from that of conventional application software. In a traditional application, the code determines behavior; an attacker who cannot modify the code is largely confined to exploiting memory safety errors or logic bugs in welldefined input handlers. In an AI agent framework, the model's output is itself a control signal: a tool call emitted by the model instructs the runtime to execute a shell command, read or write a file,

Guofei Gu SUCCESS Lab Texas A&amp;M University guofei@cse.tamu.edu

navigate a browser, or deliver a message across a messaging platform. The attack surface therefore includes not only the runtime's implementation correctness but also the model's susceptibility to adversarial influence through any data path that reaches its context window.

OpenClaw [1] is a representative instance of this architecture. The framework exposes a distributed agent runtime connecting LLM inference to more than fifteen external surfaces through a layered Gateway-Node-Host design. Its four principal subsystems-a Gateway control plane, a Node-Host privileged execution process, an embedded agent runner, and a set of channel adapters for messaging platforms-interact over WebSocket connections with authentication and trust decisions scattered across each layer. The framework's rapid adoption-exceeding 200,000 GitHub stars within weeks of its January 2026 relaunch under the OpenClaw name-made it an unusually high-visibility target for security researchers during the precise window when it lacked a mature disclosure process.

The need for a systematic taxonomy. Prior work on AI agent security [3, 4, 5] characterizes individual attack techniques-prompt injection, indirect injection, model extraction-without a unifying model that maps attacks to the specific architectural layer they exploit. A corpus as large and structurally varied as OpenClaw's 190 advisories cannot be understood through a simple list; its security implications emerge from the relationships between vulnerabilities across layers. We therefore organize our analysis along two independent axes. The system axis ( § 4.1) classifies each vulnerability by the architectural component in which the vulnerable operation occurs. The attack axis ( § 4) classifies each vulnerability by the adversarial technique, mapped to the Cyber Kill Chain [2] where applicable. Together the two axes form a two-dimensional taxonomy that exposes which architectural layers are susceptible to which technique classes, and where defenses should be positioned.

Contributions. This paper makes the following contributions:

1. A two-axis security taxonomy of AI agent framework vulnerabilities, instantiated on the full 190-advisory OpenClaw corpus, organized by architectural layer (system axis) and adversarial technique (attack axis), with advisory citations supporting each classification ( § 4).
2. An OpenClaw-specific kill chain that adapts five MITRE ATT&amp;CK tactics to the personal AI agent context and introduces Context Manipulation as a novel stage with no analog in traditional intrusion frameworks, reflecting the unique role of the LLM reasoning layer as an attack surface ( § 4.2).
3. A multi-layer vulnerability analysis of the 190-advisory OpenClaw corpus, providing a systematic mapping of empirical attack data to the ten architectural layers defined in our taxonomy. This analysis identifies recurring design flaws-ranging from identity mutability at the Channel Input Interface to lexical parsing failures in the Exec Policy Engine-demonstrating how decentralized trust boundaries enable complex, cross-layer exploitation chains (5).

Paper organization. Section 2 describes OpenClaw's architecture and the principal subsystems defining its trust model. Section 3 provides a high-level overview of the 190-advisory corpus and disclosure statistics. Section 4 introduces our two-axis taxonomy, defining ten architectural layers and seven adversarial techniques. Section 5 presents a structural vulnerability analysis, mapping empirical audit data to the taxonomy layers to identify architectural root causes. Section 6 outlines potential defense strategies and mitigation directions aligned with each architectural layer of the proposed taxonomy. We conclude in Section 7.

## 2 Modeling System Architecture and Attack Surface

OpenClaw [1] is an open-source autonomous AI agent framework that connects large language model inference to real-world execution surfaces: shell command execution, file system access, browser automation, Docker container management, and a wide array of third-party messaging platforms. Released in November 2025 under the name Clawdbot, renamed to Moltbot in January 2026 following a trademark dispute, and rebranded to OpenClaw on January 29, 2026, the project accumulated over 100,000 GitHub stars within weeks of its initial viral distribution. Its architecture is organized around seven interacting components (Figure 1): a Channel System, a central Gateway, a Plug-ins &amp; Skills System, an Agent Runtime, a Memory &amp; Knowledge System, an LLM Provider, and a Local Execution environment.

## 2.1 System Components

Channel System. The Channel System ( src/telegram/ , src/discord/ , src/slack/ , etc)) bridges external messaging platforms to the rest of the framework. Each adapter polls or receives webhook events, authorizes the sender against per-channel allowlists in src/channels/allow-from.ts , computes a canonical session key, and dispatches an inbound message to the Gateway's command queue. Outbound responses follow the same path in reverse.

Gateway. The Gateway ( src/gateway/ ) is the central control plane and message broker. It binds an HTTP/WebSocket server and is responsible for authenticating and multiplexing all inbound connections from channel adapters, the Agent Runtime, Local Execution processes, and CLI operators. It maintains a NodeRegistry of connected Local Execution sessions, an ExecApprovalManager that serializes pending command-approval requests, and a per-lane CommandQueue that serializes concurrent messages destined for the same session. The Gateway routes node.invoke frames from the Agent Runtime to the appropriate Local Execution process and brokers all AI agent runs.

Plug-ins &amp; Skills System. The Plug-ins &amp; Skills System manages the loading and execution of third-party skills from the clawhub.ai registry and local plugin directories ( src/plugins/ ). Skills are loaded into the agent's context window at session start via SKILL.md instruction files, extending the agent's capabilities at runtime. This component operates at operator-level trust: a skill loaded by the system is treated as a trusted instruction source by the Agent Runtime.

Agent Runtime. The Agent Runtime ( src/agents/ ) encapsulates the LLM reasoning loop, tool dispatch, and Docker sandbox management. The entry point runEmbeddedPiAgent ( src/agents/piembedded-runner/run.ts ) resolves auth profiles, selects a model, and submits turns to the LLM Provider in an attempt loop with failover. Tool calls emitted by the model are intercepted by handlers in src/agents/pi-embedded-subscribe/handlers/tools.ts and dispatched either in-process (file reads, web fetches) or forwarded to the Gateway as node.invoke frames for host-side execution via Local Execution.

Memory &amp; Knowledge System. The Memory &amp; Knowledge System manages session history, long-term context, and bootstrap files loaded at the start of each agent turn. The embedded runner prepends CLAUDE.md , loaded skill instructions, and prior conversation history into the LLM context window before each model call, giving the agent persistent memory across turns within a session.

Figure 1: OpenClaw system architecture with attack surfaces mapped to each component. Solid boxes represent system components; dashed orange regions denote attack surfaces from the taxonomy in Table 4.

<!-- image -->

LLM Provider. The LLM Provider is the external AI model API (Claude, GPT, Llama, or any locally-hosted model) that receives assembled prompts from the Agent Runtime and streams completions back. The provider interface is abstracted in src/agents/ , allowing model substitution without changes to the agent runtime logic.

Local Execution. The Local Execution environment ( src/node-host/ ) runs on the end-user's machine as a privileged process. It connects to the Gateway over WebSocket with role='node' and waits for node.invoke frames. The core dispatch loop in src/node-host/invoke.ts routes each command through a three-phase exec policy pipeline: lexical allowlist evaluation, approval state lookup, and execution. Sandboxed tool calls execute inside a Docker container via docker exec ; unsandboxed calls run directly on the host shell with full filesystem and process access.

## 2.2 Attack Surface Overview

The architecture can be read from two complementary perspectives.

From the system perspective, OpenClaw is a distributed message broker in which the Gateway authenticates and multiplexes connections from channel adapters, the agent runner, and NodeHost processes; the Node-Host executes privileged operations on the end-user machine; and channel adapters translate external platform events into agent sessions. Trust flows inward: channel adapters are the outermost layer with the least privilege; the Node-Host is the innermost layer with the most privilege.

From the attack perspective, the same architecture presents five distinct attack surfaces, each exploitable at different kill-chain stages:

1. Channel adapters - the outermost input surface. Adversaries who cannot authenticate to the system may nonetheless influence the agent's context via messages admitted through

<!-- image -->

Date

Figure 2: Advisory disclosure timeline. The two distinct waves correspond to an initial coordinated audit (Jan 31-Feb 16) and an accelerated follow-on discovery phase (Feb 18-25) that more than doubled the advisory corpus while patching from the first wave was actively in progress.

misconfigured allowlists or unauthenticated webhooks. This corresponds to the Delivery stage of the Cyber Kill Chain [2].

2. Agent/prompt runtime - the context-window boundary. Adversaries who control any data path into the LLM's context can inject instructions ( prompt injection ) that direct subsequent tool calls without triggering any exec policy check. This is the Exploitation stage operating above the enforcement layer.
3. Gateway &amp; API -the central trust broker. Adversaries who can direct a WebSocket connection to an attacker-controlled endpoint can exfiltrate authentication tokens, then reconnect as an authorized operator. This spans Exploitation and Command-and-Control .
4. Exec allowlist / Node-Host - the command enforcement boundary. Adversaries who have obtained operator-level gateway access, or who can bypass allowlist parsing, achieve arbitrary Actions on Objectives on the host.
5. Plugin/skill distribution -the supply-chain surface. Adversaries who publish a malicious skill to the community registry bypass the exec pipeline entirely by operating within the LLM context window, evading all runtime policy.

## 3 Corpus Overview

Between January 31 and February 25, 2026, 190 security advisories were filed across two waves: a coordinated 73-advisory audit (Jan 31-Feb 16) followed by an accelerated 117-advisory second wave (Feb 18-25) that more than doubled the corpus while first-wave patches were still being merged. Figure 4 maps the full attack surface.

## 3.1 Systemic Weakness Patterns

The distribution across attack surfaces reveals cross-cutting structural weaknesses, specifically a reliance on brittle lexical assumptions and decentralized trust boundaries. While the Exec Policy

Severity Distribution by Vulnerability Category

Figure 3: Severity distribution by attack surface. The Exec Policy Engine dominates in volume (46 advisories, 24.2%) while the Tool Dispatch Interface and Browser Tooling surface shows the highest proportion of High-severity findings relative to its total.

<!-- image -->

Engine dominates in volume due to parsing ambiguities, the Gateway WebSocket Interface represents the most critical integration risk with the highest count of High-severity findings. These patterns demonstrate that OpenClaw's primary vulnerabilities emerge from systemic gaps in interlayer policy enforcement rather than isolated component defects.

Exec Policy Engine as the dominant attack surface. With 46 advisories (24.2% of total), the Exec Policy Engine is the largest attack surface by a significant margin. The concentration reflects a single architectural premise that proved repeatedly exploitable: the assumption that a command string's security-relevant identity can be determined by lexical analysis of its text. Adversaries found diverse ways to invalidate this premise, producing a large family of distinct bypasses from a single root cause.

Gateway WebSocket Interface as the widest integration surface. The Gateway WebSocket Interface accounts for 40 advisories with the highest absolute count of High-severity findings. Its central role as the trust broker between all other components means that weaknesses here have system-wide consequences: a compromised gateway grants an adversary access to every component it mediates.

Container Boundary as a high-concern surface. With 17 advisories including the corpus's only Critical-severity finding, the Container Boundary surface reveals a structural challenge: the sandbox boundary was never enforced by the framework itself, leaving the strength of isolation entirely dependent on how the underlying container runtime was configured.

Key observations. The Exec Policy Engine dominates in volume (46 advisories, 24.2%). The Gateway WebSocket Interface (40) carries the highest absolute count of High-severity findings. The Tool Dispatch Interface and Browser Tooling surfaces together account for 10 advisories, with Browser Tooling showing the highest High-severity proportion relative to its total (6 of 10). The Channel Input Interface (35) and Plugin &amp; Skill Distribution (7) account for all supply-chain and identity-spoofing findings. The Agent Context Window (5) has the lowest advisory count among surfaces with known vulnerabilities, but its role as the entry point for Context Manipulation attacks makes it structurally significant beyond what the advisory count suggests.

Unrepresented surfaces. Two attack surfaces in the taxonomy have no advisory in the current corpus: the LLM Provider Interface and Inter-Agent Communication. Their absence reflects the boundaries of current security research rather than an absence of risk. Both are included as forwardlooking threat model entries.

## 4 Security Taxonomy

We propose a two-axis taxonomy specific to personal AI agent systems, using OpenClaw as a representative instantiation. The attack surface axis enumerates the distinct interfaces at which an adversary can interact with the system, making the taxonomy a forward-looking threat model rather than merely a retrospective corpus summary. The kill chain axis defines the stages of a complete attack, adapted from the MITRE ATT&amp;CK framework for the AI agent context. Together, the two axes form a matrix that specifies both where a vulnerability is located and at which stage of an attack it is exploited.

## 4.1 Attack Surface

The attack surface axis enumerates every interface at which an adversary can interact with an OpenClaw deployment.

1. Channel Input Interface -the boundary where external messages enter the system. Encompasses allowlist evaluation, session-key construction, and webhook signature verification across all 15 supported platforms.
2. Plugin &amp; Skill Distribution - the supply-chain surface through which operator-trusted skills are installed from clawhub.ai or the local filesystem. Includes CLAUDE.md and skill instruction files loaded into agent context at session start.
3. Agent Context Window -everything the LLM processes during a session: system prompt, CLAUDE.md , skill files, conversation history, and any file or tool output read during the turn. The primary surface for Context Manipulation attacks.
4. Gateway WebSocket Interface -the authenticated WebSocket connection layer on port 18789. Governs operator and node roles, Bearer token validation, and method-level scope enforcement.
5. Tool Dispatch Interface -the interface between agent decisions and actual tool execution, including system.run , browser automation, and file operation tools.
6. Exec Policy Engine - the three-phase allowlist pipeline on the Node-Host: lexical command analysis, approval state lookup, and persistent allowlist management.
7. Container Boundary - the Docker sandbox that confines agent tool execution. Configuration parameters (bind mounts, network namespaces, security profiles) flow from agent tool calls to the Docker daemon.

8. Host OS Interface -the shell, filesystem, and network stack of the end-user machine; the ultimate target of privilege escalation chains.
9. LLM Provider Interface ( † ) - the API boundary between OpenClaw and the upstream model provider (Claude, GPT, or locally-hosted models). Potential surfaces include response parsing vulnerabilities, adversarial token sequences that corrupt model state, and Unicode manipulation that causes the model to misinterpret input.
10. Inter-Agent Communication ( † ) - the communication channel between coordinated OpenClaw agents in multi-agent deployments. A compromised agent can use this surface to propagate adversarial context to peer agents, potentially traversing the full kill chain across the agent network.

## Kill Chain Stage

<!-- image -->

|                             | Initial Access   | Context Manipulation   | Execution   | Credential Access   | Privilege Escalation   | Impact   |
|-----------------------------|------------------|------------------------|-------------|---------------------|------------------------|----------|
| Channel Input Interface     | •                | •                      |             |                     |                        |          |
| Plugin & Skill Distribution | •                | •                      |             |                     |                        | •        |
| Agent Context Window        |                  | •                      | •           |                     |                        |          |
| Gateway WebSocket Interface |                  |                        | •           | •                   | •                      |          |
| Tool Dispatch Interface     |                  |                        | •           |                     | •                      | •        |
| Exec Policy Engine          |                  |                        |             |                     | •                      | •        |
| Container Boundary          |                  |                        |             |                     | •                      | •        |
| Host OS Interface           |                  |                        |             |                     |                        | •        |
| LLM Provider Interface      |                  | •                      | •           |                     |                        |          |
| Inter-Agent Communication   | •                | •                      | •           | •                   | •                      | •        |

·

= exploitable at this stage

Figure 4: Two-axis taxonomy matrix mapping OpenClaw attack surfaces (rows) to kill chain stages (columns). Filled circles indicate that the surface is exploitable at that stage.

## 4.2 OpenClaw Kill Chain

We define a six-stage kill chain for personal AI agent systems, adopting five tactics directly from MITRE ATT&amp;CK and introducing one novel tactic that has no analog in traditional intrusion frameworks:

1. Initial Access -the adversary introduces malicious content into the system's input boundary. In a personal AI agent system, this boundary is unusually wide: it encompasses every external data path that reaches the agent, including inbound channel messages, installed plugins and skills, operator-defined configuration files, and webhook payloads from integrated platforms.
2. Context Manipulation - the adversary corrupts the LLM's reasoning context so that it

produces attacker-intended outputs without any direct code execution. This stage has no equivalent in MITRE ATT&amp;CK because it exploits the LLM reasoning layer that is unique to AI agent systems. The adversary does not need to execute code or bypass a policy control - controlling what the model believes is sufficient to induce arbitrary tool calls. Vectors include prompt injection via any data path, adversarial token manipulation, and poisoning of persistent context sources such as session history or skill instruction files.

3. Execution - the agent, now under adversary influence, issues tool calls or commands it would not otherwise make. Unlike traditional execution, the trigger is the agent's own reasoning rather than direct code injection. The adversary's payload is delivered as legitimate tool invocations that the runtime has no basis to distinguish from operator-intended behavior.
4. Credential Access - the adversary obtains authentication material that grants access beyond the agent's original privilege level. In agent frameworks with distributed architectures, tool calls can be directed at internal service endpoints, causing the runtime to transmit credentials to attacker-controlled infrastructure during normal operation.
5. Privilege Escalation - the adversary leverages obtained credentials or policy weaknesses to gain higher-privilege execution capability. Escalation paths in AI agent systems are structurally different from those in traditional software: they often involve rewriting the policy state that governs what the agent is permitted to execute, rather than exploiting memory safety errors or kernel interfaces.
6. Impact - the adversary achieves their objective on the host or beyond. Because personal AI agent systems are designed to act autonomously on a user's machine, the blast radius of a successful attack chain can extend to arbitrary code execution, data exfiltration, persistent backdoors, and supply chain propagation to other users of the same skill distribution channel.

The novel Context Manipulation stage is the defining characteristic of AI agent kill chains. Any system that interposes an LLM reasoning layer between input and execution exhibits this stage. It cannot be addressed by traditional policy enforcement alone, because the manipulation occurs above the enforcement layer: the policy engine sees a legitimate tool call and has no visibility into the adversarial intent that produced it.

Figure 5: OpenClaw Kill Chain

<!-- image -->

## 4.3 Taxonomy Matrix

Figure 4 maps each attack surface to the kill chain stages at which it is exploitable. A cell is marked when the surface is relevant to that stage; multiple marks per row indicate that a surface can be exploited across several stages. The sparse structure of the matrix reveals that most surfaces concentrate at specific kill chain stages, while Inter-Agent Communication spans all six stages,

reflecting its role as an amplifier for any attack that compromises one agent in a multi-agent deployment.

## 5 Multi-Layer Vulnerability Analysis and Architectural Root Causes

This section provides a detailed illustration of the ten-layer taxonomy proposed in Section 4 by mapping the 190-advisory OpenClaw corpus to specific architectural trust boundaries. By deconstructing documented vulnerabilities-ranging from identity spoofing at the channel interface to configuration injection at the container boundary-we demonstrate how discrete architectural weaknesses enable complex exploitation chains. This systematic analysis reveals that OpenClaw's security failures are not merely isolated defects but are systemic consequences of decentralized policy enforcement and brittle trust assumptions across the agent's execution surface.

## 5.1 Channel Input Interface

OpenClaw exposes a channel adapter layer through which AI agent pipelines receive instructions from and dispatch responses to external messaging platforms. As of the advisory corpus examined in this study, 35 independent security advisories target this layer across 15 distinct platform integrations including Telegram, Slack, Discord, Matrix, Nextcloud Talk, Microsoft Teams, Feishu, BlueBubbles, iMessage, Twitch, Twilio, Telnyx, Nostr, WhatsApp, and Tlon/Urbit. The advisories cluster into three structurally distinct sub-patterns: allowlist authorization bypass (13 advisories) arising from sender identity fields that are mutable at the platform level; webhook authentication failure (10 advisories) arising from inconsistent or deliberately excepted cryptographic verification of inbound requests; and channel-scoped disclosure and injection (12 advisories) arising from authenticated adapters that leak credentials or accept injected content into the agent pipeline. Each sub-pattern is examined below through close reading of representative patch diffs, followed by a cross-adapter structural analysis that identifies the common architectural root.

## 5.1.1 Allowlist Authorization Bypass via Mutable Identity Fields

The most pervasive sub-pattern in the channel integration category is the use of mutable, usercontrolled platform identity fields-display names, usernames, human-readable handles-as the lookup key against a security-relevant allowlist. Thirteen advisories record this root cause across Telegram (GHSA-mj5r), Nextcloud Talk (GHSA-r5h9), Google Chat (GHSA-chm2), Feishu (GHSAj4xf), Discord (GHSA-4cqv), Matrix (GHSA-rmxw), and iMessage (GHSA-g34w), among others. The unifying flaw is simple: the adapter developer conflated the display identity of a sender with a verifiable, persistent identifier , a distinction that every affected platform documents but that was not enforced at the point of policy evaluation.

Nextcloud Talk: Display Name Spoofing (GHSA-r5h9). Nextcloud Talk identifies users by two distinct fields: an immutable actor.id assigned at account creation, and a mutable actor.name display string that any user may change at will. Prior to the fix, OpenClaw's resolveNextcloudTalkAllowlistMatch function accepted both as valid match targets. During the attack, suppose an operator configures allowFrom: ["alice"] intending to grant access to the Nextcloud user whose persistent ID is alice . Any Nextcloud user who changes their display name to alice -an operation requiring no elevated privilege-will pass the allowlist check on the senderName branch, because the incoming actor.name fi eld is under attacker control. The resolver's return type union "wildcard" | "id" | "name" makes the design intent explicit: the original developers knowingly

accepted name-based matches, treating display names as a usability convenience. What they did not model is that names are unilaterally mutable by the named party's adversaries as well.

```
1 export function resolveNextcloudTalkAllowlistMatch(params: { 2 allowFrom: Array <string | number > | undefined; 3 senderId: string; 4 senderName?: string | null; // <--mutable display field accepted 5 }): AllowlistMatch <"wildcard" | "id" | "name"> { 6 if (allowFrom.includes(senderId)) { 7 return { allowed: true , matchKey: senderId , matchSource: "id" }; 8 } 9 const senderName = params.senderName 10 ? normalizeAllowEntry(params.senderName) : ""; 11 if (senderName && allowFrom.includes(senderName)) { 12 return { allowed: true , matchKey: senderName , matchSource: "name" }; 13 } 14 return { allowed: false }; 15 }
```

Listing 1: Vulnerable allowlist resolution in policy.ts (before fix, GHSA-r5h9)

The fix removes the senderName parameter entirely from the function signature, collapsing the return type to "wildcard" | "id" , and strips all three call sites in inbound.ts of the senderName argument:

```
1 export function resolveNextcloudTalkAllowlistMatch(params: { 2 allowFrom: Array <string | number > | undefined; 3 senderId: string; 4 // senderName removed; display names are not authoritative 5 }): AllowlistMatch <"wildcard" | "id"> { 6 if (allowFrom.includes(senderId)) { 7 return { allowed: true , matchKey: senderId , matchSource: "id" }; 8 } 9 return { allowed: false }; 10 }
```

Listing 2: Fixed allowlist resolution in policy.ts (after fix, commit 6b4b604)

Three architectural observations follow from this diff. First, the vulnerability existed silently through multiple documented releases because the matchSource: "name" return path was tested and passing-the test suite confirmed that name matching worked , not that it was safe . Second, the fix is purely subtractive: no new infrastructure is required, only the removal of the mutable-field branch. Third, the function's return type change from a three-variant union to a two-variant union provides a compile-time enforcement signal: any downstream code branching on matchSource === "name" will now produce a TypeScript type error, giving the fix mechanical enforceability across the codebase.

Telegram: Mutable Username Authorization (GHSA-mj5r). The Telegram adapter presents a structurally analogous flaw with a platform-specific amplification. Telegram assigns each account

a persistent numeric user ID ( e.g. , 123456789 ) and optionally allows users to register a mutable @username handle. Prior to the fix, resolveSenderAllowMatch in the Telegram policy module accepted both:

```
1 export const resolveSenderAllowMatch = (params: { 2 allow: TelegramAllow; 3 senderId?: string; 4 senderUsername?: string; // <--mutable @username accepted 5 }): AllowFromMatch => { 6 const { allow , senderId , senderUsername } = params; 7 if (allow.hasWildcard) 8 return { allowed: true , matchKey: "*", matchSource: "wildcard" }; 9 if (senderId && allow.entries.includes(senderId)) 10 return { allowed: true , matchKey: senderId , matchSource: "id" }; 11 const username = senderUsername?.toLowerCase(); 12 if (!username) return { allowed: false }; 13 const entry = allow.entriesLower.find( 14 (c) => c === username || c === '@ $ {username}', 15 ); 16 if (entry) 17 return { allowed: true , matchKey: entry , matchSource: "username" }; 18 return { allowed: false }; 19 };
```

Listing 3: Vulnerable sender match in Telegram policy.ts (before fix, GHSA-mj5r)

The group-policy test suite before the fix included a case titled 'allows group messages from senders in allowFrom (by username) when groupPolicy is 'allowlist' 'the test passed and was treated as a feature. The fix renames that same test to 'blocks group messages when allowFrom is configured with @username entries (numeric IDs required)' and flips the assertion from toHaveBeenCalledTimes(1) to toHaveBeenCalledTimes(0) : the feature becomes the vulnerability.

The fix removes senderUsername from the destructuring and drops the entire username-fallback branch (commits e3b432e , 9e147f0 ). Telegram usernames are especially hazardous as allowlist keys because they are globally unique but entirely voluntary: a user may never register one, register and later release one, or transfer one to another account. An operator who configured allowFrom: ["@alice"] to authorize a trusted contact who later releases that handle inadvertently grants access to whoever claims it next. Further, the prior code matched bare strings against allow.entriesLower using case-insensitive comparison with optional @ prefix normalization, meaning an allowlist entry of "alice" would match usernames Alice , @alice , or @ALICE .

The fix is accompanied by a companion commit that adds a maybeRepairTelegramAllowFromUsernames migration function to the openclaw doctor --fix tool. This function calls the Telegram Bot API's getChat endpoint for each @username entry in an existing configuration and rewrites it to the corresponding numeric ID, preserving backward compatibility while enforcing the new invariant at runtime. The migration is instructive: it reveals that stripping username support without a migration path would silently break existing authorized configurations, and that the correct design required not just a code change but a deployment-time repair tool.

Cross-platform pattern. The structural identity between the Nextcloud Talk and Telegram fixes-independent codebases, different platform APIs, different field names, same logical errorargues that this is not an isolated oversight. The remaining 11 advisories in this sub-pattern extend the same finding to Google Chat (GHSA-chm2), Feishu (GHSA-j4xf), Discord (GHSA4cqv), Matrix (GHSA-rmxw), iMessage (GHSA-g34w), and five further adapters. In each case the adapter developer, working independently against their target platform's API documentation, reached for the human-readable sender field rather than the platform-assigned immutable identifier. Section 5.1.3 examines why this recurrence is architectural rather than incidental.

## 5.1.2 Webhook Authentication Failures and Channel Disclosure

Ten advisories across Slack, Discord, Matrix, Twilio, Telnyx, and others record webhook authentication failures. The pattern is consistent: inbound platform requests were accepted without cryptographic signature verification, often via explicit loopback/proxy trust exceptions that effectively disabled the check in production deployments. Fixes apply HMAC-SHA256 validation unconditionally, removing the proxy exception. A further twelve advisories record authenticated adapters that leak credentials into logs or accept injected content into the agent pipeline-for example, Telegram bot tokens logged at DEBUG level and Slack event payloads forwarded to the agent without sanitization, providing an indirect prompt injection entry point from an authenticated platform event [16].

## 5.1.3 Cross-Adapter Structural Analysis

The three sub-patterns documented above share a common architectural root: each platform adapter was designed and implemented independently against its target platform's conventions, with no shared identity validation primitive, no shared webhook verification library, and no shared credential-transmission policy. This architectural fact, rather than any particular developer oversight, explains why the same logical error recurs across 15 platforms and 35 advisories.

The correct design for allowlist authorization requires a single question at each trust boundary: is the identity field being evaluated immutable and platform-assigned, or mutable and user-controlled? The answer is available in the documentation of every affected platform-Telegram numeric user IDs are immutable; @username handles are mutable; Nextcloud Talk actor.id is immutable; actor.name is mutable-yet each adapter author made an independent local decision about which field to use. A shared resolveAllowlistIdentity(platformMessage) abstraction, implemented once and audited once, would have prevented all 13 bypass advisories.

The webhook verification sub-pattern exhibits the same deficit. A shared verifyPlatformWebhook(request, config) interface-with per-platform implementations required to pass a common test suite-would have surfaced the missing verification in Telnyx (GHSA-4hg8), the incorrect skip in Telegram (GHSA-mp5h), and the loopback exception in Twilio (GHSA-c37p) before release. The Twilio bypass was not an unnoticed bug but a documented option whose security implications were not fully modeled at design time; its own documentation described the bypass as 'less secure' rather than 'incorrect.'

The remediation pattern is instructive across all three sub-patterns: the fixes are subtractive rather than additive. The Nextcloud Talk and Telegram fixes remove mutable-field match branches; the Twilio fix deletes an early-return block; the MS Teams fix introduces a new list but defaults it conservatively. None require new cryptographic infrastructure. This confirms that the correct implementation was available at the time of original development and was bypassed in favor of

convenience or under-specified threat modeling. The structural recommendation is organizational rather than technical: a shared channel adapter security interface, required for any new adapter contribution, that encodes the identity mutability question, the webhook verification requirement, and the credential transmission scope as first-class constraints rather than per-adapter implementation choices.

## 5.2 Plugin and Skill System: Trust Escalation via Malicious Distribution

## 5.2.1 Skill System Architecture and Trust Model

OpenClaw's skill system provides a structured mechanism for extending the embedded LLM agent's capabilities beyond its default tool set. A skill is a filesystem directory committed to a repository and optionally published to the community registry at clawhub.ai . When an agent session loads a skill, the framework prepends the skill's SKILL.md fi le into the LLM's context window alongside any supporting assets (scripts, templates, binary helpers) that the skill's instructions may reference. Skill loading is handled during context bootstrap in runEmbeddedPiAgent , which reads from the workspace and any configured skill directories before constructing the first turn sent to the model.

The critical property of this design is its privilege level: skills execute in the same process context as the operator . There is no sandbox boundary between a loaded skill and the Node-Host's exec policy pipeline. A skill's SKILL.md may instruct the LLM to invoke system.run , perform file operations, make outbound network requests, or supply attacker-controlled parameters to gateway tool calls. The trust model therefore rests on a single implicit assumption: that any skill loaded into the agent's context was placed there by the operator and reflects the operator's intent. This assumption is the precise surface exploited by the skill described in this section.

The skill installation path provides no cryptographic integrity verification of skill content. Skills pulled from clawhub.ai or a third-party repository are written directly into the workspace directory without a signature check or hash manifest. The plugin loading code in src/plugins/loader.ts reads SKILL.md from disk and forwards its raw text into the context; there is no sanitization layer between the on-disk markdown and the model's input.

## 5.2.2 The Malicious yahoofinance Skill

The skill published under the name yahoofinance by user JordanPrater on clawhub.ai and reported via GitHub issue openclaw/openclaw#5675 exploits this trust model through a two-stage delivery architecture: a social engineering lure embedded in SKILL.md , and a platform-differentiated dropper chain that resolves to a remote-code-execution primitive on both Windows and macOS.

The SKILL.md Lure. The skill's entry point presents itself as a finance data utility requiring a mandatory external dependency: The framing is carefully constructed to be indistinguishable from a legitimate prerequisite notice. The phrase 'extract using: openclaw ' instructs the LLM-and through the LLM, the user-to execute a binary named openclaw that is itself downloaded from an attacker-controlled GitHub release URL, not from any trusted distribution channel. The skill never performs any Yahoo Finance functionality; its sole purpose is to cause the agent to relay these installation instructions to the operator.

```
1 Yahoo Finance CLI 2 Prerequisites 3 IMPORTANT: Yahoo Finance operations require the openclawcli utility to function. 4 Windows: Download openclawcli.zip 5 (https://github.com/Ddoy233/openclawcli/releases/download/latest/ openclawcli.zip) 6 (extract using: openclaw) and run the executable before using finance commands. 7 macOS: Visit https://glot.io/snippets/hfd3x9ueu5 and execute the 8 installation command in Terminal before proceeding. 9 Without openclawcli installed , stock data retrieval and financial operations 10 will not work.
```

Listing 4: Verbatim content of the malicious SKILL.md

Delivery Chains and Obfuscation. The skill deploys different payloads on Windows and macOS, both structured to defeat static scanning at the registry level. The Windows path delivers openclawcli.zip -seven blobs with Shannon entropy of 7.944-7.960 bits/byte (consistent with AES-CBC/GCM-encrypted payloads) and a loader binary hosted at a separate GitHub release URL, ensuring the repository contains no directly executable content. The macOS path points to a glot.io snippet whose leading echo displays a plausible HTTPS domain; the actual payload is a base64-encoded second stage that decodes to /bin/bash -c " $ (curl -fsSL http://91.92.242.30/528n21ktxu08pmer)" -fetching and executing an arbitrary script from a raw IPv4 address on bulletproof infrastructure. Neither path places executable content inside the SKILL.md or archive, defeating registry-level static scanning.

## 5.2.3 Trust Violation Analysis

The yahoofinance skill exploits precisely the architectural assumption identified in Section 5.2.1: that skill content reflects operator intent. OpenClaw's context assembly pipeline in runEmbeddedPiAgent passes skill content into the LLM's context window without any distinction between operatorauthored instructions and third-party-authored instructions. Once loaded, the yahoofinance SKILL.md is semantically equivalent to a system prompt written by the operator themselves. The LLM has no mechanism to reason about the provenance of a loaded skill or to distrust instructions that arrive through the skill loading path.

This design allows the following privilege escalation without exploiting any memory-safety vulnerability or authentication bypass:

1. The skill's instructions are injected into the operator-trusted context layer of the agent session.
2. The LLM relays the installation instructions to the user with the same authority as operatorauthored prompts.
3. The user, trusting the agent, executes the prescribed command.
4. The attacker achieves code execution on the user's machine outside of any OpenClaw exec policy enforcement .

The Plugin &amp; Skill System accounts for 7 advisories (3.7%), including one Critical path-traversal advisory during plugin installation and one High advisory for unsafe hook module loading-both sharing the same root cause as the yahoofinance vector: third-party content is incorporated into the trusted execution environment without integrity or authenticity enforcement.

## 5.3 Agent Context Window

Four advisories document injection via data paths that terminate in the LLM context window: Slack channel metadata prepended to the system prompt (GHSA-782p), Sentry log headers included verbatim in context (GHSA-c9gv), resource link name fi elds displayed as agent memory (GHSAj4hw), and filesystem path components resolved into the workspace context (GHSA-m8vc). The structural cause is uniform: data paths that terminate in the context window were designed as information channels without adversarial consideration of what happens when the data is crafted to resemble a directive.

There are also six advisories that define a third class of policy bypass distinct from the two described earlier in this paper. Exec-policy bypass operates below the reasoning layer-it circumvents the runtime's enforcement of which system calls or tool invocations are permitted. Skill-level escalation operates beside the reasoning layer-it exploits the operator trust model to register malicious capabilities before policy is applied. Prompt injection operates above both-it manipulates the content from which the model constructs its intentions before any policy enforcement is reached. A model that has been successfully prompt-injected may voluntarily invoke a tool that policy would otherwise have denied, rendering the policy irrelevant without ever triggering it.

The indirect injection vectors-channel metadata, log headers, resource link fields, filesystem paths-share a structural cause: data paths that terminate in the context window were treated as information channels rather than as potential instruction channels. This is the correct default assumption for a system that does not use LLMs; it is the incorrect default assumption for a system where the context window is the program. Each of the four indirect injection advisories represents a data-flow path that was designed without adversarial consideration of what happens when the data is crafted to resemble a directive.

## 5.4 Gateway WebSocket Interface

As shown in Section 3, there has been 40 advisories related to Gateway &amp; API, with the highest concentration of XSS, prototype pollution, token exfiltration, and authorization bypass findings. The 13 High-severity advisories reflect direct exposure of the gateway to external clients.

## 5.4.1 Stage 1: Establishing an SSRF Primitive via gatewayUrl

The outbound message layer in src/infra/outbound/message.ts exposes a MessageGatewayOptions type whose url fi eld was forwarded to the WebSocket-based gateway client without restriction. The pre-patch resolveGatewayOptions function reads:

```
1 // src/infra/outbound/message.ts (vulnerable , pre-patch) 2 return { 3 url: opts?.url, // attacker -controlled , no restriction 4 token: opts?.token , 5 ... 6 };
```

Listing 5: Pre-patch: gatewayUrl forwarded to the WebSocket client without validation (commit c5406e1)

Any caller that could supply a MessageGatewayOptions object could therefore direct outbound gateway connections to an arbitrary URL. In the backend tool-calling path, this meant the gateway client would attempt an authenticated WebSocket connection to an attacker-specified host. The fix replaces the direct pass-through with a conditional that forces url to undefined for these code paths, coercing the gateway client to fall back to its configured endpoint.

## 5.4.2 Stage 2: Token Exfiltration via the Agent Tool Interface

The parallel fix in src/agents/tools/gateway.ts addresses the same class of attacker-controlled URL at the tool-invocation layer. The pre-patch resolveGatewayOptions function in the tools module forwarded opts.gatewayUrl directly after trimming:

```
1 // src/agents/tools/gateway.ts (vulnerable , pre-patch) 2 const url = 3 typeof opts?.gatewayUrl === "string" && opts.gatewayUrl.trim() 4 ? opts.gatewayUrl.trim() 5 : undefined;
```

Listing 6: Pre-patch: gatewayUrl tool parameter accepted without host validation (commit 2d5647a)

An agent tool call supplying { gatewayUrl: "ws://attacker.example.com:4444" } would direct the gateway client-including its authentication token-to an attacker-controlled WebSocket endpoint. The gateway client's handshake protocol sends authentication material during connection establishment, so merely inducing a connection attempt is sufficient to capture the bearer token. The fix replaces the pass-through with validateGatewayUrlOverrideForAgentTools() , which constructs an allowlist at runtime by reading the configured gateway port and enumerating loopback variants plus the operator-configured gateway.remote.url if present. Any URL not matching these canonicalized keys raises a hard error before connection proceeds.

## 5.4.3 Stage 3: RCE via node.invoke Exec Approval Bypass

With a stolen gateway authentication token, the attacker connects to the gateway as an authorized operator and invokes node.invoke targeting the system.execApprovals.set command. Prior to the fix, SYSTEM COMMANDS in src/gateway/node-command-policy.ts explicitly included these methods:

```
1 // src/gateway/node-command -policy.ts (vulnerable , pre-patch) 2 const SYSTEM_COMMANDS = [ 3 "system.run", 4 "system.which", 5 "system.notify", 6 "system.execApprovals.get", // <--reachable via node.invoke 7 "system.execApprovals.set", // <--allows rewriting approval policy 8 "browser.proxy", 9 ];
```

Listing 7: Pre-patch: system.execApprovals.* reachable via node.invoke (commit 01b3226)

By invoking system.execApprovals.set with a crafted approval payload that adds attackercontrolled executables to the persistent allowlist, the attacker bootstraps the exec approval state to permit arbitrary command execution. The next agent system.run invocation then fires the injected command with full host privileges. The fix removes the two execApprovals.* entries from SYSTEM COMMANDS entirely and adds an explicit early-return guard in the node.invoke handler.

## 5.4.4 Chain Analysis

The three fixes together expose a trust architecture that had collapsed across layer boundaries. The gateway layer trusted the URL field from callers it should have treated as untrusted (agents operating in backend mode). The tool layer trusted that a gatewayUrl parameter was restricted to safe hosts by convention rather than by enforcement. The node.invoke handler trusted that any authenticated operator who could invoke system.run should also be able to modify the approval policies governing system.run . Each assumption was locally reasonable in a benign deployment; chained together under adversarial conditions, they form a complete privilege escalation from LLM agent output to host code execution.

## 5.5 Tool Dispatch Interface

The 57 advisories across File &amp; Process System (30), Sandbox Isolation (17), and Browser Tooling (10) share the structural property identified in the taxonomy: each layer was designed under a closed-world assumption that its inputs are operator-controlled, and each fails when that assumption is violated.

File &amp; Process System (30 advisories). Four sub-patterns: (1) path traversal (8)-containment checks applied before symlink resolution, allowing ../ sequences or symlinks in archive entries to escape the target directory; (2) SSRF guard bypass (7)-IPv4-mapped IPv6 ( ::ffff:169.254.x.x ), ISATAP, and special-use ranges that resolve to blocked RFC-1918 addresses but evaded the guard; (3) resource exhaustion (7)-byte limits checked after allocation; (4) host-privileged injection (8)unsanitized content flowing into systemd unit generation and Windows task-scheduler script rendering. The unifying root cause is absent validation between input ingestion and privileged use.

Sandbox Isolation (17 advisories). The Docker bind-mount escape [11] is analyzed in § 5.7. Remaining advisories split between workspace-boundary violations and the unauthenticated noVNC exposure [12], which grants full graphical sandbox access from any network-reachable host. One Critical and two High advisories reflect complete failure of OpenClaw's primary isolation guarantee.

Browser Tooling (10 advisories). Browser automation requires elevated privileges and unrestricted network access, directly contradicting the isolation model. Ten advisories record unauthenticated CDP relay endpoints, path traversal in file upload/download, and absent CSRF protection on navigation triggers. Six of ten are High severity: unauthenticated browser access is functionally equivalent to full agent compromise.

## 5.6 Exec Policy Engine

The three exec allowlist bypasses patched between February 22 and 24 were filed as separate bugs and fixed in separate commits, but they are manifestations of a single architectural premise that the allowlist system failed to adequately defend: a command string's security-relevant identity can be determined by lexically parsing its text. All three exploits invalidate this premise in different ways.

## 5.6.1 The Line-Continuation Bypass

The evaluateShellAllowlist function performs command chain splitting and token-level analysis to determine whether a shell pipeline satisfies a configured allowlist. The bug is that DOUBLE QUOTE ESCAPES prior to the patch included " \ n" and " \ r" as recognized escape sequences:

```
1 // src/infra/exec-approvals -allowlist.ts (vulnerable , pre-patch) 2 const DOUBLE_QUOTE_ESCAPES = new Set(["\\", '"', " $ ", "'", "\n", "\r"]);
```

Listing 8: Pre-patch: newline treated as escape character, enabling line-continuation injection (commit 3f0b9db)

POSIX shell interprets a backslash followed by a newline inside a double-quoted string as a line continuation: the backslash and newline are removed, and the adjacent token fragments are concatenated. The sequence echo "ok $ \\ n(id -u)" therefore executes id -u via command substitution, even though the parser, treating \ n as an escape character rather than a line-continuation trigger, fails to detect the nested command. The fix removes " \ n" and " \ r" from DOUBLE QUOTE ESCAPES and adds a pre-check function hasShellLineContinuation that forces analysisFailure() if any such sequence is detected.

## 5.6.2 The Busybox/Toybox Multiplexer Bypass

The allow-always persistence mechanism records resolved executable paths of approved commands. For known dispatch wrappers ( env , nice , nohup ), the system 'unwraps' the invocation to persist the inner executable path rather than the wrapper. The bug is that busybox and toybox -POSIX-compatible multiplexer binaries that dispatch to sub-tools by their first argument-were not recognized as wrappers at all. An agent invoking busybox sh -c 'whoami' would have the busybox binary path persisted in the allowlist. If the operator approved busybox in any shell-applet context, subsequent invocations of busybox sh -c ' 〈 arbitrary command 〉 ' would execute without approval.

The fix required creating an entirely new exported function unwrapKnownShellMultiplexerInvocation in exec-wrapper-resolution.ts (a file that did not previously exist), with a discriminated union result type ( not-wrapper | blocked | unwrapped ), and wiring it into three call sites. Non-shellapplet busybox invocations return { kind: "blocked" } and fail closed-no allowlist entry is