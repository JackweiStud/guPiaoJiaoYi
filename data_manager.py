import os
import pandas as pd
from pathlib import Path

from config import DATA_DIR, GPCODE
from config import ETFConfig


def save_data(new_df, filename):
    """数据保存主逻辑"""
    filepath = os.path.join(DATA_DIR, filename)
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(filepath):
        existing_df = pd.read_csv(filepath, parse_dates=['DateTime'])
        merged_df = _merge_data(existing_df, new_df)
        merged_df.to_csv(filepath, index=False)
        print(f"数据增量更新完成，新增{len(new_df)-len(merged_df)+len(existing_df)}条")
    else:
        new_df.to_csv(filepath, index=False)
        print(f"新ETF数据已保存：{filename}")


def _merge_data(existing_df, new_df):
    print("合并新旧数据")
    
    # 确保 DateTime 列为 datetime 类型
    existing_df['DateTime'] = pd.to_datetime(existing_df['DateTime'], errors='coerce')
    new_df['DateTime'] = pd.to_datetime(new_df['DateTime'], errors='coerce')
    
    # 删除无效日期
    existing_df = existing_df.dropna(subset=['DateTime'])
    new_df = new_df.dropna(subset=['DateTime'])
    
    # 合并数据
    merged = pd.concat([existing_df, new_df])
    
    # 排序并去重
    merged = merged.sort_values("DateTime")          # 按日期重新排序
    merged = merged.drop_duplicates("DateTime", keep="last")  # 保留最新数据
    
    return merged


def show_tail_data(df, lines=5):
    """显示数据尾部"""
    print("\n最新5条数据：")
    print(df.tail(lines))


class ETFStorage:
    def __init__(self, config: ETFConfig):
        self.config = config
        
    def save_minute_data(self, df, period):
        """保存分时数据"""
        if df.empty:
            return 0
            
        filepath = self._get_filepath(period)
        merged_df = self._merge_data(df, filepath)
        
        merged_df.sort_values('DateTime').to_csv(filepath, index=False)
        return len(df)

    def _get_filepath(self, period):
        """生成文件路径"""
        symbol_dir = self.config.data_dir / self.config.stock_code
        symbol_dir.mkdir(exist_ok=True)
        return symbol_dir / f"{self.config.stock_code}_{period}min.csv"

    def _merge_data(self, new_df, filepath):
        """合并新旧数据"""
        if filepath.exists():
            existing_df = pd.read_csv(filepath, parse_dates=['DateTime'])
            
            # 确保 DateTime 列为 datetime 类型
            existing_df['DateTime'] = pd.to_datetime(existing_df['DateTime'], errors='coerce')
            new_df['DateTime'] = pd.to_datetime(new_df['DateTime'], errors='coerce')
            
            # 删除无效日期
            existing_df = existing_df.dropna(subset=['DateTime'])
            new_df = new_df.dropna(subset=['DateTime'])
            
            # 合并数据
            merged = pd.concat([existing_df, new_df])
            
            # 排序并去重
            merged = merged.sort_values("DateTime")          # 按日期重新排序
            merged = merged.drop_duplicates("DateTime", keep="last")  # 保留最新数据
            
            return merged
        return new_df 