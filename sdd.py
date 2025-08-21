import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import itertools
from io import StringIO
import sys
from datetime import datetime
import platform
import matplotlib.font_manager as fm
import os
import json
import time
from datetime import datetime, timezone, timedelta
import multiprocessing
from functools import partial

project_root = os.path.dirname((os.path.abspath(__file__)))
sys.path.append(project_root)
print(project_root)



def get_beijing_time():
    """返回当前的北京时间 (UTC+8)"""
    return datetime.now(timezone(timedelta(hours=8)))

# 动态设置matplotlib中文字体，以适应不同操作系统
def set_chinese_font():
    """
    根据操作系统自动设置matplotlib的中文字体。
    """
    os_name = platform.system()
    print(f"当前操作系统: {os_name}，正在配置中文字体...")

    if os_name == 'Windows':
        # Windows系统: 优先使用微软雅黑，备选黑体
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
    elif os_name == 'Linux':
        # Linux系统: 尝试使用常见的开源中文字体
        # 用户可能需要预先安装这些字体, e.g., on Debian/Ubuntu:
        # sudo apt-get update && sudo apt-get install -y fonts-wqy-zenhei
        plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'Liberation Sans',  'WenQuanYi Micro Hei', 'Noto Sans CJK SC']
    elif os_name == 'Darwin':
        # macOS系统: 优先使用苹方，备选黑体-简
        plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'STHeiti']
    else:
        print("未知的操作系统，使用matplotlib默认字体，中文可能无法正常显示。")

    # 解决负号'-'显示为方块的问题
    plt.rcParams['axes.unicode_minus'] = False

    # 检查字体是否可用
    available_fonts = [f.name for f in fm.fontManager.ttflist]
    #print("可用的字体:", available_fonts)

# 在脚本开始时调用函数进行设置
set_chinese_font()

def load_etf_data(filepath):
    df = pd.read_csv(filepath, sep=',') # 或者 pd.read_excel(filepath)
    df['DateTime'] = pd.to_datetime(df['DateTime'])
    df.set_index('DateTime', inplace=True)
    # 确保数值列是float类型
    cols_to_numeric = ['OpenValue', 'CloseValue', 'HighValue', 'LowValue', 'Volume', 'ChangeRate', '成交额', '振幅', '涨跌幅', '涨跌额']
    for col in cols_to_numeric:
        df[col] = pd.to_numeric(df[col], errors='coerce') # errors='coerce' 会将无法转换的设为NaN
    df.dropna(inplace=True) # 处理可能的NaN值
    return df

# 使用示例:
#etf_data = load_etf_data("D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\588180\\588180_Day.csv")
#print(etf_data.head())



#实现简单移动平均线（Simple Moving Average, SMA）交叉策略的函数
def simple_ma_strategy(data, symbol, short_window, long_window, 
                         volume_mavg_Value=10,
                         rsi_period=13,
                         MaRateUp=1.1,
                         rsiValueThd=30,
                         rsiRateUp=1.5,
                         divergence_threshold=0.06,
                         VolumeSellRate=4.5,
                         plot_chart=1,
                         pic_folder='pic',
                         enable_file_io=True
                         ):
    """
    简单均线交叉策略
    :param data: DataFrame, 包含 'CloseValue', 'OpenValue', 'HighValue', 'LowValue', 'Volume'
    :param short_window: 短期均线窗口
    :param long_window: 长期均线窗口
    :param volume_mavg_Value: 成交量均线窗口
    :param rsi_period: RSI周期
    :param MaRateUp: 买入信号倍数
    :param rsiValueThd: RSI阈值
    :param rsiRateUp: RSI超卖倍数
    :param divergence_threshold: 乖离率阈值
    :param VolumeSellRate: 成交量卖出倍数
    :param plot_chart: int, 是否绘制K线和信号图 (0:不绘制, 1:仅保存,2: 保存图片并显示图表)
    :param pic_folder: str, 图片和CSV保存的文件夹路径
    :param enable_file_io: bool, 是否启用文件写入功能 (用于优化)
    :return: Series, 包含信号 (1: 买入, -1: 卖出, 0: 持有)
    """
    signals = pd.DataFrame(index=data.index)
    signals['signal'] = 0.0

    # 计算均线
    signals['short_mavg'] = data['CloseValue'].rolling(window=short_window, min_periods=1).mean()
    signals['long_mavg'] = data['CloseValue'].rolling(window=long_window, min_periods=1).mean()

    # 计算成交量10日均线
    volume_mavg = data['Volume'].rolling(window=volume_mavg_Value, min_periods=1).mean()

    # 1. 定义均线状态: 1代表金叉(short > long), 0代表其他.
    ma_state = (signals['short_mavg'] >= signals['long_mavg']).astype(float)
    
    # 2. 识别状态变化点, .diff()后1为金叉发生点, -1为死叉发生点
    ma_state_diff = ma_state.diff()

    # 计算13日RSI
    delta = data['CloseValue'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=rsi_period - 1, min_periods=rsi_period).mean()
    avg_loss = loss.ewm(com=rsi_period - 1, min_periods=rsi_period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # 3. 生成买入信号: (金叉发生 AND 当日成交量 > 5日均量) OR (RSI < 30)
    ma_buy_condition = (ma_state_diff == 1) & (data['Volume'] >= (volume_mavg * MaRateUp)) #& (data['CloseValue'] > signals['short_mavg'])
    # RSI超卖 且 成交量放大
    rsi_buy_condition = (rsi < rsiValueThd) & (data['Volume'] > (volume_mavg * rsiRateUp) )  
    # 新增：下跌趋势中乖离率过大，也出现买入信号 科创  etf 7.5%  买入，卖出约 -15%
    divergence_ratio = (signals['long_mavg'] - signals['short_mavg']) / signals['long_mavg']
    divergence_buy_condition = (ma_state == 0) & (divergence_ratio > divergence_threshold)  
    #最终的卖出信号
    buy_condition = ma_buy_condition | rsi_buy_condition | divergence_buy_condition

    # 将divergence_ratio转换为百分比并保存到CSV文件
    divergence_df = pd.DataFrame({
        'DateTime': data.index,
        'ma_state': ma_state,
        'divergence_buy_condition': divergence_buy_condition,
        'divergence_threshold': divergence_threshold,
        'divergence_ratio': divergence_ratio,  # 转换为百分比
        'rsiValueThd': rsiValueThd,
        'rsi': rsi,        
        
        'ma_buy_condition': ma_buy_condition,
        'rsi_buy_condition': rsi_buy_condition,
        'buy_condition': buy_condition
    })
    if enable_file_io:
        divergence_df.to_csv(os.path.join(pic_folder, f'{symbol}_divergence_ratio.csv'), index=False)
    
    
    # 卖出条件：死叉、或收盘低于长期均线，另外若收盘价格大于短期均线，暂时不卖出
    #sell_condition = (ma_state_diff == -1) | (data['CloseValue'] < signals['long_mavg'])
    #sell_condition = sell_condition & (data['CloseValue'] < signals['short_mavg'])
    
    # 生成卖出信号: 死叉发生, 或收盘价低于长均线, 或上升趋势中放出天量
    sell_condition = (ma_state_diff == -1) | (data['CloseValue'] < signals['long_mavg']) 
    sell_condition = sell_condition & (data['CloseValue'] < signals['short_mavg'])
    uptrend_volume_sell = (ma_state == 1) & (data['Volume'] > (volume_mavg * VolumeSellRate))
    sell_condition = sell_condition | uptrend_volume_sell
    

    # 5. 合成最终信号, 从short_window开始，以避免早期不稳定数据影响
    signals.loc[buy_condition, 'signal'] = 1
    signals.loc[sell_condition & ~buy_condition, 'signal'] = -1
    signals.loc[signals.index[:short_window], 'signal'] = 0

    # 新增功能：将信号保存到CSV文件
    if enable_file_io:
        signals['signal'].to_csv(os.path.join(pic_folder, f'{symbol}_temp_strategy.csv'), header=True)
    
    # 新增绘图功能
    if plot_chart >= 1:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 9), sharex=True, 
                                        gridspec_kw={'height_ratios': [3, 1]},
                                        constrained_layout=True)
        fig.suptitle('交易策略下的预期信号', fontsize=16)

        # --- 1. K线图 & 均线 & 买卖点 ---
        # 为了避免非交易日造成K线图断裂，我们使用数值索引绘图，然后将X轴标签设置为日期
        plot_data = data.join(signals)
        plot_data_reset = plot_data.reset_index()

        # 计算7日均量
        plot_data_reset['volume_ma'] = plot_data_reset['Volume'].rolling(window=7, min_periods=1).mean()

        up = plot_data_reset[plot_data_reset['CloseValue'] >= plot_data_reset['OpenValue']]
        down = plot_data_reset[plot_data_reset['CloseValue'] < plot_data_reset['OpenValue']]

        # 使用整数索引绘图
        # 绘制影线
        ax1.vlines(plot_data_reset.index, plot_data_reset['LowValue'], plot_data_reset['HighValue'], color=np.where(plot_data_reset['CloseValue'] >= plot_data_reset['OpenValue'], 'red', 'green'), linewidth=1)
        # 绘制实体 (红涨绿跌)
        ax1.vlines(up.index, up['OpenValue'], up['CloseValue'], color='red', linewidth=5)
        ax1.vlines(down.index, down['OpenValue'], down['CloseValue'], color='green', linewidth=5)

        # 绘制均线
        ax1.plot(plot_data_reset.index, plot_data_reset['short_mavg'], color='blue', label=f'短期均线({short_window})', linewidth=2)
        ax1.plot(plot_data_reset.index, plot_data_reset['long_mavg'], color='Black', label=f'长期均线({long_window})', linewidth=2)

        # 标记买卖点
        buy_signals = plot_data_reset[plot_data_reset['signal'] == 1]
        sell_signals = plot_data_reset[plot_data_reset['signal'] == -1]

        if not buy_signals.empty:
            ax1.plot(buy_signals.index, buy_signals['LowValue'] * 0.98, '^', color='red', markersize=10, label='买入信号')

        if not sell_signals.empty:
            ax1.plot(sell_signals.index, sell_signals['HighValue'] * 1.02, 'v', color='green', markersize=10, label='卖出信号')

        ax1.set_ylabel('价格')
        ax1.legend()
        ax1.grid(True)

        # --- 2. 成交量图 ---
        ax2.bar(up.index, up['Volume'] / 10000, color='red', alpha=0.7)
        ax2.bar(down.index, down['Volume'] / 10000, color='green', alpha=0.7)
        ax2.plot(plot_data_reset.index, plot_data_reset['volume_ma'] / 10000, color='blue', linestyle='--', linewidth=1, label=f'{volume_mavg_Value}日均量')
        ax2.set_ylabel('成交量(万手)')
        ax2.legend()
        ax2.grid(True)
        
        # --- 格式化 X 轴 ---
        # 选择性地显示一些日期标签以避免拥挤
        num_ticks = min(10, len(plot_data_reset))
        if num_ticks > 0:
            tick_indices = np.linspace(0, len(plot_data_reset) - 1, num_ticks, dtype=int)
            tick_labels = plot_data_reset['DateTime'].iloc[tick_indices].dt.strftime('%Y-%m-%d')
            ax2.set_xticks(tick_indices)
            ax2.set_xticklabels(tick_labels, rotation=30, ha='right')

        fig.savefig(os.path.join(pic_folder, f'{symbol}_expectSignal.png'))
        #plt.close(fig)

        if plot_chart == 2:
            plt.show()
        plt.close(fig)


    return signals['signal'] # 返回的是一个包含每天信号的Series

