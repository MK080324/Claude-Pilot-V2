"""renderer.py 单元测试。"""
import pytest

from src.renderer import render_markdown, split_message, format_tool_use


class TestRenderMarkdown:
    def test_bold(self):
        assert "<b>hello</b>" in render_markdown("**hello**")

    def test_italic(self):
        assert "<i>hello</i>" in render_markdown("*hello*")

    def test_codespan(self):
        assert "<code>x</code>" in render_markdown("`x`")

    def test_block_code(self):
        result = render_markdown("```\nprint(1)\n```")
        assert "<pre>" in result

    def test_block_code_with_lang(self):
        result = render_markdown("```python\nprint(1)\n```")
        assert 'class="language-python"' in result

    def test_link(self):
        result = render_markdown("[click](https://example.com)")
        assert '<a href="https://example.com">click</a>' in result

    def test_heading(self):
        result = render_markdown("# Title")
        assert "<b>Title</b>" in result

    def test_heading_levels(self):
        for level in range(1, 7):
            hashes = "#" * level
            result = render_markdown(f"{hashes} H{level}")
            assert f"<b>H{level}</b>" in result

    def test_image(self):
        result = render_markdown("![alt](https://img.png)")
        assert "[图片]" in result
        assert "https://img.png" in result

    def test_thematic_break(self):
        result = render_markdown("---")
        assert "---" in result

    def test_paragraph(self):
        result = render_markdown("hello")
        assert "hello" in result

    def test_list_items(self):
        result = render_markdown("- a\n- b")
        assert "•" in result

    def test_strikethrough(self):
        result = render_markdown("~~deleted~~")
        assert "<s>deleted</s>" in result

    def test_html_escape_in_text(self):
        result = render_markdown("a < b & c > d")
        assert "&lt;" in result
        assert "&amp;" in result
        assert "&gt;" in result

    def test_empty_input(self):
        assert render_markdown("") == ""


class TestSplitMessage:
    def test_short_text(self):
        assert split_message("hello") == ["hello"]

    def test_empty_input(self):
        assert split_message("") == []

    def test_within_limit(self):
        text = "a" * 4096
        assert split_message(text) == [text]

    def test_split_by_paragraph(self):
        para1 = "a" * 2000
        para2 = "b" * 2000
        para3 = "c" * 2000
        text = f"{para1}\n\n{para2}\n\n{para3}"
        chunks = split_message(text, limit=4096)
        assert len(chunks) >= 2
        for c in chunks:
            assert len(c) <= 4096

    def test_split_by_line(self):
        lines = ["x" * 100 for _ in range(50)]
        text = "\n".join(lines)
        chunks = split_message(text, limit=500)
        for c in chunks:
            assert len(c) <= 500

    def test_hard_split_no_tag_break(self):
        text = "a" * 4090 + '<b>bold</b>' + "b" * 4090
        chunks = split_message(text, limit=4096)
        for c in chunks:
            assert len(c) <= 4096
        # 确保没有在 <b> 标签中间切开
        for c in chunks:
            assert "<b" not in c or ">" in c[c.index("<b"):]

    def test_custom_limit(self):
        text = "a" * 100
        chunks = split_message(text, limit=50)
        assert len(chunks) == 2
        assert all(len(c) <= 50 for c in chunks)

    def test_preserves_content(self):
        text = "hello\n\nworld"
        chunks = split_message(text, limit=4096)
        joined = "\n\n".join(chunks)
        assert "hello" in joined
        assert "world" in joined


class TestFormatToolUse:
    def test_bash(self):
        result = format_tool_use("Bash", {"command": "ls -la"})
        assert "Bash" in result
        assert "ls -la" in result

    def test_edit(self):
        result = format_tool_use("Edit", {"file_path": "/tmp/a.py"})
        assert "Edit" in result
        assert "/tmp/a.py" in result

    def test_write(self):
        result = format_tool_use("Write", {"file_path": "/tmp/b.py"})
        assert "Write" in result
        assert "/tmp/b.py" in result

    def test_read(self):
        result = format_tool_use("Read", {"file_path": "/tmp/c.py"})
        assert "Read" in result
        assert "/tmp/c.py" in result

    def test_other_tool_short(self):
        result = format_tool_use("Grep", {"pattern": "foo"})
        assert "Grep" in result

    def test_other_tool_truncated(self):
        data = {"key": "v" * 200}
        result = format_tool_use("SomeTool", data)
        assert "..." in result

    def test_html_in_command(self):
        result = format_tool_use("Bash", {"command": "echo '<b>'"})
        assert "&lt;b&gt;" in result
