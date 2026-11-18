# 评测、调度与安装

## 真实评测

为项目选定固定任务、输入和验收标准，在 `evals/memory/cases.json` 保存实际用例。持久化的评测说明和备注使用英文；用户使用其他语言时忠实翻译相关背景。用例优先覆盖项目确实出现的检索、引用、工具失败和返工；不要用通用模板假装完成了项目评测。

分别实际运行变更前后任务。工具接收 JSONL，每行一项：

```json
{"case_id":"case-001","first_pass":true,"citation_correct":null,"rework_count":0,"duration_seconds":12.5,"suite_id":"memory-v1","environment":"model-and-tool-version","memory_version":"batch-or-git-revision","evidence":"path-to-measured-log"}
```

上述数值只展示字段类型，必须替换为实际测量。`first_pass` 与引用评价为布尔；无引用评价填 null，不当作正确；返工为非负整数，耗时为非负有限数。没有行、重复 case_id 或无效数字会被拒绝。

```text
python tools/agent_memory.py evaluate --results evals/memory/results/after.jsonl
python tools/agent_memory.py evaluate --results evals/memory/results/after.jsonl --baseline evals/memory/results/before.jsonl
```

汇总返回一次通过率、引用正确率及有效样本数、总返工次数、平均耗时；比率为 0–1。比较要求相同 case_id、suite_id、environment 和引用覆盖，返回绝对差值。正的一次通过率差值或负的耗时差值仅为观察结果，不建立因果关系。

原始工具无法导出时保留真实摘要和限制；没有前后实测就写“效果未评测”，不能把缺失值补零，也不能借用视频的客户效果数据。

## 周期运行

技能定义方法，宿主调度器提供执行时机。初始化不会创建自动任务；只有用户明确要求周期运行且目标项目、频率、运行环境明确时，再调用宿主提供的调度能力。不要仅因用户安装技能就在当前技能源码项目中创建任务。

建议先在独立会话手动跑通，个人项目每周一次，活跃期视成本加频。调度提示应固定目标项目，引用 `dreaming/README.md`，选择权限范围内的未处理记录，生成有证据的候选及审核报告，报告批次和未决事项后等待人工审核；不自动发布、提交 Git 或上传原始会话。没有新记录就退出。调度失败应如实报告，不声称后台已启动。

## 技能安装与调用

完整保留技能目录的 `SKILL.md`、`scripts/`、`assets/`、`references/`、`agents/`。只复制 `SKILL.md` 会丢失初始化器和模板。

- Codex 用户级：安装完整技能目录到 `~/.agents/skills/project-memory-dreaming/`；项目级可放 `.agents/skills/project-memory-dreaming/`。
- Claude Code：将整个技能目录复制到 `~/.claude/skills/project-memory-dreaming/` 或 `.claude/skills/project-memory-dreaming/`，并遵循目标环境的发现方式。初始化生成的 `CLAUDE.md` 已提供项目内协议入口。
- 安装目标存在时比较并保留已有内容，不无提示覆盖；检查当前环境是否同时发现同名旧副本，避免重复注册。

Codex 调用：`使用 $project-memory-dreaming 为当前新项目初始化记忆系统。` Claude Code 按其发现后的技能名称调用。若安装后没有显示，刷新或重启对应会话，再确认技能目录可见。
