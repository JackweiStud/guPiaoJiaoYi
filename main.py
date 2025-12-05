import time
from data_fetcher import ETFFetcher
from data_manager import ETFStorage
from config import ETFConfig


'''ETF 5 15 30 60 min, Day 周期数据获取'''
def ETFTest(code):
    exchange_prefix = code.split(".")[1].lower()
    symbol = f"{code.split('.')[0]}"
    #print(f"----开始获取{symbol}_ETF分钟数据----------） ")

    # 初始化配置
    config = ETFConfig(stock_code=f"{symbol}",periods=['120'])
    
    # 初始化组件
    fetcher = ETFFetcher(config)
    storage = ETFStorage(config)
    
    # 遍历所有周期 - min
    # for period in config.periods:
    #     print(f"正在获取 {period} 分钟数据...")
    #     df = fetcher.fetch_minute_data(period)
    #     
    #     if not df.empty:
    #         filepath = storage._get_filepath(period)
    #         print(f"path is {filepath}")
    #         new_count = storage.saveDataToFile(df, filepath)
    #         print(f"成功保存 {period} 分钟数据，新增 {new_count} 条")
    #     else:
    #         print(f"未获取到 {config.stock_code} {period} 分钟数据")
    
    # daily 数据
    daily_df = fetcher.get_etf_dailyNew()
    # 处理数据保存
    if not daily_df.empty:
        filepath = storage._get_filepath("Day")
        print(f"path is {filepath}")
        cnt = storage.saveDataToFile(daily_df, filepath)
        print(f"成功保存日线数据，新增 {cnt} 条")
        return True
    else:
        print(f"未获取到 {config.stock_code} 日线数据")
        return False


if __name__ == "__main__":
    # 要批量获取日线数据的 ETF 列表
    etf_codes = [
        "561560.SH",  # A股电力ETF
        "588180.SH",
        "513160.SH",
        "518880.SH",  # 黄金
        "159915.SH",  # 创业
        "513160.SH",  # 港股科技
        "511090.SH",  # 国债
        "159843.SH",  # 食品饮料
        "512820.SH",  # 银行
        "161128.SH",  ##美股


    ]



    max_attempts_per_code = 3      # 每个代码最多尝试 3 次
    retry_delay_seconds = 15       # 同一代码失败后的重试间隔

    for idx, code in enumerate(etf_codes):
        for attempt in range(1, max_attempts_per_code + 1):
            print(f"\n==== 开始获取 {code} 日线数据，第 {attempt} 次尝试 ====")
            success = ETFTest(code)
            if success:
                break

            # 本次尝试失败，且还可以重试
            if attempt < max_attempts_per_code:
                print(f"{code} 第 {attempt} 次尝试未成功，{retry_delay_seconds} 秒后将重试...")
                time.sleep(retry_delay_seconds)
            else:
                print(f"{code} 在连续 {max_attempts_per_code} 次尝试后仍未成功获取日线数据。")

        # 不同代码之间仍保留一个短间隔，避免瞬时请求过密
        if idx != len(etf_codes) - 1:
            time.sleep(1)