#全仓买入、卖出的策略
def run_backtest0(data, signals, initial_capital=100000.0, commission_rate=0.0003):
    """
    执行回测
    :param data: DataFrame, 行情数据，包含 'CloseValue', 'OpenValue'
    :param signals: Series, 策略产生的信号 (1: 买入, -1: 卖出, 0: 持有)
    :param initial_capital: 初始资金
    :param commission_rate: 手续费率 (双边)
    :return: DataFrame, 包含每日资产组合价值等信息
    """
    portfolio = pd.DataFrame(index=data.index)
    portfolio['holdings'] = 0.0  # 持有ETF的市值
    portfolio['cash'] = initial_capital
    portfolio['total'] = initial_capital
    portfolio['shares'] = 0.0    # 持有ETF的份额

    positions = pd.DataFrame(index=signals.index).fillna(0.0)
    positions['ETF'] = 0 # 假设初始不持有

    for i in range(len(data)):
        current_date = data.index[i]
        current_signal = signals.loc[current_date]
        # 假设交易价格为当日收盘价，实际可调整为次日开盘价
        trade_price = data['CloseValue'].loc[current_date]

        if i > 0: # 从第二天开始，继承前一天的状态
            portfolio.loc[current_date, 'cash'] = portfolio.loc[data.index[i-1], 'cash']
            portfolio.loc[current_date, 'shares'] = portfolio.loc[data.index[i-1], 'shares']

        # 买入信号
        if current_signal == 1 and portfolio.loc[current_date, 'shares'] == 0: # 如果有买入信号且当前空仓
            shares_to_buy = portfolio.loc[current_date, 'cash'] / trade_price
            shares_to_buy = np.floor(shares_to_buy / 100) * 100 # ETF通常100份一手，向下取整
            if shares_to_buy > 0:
                cost = shares_to_buy * trade_price * (1 + commission_rate)
                portfolio.loc[current_date, 'cash'] -= cost
                portfolio.loc[current_date, 'shares'] += shares_to_buy
                print(f"{current_date}: BUY {shares_to_buy} shares at {trade_price:.3f}")

        # 卖出信号
        elif current_signal == -1 and portfolio.loc[current_date, 'shares'] > 0: # 如果有卖出信号且当前持仓
            proceeds = portfolio.loc[current_date, 'shares'] * trade_price * (1 - commission_rate)
            portfolio.loc[current_date, 'cash'] += proceeds
            print(f"{current_date}: SELL {portfolio.loc[current_date, 'shares']} shares at {trade_price:.3f}")
            portfolio.loc[current_date, 'shares'] = 0


        # 更新每日市值
        portfolio.loc[current_date, 'holdings'] = portfolio.loc[current_date, 'shares'] * data['CloseValue'].loc[current_date]
        portfolio.loc[current_date, 'total'] = portfolio.loc[current_date, 'cash'] + portfolio.loc[current_date, 'holdings']

    portfolio['returns'] = portfolio['total'].pct_change().fillna(0)
    return portfolio


"""
    执行回测，支持逐步建仓和分批减仓。
    :param data: DataFrame, 行情数据，包含 'CloseValue', 'OpenValue'
    :param signals: Series, 策略产生的信号 (1: 买入, -1: 卖出, 0: 持有)
    :param initial_capital: 初始资金
    :param commission_rate: 手续费率 (双边)
    :param max_portfolio_allocation_pct: 单个ETF持仓占总资产的最大百分比
    :param buy_increment_pct_of_initial_capital: 每次买入动用初始总资金的百分比
    :param sell_decrement_pct_of_current_shares: 每次卖出当前持有份额的百分比
    :param min_shares_per_trade: 最小交易单位
    :param verbose: bool, 是否打印详细日志
    :return: DataFrame, 包含每日资产组合价值等信息
    """
