import akshare as ak
import pandas as pd
import os
from datetime import datetime

def get_etf_minute_data(stock_code, period, start_date):
    """
    获取ETF分时数据
    :param stock_code: ETF代码（带交易所后缀，如510050.SH）
    :param period: 分时周期 ('5', '15', '30', '60')
    :param start_date: 开始日期（格式：'YYYY-MM-DD'）
    :return: 分时数据DataFrame
    """
    try:
        # 转换代码格式
        #exchange = stock_code.split(".")[1].lower()
        symbol = f"{stock_code}"
        print(symbol)
        # 设置时间范围
        end_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(end_date)
        # 获取数据
        df = ak.fund_etf_hist_min_em(
            symbol=f"{stock_code}",
            period=f"{period}",
            adjust="",
            start_date=f"{start_date}",
            end_date="2025-03-14 17:40:00"
            #end_date=f"{end_date}"
        )

        #ak.fund_etf_hist_min_em(symbol="561560", period="30", adjust="", start_date="2025-01-20 09:30:00", end_date="2025-02-27 17:40:00")

        # 统一字段命名
        df = df.rename(columns={
            "时间": "datetime",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount"
        })
        return df

    except Exception as e:
        print(f"{stock_code} {period}分钟数据获取失败: {str(e)}")
        return pd.DataFrame()

def save_minute_data(df, stock_code, period, data_dir):
    """
    保存分时数据到CSV（增量更新）
    :param df: 新获取的数据
    :param stock_code: ETF代码
    :param period: 分时周期
    :param data_dir: 数据存储根目录
    """
    if df.empty:
        return

    # 创建存储目录
    symbol_dir = os.path.join(data_dir, stock_code)
    os.makedirs(symbol_dir, exist_ok=True)

    # 设置文件路径
    filename = f"{stock_code}_{period}min.csv"
    filepath = os.path.join(symbol_dir, filename)

    # 处理已有数据
    if os.path.exists(filepath):
        existing_df = pd.read_csv(filepath, parse_dates=['datetime'])
        merged_df = pd.concat([existing_df, df]).drop_duplicates('datetime')
    else:
        merged_df = df

    # 排序并保存
    merged_df.sort_values('datetime').to_csv(filepath, index=False)
    print(f"{stock_code} {period}分钟数据已保存至 {filename}（新增{len(df)}条）")

if __name__ == "__main__":
    # 配置参数
    config = {
        "stock_code": "561560",  # ETF代码（必须带交易所后缀）
        "periods": ['5'],  # 需要获取的周期
        "start_date": "2025-01-20 09:30:00",  # 最早数据日期
        "data_dir": "./stock_dataTest"  # 数据存储目录
    }

    # 创建数据目录
    os.makedirs(config["data_dir"], exist_ok=True)

    # 遍历所有周期
    for period in config["periods"]:
        # 获取数据
        print(f"------------time is {period} start")
        df = get_etf_minute_data(
            stock_code=config["stock_code"],
            period=period,
            start_date=config["start_date"]
        )
        #print(df)
        print(f"------------time is {period} end------------")


        # 保存数据
        if not df.empty:
            save_minute_data(
                df=df,
                stock_code=config["stock_code"],
                period=period,
                data_dir=config["data_dir"]
            )
        else:
            print(f"未获取到 {config['stock_code']} {period}分钟数据")

    print("所有分时数据更新完成")