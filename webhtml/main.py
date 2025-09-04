import logging
from datetime import datetime
from typing import Dict, Any
import sys
import os
from webhtml.config import settings
from webhtml.reporter.generator import render_report, save_report, backup_raw_data
from webhtml.reporter.mailer import send_report_mail
from webhtml.data_handler.fetcher import fetch_all_data
from webhtml.analysis.calculator import build_report_view
from webhtml.analysis.ai_summary import generate_ai_summary

# 将项目根目录添加到 Python 模块搜索路径中
# 这使得脚本可以找到 emailFile 等兄弟模块
project_root = os.path.dirname((os.path.abspath(__file__)))
sys.path.append(project_root)
print('code path is ',project_root)

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
        # 获取当前时间，格式化为 HH:MM
        current_time = datetime.now().strftime("%H:%M")
        subject = f"{current_time} 金融行情早晚报"
        body = (
            "尊敬的客户您好，我是淮州金融科技小艾：\n\n"
            f"已为您生成 {data.get('report_date')} 全球金融行情监控报告\n\n"
            f"中国大陆市场一句话总结：\n{data.get('ai_summary', '暂无总结')}\n\n"
            "详细请查看附件HTML文件获取详细图表。\n\n"
            "(本邮件由系统自动发送)"
        )
        ok = send_report_mail(subject=subject, body=body, html_path=output_path)
        logging.info(f"报告邮件发送结果: {'成功' if ok else '失败'}")

if __name__ == "__main__":
    main()


