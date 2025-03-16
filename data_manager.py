import os
import pandas as pd
from pathlib import Path
from config import ETFConfig

class ETFStorage:
    def __init__(self, config: ETFConfig):
        self.config = config
        
    def saveDataToFile(self, df, filepath):
        """保存分时数据"""
        if df.empty:
            return 0
            
        merged_df = self._merge_data(df, filepath) 
        merged_df.sort_values('DateTime').to_csv(filepath, index=False)
        return len(df)


    def _get_filepath(self, period):
        """生成文件路径"""
        symbol_dir = self.config.data_dir / self.config.stock_code
        symbol_dir.mkdir(exist_ok=True)
        return symbol_dir / f"{self.config.stock_code}_{period}.csv"

    def _merge_data(self, new_df, filepath):
        """合并新旧数据（优化合并版）"""
        if filepath.exists():
            existing_df = pd.read_csv(filepath, parse_dates=['DateTime'])
            # 调用统一合并方法
            return self._merge_dataframes(existing_df, new_df)
        return new_df

    def _merge_dataframes(self, existing_df, new_df):
        """统一的数据合并方法"""
        # 统一处理日期列
        date_col = 'DateTime'
        
        # 转换日期格式
        existing_df[date_col] = pd.to_datetime(existing_df[date_col], errors='coerce')
        new_df[date_col] = pd.to_datetime(new_df[date_col], errors='coerce')

        # 清理无效数据
        existing_clean = existing_df.dropna(subset=[date_col])
        new_clean = new_df.dropna(subset=[date_col])

        # 合并数据集
        merged = pd.concat([existing_clean, new_clean])
        
        # 去重并保留最新数据
        merged = merged.sort_values(date_col)
        merged = merged.drop_duplicates(date_col, keep='last')

        return merged