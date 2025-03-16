from data_fetcher import ETFFetcher
from data_manager import ETFStorage, save_data, show_tail_data

from config import ETFConfig, DATA_DIR, GPCODE


'''ETF 5 15 30 60 min, Day 周期数据获取'''
def ETFTest():
    exchange_prefix = GPCODE.split(".")[1].lower()
    symbol = f"{GPCODE.split('.')[0]}"
    print(f"----开始获取{symbol}_ETF分钟数据----------） ")

    # 初始化配置
    config = ETFConfig(stock_code=f"{symbol}")
    
    # 初始化组件
    fetcher = ETFFetcher(config)
    storage = ETFStorage(config)
    
    # 遍历所有周期 - min
    
    for period in config.periods:
        print(f"正在获取 {period} 分钟数据...")
        df = fetcher.fetch_minute_data(period)
        
        if not df.empty:
            new_count = storage.save_minute_data(df, period)
            print(f"成功保存 {period} 分钟数据，新增 {new_count} 条")
        else:
            print(f"未获取到 {config.stock_code} {period} 分钟数据")
    
    # daily 数据
    daily_df = fetcher.get_etf_dailyNew()
    
    # 处理数据保存
    if not daily_df.empty:
        #filename = f"{GPCODE}_dailynew.csv"
        filename = storage._get_filepath("Day_24Hour")
        save_data(daily_df, filename)
        show_tail_data(daily_df)
    else:
        print("未获取到有效数据，请检查：")

if __name__ == "__main__":
    ETFTest()



