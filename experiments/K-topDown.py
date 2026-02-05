import pandas as pd
import numpy as np
from pathlib import Path
   



class ETFDataLoader:
    def __init__(self):
        pass  # 不再需要初始化数据目录

    def load_etf_data(
        self,
        file_path: str,
        required_columns: list = ["DateTime", "OpenValue", "CloseValue", "HighValue", "LowValue", "Volume", "ChangeRate"]
    ) -> pd.DataFrame:
        """
        加载ETF数据
        :param file_path: 完整文件路径 如"D:/data/588000_Day.csv"
        """
        path_obj = Path(file_path)

        if not path_obj.exists():
            raise FileNotFoundError(f"数据文件不存在: {path_obj}")

        df = pd.read_csv(path_obj, parse_dates=['DateTime'])

        # 验证必要列
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"数据文件缺少必要列: {missing_cols}")

        return df[required_columns]


def process_klines(df):
    """
    处理K线包含关系并识别分型
    
    参数:
    df (pandas.DataFrame): 包含OHLCV数据的DataFrame，
                          需要包含 DateTime, OpenValue, CloseValue, HighValue, LowValue, Volume 列
    
    返回:
    pandas.DataFrame: 处理后的K线数据
    list: 顶分型列表 [(index, datetime, price), ...]
    list: 底分型列表 [(index, datetime, price), ...]
    """
    # 复制原始数据，防止修改原始数据
    processed_df = df.copy()
    
    # 判断初始方向（根据前两根K线）
    if len(processed_df) < 2:
        return processed_df, [], []
    
    # 判断第一根和第二根K线的实体方向
    first_candle = processed_df.iloc[0]
    second_candle = processed_df.iloc[1]
    first_is_up = first_candle['CloseValue'] > first_candle['OpenValue']
    second_is_up = second_candle['CloseValue'] > second_candle['OpenValue']
    
    # 初始方向判定
    if first_is_up and second_is_up:
        trend = "up"  # 上涨趋势
    elif not first_is_up and not second_is_up:
        trend = "down"  # 下跌趋势
    else:
        # 如果一阳一阴，根据第二根K线决定
        trend = "up" if second_is_up else "down"
    
    # 创建新的DataFrame来存储处理后的K线
    merged_df = pd.DataFrame(columns=processed_df.columns)
    merged_df.loc[0] = processed_df.iloc[0]  # 第一根K线保持不变
    # 包含处理
    merged_idx = 0
    for i in range(1, len(processed_df)):
        curr_candle = processed_df.iloc[i]
        
        # 检查是否有足够大的跳空（≥3%）
        prev_merged = merged_df.iloc[merged_idx]
        gap_ratio = 0
        
        if trend == "up":
            # 上涨中的向上跳空
            gap_ratio = (curr_candle['LowValue'] - prev_merged['HighValue']) / prev_merged['HighValue']
        else:
            # 下跌中的向下跳空
            gap_ratio = (prev_merged['LowValue'] - curr_candle['HighValue']) / prev_merged['LowValue']
        
        # 如果有明显跳空，保留原始K线
        if gap_ratio >= 0.03:  # 3%的跳空
            merged_idx += 1
            merged_df.loc[merged_idx] = curr_candle
            # 跳空后可能改变趋势方向
            if trend == "up" and gap_ratio < 0:
                trend = "down"
            elif trend == "down" and gap_ratio > 0:
                trend = "up"
            continue
        
        # 包含关系处理
        is_contain = False
        new_candle = prev_merged.copy()
        
        if trend == "up":
            # 上涨处理
            if (curr_candle['HighValue'] >= prev_merged['HighValue'] or 
                curr_candle['LowValue'] >= prev_merged['LowValue']):
                is_contain = True
                new_candle['HighValue'] = max(curr_candle['HighValue'], prev_merged['HighValue'])
                new_candle['LowValue'] = max(curr_candle['LowValue'], prev_merged['LowValue'])
                # 更新开盘收盘价
                if curr_candle['CloseValue'] > prev_merged['CloseValue']:
                    new_candle['CloseValue'] = curr_candle['CloseValue']
                if curr_candle['OpenValue'] > prev_merged['OpenValue']:
                    new_candle['OpenValue'] = curr_candle['OpenValue']
        else:
            # 下跌处理
            if (curr_candle['HighValue'] <= prev_merged['HighValue'] or 
                curr_candle['LowValue'] <= prev_merged['LowValue']):
                is_contain = True
                new_candle['HighValue'] = min(curr_candle['HighValue'], prev_merged['HighValue'])
                new_candle['LowValue'] = min(curr_candle['LowValue'], prev_merged['LowValue'])
                # 更新开盘收盘价
                if curr_candle['CloseValue'] < prev_merged['CloseValue']:
                    new_candle['CloseValue'] = curr_candle['CloseValue']
                if curr_candle['OpenValue'] < prev_merged['OpenValue']:
                    new_candle['OpenValue'] = curr_candle['OpenValue']
        
        # 更新K线
        if is_contain:
            # 包含关系，更新当前合并K线
            merged_df.iloc[merged_idx] = new_candle
            # 更新成交量为两者之和
            merged_df.at[merged_idx, 'Volume'] += curr_candle['Volume']
            # 保留最新日期
            merged_df.at[merged_idx, 'DateTime'] = curr_candle['DateTime']
        else:
            # 非包含关系，添加新K线
            merged_idx += 1
            merged_df.loc[merged_idx] = curr_candle
            
            # 检查是否需要转变趋势
            prev_merged = merged_df.iloc[merged_idx-1]
            curr_merged = merged_df.iloc[merged_idx]
            
            if trend == "up" and curr_merged['LowValue'] < prev_merged['LowValue']:
                trend = "down"
            elif trend == "down" and curr_merged['HighValue'] > prev_merged['HighValue']:
                trend = "up"
    
    # 重置索引
    merged_df = merged_df.reset_index(drop=True)
    
    # 分型验证
    top_patterns = []  # 顶分型列表
    bottom_patterns = []  # 底分型列表
    
    for i in range(1, len(merged_df) - 1):
        prev_k = merged_df.iloc[i-1]
        curr_k = merged_df.iloc[i]
        next_k = merged_df.iloc[i+1]
        
        # 顶分型判断
        if (curr_k['HighValue'] > prev_k['HighValue'] and 
            curr_k['HighValue'] > next_k['HighValue'] and 
            curr_k['LowValue'] > prev_k['LowValue'] and 
            curr_k['LowValue'] > next_k['LowValue']):
            top_patterns.append((i, curr_k['DateTime'], curr_k['HighValue']))
        
        # 底分型判断
        if (curr_k['LowValue'] < prev_k['LowValue'] and 
            curr_k['LowValue'] < next_k['LowValue'] and 
            curr_k['HighValue'] < prev_k['HighValue'] and 
            curr_k['HighValue'] < next_k['HighValue']):
            bottom_patterns.append((i, curr_k['DateTime'], curr_k['LowValue']))
    
    # 过滤条件：分型间隔≥5根K线且波动≥1.5%
    filtered_tops = []
    filtered_bottoms = []
    
    if len(top_patterns) > 0:
        filtered_tops.append(top_patterns[0])
        
        for i in range(1, len(top_patterns)):
            prev_idx, prev_date, prev_price = filtered_tops[-1]
            curr_idx, curr_date, curr_price = top_patterns[i]
            
            # 检查间隔是否≥5根K线
            if curr_idx - prev_idx >= 5:
                # 检查波动是否≥1.5%
                price_change = abs(curr_price - prev_price) / min(curr_price, prev_price)
                if price_change >= 0.015:  # 1.5%
                    filtered_tops.append(top_patterns[i])
    
    if len(bottom_patterns) > 0:
        filtered_bottoms.append(bottom_patterns[0])
        
        for i in range(1, len(bottom_patterns)):
            prev_idx, prev_date, prev_price = filtered_bottoms[-1]
            curr_idx, curr_date, curr_price = bottom_patterns[i]
            
            # 检查间隔是否≥5根K线
            if curr_idx - prev_idx >= 5:
                # 检查波动是否≥1.5%
                price_change = abs(curr_price - prev_price) / min(curr_price, prev_price)
                if price_change >= 0.015:  # 1.5%
                    filtered_bottoms.append(bottom_patterns[i])
    
    return merged_df, filtered_tops, filtered_bottoms

