import sys
import os
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

# 将项目根目录添加到 Python 模块搜索路径中
# 这使得脚本可以找到 emailFile 等兄弟模块
project_root = os.path.dirname((os.path.abspath(__file__)))
sys.path.append(project_root)
print('code path is ',project_root)

from main import ETFTest
from sdd import strategyFunc
from mailFun import EmailSender
from mailFun import config as email_config

def get_beijing_time():
    """返回当前的北京时间 (UTC+8)"""
    return datetime.now(timezone(timedelta(hours=8)))

def run_trading_strategy(stock_code="588180.SH"):
    """
    执行完整的交易策略流程：获取数据、分析信号、发送邮件。
    """
    print("="*50)
    print(f"开始执行 {stock_code} 交易策略自动化流程...")
    print(f"执行时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)

    # 1. 获取最新的ETF数据，增加鲁棒性
    try:
        print("\n[步骤 1/3] 正在获取最新ETF数据...")
        ETFTest(stock_code)
        print("数据获取成功。")
    except Exception as e:
        print(f"错误：获取ETF数据失败。错误信息: {e}")
        # 如果数据获取失败，可以选择发送错误邮件或直接退出
        notify_error(f"ETF数据获取失败 for {stock_code}", f"错误详情: {e}")
        return

    # 2. 实现类似 testOnlyNew 的功能，分析交易信号
    print("\n[步骤 2/3] 正在分析交易信号...")
    signal_today, signal_text = get_trading_signal(stock_code)
    print(f"分析完成。今日信号: {signal_text}")

    # 3. 根据交易信号发送邮件
    print("\n[步骤 3/3] 正在准备发送邮件通知...")
    notify_by_email(stock_code, signal_today, signal_text)

    print("\n" + "="*50)
    print("自动化流程执行完毕。")
    print("="*50)

def get_trading_signal(stock_code):
    """
    调用策略函数，获取最新的交易信号。
    返回信号类型和信号文本。
    """
    symbol = stock_code.split('.')[0]
    filepath = os.path.join(project_root, 'stock_data',  f'{symbol}', f'{symbol}_Day.csv')

    if not os.path.exists(filepath):
        print(f"错误：数据文件不存在 -> {filepath}")
        return "error", "数据文件丢失"

    # 使用与 testOnlyNew 中相同的策略参数
    params = {
        'short_window': np.int64(3), 'long_window': np.int64(12),
        'volume_mavg_Value': np.int64(5), 'MaRateUp': np.float64(1.5),
        'VolumeSellRate': np.float64(3.0), 'rsi_period': np.int64(11),
        'rsiValueThd': np.int64(29), 'rsiRateUp': np.float64(1.4),
        'divergence_threshold': np.float64(0.04)
    }

    try:
        performance_stats = strategyFunc(
            filepath=filepath,
            short_window=params['short_window'], long_window=params['long_window'],
            volume_mavg_Value=params['volume_mavg_Value'], MaRateUp=params['MaRateUp'],
            VolumeSellRate=params['VolumeSellRate'], rsi_period=params['rsi_period'],
            rsiValueThd=params['rsiValueThd'], rsiRateUp=params['rsiRateUp'],
            divergence_threshold=params['divergence_threshold'],
            # 其他回测参数，保持与 testOnlyNew 一致
            initial_capital=10000.0, commission=0.0003, max_portfolio_allocation_pct=1,
            buy_increment_pct_of_initial_capital=1, sell_decrement_pct_of_current_shares=1,
            min_shares_per_trade=100,
            # 设置时间范围，确保包含今天
            statTime='2025-01-01', endTime=get_beijing_time().strftime('%Y-%m-%d'),
            plot_results=True,  # 需要设置为True以生成图片
            verbose=False
        )

        portfolio_df = performance_stats.get('portfolio_df')

        if portfolio_df is not None and not portfolio_df.empty:
            today = pd.to_datetime(get_beijing_time().date())
            # 检查回测结果中是否有今天的信号
            if today in portfolio_df.index:
                todays_signal_val = portfolio_df.loc[today]['signal']
                if todays_signal_val == 1:
                    return "buy", "买入"
                elif todays_signal_val == -1:
                    return "sell", "卖出"
                else:
                    return "hold", "无信号"
            else:
                 # 获取最后一个交易日的信号作为参考
                last_signal_date = portfolio_df.index[-1]
                last_signal_val = portfolio_df.iloc[-1]['signal']
                signal_map = {1: "买入", -1: "卖出"}
                last_signal_str = signal_map.get(last_signal_val, "无信号")
                print(f"警告：策略结果中不包含今天({today.strftime('%Y-%m-%d')})的数据。")
                print(f"最后一个有信号的日期是 {last_signal_date.strftime('%Y-%m-%d')}，信号为: {last_signal_str}")
                return "no_data", f"无信号 (最后一个信号: {last_signal_str})"
        else:
            return "hold", "无信号"

    except Exception as e:
        import traceback
        print(f"错误：策略回测执行失败。错误信息: {e}")
        print(traceback.format_exc())
        return "error", "策略执行出错"

def notify_by_email(stock_code, signal_type, signal_text):
    """
    根据信号发送邮件。
    """
    subject = f"交易信号提醒: {stock_code} - {signal_text}"
    body = f"""
你好，

这是来自您的自动化交易策略机器人的通知。

标的: {stock_code}
时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}
信号: {signal_text}

请查看附件图片获取详细图表。

祝好，
交易机器人
"""
    
    image_paths = []
    # 无条件附上图片
    image_folder = os.path.join(project_root, 'pic')
    required_images = ['expectSignal.png', 'RealSignal.png', 'RealTimeReturn.png', 'temp_strategy.csv', 'BuyAndSell.csv']
    
    for img_name in required_images:
        path = os.path.join(image_folder, img_name)
        if os.path.exists(path):
            image_paths.append(path)
        else:
            print(f"警告：邮件附件图片不存在 -> {path}")

    try:
        sender = EmailSender(provider_name=email_config.ACTIVE_SMTP_PROVIDER)
        success = sender.send(
            recipient_emails=email_config.DEFAULT_RECIPIENTS["to"],
            cc_emails=email_config.DEFAULT_RECIPIENTS["cc"],
            subject=subject,
            body_text=body,
            image_paths=image_paths
        )
        if success:
            print("邮件通知已成功发送。")
        else:
            print("错误：邮件发送失败，请检查 emailFile/mailFun.py 的输出日志。")
    except Exception as e:
        print(f"错误：初始化或发送邮件时发生严重错误: {e}")

def notify_error(subject, body):
    """
    当发生严重错误时，发送不带附件的纯文本邮件。
    """
    print(f"正在发送错误报告邮件: {subject}")
    try:
        sender = EmailSender(provider_name=email_config.ACTIVE_SMTP_PROVIDER)
        sender.send(
            recipient_emails=email_config.DEFAULT_RECIPIENTS["to"],
            subject=f"[策略机器人错误] {subject}",
            body_text=f"错误报告:\n\n{body}"
        )
        print("错误报告邮件已发送。")
    except Exception as e:
        print(f"错误：发送错误报告邮件失败: {e}")


if __name__ == "__main__":
    # 要监控的ETF代码
    target_stock_code = "588180.SH"
    run_trading_strategy(target_stock_code)