def run_backtest(data,symbol,
                 signals,
                 initial_capital=100000.0,
                 commission_rate=0.0003,
                 max_portfolio_allocation_pct=1, # 最多用80%的总资产投资此ETF
                 buy_increment_pct_of_initial_capital=0.2, # 每次买入动用初始总资金的20%
                 sell_decrement_pct_of_current_shares=0.5, # 每次卖出当前持仓的50%
                 min_shares_per_trade=100, # 最小交易股数 (ETF通常100份)
                 verbose=True,
                 statTime=None, 
                 endTime=None,
                 pic_folder='pic',
                 enable_file_io=True
                ):
    
    # 根据回测时间范围筛选数据
    if statTime or endTime:
        backtest_data = data.loc[statTime:endTime]
    else:
        backtest_data = data

    portfolio = pd.DataFrame(index=backtest_data.index)
    portfolio['holdings_value'] = 0.0  # 持有ETF的市值
    portfolio['cash'] = initial_capital
    portfolio['total_value'] = initial_capital
    portfolio['shares'] = 0.0    # 持有ETF的份额
    portfolio['commission_paid'] = 0.0 # 记录手续费
    portfolio['signal'] = 0.0 # 记录实际发生的交易信号

    if verbose:
        print(f"Backtest Parameters:\n"
              f"  初始本金: {initial_capital}\n"
              f"  最大持仓比例: {max_portfolio_allocation_pct*100}%\n"
              f"  每次买入动用初始总资金的百分比: {buy_increment_pct_of_initial_capital*100}%\n"
              f"  每次卖出当前持有份额的百分比: {sell_decrement_pct_of_current_shares*100}%\n"
              f"  最小交易单位--100份: {min_shares_per_trade}")

    for i in range(len(backtest_data)):
        current_date = backtest_data.index[i]
        current_signal = signals.loc[current_date]
        trade_price = backtest_data['CloseValue'].loc[current_date] # 假设以当日收盘价交易

        # 继承前一天的状态
        if i > 0:
            prev_date = backtest_data.index[i-1]
            portfolio.loc[current_date, 'cash'] = portfolio.loc[prev_date, 'cash']
            portfolio.loc[current_date, 'shares'] = portfolio.loc[prev_date, 'shares']
            portfolio.loc[current_date, 'commission_paid'] = 0 # 当日手续费重置

        current_shares = portfolio.loc[current_date, 'shares']
        current_cash = portfolio.loc[current_date, 'cash']
        current_total_value = portfolio.loc[prev_date, 'total_value'] if i > 0 else initial_capital # 使用前一天的总资产来计算分配上限

        # --- 买入逻辑 ---
        if current_signal == 1:
            # 1. 计算当前持仓市值 和 允许的最大持仓市值
            current_position_value = current_shares * trade_price
            max_allowed_position_value = current_total_value * max_portfolio_allocation_pct

            if current_position_value < max_allowed_position_value:
                # 2. 计算本次计划买入的金额
                capital_for_this_buy_increment = initial_capital * buy_increment_pct_of_initial_capital

                # 3. 实际可用于本次买入的金额 (不能超过最大持仓限额的剩余空间，也不能超过可用现金)
                potential_additional_investment = max_allowed_position_value - current_position_value
                capital_to_invest = min(capital_for_this_buy_increment, potential_additional_investment, current_cash)

                if capital_to_invest > 0:
                    # 4. 计算可购买的股数 (考虑最小交易单位和手续费)
                    # 先估算不含手续费能买多少股，再精确计算含手续费的成本
                    shares_can_afford_approx = capital_to_invest / trade_price
                    shares_to_buy = np.floor(shares_can_afford_approx / min_shares_per_trade) * min_shares_per_trade

                    if shares_to_buy > 0:
                        cost_before_commission = shares_to_buy * trade_price
                        commission = cost_before_commission * commission_rate
                        total_cost = cost_before_commission + commission

                        if total_cost <= current_cash: # 再次确认现金充足
                            portfolio.loc[current_date, 'cash'] -= total_cost
                            portfolio.loc[current_date, 'shares'] += shares_to_buy
                            portfolio.loc[current_date, 'commission_paid'] += commission
                            portfolio.loc[current_date, 'signal'] = 1 # 记录买入
                            if verbose:
                                print(f"{current_date}: BUY {shares_to_buy} shares at {trade_price:.3f}, Cost: {total_cost:.2f}, Commission: {commission:.2f}")
                        # else:
                            # print(f"{current_date}: Attempted BUY, but insufficient cash for {shares_to_buy} shares after commission.")
            # else:
                # print(f"{current_date}: BUY signal, but already at max allocation or no room to add significantly.")

        # --- 卖出逻辑 ---
        elif current_signal == -1 and current_shares > 0:
            # 1. 计算计划卖出的股数
            shares_to_sell_raw = current_shares * sell_decrement_pct_of_current_shares
            shares_to_sell = np.floor(shares_to_sell_raw / min_shares_per_trade) * min_shares_per_trade

            # 如果计算出的股数小于最小交易单位但大于0，且不是清仓，则至少卖出最小单位（如果持有足够）
            # 或者，如果计算后为0，但仍有持仓且卖出比例大于0，则考虑是否清仓或卖出最小单位
            if shares_to_sell == 0 and shares_to_sell_raw > 0 and current_shares >= min_shares_per_trade :
                shares_to_sell = min_shares_per_trade
            elif shares_to_sell == 0 and shares_to_sell_raw > 0 and current_shares < min_shares_per_trade and current_shares > 0:
                 shares_to_sell = current_shares # 卖出剩余的零头

            # 确保不会卖出超过持有的股数 (虽然按比例一般不会，但取整可能导致)
            shares_to_sell = min(shares_to_sell, current_shares)

            if shares_to_sell > 0:
                proceeds_before_commission = shares_to_sell * trade_price
                commission = proceeds_before_commission * commission_rate
                total_proceeds = proceeds_before_commission - commission

                portfolio.loc[current_date, 'cash'] += total_proceeds
                portfolio.loc[current_date, 'shares'] -= shares_to_sell
                portfolio.loc[current_date, 'commission_paid'] += commission
                portfolio.loc[current_date, 'signal'] = -1 # 记录卖出
                if verbose:
                    print(f"{current_date}: SELL {shares_to_sell} shares at {trade_price:.3f}, Proceeds: {total_proceeds:.2f}, Commission: {commission:.2f}")
            # else:
                # print(f"{current_date}: SELL signal, but calculated shares to sell is 0 or no shares held.")

        # 更新每日市值和总资产
        portfolio.loc[current_date, 'holdings_value'] = portfolio.loc[current_date, 'shares'] * trade_price
        portfolio.loc[current_date, 'total_value'] = portfolio.loc[current_date, 'cash'] + portfolio.loc[current_date, 'holdings_value']

    # 计算每日收益率 (基于 total_value)
    portfolio['returns'] = portfolio['total_value'].pct_change().fillna(0)
    # 计算累计收益率
    portfolio['cumulative_returns'] = (1 + portfolio['returns']).cumprod() - 1
    # 重命名列以匹配 performance_analyzer 的期望
    portfolio.rename(columns={'total_value': 'total', 'holdings_value': 'holdings'}, inplace=True)
    # 保存投资组合信息到CSV文件
    if enable_file_io:
        portfolio_info = portfolio[['cash', 'shares', 'holdings', 'total', 'returns', 'cumulative_returns','commission_paid']].copy()
        portfolio_info['returns'] = portfolio_info['returns'].map('{:.2%}'.format)
        portfolio_info['cumulative_returns'] = portfolio_info['cumulative_returns'].map('{:.2%}'.format)
        portfolio_info.index.name = 'DateTime'
        portfolio_info.to_csv(os.path.join(pic_folder, f'{symbol}_BuyAndSell.csv'), float_format='%.2f')
    return portfolio


