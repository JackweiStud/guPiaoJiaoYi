# -----------------------------------------------------------------------------
# 依赖库说明
# -----------------------------------------------------------------------------
# 本脚本主要使用 Python 内置库，无需额外安装核心功能的依赖。
# - smtplib: 用于发送邮件 (内置)
# - email: 用于构建邮件内容 (内置)
# - os: 用于处理文件路径 (内置)
#
# 为了方便演示，我们使用 Pillow 库来动态创建一张测试图片。
# 如果你不想安装 Pillow，可以注释掉相关代码，并手动提供一张图片。
# 安装命令: pip install Pillow
# -----------------------------------------------------------------------------

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional

# 从配置文件中导入配置信息
try:
    from . import config
except ImportError:
    import config


class EmailSender:
    """
    一个灵活的邮件发送类，支持通过配置切换不同的SMTP服务商。
    """
    def __init__(self, provider_name: str):
        """
        使用指定的服务商名称初始化邮件发送器。
        
        :param provider_name: 服务商名称，必须在 config.SMTP_CONFIGS 中定义。
        """
        if provider_name not in config.SMTP_CONFIGS:
            raise ValueError(f"错误：未知的邮件服务商 '{provider_name}'。请在 config.py 中配置。")

        provider_config = config.SMTP_CONFIGS[provider_name]
        self.smtp_server = provider_config["server"]
        self.smtp_port = provider_config["port"]
        
        self.sender_email = config.SENDER_CREDENTIALS["email"]
        self.sender_password = config.SENDER_CREDENTIALS["password"]
        
        print(f"邮件发送器已初始化，使用 {provider_name.upper()} 服务。")
        print(f"发件人: {self.sender_email}")

    def send(
        self,
        recipient_emails: List[str],
        subject: str,
        body_text: str,
        image_paths: Optional[List[str]] = None,
        cc_emails: Optional[List[str]] = None
    ) -> bool:
        """
        发送一封邮件给一个或多个收件人。
        """
        if not recipient_emails:
            print("错误：收件人列表不能为空。")
            return False

        message = MIMEMultipart()
        message['From'] = self.sender_email
        message['To'] = ", ".join(recipient_emails)
        message['Subject'] = subject

        if cc_emails:
            message['Cc'] = ", ".join(cc_emails)
        
        all_recipients = recipient_emails + (cc_emails or [])

        message.attach(MIMEText(body_text, 'plain', 'utf-8'))

        if image_paths:
            for image_path in image_paths:
                if not os.path.exists(image_path):
                    print(f"警告：附件文件路径不存在 -> {image_path}")
                    continue
                
                try:
                    with open(image_path, 'rb') as f:
                        file_name = os.path.basename(image_path)
                        
                        # 根据文件扩展名选择合适的MIME类型
                        if file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                            part = MIMEImage(f.read(), name=file_name)
                            part.add_header('Content-Disposition', f'attachment; filename="{file_name}"')
                        else:
                            # 对于非图片文件（如CSV），使用通用的 application/octet-stream
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header('Content-Disposition', f'attachment; filename="{file_name}"')
                        
                        message.attach(part)
                except Exception as e:
                    print(f"错误：附加文件 {image_path} 时发生错误 -> {e}")

        server = None
        try:
            # 根据配置选择是否使用SSL
            if config.SMTP_CONFIGS.get(config.ACTIVE_SMTP_PROVIDER, {}).get('use_ssl', False):
                 server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
            
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, all_recipients, message.as_string())
            
            print(f"邮件已成功发送至: {', '.join(all_recipients)}")
            return True
        except smtplib.SMTPAuthenticationError:
            print("错误：SMTP认证失败。请检查：")
            print("1. 邮箱地址和密码/授权码是否正确。")
            print("2. 如果使用Gmail等，是否开启了2FA并使用了【应用专用密码】。")
            return False
        except Exception as e:
            print(f"错误：发送邮件时发生未知错误 -> {e}")
            return False
        finally:
            if server:
                server.quit()


def create_demo_image(path: str):
    """
    使用 Pillow 库创建一个用于演示的图片。
    如果 Pillow 未安装，则会打印警告信息。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('RGB', (400, 200), color='#4A90E2') # A nice blue
        draw = ImageDraw.Draw(img)
        
        try:
            # 尝试加载一个好看的字体，如果失败则使用默认字体
            font = ImageFont.truetype("arial.ttf", 24)
        except IOError:
            font = ImageFont.load_default()
            
        text = "Email from Refactored Code!\n\n- More Readable\n- More Extensible"
        draw.text((30, 50), text, fill='white', font=font)
        
        img.save(path)
        print(f"演示图片 '{path}' 已创建。")
    except ImportError:
        print("警告：Pillow 库未安装，无法创建演示图片。")
        print("请运行 'pip install Pillow' 进行安装。")

def mailSendTest():
    print("\n" + "="*60)
    print("               邮件发送测试程序 (重构版)")
    print("="*60)

    # 步骤 1: 创建演示图片
    create_demo_image(config.DEMO_CONTENT["image_path"])
    print("-"*60)

    # 步骤 2: 检查配置是否已修改
    if "your_email" in config.SENDER_CREDENTIALS["email"] or "your_password" in config.SENDER_CREDENTIALS["password"]:
         print(">>> 配置错误：请先在 'config.py' 文件中填写你的邮箱信息！<<<")
    else:
        try:
            # 步骤 3: 初始化邮件发送器
            # 使用在 config.py 中配置的活动服务商
            sender = EmailSender(provider_name=config.ACTIVE_SMTP_PROVIDER)
            
            # 步骤 4: 发送邮件
            print("正在准备发送邮件...")
            success = sender.send(
                recipient_emails=config.DEFAULT_RECIPIENTS["to"],
                cc_emails=config.DEFAULT_RECIPIENTS["cc"],
                subject=config.DEMO_CONTENT["subject"],
                body_text=config.DEMO_CONTENT["body"],
                image_paths=[config.DEMO_CONTENT["image_path"]]
            )

            # 步骤 5: 打印结果
            print("\n" + "-"*25 + " 测试结果 " + "-"*25)
            if success:
                print("✅ 任务完成！邮件发送成功。")
            else:
                print("❌ 任务失败：邮件未能发送。请检查配置或错误信息。")

        except ValueError as e:
            print(e)
        except Exception as e:
            print(f"发生意外错误: {e}")
            
    print("="*60)

if __name__ == '__main__':
    mailSendTest()