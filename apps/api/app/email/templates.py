"""The site's own emails (verify, reset password, welcome, reminders): the
TryOnU heading, a few short lines, one big button, a footer. Email programs
ignore modern page layout, so this is tables and inline styles only."""

from __future__ import annotations

import html

from app.core.config import get_settings

SAGE = "#57634f"
INK = "#1c1b17"
MUTED = "#6f6c64"


def site_url(path: str = "") -> str:
    """The website's address with a path, never with a double slash."""
    base = str(get_settings().FRONTEND_URL).rstrip("/")
    return f"{base}/{path.lstrip('/')}" if path else base


def action_email(
    heading: str,
    lines: list[str],
    button: str,
    url: str,
    *,
    after: list[str] | None = None,
    footer: str | None = None,
    picture: str | None = None,
) -> tuple[str, str]:
    """(plain text, page) for an email with one thing to do."""
    s = get_settings()
    after = after or []
    foot = footer or f"Questions? Reply to this email or write to {s.SUPPORT_EMAIL}."
    text = "\n\n".join([heading, *lines, f"{button}: {url}", *after, f"--\nTryOnU · {site_url()}\n{foot}"])

    p = lambda t: f'<p style="margin:0 0 14px;font:15px/1.55 Arial,Helvetica,sans-serif;color:{INK}">{html.escape(t)}</p>'  # noqa: E731
    pic = (
        f'<img src="{html.escape(picture)}" width="480" alt="" style="display:block;width:100%;max-width:480px;'
        'height:auto;border:0;border-radius:14px;margin:0 0 16px">'
        if picture
        else ""
    )
    page = f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#f6f3ee">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f3ee"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="width:100%;max-width:560px">
<tr><td style="padding:0 6px 16px;font:bold 24px Georgia,serif;color:{SAGE}">TryOnU</td></tr>
<tr><td style="background:#ffffff;border:1px solid #e5ddd3;border-radius:18px;padding:26px 22px">
<p style="margin:0 0 16px;font:bold 21px Georgia,serif;color:{INK}">{html.escape(heading)}</p>
{pic}{"".join(p(t) for t in lines)}
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 16px"><tr>
<td style="background:{SAGE};border-radius:999px"><a href="{html.escape(url)}" style="display:inline-block;padding:14px 28px;
font:bold 16px Arial,Helvetica,sans-serif;color:#ffffff;text-decoration:none">{html.escape(button)}</a></td></tr></table>
<p style="margin:0 0 14px;font:12.5px/1.5 Arial,Helvetica,sans-serif;color:{MUTED}">If the button doesn't work, open this link:<br>
<a href="{html.escape(url)}" style="color:{SAGE};word-break:break-all">{html.escape(url)}</a></p>
{"".join(p(t) for t in after)}
</td></tr>
<tr><td style="padding:18px 6px 0;font:12.5px/1.5 Arial,Helvetica,sans-serif;color:#8a8a80">{html.escape(foot)}</td></tr>
</table></td></tr></table></body></html>"""
    return text, page