def calculate_performance(portfolio_df, initial_capital, verbose=True):
    """
    计算并打印绩效指标
    :param portfolio_df: DataFrame, 回测引擎返回的每日资产组合信息
    :param initial_capital: 初始资金
    :param verbose: bool, 是否打印绩效指标
    """
    final_value = portfolio_df['total'].iloc[-1]
    total_return = (final_value / initial_capital) - 1
    num_days = len(portfolio_df)
    # 假设一年245个交易日
    annualized_return = ((1 + total_return) ** (252.0 / num_days)) - 1 if num_days > 0 else 0

    # 最大回撤
    portfolio_df['peak'] = portfolio_df['total'].cummax()
    portfolio_df['drawdown'] = (portfolio_df['total'] - portfolio_df['peak']) / portfolio_df['peak']
    max_drawdown = portfolio_df['drawdown'].min()

    # 夏普比率 (简化版，假设无风险利率为0)
    daily_returns = portfolio_df['returns']
    sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() != 0 else 0

    if verbose:
        print(f"------ 绩效指标 ------") 
        print(f"初始资本: {initial_capital:.2f}") 
        print(f"最终投资组合价值: {final_value:.2f}") 
        print(f"总回报率: {total_return*100:.2f}%") 
        print(f"年化回报率: {annualized_return*100:.2f}%") 
        print(f"最大回撤: {max_drawdown*100:.2f}%") 
        print(f"夏普比率: {sharpe_ratio:.2f}")

    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "portfolio_df": portfolio_df # 返回带有计算列的DataFrame
    }

def add_crosshair_cursor(fig, ax0, ax3, plot_data):
    """
    为K线图和成交量图添加交互式十字光标和信息显示。

    :param fig: Figure对象
    :param ax0: K线图的Axes对象
    :param ax3: 成交量图的Axes对象
    :param plot_data: 包含绘图数据的DataFrame
    """
    # 创建十字光标的线条，初始时不可见
    cursor_v_ax0 = ax0.axvline(x=-1, color='k', linestyle='--', linewidth=0.8, visible=False)
    cursor_v_ax3 = ax3.axvline(x=-1, color='k', linestyle='--', linewidth=0.8, visible=False)
    cursor_h_ax3 = ax3.axhline(y=-1, color='k', linestyle='--', linewidth=0.8, visible=False)

    # 创建信息注释框，初始时不可见
    annot_text = ax3.text(0, 0, '', visible=False,
                          bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.8),
                          fontdict={'size': 10})

    def on_mouse_move(event):
        # 检查鼠标是否在ax0或ax3坐标轴内
        if event.inaxes not in [ax0, ax3]:
            # 如果鼠标移出，则隐藏所有指示元素
            if cursor_v_ax0.get_visible():
                cursor_v_ax0.set_visible(False)
                cursor_v_ax3.set_visible(False)
                cursor_h_ax3.set_visible(False)
                annot_text.set_visible(False)
                fig.canvas.draw_idle()
            return

        # 获取鼠标位置对应的x轴索引
        x_idx = int(round(event.xdata))

        # 确保索引在有效范围内
        if 0 <= x_idx < len(plot_data):
            # 获取对应数据点的信息
            data_point = plot_data.iloc[x_idx]
            close_price = data_point['CloseValue']
            volume = data_point['Volume']
            date_str = data_point['DateTime'].strftime('%Y-%m-%d')
            rsi_value = data_point.get('rsi', float('nan'))
            
            # 更新垂直线的位置
            cursor_v_ax0.set_xdata([x_idx, x_idx])
            cursor_v_ax3.set_xdata([x_idx, x_idx])

            # 只在鼠标悬停于ax3上时显示水平线
            if event.inaxes == ax3:
                cursor_h_ax3.set_ydata([event.ydata, event.ydata])
                cursor_h_ax3.set_visible(True)
            else:
                cursor_h_ax3.set_visible(False)

            # 准备要显示的文本
            text_to_display = f"日期: {date_str}\n收盘价: {close_price:.2f}\n成交量: {volume/10000:.2f}万手\nRSI: {rsi_value:.2f}"
            annot_text.set_text(text_to_display)

            # 根据鼠标位置决定文本框显示在左侧还是右侧，避免遮挡
            xlim = ax3.get_xlim()
            if event.xdata > (xlim[0] + xlim[1]) / 2:
                annot_text.set_position((event.xdata - (xlim[1]-xlim[0])*0.02, event.ydata))
                annot_text.set_ha('right') # 水平对齐：右
            else:
                annot_text.set_position((event.xdata + (xlim[1]-xlim[0])*0.02, event.ydata))
                annot_text.set_ha('left') # 水平对齐：左

            annot_text.set_va('center') # 垂直居中对齐
            
            # 设置所有指示元素为可见
            cursor_v_ax0.set_visible(True)
            cursor_v_ax3.set_visible(True)
            annot_text.set_visible(True)
            
            # 重绘画布以显示更新
            fig.canvas.draw_idle()

    # 将事件处理函数连接到图
    fig.canvas.mpl_connect('motion_notify_event', on_mouse_move)

def _plot_candlestick(ax, plot_data, title="K线图及交易信号"):
    """辅助函数：在给定的Axes上绘制K线图"""
    up = plot_data[plot_data['CloseValue'] >= plot_data['OpenValue']]
    down = plot_data[plot_data['CloseValue'] < plot_data['OpenValue']]
    
    # 绘制影线 (红涨绿跌)
    ax.vlines(up.index, up['LowValue'], up['HighValue'], color='red', linewidth=1, alpha=0.8)
    ax.vlines(down.index, down['LowValue'], down['HighValue'], color='green', linewidth=1, alpha=0.8)
    # 绘制实体
    ax.vlines(up.index, up['OpenValue'], up['CloseValue'], color='red', linewidth=5)
    ax.vlines(down.index, down['OpenValue'], down['CloseValue'], color='green', linewidth=5)
    
    ax.set_title(title)
    ax.set_ylabel('价格')
    ax.grid(True)


