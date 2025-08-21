from data_fetcher import ETFFetcher
from data_manager import ETFStorage
from config import ETFConfig


'''ETF 5 15 30 60 min, Day 周期数据获取'''
def ETFTest(code):
    exchange_prefix = code.split(".")[1].lower()
    symbol = f"{code.split('.')[0]}"
    print(f"----开始获取{symbol}_ETF分钟数据----------） ")

    # 初始化配置
    config = ETFConfig(stock_code=f"{symbol}",periods=['120'])
    
    # 初始化组件
    fetcher = ETFFetcher(config)
    storage = ETFStorage(config)
    
    # 遍历所有周期 - min
    for period in config.periods:
        print(f"正在获取 {period} 分钟数据...")
        df = fetcher.fetch_minute_data(period)
        
        if not df.empty:
            filepath = storage._get_filepath(period)
            print(f"path is {filepath}")
            new_count = storage.saveDataToFile(df, filepath)
            print(f"成功保存 {period} 分钟数据，新增 {new_count} 条")
        else:
            print(f"未获取到 {config.stock_code} {period} 分钟数据")
    
    # daily 数据
    daily_df = fetcher.get_etf_dailyNew()
    # 处理数据保存
    if not daily_df.empty:
        filepath = storage._get_filepath("Day")
        print(f"path is {filepath}")
        cnt = storage.saveDataToFile(daily_df, filepath)
        print(f"成功保存日线数据，新增 {cnt} 条")
    else:
        print(f"未获取到 {config.stock_code} 日线数据")

if __name__ == "__main__":
    #case1 A股的电力ETF m'KeyboardInterrupt
    #ETFTest("561560.SH")
    #ETFTest("588180.SH")
    #ETFTest("513160.SH")
    #ETFTest("518880.SH") ##黄金
    #ETFTest("159915.SH") ##创业
    #ETFTest("513160.SH") #港股科技
    #ETFTest("511090.SH") #国债
    ETFTest("159843.SH") #国债



