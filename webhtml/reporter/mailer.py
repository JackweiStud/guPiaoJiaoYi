"""可选邮件发送(默认关闭)。

为避免引入外部依赖，此处留出接口，默认不做实际发送。
如需复用现有 mailFun.EmailSender，可在 settings.SEND_MAIL=True 时调用。
"""

from __future__ import annotations

from typing import Optional
from webhtml.config import settings


def send_report_mail(subject: str, body: str, html_path: str) -> bool:
    if not settings.SEND_MAIL:
        return False
    try:
        # 示例：复用项目根目录 mailFun
        from mailFun import EmailSender, config as email_config  # type: ignore

        sender = EmailSender(provider_name=email_config.ACTIVE_SMTP_PROVIDER)
        return sender.send(
            recipient_emails=email_config.DEFAULT_RECIPIENTS["to"],
            subject=subject,
            body_text=body,
            image_paths=[html_path],
        )
    except Exception:
        return False


