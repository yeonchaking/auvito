"""Jinja2-based prompt template engine."""

from jinja2 import Environment, FileSystemLoader, PackageLoader
from typing import Optional, Any


class PromptEngine:
    """Prompt template rendering engine."""

    def __init__(self, template_dir: Optional[str] = None):
        """Initialize prompt engine."""
        if template_dir:
            self.env = Environment(loader=FileSystemLoader(template_dir))
        else:
            self.env = Environment(loader=PackageLoader("app", "prompts"))

    def render(self, template_path: str, context: dict[str, Any]) -> str:
        """Render a template with context."""
        template = self.env.get_template(template_path)
        return template.render(**context)
