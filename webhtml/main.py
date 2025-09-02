import logging
from datetime import datetime
from typing import Dict, Any

from webhtml.config import settings
from webhtml.reporter.generator import render_report, save_report, backup_raw_data
from webhtml.reporter.mailer import send_report_mail
from webhtml.data_handler.fetcher import fetch_all_data
from webhtml.analysis.calculator import build_report_view
from webhtml.analysis.ai_summary import generate_ai_summary


def setup_logging() -> None:
    settings.ensure_directories()
    log_path = settings.LOG_DIR + f"/app_{settings.today_str()}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


def build_pipeline_data() -> Dict[str, Any]:
    raw = fetch_all_data()
    view = build_report_view(raw)
    view["ai_summary"] = generate_ai_summary(view)
    return view


def main() -> None:
    setup_logging()
    logging.info("开始生成报告...")
    data = build_pipeline_data()
    backup_raw_data(data.get("_raw", {}))

    html = render_report(data)
    output_path = save_report(html)
    logging.info(f"报告已生成: {output_path}")

    # 邮件发送默认关闭，按 settings.SEND_MAIL 控制
    if settings.SEND_MAIL:
        subject = f"金融行情监控仪表盘 | {data.get('report_date')}"
        body = (
            "您好，\n\n"
            "已生成当日金融行情监控报告，请查收附件HTML文件。\n\n"
            "(本邮件由系统自动发送)"
        )
        ok = send_report_mail(subject=subject, body=body, html_path=output_path)
        logging.info(f"报告邮件发送结果: {'成功' if ok else '失败'}")


if __name__ == "__main__":
    main()


