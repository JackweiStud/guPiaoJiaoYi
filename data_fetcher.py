import akshare as ak
import pandas as pd
from config import ETFConfig, DATA_DIR, GPCODE  # Combined into single import

class ETFFetcher:
    def __init__(self, config: ETFConfig):
        self.config = config
        
    def fetch_minute_data(self, period):
        """获取单周期分时数据"""
        # 设置时间范围
       
        try:
            print(f"Fetching minute data for symbol: {self.config.stock_code}, period: {period}, start date: {self.config.start_date}, end date: {self.config.end_time}")
            #etching minute data for symbol: 561560, period: 5, start date: 2025-01-01 09:30:00, end date: 2025-03-15 13:22:15
            df = ak.fund_etf_hist_min_em(
                symbol=f"{self.config.stock_code}",
                period=str(period),
                adjust="",
                start_date=f"{self.config.start_date}",
                end_date=f"{self.config.end_time}",
            )
            #print(df.head())  # 打印返回的数据框
            return self._etf_min_format_data(df)
        except Exception as e:
            self._log_error(period, e)
            return pd.DataFrame()

    def _etf_min_format_data(self, df):
        """统一数据格式"""
        return df.rename(columns={
            "时间": "DateTime",
            "开盘": "OpenValue",
            "收盘": "CloseValue",
            "最高": "HighValue",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount"
        }).sort_values("DateTime") 

        #DateTime,OpenValue,HighValue,LowValue,CloseValue,volume

    def _log_error(self, period, error):
        print(f"[Error] {self.config.stock_code} {period}分钟数据获取失败: {str(error)}")

    


    def get_etf_dailyNew(self):
        """获取ETF日线数据（新接口）"""
        try:
            # 使用akshare新接口获取数据
            start_date=f"{self.config.start_date.split()[0].replace('-', '')}"
            end_date=f"{self.config.end_time.split()[0].replace('-', '')}"

            print(f"正在请求ETF日线数据，参数: symbol={self.config.stock_code}, period=daily, "
                  f"start_date={start_date}, end_date={end_date}")

            df = ak.fund_etf_hist_em(
                symbol=f"{self.config.stock_code}",
                period="daily",
                start_date=f"{start_date}",
                end_date=f"{end_date}",
                adjust=""
            )
            return self._process_raw_dataDaily(df)
        except Exception as e:
            print(f"ETF日线数据获取失败：{str(e)}")
            return pd.DataFrame()

    def _process_raw_dataDaily(self, df):
        if df.empty:
            return df
        return df.rename(columns={
            "日期": "DateTime",
            "开盘": "OpenValue",
            "最高": "HighValue",
            "最低": "LowValue",
            "收盘": "CloseValue",
            "成交量": "volume"

        }).sort_values("DateTime") 

    