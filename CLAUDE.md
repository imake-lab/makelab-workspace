# CLAUDE.md — Claude Code 入口

@AGENTS.md

> 上面一行是 Claude Code 的文件引用语法，会把同目录 `AGENTS.md` 的全文引入本次会话。
> 规则只写在 `AGENTS.md`。本文件只放 Claude Code 专属的说明，不重复任何规则，避免两处打架。

## Claude Code 专属说明

- `skills/` 下的技能不是 Claude Code 注册的技能，Skill 工具找不到它们。按 `skills/README.md` 匹配任务后，用 Read 打开对应的 SKILL.md。
- 不建 `.claude/skills/`。原因见 `AGENTS.md` 第 4 节第 2 条：放进去只有 Claude Code 看得见。
- 工作空间放在网络盘上、盘掉了会话就起不来时，用跳板目录的做法，见仓库 README「常见问题」。