def plot_performance(portfolio_df, symbol, benchmark_data=None, 
                     short_window=5, long_window=21, # 均线值
                     volume_mavg_Value=10, #成交量x日均值
                     rsi_period=13, # RSI周期
                     plot_chart=2,
                     pic_folder='pic'):
    """
    绘制集成化的绩效分析仪表盘
    :param portfolio_df: DataFrame, 包含 'total', 'drawdown', 'OpenValue', ... 'signal' 列
    :param benchmark_data: Series, 基准收益率
    :param short_window: 短期均线窗口
    :param long_window: 长期均线窗口
    :param volume_mavg_Value: 成交量均线窗口
    :param rsi_period: RSI 计算周期
    :param plot_chart: int, 控制绘图。0:不处理, 1:仅保存, 2:保存并显示
    :param pic_folder: str, 图片和CSV保存的文件夹路径
    """
    required_cols = ['OpenValue', 'HighValue', 'LowValue', 'CloseValue', 'Volume', 'signal', 'total', 'drawdown']
    if not all(col in portfolio_df.columns for col in required_cols):
        print("绘图失败：DataFrame缺少必要的列。")
        if 'total' in portfolio_df.columns:
            portfolio_df['total'].plot(title='投资组合价值').grid(True)
            plt.show()
        return

    plot_data = portfolio_df.reset_index()
    
    # --- 1. 数据计算 ---
    ma_short_col = f'ma{short_window}'
    ma_long_col = f'ma{long_window}'
    plot_data[ma_short_col] = plot_data['CloseValue'].rolling(window=short_window).mean()
    plot_data[ma_long_col] = plot_data['CloseValue'].rolling(window=long_window).mean()
    plot_data['volume_ma'] = plot_data['Volume'].rolling(window=volume_mavg_Value).mean()
    
    # 计算RSI
    delta = plot_data['CloseValue'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=rsi_period - 1, min_periods=rsi_period).mean()
    avg_loss = loss.ewm(com=rsi_period - 1, min_periods=rsi_period).mean()
    plot_data['rsi'] = 100 - (100 / (1 + (avg_gain / avg_loss)))

    # --- 2. 图表布局 (新顺序) ---
    fig = plt.figure(figsize=(20, 18), constrained_layout=True)
    fig.suptitle('策略绩效分析仪表盘', fontsize=20)
    # K线(6), 成交量(1.5), RSI(1), 净值(2), 回撤(1)
    gs = fig.add_gridspec(5, 1, height_ratios=[6, 1.5, 1, 2, 1])
    
    ax_kline = fig.add_subplot(gs[0])
    ax_volume = fig.add_subplot(gs[1], sharex=ax_kline)
    ax_rsi = fig.add_subplot(gs[2], sharex=ax_kline)
    ax_equity = fig.add_subplot(gs[3], sharex=ax_kline)
    ax_drawdown = fig.add_subplot(gs[4], sharex=ax_kline)

    # 隐藏非底部图表的X轴标签
    plt.setp(ax_kline.get_xticklabels(), visible=False)
    plt.setp(ax_volume.get_xticklabels(), visible=False)
    plt.setp(ax_rsi.get_xticklabels(), visible=False)
    plt.setp(ax_equity.get_xticklabels(), visible=False)

    # --- 3. 绘制各个子图 (新顺序) ---
    # K线图, 均线, 交易信号
    _plot_candlestick(ax_kline, plot_data)
    ax_kline.plot(plot_data.index, plot_data[ma_short_col], color='blue', lw=1.5, label=f'{short_window}日均线')
    ax_kline.plot(plot_data.index, plot_data[ma_long_col], color='purple', lw=1.5, label=f'{long_window}日均线')

    buy_signals = plot_data[plot_data['signal'] == 1]
    sell_signals = plot_data[plot_data['signal'] == -1]
    if not buy_signals.empty:
        ax_kline.plot(buy_signals.index, buy_signals['LowValue'] * 0.99, '^', c='red', ms=12, label='买入信号', mec='black')
    if not sell_signals.empty:
        ax_kline.plot(sell_signals.index, sell_signals['HighValue'] * 1.01, 'v', c='green', ms=12, label='卖出信号', mec='black')
    ax_kline.legend(loc='upper left')
    
    # 成交量图
    up = plot_data[plot_data['CloseValue'] >= plot_data['OpenValue']]
    down = plot_data[plot_data['CloseValue'] < plot_data['OpenValue']]
    ax_volume.bar(up.index, up['Volume'] / 10000, color='red', alpha=0.7)
    ax_volume.bar(down.index, down['Volume'] / 10000, color='green', alpha=0.7)
    ax_volume.plot(plot_data.index, plot_data['volume_ma'] / 10000, color='blue', lw=1, label=f'{volume_mavg_Value}日均量')
    ax_volume.set_title('成交量(万手)')
    ax_volume.set_ylabel('成交量(万手)')
    ax_volume.legend(loc='upper left')
    ax_volume.grid(True)
    
    # RSI 指标图
    ax_rsi.set_title('RSI 指标')
    ax_rsi.plot(plot_data.index, plot_data['rsi'], color='orange', lw=1.5, label=f'RSI({rsi_period})')
    ax_rsi.axhline(70, color='red', linestyle='--', lw=1, alpha=0.8)
    ax_rsi.axhline(30, color='green', linestyle='--', lw=1, alpha=0.8)
    ax_rsi.fill_between(plot_data.index, 70, 100, color='red', alpha=0.1)
    ax_rsi.fill_between(plot_data.index, 0, 30, color='green', alpha=0.1)
    ax_rsi.set_ylim(0, 100)
    ax_rsi.legend(loc='upper left')
    ax_rsi.grid(True)

    # 资产净值曲线 vs. 基准
    ax_equity.set_title('投资组合价值')
    ax_equity.plot(plot_data.index, plot_data['total'], label='策略净值', color='dodgerblue')
    if benchmark_data is not None:
        initial_capital = plot_data['total'].iloc[0]
        benchmark_normalized = (1 + benchmark_data['returns']).cumprod() * initial_capital
        benchmark_normalized = benchmark_normalized.reindex(plot_data['DateTime'], method='pad').values
        ax_equity.plot(plot_data.index, benchmark_normalized, label='基准', color='darkgrey', linestyle='--')
    ax_equity.legend(loc='upper left')
    ax_equity.grid(True)
    
    # 回撤曲线
    ax_drawdown.set_title('回撤')
    ax_drawdown.plot(plot_data.index, plot_data['drawdown'], color='#F4A460')
    ax_drawdown.fill_between(plot_data.index, plot_data['drawdown'], 0, color='#FF7F7F', alpha=0.5)
    ax_drawdown.grid(True)

    # --- 4. 格式化和显示 ---
    num_ticks = min(20, len(plot_data))
    if num_ticks > 0:
        tick_indices = np.linspace(0, len(plot_data) - 1, num_ticks, dtype=int)
        tick_labels = plot_data['DateTime'].iloc[tick_indices].dt.strftime('%Y-%m-%d')
        ax_drawdown.set_xticks(tick_indices)
        ax_drawdown.set_xticklabels(tick_labels, rotation=30, ha='right')

    # 为所有子图添加十字光标功能
    add_crosshair_cursor(fig, ax_kline, ax_volume, plot_data)
    
    fig.savefig(os.path.join(pic_folder, f'{symbol}_Strategy_Performance_Dashboard.png'))
    
    if plot_chart == 2:
        plt.show()
    
    plt.close(fig)



