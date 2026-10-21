from django import template
from django.utils.html import escape, format_html_join
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def ai_summary(text):
    """The AI summary as safe HTML: "Heading:" lines in bold, "- " lines as a list."""
    blocks, items = [], []

    def flush():
        if items:
            blocks.append(format_html_join("", "<li>{}</li>", ((i,) for i in items)).join(("<ul>", "</ul>")))
            items.clear()

    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ", "• ")):
            items.append(line[2:].strip())
            continue
        flush()
        if line.endswith(":") and len(line) < 60:
            blocks.append(f"<h3>{escape(line[:-1])}</h3>")
        else:
            blocks.append(f"<p>{escape(line)}</p>")
    flush()
    return mark_safe("".join(blocks))
