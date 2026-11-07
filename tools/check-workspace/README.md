# check-workspace：结构自检

只读，不改任何文件。Python 3.8 以上，只用标准库，不用装依赖。

## 用法

在工作空间根目录执行：

```bash
python3 tools/check-workspace/check.py
# 或者指定目录
python3 tools/check-workspace/check.py --root /path/to/workspace
```

有「错误」时退出码为 1；只有「提醒」或全部通过时为 0。

## 查什么

| 项 | 级别 | 说明 |
| --- | --- | --- |
| 必需路径 | 错误 | 清单从 `AGENTS.md` 的 `<!-- check:required -->` 标记里读，规则和脚本用同一份清单 |
| `AGENTS.md` 行数 | 错误 | 超过 500 行 |
| `CLAUDE.md` 引入 | 错误 | 没有单独一行 `@AGENTS.md` |
| 子目录规则文件 | 错误 | 根目录以外出现 `AGENTS.md` / `CLAUDE.md`（不区分大小写；`_archive/`、`.git/` 等除外）。有意保留的分线规则文件在 `AGENTS.md` 的 `<!-- check:allow-nested -->` 标记里声明后放行；声明了但文件不存在也报错 |
| 工具专属技能目录 | 提醒 | 存在 `.claude/skills/`、`.agents/skills/` |
| 记忆文件 | 错误 / 提醒 | 超过 200 行是错误；条目句末没有日期、缺「已推翻」节是提醒 |
| 技能索引 | 错误 | `skills/` 下的目录和 `skills/README.md` 要一一对应，每个目录都有 SKILL.md |
| 工具索引 | 错误 | `tools/` 下的目录都登记在 `tools/README.md`，每个目录都有 README.md |
| 疑似密钥 | 错误 | 扫 `memory/`、`identity/`；只报文件和行号，不回显内容 |
| `.gitignore` | 提醒 | 没有忽略 `.env` |

密钥识别只是正则启发式，查不全，也可能误报。它是兜底，不能代替「不往记忆里写凭据」这条规则。

## 测试

```bash
python3 -m unittest discover -s tools/check-workspace/tests -v
```