'''
from data_handler import load_etf_data
from strategy import simple_ma_strategy # 或者你的策略函数
from backtester import run_backtest
from performance_analyzer import calculate_performance, plot_performance
'''
"""
测试策略函数
:param filepath: 数据文件路径
:param short_window: 短期均线窗口
:param long_window: 长期均线窗口
:param initial_capital: 初始资金
:param commission: 手续费率
:param max_portfolio_allocation_pct: 最大资金使用比例
:param buy_increment_pct_of_initial_capital: 每次买入资金比例
:param sell_decrement_pct_of_current_shares: 每次卖出份额比例
:param min_shares_per_trade: 最小交易份额
:param volume_mavg_Value: 成交量均线窗口
:param rsi_period: RSI周期
:param MaRateUp: 买入信号倍数
:param rsiValueThd: RSI阈值
:param rsiRateUp: RSI超卖倍数
:param divergence_threshold: 乖离率阈值
:param VolumeSellRate: 成交量卖出倍数
:param plot_results: int, 控制绘图和保存。0:不绘制不保存, 1:仅保存图片, 2:保存并显示图片
:param verbose: bool, 是否打印详细日志
"""
def strategyFunc(filepath=None, 
             data=None,
             symbol=None,
             short_window=5, 
             long_window=16,
             initial_capital=10000.0,
             commission=0.0003,
             max_portfolio_allocation_pct=1,
             buy_increment_pct_of_initial_capital=1,
             sell_decrement_pct_of_current_shares=1,
             min_shares_per_trade=100,
             volume_mavg_Value=10,
             rsi_period=13,
             MaRateUp=1.1,
             rsiValueThd=30,
             rsiRateUp=1.5,
             divergence_threshold=0.06,
             VolumeSellRate=4.5,
             statTime=None, endTime=None,
             plot_results=2, verbose=True,
             enable_file_io=True):

        # 从filepath推断出根目录和pic目录
        # filepath is like '.../stock_data/588180/588180_Day.csv'
        # We want '.../pic'
        if filepath:
            stock_data_folder = os.path.dirname(os.path.dirname(filepath)) # .../stock_data
            project_root_folder = os.path.dirname(stock_data_folder) # .../
            pic_folder = os.path.join(project_root_folder, 'pic')
        else:
            pic_folder = os.path.join(project_root, 'pic')

        # 确保pic文件夹存在
        os.makedirs(pic_folder, exist_ok=True)
        #print(f"图片和CSV将保存到: {pic_folder}")

        # 1. 加载数据
        if data is not None:
            etf_data = data
        elif filepath:
            etf_data = load_etf_data(filepath)
        else:
            raise ValueError("Either 'filepath' or 'data' must be provided to strategyFunc.")
        
        if verbose:
            print("数据加载成功:")
            print(etf_data.head())

        # 2. 生成策略信号
        signals = simple_ma_strategy(etf_data, symbol,
                                     short_window=short_window, long_window=long_window, 
                                     volume_mavg_Value=volume_mavg_Value,
                                     rsi_period=rsi_period,
                                     MaRateUp=MaRateUp,
                                     rsiValueThd=rsiValueThd,
                                     rsiRateUp=rsiRateUp,
                                     divergence_threshold=divergence_threshold,
                                     VolumeSellRate=VolumeSellRate,
                                     plot_chart=plot_results,
                                     pic_folder=pic_folder,
                                     enable_file_io=enable_file_io
                                     )

        # 3. 执行回测
        portfolio_results_df = run_backtest(
            etf_data,symbol,
            signals,
            initial_capital=initial_capital,
            commission_rate=commission,
            max_portfolio_allocation_pct=max_portfolio_allocation_pct,
            buy_increment_pct_of_initial_capital=buy_increment_pct_of_initial_capital,
            sell_decrement_pct_of_current_shares=sell_decrement_pct_of_current_shares,
            min_shares_per_trade=min_shares_per_trade,
            verbose=verbose,
            statTime=statTime,
            endTime=endTime,
            pic_folder=pic_folder,
            enable_file_io=enable_file_io
        )

        # 4. 计算并展示绩效
        benchmark_returns = etf_data['CloseValue'].pct_change().fillna(0)
        benchmark_df_for_plot = pd.DataFrame({'returns': benchmark_returns}, index=etf_data.index)

        performance_stats = calculate_performance(portfolio_results_df, initial_capital, verbose=verbose)
        

        portfolio_df_for_plot = performance_stats["portfolio_df"]

        # 5. 准备绘图数据
        plot_df = portfolio_df_for_plot.join(etf_data[['OpenValue', 'HighValue', 'LowValue', 'CloseValue', 'Volume']])

        # 6. 绘制图表
        if plot_results >= 1:
            plot_performance(plot_df, symbol, benchmark_df_for_plot, 
                                short_window, 
                                long_window, 
                                volume_mavg_Value,
                                rsi_period,
                                plot_chart=plot_results,
                                pic_folder=pic_folder)
        
        if verbose:
            print("\n回测完成。")
        return performance_stats


def testOnlyOk(symbol):
    #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\561560_Day.csv"
   #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\518880_Day.csv"
   #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\588180_Day.csv" # 科创50
   #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\159915_Day.csv" #创业板
   #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\513160_Day.csv" #港股科技
   filepath = os.path.join(project_root, 'stock_data', f'{symbol}', f'{symbol}_Day.csv')
   print(filepath) 
   # --- 策略参数 ---
   short_window = 5
   long_window = 21
   volume_mavg_Value=10
   MaRateUp=1.1
   VolumeSellRate=4.5
   rsi_period=13
   rsiValueThd=30
   rsiRateUp=1.5
   divergence_threshold=0.06

   # --- 回测参数 ---
   initial_capital=10000.0
   commission=0.0003
   max_portfolio_allocation_pct=1
   buy_increment = 1  # 每次买入动用初始总资金的百分比, 1为全仓
   sell_decrement = 1 # 每次卖出当前持有份额的百分比, 1为全部卖出
   min_shares_per_trade=100

   strategyFunc(filepath,
            symbol=symbol,
            short_window=short_window,
            long_window=long_window,
            initial_capital=initial_capital,
            commission=commission,
            max_portfolio_allocation_pct=max_portfolio_allocation_pct,
            buy_increment_pct_of_initial_capital=buy_increment,
            sell_decrement_pct_of_current_shares=sell_decrement,
            min_shares_per_trade=min_shares_per_trade,
            volume_mavg_Value=volume_mavg_Value,
            rsi_period=rsi_period,
            MaRateUp=MaRateUp,
            rsiValueThd=rsiValueThd,
            rsiRateUp=rsiRateUp,
            divergence_threshold=divergence_threshold,
            VolumeSellRate=VolumeSellRate,
            statTime='2023-1-01',
            endTime='2025-9-20',
            plot_results=2,
            verbose=True,
            enable_file_io=True)


def testOnly1(symbol = "588180"):
    #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\561560_Day.csv"
   #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\518880_Day.csv"
   #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\588180_Day.csv" # 科创50
   #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\159915_Day.csv" #创业板
   #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\513160_Day.csv" #港股科技
   
   filepath = os.path.join(project_root, 'stock_data', f'{symbol}', f'{symbol}_Day.csv')
   print(filepath)

   # --- 策略参数 ---
   Parameters1 = {'short_window': np.int64(3), 
                'long_window': np.int64(10), 
                'volume_mavg_Value': np.int64(10), 
                'MaRateUp': np.float64(1.5), 
                'VolumeSellRate': np.float64(3.0), 
                'rsi_period': np.int64(10), 
                'rsiValueThd': np.int64(30), 
                'rsiRateUp': np.float64(1.5), 
                'divergence_threshold': np.float64(0.04)
                }
   Parameters = {'short_window': np.int64(3), 
                'long_window': np.int64(12), 
                'volume_mavg_Value': np.int64(5), 
                'MaRateUp': np.float64(1.5), 
                'VolumeSellRate': np.float64(3.0), 
                'rsi_period': np.int64(11), 
                'rsiValueThd': np.int64(29), 
                'rsiRateUp': np.float64(1.4), 
                'divergence_threshold': np.float64(0.04)}
   
   short_window = Parameters['short_window']
   long_window = Parameters['long_window']
   volume_mavg_Value=Parameters['volume_mavg_Value']
   MaRateUp=Parameters['MaRateUp']
   VolumeSellRate=Parameters['VolumeSellRate']
   rsi_period=Parameters['rsi_period']
   rsiValueThd=Parameters['rsiValueThd']
   rsiRateUp=Parameters['rsiRateUp']
   divergence_threshold=Parameters['divergence_threshold']

   # --- 回测参数 ---
   initial_capital=10000.0
   commission=0.0003
   max_portfolio_allocation_pct=1
   buy_increment = 1  # 每次买入动用初始总资金的百分比, 1为全仓
   sell_decrement = 1 # 每次卖出当前持有份额的百分比, 1为全部卖出
   min_shares_per_trade=100

   strategyFunc(filepath,
            symbol=symbol,
            short_window=short_window,
            long_window=long_window,
            initial_capital=initial_capital,
            commission=commission,
            max_portfolio_allocation_pct=max_portfolio_allocation_pct,
            buy_increment_pct_of_initial_capital=buy_increment,
            sell_decrement_pct_of_current_shares=sell_decrement,
            min_shares_per_trade=min_shares_per_trade,
            volume_mavg_Value=volume_mavg_Value,
            rsi_period=rsi_period,
            MaRateUp=MaRateUp,
            rsiValueThd=rsiValueThd,
            rsiRateUp=rsiRateUp,
            divergence_threshold=divergence_threshold,
            VolumeSellRate=VolumeSellRate,
            statTime='2022-1-01',
            endTime='2025-9-20',
            plot_results=0,
            verbose=True,
            enable_file_io=True)

