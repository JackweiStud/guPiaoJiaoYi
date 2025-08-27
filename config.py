# 配置参数统一管理

from pathlib import Path
from datetime import datetime
import os


#数据存储目录（相对于项目根目录）
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "stock_data"
START_TIME = "2021-01-01 09:30:00"

class ETFConfig:
    DEFAULT_PERIODS = ['5', '15', '30', '60', '120']
    dataPath = Path(DATA_DIR)
    startTime = START_TIME
    
    def __init__(self, stock_code="561560", periods=None, start_date=None):
        self.stock_code = stock_code
        self.periods = periods or self.DEFAULT_PERIODS
        self.start_date = start_date or self.startTime
        self.data_dir = self.dataPath
        self.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 初始化目录
        self.data_dir.mkdir(exist_ok=True)




# emailFile/config.py

# ========================================================================
# 邮件服务商 SMTP 配置
# ========================================================================
# 在这里定义不同邮件服务商的 SMTP 服务器信息。
# 将来如果需要支持新的服务商（如 Outlook, QQ邮箱），只需在此处添加新的配置即可。
SMTP_CONFIGS = {
    "gmail": {
        "server": "smtp.gmail.com",
        "port": 587,
        "description": "谷歌邮箱 (需要使用应用专用密码)"
    },
    "outlook": {
        "server": "smtp.office365.com",
        "port": 587,
        "description": "微软 Outlook 邮箱"
    },
    "qq": {
        "server": "smtp.qq.com",
        "port": 465,  # QQ邮箱推荐使用465端口，SSL加密
        "use_ssl": True,  # QQ邮箱必须使用SSL
        "description": "腾讯QQ邮箱 (需要使用授权码，非QQ密码)"
    }
}

# ========================================================================
# 发件人账户信息
# ========================================================================
# 请在这里填写你的发件人信息。
# 重要提示：出于安全考虑，密码等敏感信息最好通过环境变量等方式管理，
# 而不是直接硬编码在代码中。这里为了演示方便，我们暂时写在这里。

# --- 选择你要使用的发件服务商 ---
# 从上面 SMTP_CONFIGS 中选择一个，例如 "gmail" 或 "outlook"
ACTIVE_SMTP_PROVIDER1 = "gmail"
ACTIVE_SMTP_PROVIDER = "qq"

# --- 填写该服务商对应的邮箱和密码/授权码 ---
SENDER_CREDENTIALS = {
    "email": "",       # 你的发件邮箱地址
    "password": ""          # 双认证后===你的邮箱密码或应用专用密码/授权码
}


SENDER_CREDENTIALS1 = {
    "email": "",       # 你的发件邮箱地址
    "password": ""          # 双认证后===你的邮箱密码或应用专用密码/授权码
}

# ========================================================================
# 默认收件人和抄送人
# ========================================================================
# 在这里设置默认的收件人和抄送人列表，方便测试。
# 实际使用中，这些信息通常由程序的业务逻辑动态提供。
DEFAULT_RECIPIENTS = {
    "to": [""],
    "cc": [""]
}

# ========================================================================
# 演示内容
# ========================================================================
DEMO_CONTENT = {
    "subject": "[Python 测试] 这是一封来自重构后代码的邮件",
    "body": "你好，\n\n如果你收到了这封邮件，说明代码重构成功，现在结构更清晰、更易于扩展了！",
    "image_path": "python_email_demo_image.png"
} 

