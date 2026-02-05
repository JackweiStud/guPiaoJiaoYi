#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QQ邮箱配置测试脚本
用于测试QQ邮箱的SMTP连接和邮件发送功能
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from mailFun import EmailSender
    import config
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在项目根目录下运行此脚本")
    sys.exit(1)

def test_qq_email_config():
    """测试QQ邮箱配置"""
    print("=" * 60)
    print("                QQ邮箱配置测试")
    print("=" * 60)
    
    # 检查QQ邮箱是否在配置中
    if "qq" not in config.SMTP_CONFIGS:
        print("❌ 错误：QQ邮箱配置未找到！")
        print("请先在 config.py 中添加QQ邮箱配置")
        return False
    
    print("✅ QQ邮箱配置已找到")
    qq_config = config.SMTP_CONFIGS["qq"]
    print(f"   服务器: {qq_config['server']}")
    print(f"   端口: {qq_config['port']}")
    print(f"   SSL: {qq_config.get('use_ssl', False)}")
    print(f"   描述: {qq_config['description']}")
    
    return True

def test_qq_email_connection():
    """测试QQ邮箱连接"""
    print("\n" + "-" * 40)
    print("正在测试QQ邮箱连接...")
    
    try:
        # 创建QQ邮箱发送器
        sender = EmailSender("qq")
        print("✅ QQ邮箱发送器创建成功")
        return True
    except ValueError as e:
        print(f"❌ 错误：{e}")
        return False
    except Exception as e:
        print(f"❌ 连接失败：{e}")
        return False

def test_qq_email_send():
    """测试QQ邮箱发送功能"""
    print("\n" + "-" * 40)
    print("正在测试QQ邮箱发送功能...")
    
    try:
        # 创建QQ邮箱发送器
        sender = EmailSender("qq")
        
        # 测试发送邮件
        test_subject = "[QQ邮箱测试] 这是一封测试邮件"
        test_body = """
你好！

这是一封来自QQ邮箱的测试邮件，用于验证配置是否正确。

如果你收到这封邮件，说明：
1. QQ邮箱配置正确
2. 授权码有效
3. SMTP连接成功

测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

祝好！
        """.strip()
        
        # 发送测试邮件
        success = sender.send(
            recipient_emails=config.DEFAULT_RECIPIENTS["to"],
            cc_emails=config.DEFAULT_RECIPIENTS["cc"],
            subject=test_subject,
            body_text=test_body
        )
        
        if success:
            print("✅ 测试邮件发送成功！")
            return True
        else:
            print("❌ 测试邮件发送失败")
            return False
            
    except Exception as e:
        print(f"❌ 发送测试失败：{e}")
        return False

def show_qq_email_setup_guide():
    """显示QQ邮箱设置指南"""
    print("\n" + "=" * 60)
    print("                QQ邮箱设置指南")
    print("=" * 60)
    
    print("\n📧 步骤1: 获取QQ邮箱授权码")
    print("   1. 登录QQ邮箱网页版 (mail.qq.com)")
    print("   2. 点击右上角'设置' -> '账户'")
    print("   3. 找到'POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务'")
    print("   4. 开启'POP3/SMTP服务'或'IMAP/SMTP服务'")
    print("   5. 点击'生成授权码'")
    print("   6. 复制生成的授权码（注意：不是QQ密码！）")
    
    print("\n⚙️  步骤2: 配置环境变量（推荐）")
    print("   1. 编辑项目根目录的 .env 文件（或设置系统环境变量）")
    print("   2. 添加以下配置：")
    print("      - SMTP_PROVIDER=qq")
    print("      - SMTP_SENDER_EMAIL=你的QQ邮箱地址")
    print("      - SMTP_SENDER_PASSWORD=刚才获取的授权码")
    
    print("\n🧪 步骤3: 运行测试")
    print("   运行命令: python experiments/test_qq_email.py")
    
    print("\n⚠️  重要提醒:")
    print("   - 授权码不是QQ密码")
    print("   - 授权码需要保密，不要泄露给他人")
    print("   - 如果修改QQ密码，授权码会失效，需要重新生成")
    
    print("=" * 60)

def main():
    """主函数"""
    print("QQ邮箱配置测试工具")
    print("请确保已经按照指南配置好QQ邮箱信息")
    
    # 检查配置
    if not test_qq_email_config():
        show_qq_email_setup_guide()
        return
    
    # 测试连接
    if not test_qq_email_connection():
        show_qq_email_setup_guide()
        return
    
    # 测试发送
    if test_qq_email_send():
        print("\n🎉 恭喜！QQ邮箱配置测试全部通过！")
        print("现在你可以使用QQ邮箱发送邮件了")
    else:
        print("\n❌ QQ邮箱发送测试失败")
        print("请检查配置信息，特别是授权码是否正确")
        show_qq_email_setup_guide()

if __name__ == "__main__":
    main()
