import sys
import os
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
import json
import time

# 将项目根目录添加到 Python 模块搜索路径中
# 这使得脚本可以找到 emailFile 等兄弟模块
project_root = os.path.dirname((os.path.abspath(__file__)))
sys.path.append(project_root)
print('code path is ',project_root)

from main import ETFTest
from sdd import strategyFunc
from mailFun import EmailSender
from mailFun import config as email_config
from deepSeekAi import aiDeepSeekAnly, extract_position_strategy

def get_beijing_time():
    """返回当前的北京时间 (UTC+8)"""
    return datetime.now(timezone(timedelta(hours=8)))

def run_trading_strategy(stock_code):
    """
    执行完整的交易策略流程：获取数据、分析信号、发送邮件。
    """
    print("="*50)
    print(f"开始执行 {stock_code} 交易策略自动化流程...")
    print(f"执行时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)

    # 1. 获取最新的ETF数据，增加鲁棒性（返回值检查 + 重试）
    try:
        print("\n[步骤 1/3] 正在获取最新ETF数据...")
        max_retries = 3
        delay_seconds = 15
        success = False

        for attempt in range(1, max_retries + 1):
            success = ETFTest(stock_code)
            if success:
                print("数据获取成功。")
                break

            if attempt < max_retries:
                print(f"第 {attempt} 次获取ETF数据失败，{delay_seconds} 秒后重试...")
                time.sleep(delay_seconds)

        if not success:
            msg = f"在连续 {max_retries} 次尝试后仍未成功获取 {stock_code} 的ETF数据。"
            print(msg)
            notify_error(f"ETF数据获取失败 for {stock_code}", msg)
            return

    except Exception as e:
        print(f"错误：获取ETF数据失败（异常）。错误信息: {e}")
        # 如果数据获取失败，可以选择发送错误邮件或直接退出
        notify_error(f"ETF数据获取失败 for {stock_code}", f"错误详情: {e}")
        return

    # 2. 实现类似 testOnlyNew 的功能，分析交易信号
    print("\n[步骤 2/3] 正在分析交易信号...")
    _, signal_text = get_trading_signal(stock_code)
    print(f"分析完成。{stock_code} 的今日信号: {signal_text}")

    #3 新增股票分析功能 调用 aiDeepSeekAnly("588180") 
    symbol = f"{stock_code.split('.')[0]}"
    print(f"----AI开始获取{symbol}数据，并智能分析---------） ")
    aiResultInfo = aiDeepSeekAnly(symbol)
    
    # 根据AI分析结果拼接signal_text
    aiDataInfo = ""
    strategyinfo = ""
    if aiResultInfo and aiResultInfo.strip():
        aiDataInfo = aiResultInfo
        print(f"AI分析结果长度: {len(aiDataInfo)}")
        strategyinfo = extract_position_strategy(aiDataInfo)
    else:
        aiDataInfo =  "aiResultInfo not ok"
        print("AI分析结果为空，已添加默认提示信息")

    # 4. 根据交易信号发送邮件
    print("\n[步骤 3/3] 正在准备发送邮件通知...")
    notify_by_email(stock_code, signal_text, aiDataInfo, strategyinfo)

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

    # 从JSON文件加载策略参数
    params_path = os.path.join(project_root, 'strategy_params.json')
    try:
        with open(params_path, 'r', encoding='utf-8') as f:
            # 移除JSON文件中的注释行 (以 // 开头)
            lines = f.readlines()
            json_str = "".join([line for line in lines if not line.strip().startswith('//')])
            all_params = json.loads(json_str)
        
        # 获取对应 symbol 的参数，如果不存在则使用 default 参数
        stock_params = all_params.get(symbol, all_params['default'])
        
        # 将从 JSON 中读取的参数转换为 NumPy 特定类型
        params = {
            'short_window': np.int64(stock_params['short_window']), 
            'long_window': np.int64(stock_params['long_window']),
            'volume_mavg_Value': np.int64(stock_params['volume_mavg_Value']), 
            'MaRateUp': np.float64(stock_params['MaRateUp']),
            'VolumeSellRate': np.float64(stock_params['VolumeSellRate']), 
            'rsi_period': np.int64(stock_params['rsi_period']),
            'rsiValueThd': np.int64(stock_params['rsiValueThd']), 
            'rsiRateUp': np.float64(stock_params['rsiRateUp']),
            'divergence_threshold': np.float64(stock_params['divergence_threshold'])
        }
        print(f"已为 {symbol} 从 'strategy_params.json' 加载策略参数。")

    except (FileNotFoundError, KeyError) as e:
        print(f"警告: 无法从 'strategy_params.json' 加载参数 (错误: {e})。将使用代码中定义的默认参数。")
    
    # 策略执行起始时间
    statTime='2024-01-01'
    try:
        performance_stats = strategyFunc(
            filepath=filepath,
            symbol=symbol,
            short_window=params['short_window'], long_window=params['long_window'],
            volume_mavg_Value=params['volume_mavg_Value'], MaRateUp=params['MaRateUp'],
            VolumeSellRate=params['VolumeSellRate'], rsi_period=params['rsi_period'],
            rsiValueThd=params['rsiValueThd'], rsiRateUp=params['rsiRateUp'],
            divergence_threshold=params['divergence_threshold'],
            # 其他回测参数，保持与 testOnlyNew 一致
            initial_capital=100000.0, 
            commission=0.0003, 
            max_portfolio_allocation_pct=1,
            buy_increment_pct_of_initial_capital=1, 
            sell_decrement_pct_of_current_shares=1,
            min_shares_per_trade=100,
            # 设置时间范围，确保包含今天
            statTime = statTime, 
            endTime=get_beijing_time().strftime('%Y-%m-%d'),
            plot_results=1,  # 需要设置为True以生成图片
            verbose=False,
            enable_file_io=True
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

def notify_by_email(stock_code, signal_text, aiDataInfo = None, strategyinfo = None):
    """
    根据信号发送邮件，增加5次重试逻辑。
    """
    subject = f"交易信号提醒: {stock_code} - {signal_text}"
    body = f"""
            你好，

            这是来自您的自动化策略信号识别系统机器人的通知。

            标的: {stock_code}
            时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}
            交易信号: {signal_text}

            AI趋势策略：\n
            {strategyinfo}

            详细AI趋势分析：\n
            {aiDataInfo}

            请查看附件图片获取详细图表。

            祝好，
            交易机器人
            """
    
    image_paths = []
    # 无条件附上图片
    symbol = stock_code.split('.')[0]
    image_folder = os.path.join(project_root, 'pic')
    print(f"图片文件夹路径为: {image_folder}")
    required_images = [f'{symbol}_expectSignal.png', 
                       f'{symbol}_Strategy_Performance_Dashboard.png',
                       f'{symbol}_temp_strategy.csv', 
                       f'{symbol}_divergence_ratio.csv', 
                       f'{symbol}_BuyAndSell.csv']
    
    for img_name in required_images:
        path = os.path.join(image_folder, img_name)
        if os.path.exists(path):
            image_paths.append(path)
        else:
            print(f"警告：邮件附件图片不存在 -> {path}")

    max_retries = 3
    delay_seconds = 10

    for attempt in range(max_retries):
        try:
            sender = EmailSender(provider_name=email_config.ACTIVE_SMTP_PROVIDER)
            time.sleep(2)
            success = sender.send(
                recipient_emails=email_config.DEFAULT_RECIPIENTS["to"],
                cc_emails=email_config.DEFAULT_RECIPIENTS["cc"],
                subject=subject,
                body_text=body,
                image_paths=image_paths
            )
            if success:
                print("邮件通知已成功发送。")
                return
            else:
                print(f"邮件发送返回失败状态 (尝试 {attempt + 1}/{max_retries})")
        except Exception as e:
            print(f"错误：初始化或发送邮件时发生严重错误 (尝试 {attempt + 1}/{max_retries}): {e}")

        if attempt < max_retries - 1:
            print(f"将在 {delay_seconds} 秒后重试...")
            time.sleep(delay_seconds)
    
    print("错误：邮件发送失败，已达到最大重试次数。请检查 emailFile/mailFun.py 的输出日志。")

def notify_error(subject, body):
    """
    当发生严重错误时，发送不带附件的纯文本邮件，增加5次重试逻辑。
    """
    print(f"正在发送错误报告邮件: {subject}")
    max_retries = 5
    delay_seconds = 10

    for attempt in range(max_retries):
        try:
            sender = EmailSender(provider_name=email_config.ACTIVE_SMTP_PROVIDER)
            success = sender.send(
                recipient_emails=email_config.DEFAULT_RECIPIENTS["to"],
                subject=f"[策略机器人错误] {subject}",
                body_text=f"错误报告:\n\n{body}"
            )
            if success:
                print("错误报告邮件已发送。")
                return
            else:
                print(f"错误报告邮件发送返回失败状态 (尝试 {attempt + 1}/{max_retries})")
        except Exception as e:
            print(f"错误：发送错误报告邮件失败 (尝试 {attempt + 1}/{max_retries}): {e}")

        if attempt < max_retries - 1:
            print(f"将在 {delay_seconds} 秒后重试...")
            time.sleep(delay_seconds)
    
    print("错误：发送错误报告邮件失败，已达到最大重试次数。")

def autoProcessETF(target_stock_code):
    # 要监控的ETF代码
    #target_stock_code = "58818 .SH"
    run_trading_strategy(target_stock_code)

if __name__ == "__main__":
   
    #autoProcessETF("511090.SH") ##国债
    #autoProcessETF("161128.SH") ##美股
    #autoProcessETF("513160.SH") ##ganggu30
    autoProcessETF("159843.SH") ##消费
    autoProcessETF("588180.SH") #科创50
    #autoProcessETF("159915.SH") ##创业
    autoProcessETF("512820.SH") ##银行
    