def testOnlyNew(symbol):
    #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\561560_Day.csv"
   #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\518880_Day.csv"
   #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\588180_Day.csv" # 科创50
   #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\159915_Day.csv" #创业板
   #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\513160_Day.csv" #港股科技
   filepath = os.path.join(project_root, 'stock_data', f'{symbol}', f'{symbol}_Day.csv')
   print(filepath) 
   # --- 策略参数 ---
   Parameters = {'short_window': np.int64(3), 
                'long_window': np.int64(12), 
                'volume_mavg_Value': np.int64(5), 
                'MaRateUp': np.float64(1.5), 
                'VolumeSellRate': np.float64(3.0), 
                'rsi_period': np.int64(11), 
                'rsiValueThd': np.int64(29), 
                'rsiRateUp': np.float64(1.4), 
                'divergence_threshold': np.float64(0.04)}
   
   short_window = Parameters['short_window']
   long_window = Parameters['long_window']
   volume_mavg_Value=Parameters['volume_mavg_Value']
   MaRateUp=Parameters['MaRateUp']
   VolumeSellRate=Parameters['VolumeSellRate']
   rsi_period=Parameters['rsi_period']
   rsiValueThd=Parameters['rsiValueThd']
   rsiRateUp=Parameters['rsiRateUp']
   divergence_threshold=Parameters['divergence_threshold']

   # --- 回测参数 ---
   initial_capital=10000.0
   commission=0.0003
   max_portfolio_allocation_pct=1
   buy_increment = 1  # 每次买入动用初始总资金的百分比, 1为全仓
   sell_decrement = 1 # 每次卖出当前持有份额的百分比, 1为全部卖出
   min_shares_per_trade=100

   performance_stats = strategyFunc(filepath,
        symbol=symbol,
        short_window=short_window,
        long_window=long_window,
        initial_capital=initial_capital,
        commission=commission,
        max_portfolio_allocation_pct=max_portfolio_allocation_pct,
        buy_increment_pct_of_initial_capital=buy_increment,
        sell_decrement_pct_of_current_shares=sell_decrement,
        min_shares_per_trade=min_shares_per_trade,
        volume_mavg_Value=volume_mavg_Value,
        rsi_period=rsi_period,
        MaRateUp=MaRateUp,
        rsiValueThd=rsiValueThd,
        rsiRateUp=rsiRateUp,
        divergence_threshold=divergence_threshold,
        VolumeSellRate=VolumeSellRate,
        statTime='2025-1-1',
        endTime='2025-9-20',
        plot_results=2, 
        verbose=False,
        enable_file_io=True)

    # 获取回测结果的 portfolio DataFrame
   portfolio_df = performance_stats.get('portfolio_df')

   if portfolio_df is not None and not portfolio_df.empty:
        # 获取今天的日期 (Timestamp, a specific point in time, with date and time components)
       today = pd.to_datetime(datetime.now().date())
       print(f"\n当前日期: {today.strftime('%Y-%m-%d')}")

       #print("\n回测结果中的信号:")
       #for index, row in portfolio_df.iterrows():
       #    print(f"{index.strftime('%Y-%m-%d')}, {row['signal']}")

        # 检查今天的日期是否存在于回测结果的索引中
       if today in portfolio_df.index:
           todays_signal = portfolio_df.loc[today]['signal']
           if todays_signal == 1:
               print(f"\n交易信号 ({today.strftime('%Y-%m-%d')}): 买入")

           elif todays_signal == -1:
               print(f"\n交易信号 ({today.strftime('%Y-%m-%d')}): 卖出")

           else:
               print(f"\n交易信号 ({today.strftime('%Y-%m-%d')}): 无买卖信号")

       else:
           print("\n今天无买卖信号")
   else:
       print("\n今天无买卖信号")

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)

def _find_params_worker(args):
    """
    Worker function for findGoodParam's multiprocessing pool.
    Runs a single backtest with a given set of parameters.
    Unpacks arguments for multiprocessing.
    """
    params, etf_data, symbol, statTime, endTime = args
    try:
        performance_stats = strategyFunc(
            data=etf_data, # 直接传递数据
            symbol=symbol,
            **params,
            initial_capital=10000.0,
            commission=0.0003,
            max_portfolio_allocation_pct=1,
            buy_increment_pct_of_initial_capital=1,
            sell_decrement_pct_of_current_shares=1,
            min_shares_per_trade=100,
            statTime=statTime,
            endTime=endTime,
            plot_results=0,  # Disable plotting for optimization
            verbose=False,   # Disable verbose logging for optimization
            enable_file_io=False # 禁用文件写入
        )

        return {
            'params': params,
            'total_return': performance_stats['total_return'],
            'annualized_return': performance_stats['annualized_return'],
            'sharpe_ratio': performance_stats['sharpe_ratio'],
            'max_drawdown': performance_stats['max_drawdown']
        }
    except Exception as e:
        # Optional: Log the error. For now, just returning None is fine.
        # print(f"\nError with params {params}: {e}")
        return None

def findGoodParam(symbol, 
                param_grid=None, 
                statTime='2021-1-30',
                endTime='2025-3-10'):
    #filepath="D:\\Code\\Ai\\jinrongTest\\github\\stock_data\\588180_Day.csv" # 科创50
    filepath = os.path.join(project_root, 'stock_data', f'{symbol}', f'{symbol}_Day.csv')
    print(f"Loading data from: {filepath}") 
    # 1. 一次性加载数据
    etf_data = load_etf_data(filepath)
    print("Data loaded successfully.")

    stock_data_folder = os.path.dirname(filepath) # .../stock_data/symbol
    print(stock_data_folder) 

    # 生成所有参数组合
    keys, values = zip(*param_grid.items())
    param_combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]

    # 预先筛选无效的组合
    valid_combinations = [p for p in param_combinations if p.get('long_window', 0) > p.get('short_window', 0)]
    
    total_combinations = len(valid_combinations)
    if total_combinations == 0:
        print("没有有效的参数组合。")
        return

    print(f"开始寻找最优参数，共 {total_combinations} 种有效组合...")

    # 使用所有可用的CPU核心
    num_processes = multiprocessing.cpu_count()
    print(f"使用 {num_processes} 个进程进行并行计算...")
    
    # 2. 准备要传递给工作进程的参数
    # 将共享的参数与每个变化的参数组合打包
    tasks = [(p, etf_data, symbol, statTime, endTime) for p in valid_combinations]

    results = []
    # 使用多进程池并行执行回测
    with multiprocessing.Pool(processes=num_processes) as pool:
        # 使用functools.partial来创建一个带有固定参数的新函数
        # task = partial(_find_params_worker, etf_data=etf_data, symbol=symbol, statTime=statTime, endTime=endTime)
        
        # imap_unordered可以让我们在任务完成时立即获得结果，便于展示进度
        for i, result in enumerate(pool.imap_unordered(_find_params_worker, tasks), 1):
            if result:
                results.append(result)
            
            # 在控制台更新进度
            progress = f"进度: {i}/{total_combinations} ({(i / total_combinations) * 100:.1f}%)"
            sys.stdout.write(f'\r{progress}')
            sys.stdout.flush()
    
    print(f"\n\n------------{symbol}:参数寻优完成！------------")
    
    if not results:
        print("所有参数组合均未产生有效结果。")
        return

    # 对结果进行排序
    results.sort(key=lambda x: (x['total_return'], x['sharpe_ratio'], x['max_drawdown']), reverse=True)
    top_results = results[:50]

    print("------------------------------------")
    if top_results:
        best_result = top_results[0]
        print(f"最佳参数组合: {best_result['params']}")
        print(f"对应的夏普比率: {best_result['sharpe_ratio']:.2f}")
        print(f"总回报率: {best_result['total_return']*100:.2f}%")
        print(f"最大年化回报率: {best_result['annualized_return']*100:.2f}%")
       
        print(f"对应的最大回撤: {best_result['max_drawdown']*100:.2f}%")

        try:
            
            logFile = os.path.join(stock_data_folder, f'{symbol}_FindReturn.log')
            with open(logFile, 'w', encoding='utf-8') as f:
                f.write(f"Top 50 Parameter Combinations for {symbol}\n")
                f.write("Ranked by Total Return, then Sharpe Ratio, then Max Drawdown\n")
                f.write("="*50 + "\n")
                for i, result in enumerate(top_results):
                    f.write(f"Rank {i+1}:\n")
                    f.write(f"  Sharpe Ratio: {result['sharpe_ratio']:.2f}\n")  
                    f.write(f"  Total Return: {result['total_return']*100:.2f}%\n") 
                    f.write(f"  Max Drawdown: {result['max_drawdown']*100:.2f}%\n")
                    f.write(f"  Annualized Return: {result['annualized_return']*100:.2f}%\n")
                                   
                    f.write(f"  Parameters: {json.dumps(result['params'], indent=2, cls=NpEncoder)}\n")
                    f.write("-" * 20 + "\n")
            print(f"\nTop 50 results saved to {logFile}")
        except IOError as e:
            print(f"\nError writing to file {logFile}: {e}")
    else:
        print("没有找到有效的参数组合。")



