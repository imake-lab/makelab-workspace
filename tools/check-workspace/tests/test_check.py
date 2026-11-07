import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import check  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

AGENTS = """# AGENTS.md
<!-- check:required -->
- AGENTS.md
- CLAUDE.md
- memory/MEMORY.md
- skills/README.md
- tools/README.md
<!-- /check:required -->
"""


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        write(self.root, "AGENTS.md", AGENTS)
        write(self.root, "CLAUDE.md", "# CLAUDE.md\n\n@AGENTS.md\n")
        write(self.root, "memory/MEMORY.md", "# M\n\n## 偏好\n\n- 结论先行（2026-01-01）\n\n## 已推翻\n")
        write(self.root, "skills/README.md", "| a | `skills/a/SKILL.md` |\n")
        write(self.root, "skills/a/SKILL.md", "# a\n")
        write(self.root, "tools/README.md", "| t | x |\n")
        write(self.root, "tools/t/README.md", "# t\n")
        write(self.root, ".gitignore", ".env\n")

    def tearDown(self):
        shutil.rmtree(self.root)

    def run_check(self):
        return check.run(self.root)

    def test_clean_workspace_passes(self):
        rep = self.run_check()
        self.assertEqual(rep.errors, [])
        self.assertEqual(rep.warnings, [])

    def test_missing_required_path(self):
        os.remove(os.path.join(self.root, "memory/MEMORY.md"))
        self.assertIn("缺少必需路径：memory/MEMORY.md", self.run_check().errors)

    def test_claude_md_must_import_agents(self):
        write(self.root, "CLAUDE.md", "# CLAUDE.md\n见 AGENTS.md\n")
        self.assertTrue(any("@AGENTS.md" in e for e in self.run_check().errors))

    def test_nested_rule_file_is_error(self):
        write(self.root, "projects/x/AGENTS.md", "# nested\n")
        write(self.root, "projects/y/claude.md", "# nested\n")
        errors = self.run_check().errors
        self.assertTrue(any("projects/x/AGENTS.md" in e for e in errors))
        self.assertTrue(any("projects/y/claude.md" in e for e in errors))

    def test_declared_line_rule_file_is_allowed(self):
        write(self.root, "AGENTS.md", AGENTS + "<!-- check:allow-nested -->\n- lines/a/AGENTS.md\n<!-- /check:allow-nested -->\n")
        write(self.root, "lines/a/AGENTS.md", "# line a\n")
        write(self.root, "lines/b/AGENTS.md", "# line b\n")
        errors = self.run_check().errors
        self.assertFalse(any("lines/a/AGENTS.md" in e for e in errors))
        self.assertTrue(any("lines/b/AGENTS.md" in e for e in errors))

    def test_declared_line_rule_file_missing(self):
        write(self.root, "AGENTS.md", AGENTS + "<!-- check:allow-nested -->\n- lines/x/AGENTS.md\n<!-- /check:allow-nested -->\n")
        self.assertTrue(any("lines/x/AGENTS.md" in e and "不存在" in e for e in self.run_check().errors))

    def test_archive_is_ignored(self):
        write(self.root, "_archive/2026-01/AGENTS.md", "# old\n")
        self.assertEqual(self.run_check().errors, [])

    def test_tool_specific_skill_dir_warns(self):
        os.makedirs(os.path.join(self.root, ".claude/skills/a"))
        self.assertTrue(any(".claude/skills" in w for w in self.run_check().warnings))

    def test_unindexed_skill(self):
        write(self.root, "skills/b/SKILL.md", "# b\n")
        self.assertTrue(any("技能 b 没有登记" in e for e in self.run_check().errors))

    def test_indexed_skill_missing(self):
        write(self.root, "skills/README.md", "`skills/a/SKILL.md` `skills/ghost/SKILL.md`\n")
        self.assertTrue(any("ghost" in e for e in self.run_check().errors))

    def test_placeholder_in_index_is_ignored(self):
        write(self.root, "skills/README.md", "新增技能建 `skills/<技能名>/SKILL.md`\n`skills/a/SKILL.md`\n")
        self.assertEqual(self.run_check().errors, [])

    def test_skill_dir_without_skill_md(self):
        os.makedirs(os.path.join(self.root, "skills/c"))
        write(self.root, "skills/README.md", "`skills/a/SKILL.md` `skills/c/SKILL.md`\n")
        self.assertTrue(any("skills/c/ 里没有 SKILL.md" in e for e in self.run_check().errors))

    def test_unindexed_tool(self):
        write(self.root, "tools/u/README.md", "# u\n")
        self.assertTrue(any("工具 u 没有登记" in e for e in self.run_check().errors))

    def test_memory_too_long(self):
        lines = ["# M", "## 已推翻"] + ["- x（2026-01-01）"] * 200
        write(self.root, "memory/MEMORY.md", "\n".join(lines) + "\n")
        self.assertTrue(any("超过 200 行" in e for e in self.run_check().errors))

    def test_memory_entry_without_date_warns(self):
        write(self.root, "memory/MEMORY.md", "# M\n\n## 偏好\n\n- 没写日期\n\n## 已推翻\n")
        self.assertTrue(any("MEMORY.md:5" in w for w in self.run_check().warnings))

    def test_memory_without_overturned_section_warns(self):
        write(self.root, "memory/MEMORY.md", "# M\n\n## 偏好\n")
        self.assertTrue(any("已推翻" in w for w in self.run_check().warnings))

    def test_secret_detected_but_not_echoed(self):
        secret = "sk-" + "A1b2C3d4E5f6G7h8I9j0K1"
        write(self.root, "memory/MEMORY.md",
              "# M\n\n## 事实\n\n- key 是 %s（2026-01-01）\n\n## 已推翻\n" % secret)
        rep = self.run_check()
        self.assertTrue(any("memory/MEMORY.md:5" in e for e in rep.errors))
        self.assertFalse(any(secret in m for m in rep.errors + rep.warnings))

    def test_credential_assignment_detected(self):
        write(self.root, "identity/ME.md", "password = hunter2hunter2\n")
        self.assertTrue(any("identity/ME.md:1" in e for e in self.run_check().errors))

    def test_missing_markers_falls_back(self):
        write(self.root, "AGENTS.md", "# AGENTS.md\n")
        rep = self.run_check()
        self.assertEqual(rep.errors, [])
        self.assertTrue(any("自检清单标记" in w for w in rep.warnings))

    def test_gitignore_without_env_warns(self):
        write(self.root, ".gitignore", "*.pyc\n")
        self.assertTrue(any(".env" in w for w in self.run_check().warnings))

    def test_exit_codes(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(check.main(["--root", self.root]), 0)
            os.remove(os.path.join(self.root, "CLAUDE.md"))
            self.assertEqual(check.main(["--root", self.root]), 1)


class TemplateRepoTest(unittest.TestCase):
    def test_template_itself_passes(self):
        rep = check.run(REPO_ROOT)
        self.assertEqual(rep.errors, [])


if __name__ == "__main__":
    unittest.main()
