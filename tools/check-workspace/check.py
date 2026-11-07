#!/usr/bin/env python3
"""多智能体共用工作空间的结构自检。

只读，不改任何文件。用法（在工作空间根目录）：

    python3 tools/check-workspace/check.py
    python3 tools/check-workspace/check.py --root /path/to/workspace

有「错误」时退出码为 1，只有「提醒」或全部通过时为 0。
"""

import argparse
import os
import re
import sys

ENTRY = "AGENTS.md"
CLAUDE_ENTRY = "CLAUDE.md"
RULE_FILE_NAMES = {"agents.md", "claude.md"}
REQUIRED_BEGIN = "<!-- check:required -->"
REQUIRED_END = "<!-- /check:required -->"
ALLOW_BEGIN = "<!-- check:allow-nested -->"
ALLOW_END = "<!-- /check:allow-nested -->"
FALLBACK_REQUIRED = [ENTRY, CLAUDE_ENTRY]
SKIP_DIRS = {".git", "_archive", "node_modules", ".venv", "venv", "__pycache__"}
TOOL_SKILL_DIRS = [".claude/skills", ".agents/skills"]
MAX_ENTRY_LINES = 500
MAX_MEMORY_LINES = 200
DATE_AT_END = re.compile(r"\d{4}-\d{2}-\d{2}\s*[)）]?\s*[。.]?\s*$")
SECRET_PATTERNS = [
    ("疑似 OpenAI / Anthropic 类密钥", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("疑似 AWS 访问密钥", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("疑似 GitHub Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("疑似 Slack Token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("疑似私钥", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("疑似明文凭据赋值", re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd|appsecret)\b\s*[:=]\s*['\"]?[^\s'\"，。]{8,}")),
]
SECRET_SCAN_TARGETS = ["memory", "identity"]


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def marked_list(root, begin, end_marker):
    """读 AGENTS.md 里两个标记之间的「- 路径」列表；没有标记返回 None。"""
    entry = os.path.join(root, ENTRY)
    if not os.path.isfile(entry):
        return None
    text = read_text(entry)
    start = text.find(begin)
    end = text.find(end_marker)
    if start < 0 or end < start:
        return None
    paths = []
    for line in text[start + len(begin):end].splitlines():
        line = line.strip()
        if line.startswith("- "):
            item = line[2:].strip().strip("`")
            if item:
                paths.append(item)
    return paths


def required_paths(root, rep):
    if not os.path.isfile(os.path.join(root, ENTRY)):
        return list(FALLBACK_REQUIRED)
    paths = marked_list(root, REQUIRED_BEGIN, REQUIRED_END)
    if paths is None:
        rep.warn("%s 里没有找到自检清单标记 %s … %s，只检查 %s"
                 % (ENTRY, REQUIRED_BEGIN, REQUIRED_END, "、".join(FALLBACK_REQUIRED)))
        return list(FALLBACK_REQUIRED)
    return paths or list(FALLBACK_REQUIRED)


def check_required(root, rep):
    for rel in required_paths(root, rep):
        if not os.path.exists(os.path.join(root, rel)):
            rep.error("缺少必需路径：%s" % rel)


def check_entry(root, rep):
    entry = os.path.join(root, ENTRY)
    if os.path.isfile(entry):
        n = len(read_text(entry).splitlines())
        if n > MAX_ENTRY_LINES:
            rep.error("%s 有 %d 行，超过 %d 行上限" % (ENTRY, n, MAX_ENTRY_LINES))
    claude = os.path.join(root, CLAUDE_ENTRY)
    if os.path.isfile(claude):
        lines = [l.strip() for l in read_text(claude).splitlines()]
        if "@" + ENTRY not in lines:
            rep.error("%s 里没有单独一行 @%s，Claude Code 读不到主规则" % (CLAUDE_ENTRY, ENTRY))


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        yield dirpath, dirnames, sorted(filenames)


def check_nested_rules(root, rep):
    # 有意保留的分线规则文件（由根规则按需加载）在 AGENTS.md 的 allow-nested 标记里声明
    allowed = set(os.path.normpath(p) for p in (marked_list(root, ALLOW_BEGIN, ALLOW_END) or []))
    for rel in sorted(allowed):
        if not os.path.isfile(os.path.join(root, rel)):
            rep.error("AGENTS.md 声明了分线规则文件 %s，但文件不存在" % rel)
    for dirpath, _, filenames in walk(root):
        if os.path.abspath(dirpath) == os.path.abspath(root):
            continue
        for name in filenames:
            if name.lower() in RULE_FILE_NAMES:
                rel = os.path.relpath(os.path.join(dirpath, name), root)
                if os.path.normpath(rel) in allowed:
                    continue
                rep.error("子目录里有规则文件：%s（只能有根目录一份）" % rel)


def check_tool_skill_dirs(root, rep):
    for rel in TOOL_SKILL_DIRS:
        if os.path.isdir(os.path.join(root, rel)):
            rep.warn("发现工具专属技能目录 %s：放在这里的技能只有一个工具看得见，建议挪到 skills/" % rel)


def check_memory(root, rep):
    mem_dir = os.path.join(root, "memory")
    if not os.path.isdir(mem_dir):
        return
    for name in sorted(os.listdir(mem_dir)):
        if not name.endswith(".md"):
            continue
        rel = "memory/" + name
        lines = read_text(os.path.join(mem_dir, name)).splitlines()
        if len(lines) > MAX_MEMORY_LINES:
            rep.error("%s 有 %d 行，超过 %d 行上限" % (rel, len(lines), MAX_MEMORY_LINES))
        if not any(l.strip().startswith("## ") and "已推翻" in l for l in lines):
            rep.warn("%s 没有「已推翻」节" % rel)
        in_section = False
        for i, line in enumerate(lines, 1):
            if line.startswith("## "):
                in_section = True
                continue
            if in_section and line.startswith("- ") and not DATE_AT_END.search(line):
                rep.warn("%s:%d 记忆条目句末没有日期" % (rel, i))


def subdirs(path):
    if not os.path.isdir(path):
        return []
    return sorted(d for d in os.listdir(path)
                  if os.path.isdir(os.path.join(path, d)) and not d.startswith((".", "_")))


def check_skills(root, rep):
    skills = os.path.join(root, "skills")
    index = os.path.join(skills, "README.md")
    if not os.path.isdir(skills):
        return
    index_text = read_text(index) if os.path.isfile(index) else ""
    for name in subdirs(skills):
        if not os.path.isfile(os.path.join(skills, name, "SKILL.md")):
            rep.error("技能 skills/%s/ 里没有 SKILL.md" % name)
        if "skills/%s/SKILL.md" % name not in index_text:
            rep.error("技能 %s 没有登记在 skills/README.md（应写出路径 skills/%s/SKILL.md）" % (name, name))
    # 跳过 skills/<技能名>/SKILL.md 这类说明里的占位写法
    for ref in sorted(set(re.findall(r"skills/([^/\s`|<>]+)/SKILL\.md", index_text))):
        if not os.path.isfile(os.path.join(skills, ref, "SKILL.md")):
            rep.error("skills/README.md 登记了 %s，但 skills/%s/SKILL.md 不存在" % (ref, ref))


def check_tools(root, rep):
    tools = os.path.join(root, "tools")
    index = os.path.join(tools, "README.md")
    if not os.path.isdir(tools):
        return
    index_text = read_text(index) if os.path.isfile(index) else ""
    for name in subdirs(tools):
        if not os.path.isfile(os.path.join(tools, name, "README.md")):
            rep.error("工具 tools/%s/ 里没有 README.md" % name)
        if not re.search(r"(^|[\s|`/])%s($|[\s|`/])" % re.escape(name), index_text, re.M):
            rep.error("工具 %s 没有登记在 tools/README.md" % name)


def secret_files(root):
    for target in SECRET_SCAN_TARGETS:
        path = os.path.join(root, target)
        if os.path.isfile(path):
            yield path
        elif os.path.isdir(path):
            for dirpath, _, filenames in walk(path):
                for name in filenames:
                    if name.endswith((".md", ".txt", ".json", ".yaml", ".yml")):
                        yield os.path.join(dirpath, name)


def check_secrets(root, rep):
    for path in secret_files(root):
        rel = os.path.relpath(path, root)
        try:
            lines = read_text(path).splitlines()
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(lines, 1):
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    # 只报位置，不回显内容
                    rep.error("%s:%d %s，请人工核对后删除" % (rel, i, label))
                    break


def check_gitignore(root, rep):
    path = os.path.join(root, ".gitignore")
    if not os.path.isfile(path):
        rep.warn("没有 .gitignore，.env 可能被提交进仓库")
        return
    if ".env" not in read_text(path):
        rep.warn(".gitignore 没有忽略 .env")


CHECKS = [
    check_required,
    check_entry,
    check_nested_rules,
    check_tool_skill_dirs,
    check_memory,
    check_skills,
    check_tools,
    check_secrets,
    check_gitignore,
]


def run(root):
    rep = Report()
    for check in CHECKS:
        check(root, rep)
    return rep


def main(argv=None):
    parser = argparse.ArgumentParser(description="多智能体共用工作空间的结构自检（只读）")
    parser.add_argument("--root", default=".", help="工作空间根目录，默认当前目录")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print("错误：目录不存在：%s" % root)
        return 1
    rep = run(root)
    for msg in rep.errors:
        print("错误：" + msg)
    for msg in rep.warnings:
        print("提醒：" + msg)
    if rep.errors:
        print("自检未通过：%d 个错误，%d 个提醒" % (len(rep.errors), len(rep.warnings)))
        return 1
    print("自检通过" + ("（%d 个提醒）" % len(rep.warnings) if rep.warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