def chuanyeETFParaFind(): 
   symbol = "159915"  
   # 定义自定义参数网格
   custom_param_grid = {
       'short_window': np.arange(3, 6, 1),            
       'long_window': np.arange(10, 20, 3),           
       'volume_mavg_Value': np.arange(5, 15, 5),      
       'MaRateUp': np.arange(1, 2, 0.5),          
       'VolumeSellRate': np.arange(3.0, 6, 1),    
       'rsi_period': np.arange(7, 14, 3),             
       'rsiValueThd': np.arange(23, 30, 1),          
       'rsiRateUp': np.arange(1, 3, 0.5),         
       'divergence_threshold': np.round(np.arange(0.04, 0.08, 0.01), 2)
   }
   
   # 使用自定义参数网格和时间范围调用findGoodParam
   findGoodParam(
       symbol = symbol,
       param_grid = custom_param_grid,
       statTime = '2022-1-01',
       endTime = '2025-1-01'
   )



def kechuang50ETFParaFind():   

   symbol = "588180"
   custom_param_grid = {
        'short_window': np.arange(3, 6, 1),            # 从3到8，步长为2
        'long_window': np.arange(10, 20, 2),           # 从10到30，步长为5
        'volume_mavg_Value': np.arange(5, 15, 4),      # 从5到15，步长为5
        'MaRateUp': np.arange(1, 2, 0.5),          # 从0.5到1.5，步长为0.5
        'VolumeSellRate': np.arange(3.0, 6, 1),    # 从2.0到8.0，步长为2.0
        'rsi_period': np.arange(7, 16, 4),             # 从7到20，步长为3
        'rsiValueThd': np.arange(25, 35, 4),          # 从10到50，步长为10
        'rsiRateUp': np.arange(1, 2, 0.4),         # 从0.5到5.0，步长为1.0
        'divergence_threshold': np.round(np.arange(0.04, 0.08, 0.05), 2) # 从0.03到0.1，步长为0.02
    }
   
   # 使用自定义参数网格和时间范围调用findGoodParam2
   findGoodParam(
       symbol = symbol,
       param_grid = custom_param_grid,
       statTime = '2022-1-01',
       endTime = '2024-9-20'
   )


def ganggu30ETFParaFind():   

   symbol = "513160"
   custom_param_grid = {
        'short_window': np.arange(3, 6, 1),            # 从3到8，步长为2
        'long_window': np.arange(10, 20, 2),           # 从10到30，步长为5
        'volume_mavg_Value': np.arange(5, 15, 2),      # 从5到15，步长为5
        'MaRateUp': np.arange(1, 3, 0.5),          # 从0.5到1.5，步长为0.5
        'VolumeSellRate': np.arange(1.0, 6.0, 1),    # 从2.0到8.0，步长为2.0
        'rsi_period': np.arange(7, 16, 2),             # 从7到20，步长为3
        'rsiValueThd': np.arange(26, 36, 2),          # 从10到50，步长为10
        'rsiRateUp': np.arange(1, 3, 1),         # 从0.5到5.0，步长为1.0
        'divergence_threshold': np.round(np.arange(0.04, 0.08, 0.02), 2) # 从0.03到0.1，步长为0.02
    }
   
   # 使用自定义参数网格和时间范围调用findGoodParam2
   findGoodParam(
       symbol = symbol,
       param_grid = custom_param_grid,
       statTime = '2022-03-10',
       endTime = '2025-03-10'
   )


def gangguxiaofeiETFParaFind():   

   symbol = "159843"
   custom_param_grid = {
        'short_window': np.arange(3, 6, 1),            # 从3到8，步长为2
        'long_window': np.arange(10, 20, 2),           # 从10到30，步长为5
        'volume_mavg_Value': np.arange(5, 15, 2),      # 从5到15，步长为5
        'MaRateUp': np.arange(1, 3, 0.5),          # 从0.5到1.5，步长为0.5
        'VolumeSellRate': np.arange(1.0, 6.0, 1),    # 从2.0到8.0，步长为2.0
        'rsi_period': np.arange(7, 16, 2),             # 从7到20，步长为3
        'rsiValueThd': np.arange(25, 35, 2),          # 从10到50，步长为10
        'rsiRateUp': np.arange(1, 3, 1),         # 从0.5到5.0，步长为1.0
        'divergence_threshold': np.round(np.arange(0.03, 0.09, 0.02), 2) # 从0.03到0.1，步长为0.02
    }
   
   # 使用自定义参数网格和时间范围调用findGoodParam2
   findGoodParam(
       symbol = symbol,
       param_grid = custom_param_grid,
       statTime = '2021-03-10',
       endTime = '2025-03-10'
   )



def testAuto(symbol):

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

    performance_stats = strategyFunc(
            filepath=filepath,
            symbol=symbol,
            short_window=params['short_window'], long_window=params['long_window'],
            volume_mavg_Value=params['volume_mavg_Value'], MaRateUp=params['MaRateUp'],
            VolumeSellRate=params['VolumeSellRate'], rsi_period=params['rsi_period'],
            rsiValueThd=params['rsiValueThd'], rsiRateUp=params['rsiRateUp'],
            divergence_threshold=params['divergence_threshold'],
            # 其他回测参数，保持与 testOnlyNew 一致
            initial_capital=10000.0, 
            commission=0.0003, 
            max_portfolio_allocation_pct=1,
            buy_increment_pct_of_initial_capital=1, 
            sell_decrement_pct_of_current_shares=1,
            min_shares_per_trade=100,
            # 设置时间范围，确保包含今天
            statTime = statTime, 
            endTime=get_beijing_time().strftime('%Y-%m-%d'),
            plot_results=2,  # 需要设置为True以生成图片
            verbose=True,
            enable_file_io=True
        )
    



    


if __name__ == "__main__":
   #testOnlyOk(symbol = "588180") #固定参数测试

   #testOnlyOk(symbol = "159915") #固定参数测试
   #testOnly1(symbol = "588180")
   #chuanyeETFParaFind()
   #kechuang50ETFParaFind()

   #testOnlyNew("588180")

   #testAuto(symbol = "159915")
   #testAuto(symbol = "588180")
   #ganggu30ETFParaFind()
   #testAuto(symbol = "513160") # 港股

   #testAuto(symbol = "513160") # 港股

   #gangguxiaofeiETFParaFind()
   testAuto(symbol = "159843") # 消费
