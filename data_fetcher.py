import akshare as ak
import pandas as pd
import requests
import json
from tenacity import retry, stop_after_attempt, wait_exponential
from config import ETFConfig


def _convert_code_to_sina(code: str) -> str:
    """
    将 ETF 代码转换为新浪接口格式
    输入: "159843" 或 "159843.SH" 或 "510050"
    输出: "sz159843" 或 "sh510050"
    """
    # 去掉后缀如 .SH, .SZ
    code = str(code).split(".")[0].strip()
    code = code.zfill(6)
    
    # 根据代码判断市场
    # 5/6开头 -> 上海, 0/1/3开头 -> 深圳
    if code.startswith("5") or code.startswith("6"):
        return f"sh{code}"
    else:
        return f"sz{code}"


def _sina_etf_daily_hist(code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    通过新浪接口获取 ETF 历史日线数据（更稳定，不走代理）
    
    参数:
        code: ETF 代码，如 "159843" 或 "510050"
        start_date: 开始日期，格式 "YYYYMMDD"（可选）
        end_date: 结束日期，格式 "YYYYMMDD"（可选）
    
    返回:
        DataFrame，包含 日期/开盘/收盘/最高/最低/成交量 等字段
    """
    sina_code = _convert_code_to_sina(code)
    
    # 新浪历史 K 线接口
    # scale=240 表示日线，datalen 表示获取多少条数据
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {
        "symbol": sina_code,
        "scale": 240,  # 日线
        "ma": "no",
        "datalen": 1000,  # 获取最近1000个交易日数据
    }
    
    headers = {
        "Referer": "http://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.encoding = "utf-8"
        
        # 解析 JSON 数据
        data = json.loads(resp.text)
        
        if not data:
            return pd.DataFrame()
        
        # 转换为 DataFrame
        df = pd.DataFrame(data)
        
        # 重命名列: day -> 日期, open -> 开盘, high -> 最高, low -> 最低, close -> 收盘, volume -> 成交量
        df = df.rename(columns={
            "day": "日期",
            "open": "开盘",
            "high": "最高",
            "low": "最低",
            "close": "收盘",
            "volume": "成交量",
        })
        
        # 转换数据类型
        for col in ["开盘", "最高", "最低", "收盘"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "成交量" in df.columns:
            df["成交量"] = pd.to_numeric(df["成交量"], errors="coerce")
        
        # 日期过滤
        if start_date:
            start_date_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            df = df[df["日期"] >= start_date_fmt]
        if end_date:
            end_date_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
            df = df[df["日期"] <= end_date_fmt]
        
        return df.reset_index(drop=True)
        
    except Exception as e:
        print(f"[新浪接口] {code} 历史数据获取失败: {e}")
        return pd.DataFrame()

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

    def _fetch_etf_daily_raw(self, symbol, period, start_date, end_date, adjust):
        """
        东方财富接口请求（无内置重试，由调用方控制重试逻辑）
        """
        return ak.fund_etf_hist_em(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust
        )

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
        """获取ETF日线数据
        优先使用东方财富接口（重试1次），失败后使用新浪接口备用
        """
        import time
        
        start_date = f"{self.config.start_date.split()[0].replace('-', '')}"
        end_date = f"{self.config.end_time.split()[0].replace('-', '')}"
        
        # ===== 方案1: 优先使用东方财富接口（重试1次） =====
        max_retries = 2
        for attempt in range(max_retries):
            try:
                if attempt == 0:
                    print(f"[东方财富接口] 尝试获取 {self.config.stock_code} 日线数据...")
                else:
                    print(f"[东方财富接口] 第 {attempt + 1} 次重试...")
                
                df = self._fetch_etf_daily_raw(
                    symbol=f"{self.config.stock_code}",
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust=""
                )
                if df is not None and not df.empty:
                    print(f"[东方财富接口] {self.config.stock_code} 日线数据获取成功，共 {len(df)} 条")
                    return self._process_raw_dataDaily(df)
            except Exception as e:
                print(f"[东方财富接口] {self.config.stock_code} 获取失败: {e}")
                if attempt < max_retries - 1:
                    wait_time = 5 * (attempt + 1)  # 5秒, 10秒
                    print(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
        
        # ===== 方案2: 新浪接口备用 =====
        try:
            print(f"[新浪接口] 东方财富接口失败，切换到备用新浪接口...")
            df = _sina_etf_daily_hist(self.config.stock_code, start_date, end_date)
            if df is not None and not df.empty:
                print(f"[新浪接口] {self.config.stock_code} 日线数据获取成功，共 {len(df)} 条")
                return self._process_raw_dataDaily(df)
        except Exception as e:
            print(f"[新浪接口] {self.config.stock_code} 也失败: {e}")
        
        print(f"ETF日线数据获取失败：所有接口均不可用")
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
        
        # 如果没有换手率字段，添加 NaN 表示缺失（新浪接口不返回换手率）
        if "ChangeRate" not in processed_df.columns:
            processed_df["ChangeRate"] = None  # pandas 会自动转换为 NaN
        
        # 指定列顺序（固定前5列顺序，保留其他字段）
        base_columns = ['DateTime', 'OpenValue', 'CloseValue', 'HighValue', 'LowValue', 'Volume', 'ChangeRate']
        # 只保留存在的列
        existing_base_columns = [col for col in base_columns if col in processed_df.columns]
        other_columns = [col for col in processed_df.columns if col not in base_columns]
        
        return processed_df[existing_base_columns + other_columns].sort_values("DateTime") 

    