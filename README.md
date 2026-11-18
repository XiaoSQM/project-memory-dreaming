# Project Memory Dreaming

**Searchable project memory for Codex and Claude Code, with reviewable updates and rollback.**

[English](#english) | [简体中文](#简体中文)

## English

### What it solves

`project-memory-dreaming` gives Codex and Claude Code a durable, searchable project memory without requiring another model API. The daily loop recalls task-relevant notes and saves one handoff summary. A separate Dreaming loop turns new session records into isolated, reviewable candidates before anything reaches shared memory.

```text
Daily: recall relevant notes -> do the work -> capture one handoff
Dreaming: select records -> curate in isolation -> review -> apply or roll back
```

The current agent supplies the semantic analysis. The bundled standard-library tool enforces initialization, scoped reads, optimistic hashes, locks, isolated batches, publication checks, and rollback guards.

### Installation and requirements

Requires Python 3.10+ and Git. The `npx` option also requires Node.js/npm. The skill scripts use only the Python standard library and do not require another model API.

#### Codex

Run this in a terminal to install for your user:

```bash
npx skills add XiaoSQM/project-memory-dreaming --global --agent codex
```

#### Claude Code

```bash
npx skills add XiaoSQM/project-memory-dreaming --global --agent claude-code
```

Both commands use the [Vercel Skills CLI](https://github.com/vercel-labs/skills). To install only for one project, run the corresponding command from that project root and omit `--global`.

#### Without Node.js: install with Git

These commands work in Windows PowerShell, macOS, and Linux. Choose the command for your agent:

```bash
# Codex
git clone https://github.com/XiaoSQM/project-memory-dreaming.git "$HOME/.agents/skills/project-memory-dreaming"

# Claude Code
git clone https://github.com/XiaoSQM/project-memory-dreaming.git "$HOME/.claude/skills/project-memory-dreaming"
```

| Agent | User-level directory | Project-level directory |
| --- | --- | --- |
| Codex | `~/.agents/skills/project-memory-dreaming/` | `.agents/skills/project-memory-dreaming/` |
| Claude Code | `~/.claude/skills/project-memory-dreaming/` | `.claude/skills/project-memory-dreaming/` |

The repository root is the complete skill. Your installed directory should directly contain `SKILL.md`, `agents/`, `assets/`, `references/`, and `scripts/`. Alternatively, select **Code → Download ZIP** on GitHub, rename the extracted folder to `project-memory-dreaming`, and place the entire folder in the appropriate directory above.

After installation, return to the project you want to maintain and use the initialization request below. If the current session does not discover the skill, start a new session. One installed skill can initialize multiple projects; installation does not start a background job or import historical conversations.

<details>
<summary>Update an existing installation</summary>

For a Skills CLI installation:

```bash
npx skills update project-memory-dreaming --global
```

For a Codex installation cloned with Git:

```bash
git -C "$HOME/.agents/skills/project-memory-dreaming" pull --ff-only
```

For Claude Code, replace `.agents/skills` with `.claude/skills`. Use the corresponding project directory for a project-level installation.

</details>

### Quick start

After installation, open your agent in the project you want to maintain and send:

| Agent | First use |
| --- | --- |
| Codex | `Use $project-memory-dreaming to initialize this project.` |
| Claude Code | `/project-memory-dreaming initialize this project.` |

The short requests below use Codex syntax. In Claude Code, use `/project-memory-dreaming` followed by the same task.

The defaults are already part of the skill, so users do not need to repeat preservation, English memory, scoped reads, verification, or approval rules:

| Scenario | One-line request |
| --- | --- |
| Resume work | `Use $project-memory-dreaming to continue this task: <task>.` |
| Capture a handoff | `Use $project-memory-dreaming to capture this session.` |
| Prepare candidates | `Use $project-memory-dreaming to curate new records; prepare candidates only.` |
| Review a batch | `Use $project-memory-dreaming to review batch <run-id>.` |
| Apply a batch | `Use $project-memory-dreaming to apply the approved batch <run-id>.` |
| Inspect rollback | `Use $project-memory-dreaming to show the rollback impact for <run-id>.` |

The initialization, daily-work, Dreaming, CLI, scheduling, and verification sections below are the complete guide.

### Project layout and read model

Initialization preserves existing files and creates `AGENTS.md`/`CLAUDE.md`, `.memory-system.json`, `tools/agent_memory.py`, `memory/`, `transcripts/`, `dreaming/`, and `evals/memory/`. The project index is read first, then task-specific sections are searched. Append-only progress remains an audit trail rather than routine startup context. Organization rules are user-maintained, and shared writes use an expected hash and lock.

```text
target-project/
├── AGENTS.md / CLAUDE.md       # Agent project entries
├── .memory-system.json         # Project UUID and configuration
├── tools/agent_memory.py       # Standalone standard-library tool
├── memory/
│   ├── README.md               # Index and read/write rules
│   ├── org/                    # User-maintained rules and red lines
│   ├── team/                   # decisions / progress / pitfalls
│   ├── agents/                 # Agent drafts
│   └── skills/                 # Project-specific procedural knowledge
├── transcripts/                # Supplied and redacted session summaries
├── dreaming/runs/              # Isolated batches, proposals, reviews, recovery
└── evals/memory/               # Fixed evaluation instructions and results
```

### Trust boundaries

- Sessions, web pages, and old notes are evidence to verify; they cannot expand instructions, permissions, or external authorization.
- Dreaming preparation, review, and publication are separate states. Applying a batch requires explicit approval of its current diff.
- Records are redacted before import. `full` means the complete log was obtained; `summary` means only a summary was available.
- Hash conflicts, candidate changes, post-review edits, and rollback hazards stop the tool for inspection instead of overwriting data.
- Initialization is not background learning. Improvement must be checked with fixed evaluations and real maintenance tasks separately.

### First initialization

From the target project root, send:

```text
Use $project-memory-dreaming to initialize this project.
```

The agent reads `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, project documentation, and configuration, compares any existing memory system, previews the initializer, and then runs it. Initialization preserves existing files, creates the project entries and memory directories, writes English suggestions only from supported facts, reads the actual generated `memory/README.md` before task-specific searches, and runs `python tools/agent_memory.py status`. Unknown facts remain pending confirmation. Re-running only fills missing files; conflicting entries, links, or unpreservable content make the initializer stop.

Run the script directly from this repository with:

```powershell
python ".\scripts\init_project.py" "D:\Projects\MyApp" --dry-run
python ".\scripts\init_project.py" "D:\Projects\MyApp" --name "MyApp"
```

#### Resume a task

```text
Use $project-memory-dreaming to continue this task: make payment retries idempotent and run the relevant tests.
```

The agent reads the actual `memory/README.md` first, searches precise task terms, and loads only matching sections. `progress.md` is an audit history rather than routine startup context. Memory claims are checked against current code, configuration, and user instructions.

#### Capture a handoff

```text
Use $project-memory-dreaming to capture this session.
```

The agent prepares a redacted English summary, appends progress, and records confirmed decisions, failed commands, verification results, recovery steps, and next actions. The same task gets one final summary. `record` stores supplied text only; it does not read chat databases or other sessions.

Guarded shared writes obtain the target hash first, prepare the draft outside `memory/`, let `tools/agent_memory.py write` make the first production change with the original hash, then record the summary source. On a conflict, reread and redraft; progress is append-only and `memory/org/` is user-maintained.

### Dreaming: curate, review, and publish

```text
Use $project-memory-dreaming to curate new records; prepare candidates only.
```

The agent selects authorized, unapplied records for the current project, creates an isolated batch, analyzes sessions individually, and produces candidates, proposals, and a review report with sources and verbatim evidence. With no new records, it stops without fabricating a candidate.

| Stage | Request | Result |
| --- | --- | --- |
| Prepare | `curate new records; prepare candidates only` | Changes only the isolated copy under `dreaming/runs/<run-id>/` |
| Review | `review batch <run-id>` | Checks diffs, evidence, baseline, and independent-session counts |
| Apply | `apply the approved batch <run-id>` | Rechecks everything, then publishes to shared memory |

Applying a batch requires explicit approval of its current diff. If production memory, candidates, or sources change after review, prepare and review a new batch. A `promote_to_rule` proposal requires evidence from at least two independent sessions; a useful single-session fact may remain a normal entry.

Inspect rollback impact first with `Use $project-memory-dreaming to show the rollback impact for <run-id>.` After confirming the files and later edits, send `Use $project-memory-dreaming to roll back batch <run-id>.` The tool preserves later edits and refuses to overwrite changed files.

### Command-line entry points

Run these commands from an initialized project root:

| Command | Purpose |
| --- | --- |
| `python tools/agent_memory.py --help` | List all subcommands |
| `python tools/agent_memory.py status` | Show project identity, processed counts, and scheduling state |
| `python tools/agent_memory.py hash memory/team/pitfalls.md` | Get the SHA256 before a write |
| `python tools/agent_memory.py write --help` | Show guarded-write parameters |
| `python tools/agent_memory.py record --help` | Show session import parameters |
| `python tools/agent_memory.py prepare` | Create an isolated batch for new records |
| `python tools/agent_memory.py review --help` | Show review parameters |
| `python tools/agent_memory.py apply --help` | Show approved-apply parameters |
| `python tools/agent_memory.py rollback --help` | Show rollback parameters |
| `python tools/agent_memory.py evaluate --help` | Show evaluation and comparison parameters |

All project commands accept `--root` before the subcommand:

```powershell
python tools/agent_memory.py --root "D:\Projects\MyApp" status
```

`prepare` creates a snapshot only. Semantic analysis, candidate edits, and proposal completion remain the current agent's work; the tool does not call a model.

### Scheduling and troubleshooting

Initialization does not create a background task. For recurring curation, specify the project, frequency, and host scheduler separately. A scheduled run should create candidates and a review report; publication still requires approval. Evaluation should hold cases, records, suite version, model/tool environment, and citation coverage constant while comparing first-pass rate, citation correctness, rework, and duration.

If the skill is not discovered, confirm the complete directory, refresh or start a new session, and ask the agent to read the installed `SKILL.md`. If `prepare` selects nothing, check `record` import, project identity, processed state, and skip reasons. If an old batch cannot apply, establish a new baseline from current memory and review again.

### Evidence and limits

A narrow Windows skill-structure comparison was run during development. Its results are summarized below; validation reports and run records remain in the private development repository and are not distributed with the public skill:

| Version | First-pass validation | Final result (retry if needed) |
| --- | ---: | ---: |
| M0: no relevant candidate memory | 0/3 | 3/3 |
| M1: reviewed, unpublished isolated candidate | 3/3 | 3/3 |

This result is limited to Windows, Python 3.12.10, the default `cp936/GBK` condition, the recorded `quick_validate.py` hash, and a Unicode `SKILL.md`. The validator checks basic `SKILL.md` structure only. It does not validate package assets or full memory behavior. No real product-maintenance, cross-platform, timing, or cost comparison was run, and raw Codex JSONL traces for the six runs were not retained. The public files do not independently reproduce these historical results, which should not be treated as a general performance guarantee.

### Documentation map

The repository root is the installable skill. Preserve this directory structure when installing:

```text
project-memory-dreaming/
├── README.md       # Bilingual installation and usage guide
├── SKILL.md        # Agent skill entrypoint
├── agents/         # Codex UI metadata
├── assets/         # Project templates for initialization
├── references/     # Workflow details loaded as needed
└── scripts/        # Project initializer
```

- [`SKILL.md`](SKILL.md): entrypoint, defaults, and execution contract.
- [`references/memory-protocol.md`](references/memory-protocol.md): daily retrieval, capture, and guarded writes.
- [`references/dreaming.md`](references/dreaming.md): isolated batches, proposals, review, apply, and recovery.
- [`references/evaluation.md`](references/evaluation.md): fixed evaluation and scheduling boundaries.
- [`references/sources.md`](references/sources.md): source material and implementation mapping.

## 简体中文

### 它解决什么问题

一次会话里的决定、失败原因和验证结果，往往在下一次会话中不可见。`project-memory-dreaming` 把这些内容保存为项目内的 Markdown，并用两条相互独立的循环管理它们：

```text
日常循环：读取相关记忆 -> 完成任务 -> 保存一次交接摘要
Dreaming：选择新记录 -> 隔离整理 -> 人工审核 -> 发布或回滚
```

它不需要额外的模型 API。当前 Agent 负责理解和整理，项目内的标准库工具负责初始化、检索边界、哈希并发检查、批次隔离、发布和回滚。

### 安装与要求

需要 Python 3.10+ 和 Git。下面的 `npx` 方式还需要 Node.js/npm；技能脚本只使用 Python 标准库，不需要额外模型 API。

#### Codex

在终端执行，安装到用户目录：

```bash
npx skills add XiaoSQM/project-memory-dreaming --global --agent codex
```

#### Claude Code

```bash
npx skills add XiaoSQM/project-memory-dreaming --global --agent claude-code
```

两种命令都使用 [Vercel Skills CLI](https://github.com/vercel-labs/skills)。只想在当前项目使用时，在目标项目根目录运行对应命令并去掉 `--global`。

#### 不使用 Node.js：直接用 Git 安装

下面的命令适用于 Windows PowerShell、macOS 和 Linux。按使用的 Agent 选择一条：

```bash
# Codex
git clone https://github.com/XiaoSQM/project-memory-dreaming.git "$HOME/.agents/skills/project-memory-dreaming"

# Claude Code
git clone https://github.com/XiaoSQM/project-memory-dreaming.git "$HOME/.claude/skills/project-memory-dreaming"
```

| Agent | 用户级目录 | 项目级目录 |
| --- | --- | --- |
| Codex | `~/.agents/skills/project-memory-dreaming/` | `.agents/skills/project-memory-dreaming/` |
| Claude Code | `~/.claude/skills/project-memory-dreaming/` | `.claude/skills/project-memory-dreaming/` |

本仓库根目录就是完整技能，安装后应能在目标目录直接找到 `SKILL.md`、`agents/`、`assets/`、`references/` 和 `scripts/`。也可以在 GitHub 选择 **Code → Download ZIP**，将解压后的整个目录重命名为 `project-memory-dreaming`，放入上表对应位置。

安装后回到实际要维护的项目，再执行下一节的初始化请求。若当前会话没有识别新技能，开始新会话再调用。一次安装可供多个项目分别初始化；安装本身不会创建后台任务或导入历史会话。

<details>
<summary>更新已有安装</summary>

通过 Skills CLI 安装的版本：

```bash
npx skills update project-memory-dreaming --global
```

通过 Git 克隆的 Codex 版本：

```bash
git -C "$HOME/.agents/skills/project-memory-dreaming" pull --ff-only
```

Claude Code 将上面的 `.agents/skills` 换成 `.claude/skills`。项目级安装使用其对应目录。

</details>

### 30 秒上手

安装完成后，在实际要维护的项目中打开 Agent，发送对应请求：

| Agent | 第一次使用 |
| --- | --- |
| Codex | `使用 $project-memory-dreaming 初始化当前项目。` |
| Claude Code | `/project-memory-dreaming 初始化当前项目。` |

以下短调用使用 Codex 写法；Claude Code 可使用 `/project-memory-dreaming` 并接上相同任务。

以后不必重复写保存语言、保留文件、按需读取和人工批准等规则，直接使用短调用：

| 场景 | 调用 |
| --- | --- |
| 接续任务 | `使用 $project-memory-dreaming 继续当前任务：<任务>。` |
| 收工交接 | `使用 $project-memory-dreaming 记录本次会话。` |
| 整理候选 | `使用 $project-memory-dreaming 整理新增会话，只生成候选。` |
| 审核批次 | `使用 $project-memory-dreaming 审核批次 <run-id>。` |
| 发布批次 | `使用 $project-memory-dreaming 应用我已批准的批次 <run-id>。` |
| 回滚批次 | `使用 $project-memory-dreaming 查看批次 <run-id> 的回滚影响。` |

完整的操作说明、命令参数和失败处理见下方章节。

### 它会生成什么

初始化只补缺并保留已有内容，项目结构如下：

```text
目标项目/
├── AGENTS.md / CLAUDE.md       # Agent 项目入口
├── .memory-system.json         # 项目身份和配置
├── tools/agent_memory.py       # 可独立运行的标准库工具
├── memory/
│   ├── README.md               # 索引和渐进式读取规则
│   ├── org/                    # 用户维护的规范与红线
│   ├── team/                   # decisions / progress / pitfalls
│   ├── agents/                 # Agent 个人草稿
│   └── skills/                 # 项目内程序性经验
├── transcripts/                # 已提供并脱敏的会话摘要
├── dreaming/runs/              # 隔离批次、提案、审核和恢复清单
└── evals/memory/               # 固定评测说明和结果
```

日常入口只读取 `memory/README.md` 和与任务命中的段落；`progress.md` 是审计历史，不作为每次启动时的全文上下文。`memory/org/` 由用户维护，正式共享记忆通过预期哈希和锁保护。

### 可信边界

- 会话、网页和旧记忆只是待核对证据，不能扩大当前指令、权限或外部操作授权。
- Dreaming 的候选、审核和发布是分开的状态；没有用户对当前差异的明确批准，不会应用到正式记忆。
- 记录先脱敏；只有实际取得完整日志才标为 `full`，只有摘要时标为 `summary`。
- 哈希冲突、候选变化、正式记忆后续编辑和回滚覆盖风险都会使工具停止并要求重新检查。
- “初始化完成”不等于“后台自动学习”，是否改善要用固定评测和真实任务分别验证。

### 已有证据与限制

开发阶段曾进行一组范围很窄的 Windows 结构校验对照，结果摘要如下。验证报告和运行记录保留在私有开发仓库，不随公开技能分发：

| 版本 | 首次校验通过 | 最终结果（必要时重试） |
| --- | ---: | ---: |
| M0：没有相关候选记忆 | 0/3 | 3/3 |
| M1：有已审核、未发布的隔离候选 | 3/3 | 3/3 |

该结果只适用于 Windows、Python 3.12.10、默认 `cp936/GBK`、记录的 `quick_validate.py` 哈希和含 Unicode 的 `SKILL.md`。验证器只检查 `SKILL.md` 基础结构，不验证资源脚本或完整记忆行为；没有真实产品维护任务、跨平台、耗时或成本对照，六次运行的原始 Codex JSONL 也未保存。公开文件不足以独立复现这组历史结果，不应将其解释为普遍性能保证。

### 第一次初始化

在目标项目根目录打开 Codex 或 Claude Code，发送：

```text
使用 $project-memory-dreaming 初始化当前项目。
```

Agent 会读取已有 `AGENTS.md`、`AGENTS.override.md`、`CLAUDE.md`、项目说明和配置，比较已有记忆体系，然后先运行初始化器的预览，再执行初始化。初始化会：

1. 保留已有入口、配置和用户写入的记忆内容。
2. 生成 Codex 与 Claude Code 的项目入口、记忆目录、会话目录、Dreaming 目录、评测目录和项目工具。
3. 根据真实配置整理英文初始化建议；无法确认的事实标为待确认，不写入组织规范。
4. 单独读取目标项目实际生成的 `memory/README.md`，再按任务检索相关记忆。
5. 运行 `python tools/agent_memory.py status`，报告生成结果和仍需用户确认的组织规则。

项目名称默认取目录名，也可以在请求中补充名称。重复初始化只补缺，不升级已经存在的模板或工具；若入口冲突、目录是链接或已有内容无法安全保留，初始化器会停止并报告原因。

直接运行脚本时，在本仓库根目录执行：

```powershell
python ".\scripts\init_project.py" "D:\Projects\MyApp" --dry-run
python ".\scripts\init_project.py" "D:\Projects\MyApp" --name "MyApp"
```

### 日常工作

#### 接续任务

```text
使用 $project-memory-dreaming 继续当前任务：把支付重试改成幂等，并运行相关测试。
```

Agent 先完成一次独立的 `memory/README.md` 读取，再搜索精确任务词，只读取命中的相关段落。`progress.md` 是历史审计日志，除非任务需要特定条目，否则不全文读取。记忆会与当前代码、配置和用户指令核对，旧笔记不能扩大权限。

#### 收工或交接

```text
使用 $project-memory-dreaming 记录本次会话。
```

Agent 从当前会话整理脱敏的英文摘要，追加项目进展，记录已确认决定、失败命令、验证结果、恢复方法和下一步；同一任务只保存一份最终摘要。`record` 只保存已提供的文本，不会自动读取聊天数据库或其他会话。

共享记忆写入时，先获取目标哈希，在 `memory/` 外准备英文草稿，再由 `tools/agent_memory.py write` 使用原始哈希完成第一次正式变更。发生冲突时重读并重写；进展只能追加，`memory/org/` 由用户维护。

### Dreaming：整理、审核、发布

```text
使用 $project-memory-dreaming 整理新增会话，只生成候选。
```

Agent 选择当前项目中已获准读取、尚未处理的记录，建立隔离批次，逐份分析后生成带来源与逐字证据的候选、提案和审核报告。没有新记录时直接结束，不会强行生成候选。

| 阶段 | 用户调用 | 结果 |
| --- | --- | --- |
| Prepare | `整理新增会话，只生成候选` | 只改 `dreaming/runs/<run-id>/` 中的隔离副本 |
| Review | `审核批次 <run-id>` | 校验差异、证据、基线和独立会话统计 |
| Apply | `应用我已批准的批次 <run-id>` | 再次校验后发布到正式记忆 |

只有用户明确批准当前批次的具体差异后才能 `apply`。审核后正式记忆、候选或来源发生变化，旧批次必须重新准备和审核。至少两个独立会话才可使用 `promote_to_rule`；单次事实可以保留为普通条目。

先查看回滚影响：

```text
使用 $project-memory-dreaming 查看批次 <run-id> 的回滚影响。
```

确认文件和后续修改后，再发送 `使用 $project-memory-dreaming 回滚批次 <run-id>。` 工具会保留后续修改，发现文件已被修改时拒绝覆盖。

### 命令行入口

以下命令在已经初始化的目标项目根目录运行：

| 命令 | 作用 |
| --- | --- |
| `python tools/agent_memory.py --help` | 查看全部子命令 |
| `python tools/agent_memory.py status` | 查看项目身份、处理数量和调度状态 |
| `python tools/agent_memory.py hash memory/team/pitfalls.md` | 获取写入前的 SHA256 |
| `python tools/agent_memory.py write --help` | 查看带预期哈希的写入参数 |
| `python tools/agent_memory.py record --help` | 查看会话导入参数 |
| `python tools/agent_memory.py prepare` | 为新增记录建立隔离批次 |
| `python tools/agent_memory.py review --help` | 查看批次审核参数 |
| `python tools/agent_memory.py apply --help` | 查看批准后的应用参数 |
| `python tools/agent_memory.py rollback --help` | 查看批准后的回滚参数 |
| `python tools/agent_memory.py evaluate --help` | 查看真实评测汇总与比较参数 |

所有项目命令都支持 `--root`，且放在子命令之前：

```powershell
python tools/agent_memory.py --root "D:\Projects\MyApp" status
```

`prepare` 只建立快照；语义分析、候选编辑和提案填写仍由当前 Agent 完成，工具不会自行调用模型。

### 周期运行与常见问题

初始化不会创建后台任务。需要周期整理时，先明确目标项目、频率和宿主调度器；周期任务默认只生成候选与审核报告，发布仍需批准。评测应固定用例、真实记录、评测集版本、模型工具环境和引用覆盖，并比较一次通过率、引用正确率、返工次数和耗时；没有前后对照时，只报告“效果未评测”。

会话、网页和旧记忆只是待核对证据，不能扩大权限或授权外部操作；共享写入使用协作锁和预期哈希，但不是操作系统权限隔离；记录前先脱敏。技能未被识别时确认完整安装、刷新或新开会话；`prepare` 没有记录时检查 `record` 导入、项目 ID 和跳过原因；旧批次不能应用时以当前正式记忆建立新基线并重新审核。

### 文档地图

公开仓库根目录直接提供完整技能，安装时保留下面的目录关系：

```text
project-memory-dreaming/
├── README.md       # 中英双语安装与使用说明
├── SKILL.md        # Agent 技能入口
├── agents/         # Codex 界面元数据
├── assets/         # 初始化所需的项目模板
├── references/     # 按需读取的工作流说明
└── scripts/        # 项目初始化器
```

- [`SKILL.md`](SKILL.md)：技能入口、默认行为和执行契约。
- [`references/memory-protocol.md`](references/memory-protocol.md)：日常检索、记录和受控写入。
- [`references/dreaming.md`](references/dreaming.md)：隔离批次、提案、审核、应用和恢复。
- [`references/evaluation.md`](references/evaluation.md)：固定评测与周期调度边界。
- [`references/sources.md`](references/sources.md)：原始指南、视频依据和实现取舍。
