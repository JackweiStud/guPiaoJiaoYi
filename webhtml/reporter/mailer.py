"""可选邮件发送(默认关闭)。

为避免引入外部依赖，此处留出接口，默认不做实际发送。
如需复用现有 mailFun.EmailSender，可在 settings.SEND_MAIL=True 时调用。
"""

from __future__ import annotations

import time
from typing import Optional
from webhtml.config import settings


def send_report_mail(subject: str, body: str, html_path: str) -> bool:
    if not settings.SEND_MAIL:
        return False
    
    max_retries = 3
    delay_seconds = 10

    for attempt in range(max_retries):
        try:
            # 示例：复用项目根目录 mailFun
            from mailFun import EmailSender, config as email_config  # type: ignore

            sender = EmailSender(provider_name=email_config.ACTIVE_SMTP_PROVIDER)
            time.sleep(2)  # 初始化后短暂延迟
            success = sender.send(
                recipient_emails=email_config.DEFAULT_RECIPIENTS["to"],
                subject=subject,
                body_text=body,
                image_paths=[html_path],
                cc_emails=email_config.DEFAULT_RECIPIENTS["cc"],
            )
            if success:
                print("邮件报告已成功发送。")
                return True
            else:
                print(f"邮件发送返回失败状态 (尝试 {attempt + 1}/{max_retries})")
        except Exception as e:
            print(f"错误：初始化或发送邮件时发生严重错误 (尝试 {attempt + 1}/{max_retries}): {e}")

        if attempt < max_retries - 1:
            print(f"将在 {delay_seconds} 秒后重试...")
            time.sleep(delay_seconds)
    
    print("错误：邮件发送失败，已达到最大重试次数。请检查 emailFile/mailFun.py 的输出日志。")
    return False


