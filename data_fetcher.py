import akshare as ak
import pandas as pd
from config import ETFConfig

class ETFFetcher:
    def __init__(self, config: ETFConfig):
        self.config = config
        
    def fetch_minute_data(self, period):
        """获取单周期分时数据"""
        # 设置时间范围
       
        try:
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
            print(f"[Error] {self.config.stock_code} {period}分钟数据获取失败: {str(e)}")
            return pd.DataFrame()

    def _etf_min_format_data(self, df):
        """统一数据格式"""
        processed_df = df.rename(columns={
            "时间": "DateTime",
            "开盘": "OpenValue",
            "收盘": "CloseValue",
            "最高": "HighValue",
            "最低": "LowValue",
            "成交量": "Volume",
            "成交额": "amount",
            "换手率": "ChangeRate"
        }).sort_values("DateTime") 
         # 指定列顺序（固定前5列顺序，保留其他字段）
        base_columns = ['DateTime', 'OpenValue', 'CloseValue', 'HighValue', 'LowValue', 'Volume', 'ChangeRate']
        other_columns = [col for col in processed_df.columns if col not in base_columns]
        
        return processed_df[base_columns + other_columns].sort_values("DateTime") 

    def get_etf_dailyNew(self):
        """获取ETF日线数据（新接口）"""
        try:
            # 使用akshare新接口获取数据 20200930格式
            start_date=f"{self.config.start_date.split()[0].replace('-', '')}"
            end_date=f"{self.config.end_time.split()[0].replace('-', '')}"

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
        
        # 重命名字段
        processed_df = df.rename(columns={
            "日期": "DateTime",
            "开盘": "OpenValue",
            "最高": "HighValue",
            "最低": "LowValue",
            "收盘": "CloseValue",
            "成交量": "Volume",
            "换手率": "ChangeRate"
        })
        
        # 指定列顺序（固定前5列顺序，保留其他字段）
        base_columns = ['DateTime', 'OpenValue', 'CloseValue', 'HighValue', 'LowValue', 'Volume', 'ChangeRate']
        other_columns = [col for col in processed_df.columns if col not in base_columns]
        
        return processed_df[base_columns + other_columns].sort_values("DateTime") 

    