# 示例使用:
if __name__ == "__main__":
    # 假设 df 是包含OHLCV数据的DataFrame
    # 例如从CSV文件读取:
    # df = pd.read_csv('stock_data.csv')
    
    # 示例DataFrame创建
    data = {
        'DateTime': pd.date_range(start='2024-12-01', periods=20),
        'OpenValue': [0.65, 0.658, 0.656, 0.643, 0.648, 0.656, 0.682, 0.651, 0.65, 0.651,
                      0.641, 0.632, 0.624, 0.627, 0.638, 0.653, 0.646, 0.658, 0.656, 0.662],
        'CloseValue': [0.657, 0.649, 0.646, 0.648, 0.655, 0.649, 0.654, 0.652, 0.653, 0.641,
                       0.629, 0.625, 0.635, 0.641, 0.652, 0.646, 0.654, 0.656, 0.662, 0.659],
        'HighValue': [0.661, 0.66, 0.665, 0.651, 0.663, 0.657, 0.684, 0.657, 0.656, 0.652,
                      0.641, 0.635, 0.636, 0.644, 0.661, 0.662, 0.656, 0.662, 0.666, 0.675],
        'LowValue': [0.648, 0.644, 0.643, 0.642, 0.643, 0.644, 0.651, 0.65, 0.646, 0.639,
                     0.628, 0.624, 0.624, 0.625, 0.638, 0.644, 0.641, 0.652, 0.653, 0.657],
        'Volume': [807779, 1115615, 771535, 494284, 1031512, 461245, 1390842, 577091, 651725, 791610,
                  559065, 1020070, 648114, 739071, 1278075, 767816, 655081, 772554, 826443, 891653]
    }

    code = "588180"
    dataPath = f"/content/drive/MyDrive/guPiaoJiaoYi/guPiaoJiaoYi/stock_data/{code}/{code}_Day.csv"
    print(dataPath)

    # 2. 加载数据
    loader = ETFDataLoader()
    df = loader.load_etf_data(file_path=dataPath)

    
    #df = pd.DataFrame(data)
    
    # 处理K线并识别分型
    processed_klines, top_patterns, bottom_patterns = process_klines(df)
    
    print("处理后的K线数量:", len(processed_klines))
    print("\n顶分型:")
    for idx, date, price in top_patterns:
        print(f"索引: {idx}, 日期: {date}, 价格: {price}")
    
    print("\n底分型:")
    for idx, date, price in bottom_patterns:
        print(f"索引: {idx}, 日期: {date}, 价格: {price}")
    
    