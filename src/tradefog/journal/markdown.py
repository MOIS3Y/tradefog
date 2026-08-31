"""Safe Markdown rendering for persisted trade descriptions."""

from typing import cast

from markdown_it import MarkdownIt

_RENDERER = MarkdownIt(
    "gfm-like",
    {
        "html": False,
        "linkify": False,
        "typographer": False,
    },
)
_ = _RENDERER.disable("image")


def render_markdown(source: str) -> str:
    """Render CommonMark while escaping embedded raw HTML."""
    return cast(str, _RENDERER.render(source))
