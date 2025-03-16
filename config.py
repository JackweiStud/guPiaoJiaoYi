# 配置参数统一管理

from pathlib import Path
from datetime import datetime
import os


#数据存储目录（相对于项目根目录）
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "stock_data"
START_TIME = "2024-09-20 09:30:00"

class ETFConfig:
    DEFAULT_PERIODS = ['5', '15', '30', '60']
    dataPath = Path(DATA_DIR)
    startTime = START_TIME
    
    def __init__(self, stock_code="561560", periods=None, start_date=None):
        self.stock_code = stock_code
        self.periods = periods or self.DEFAULT_PERIODS
        self.start_date = start_date or self.startTime
        self.data_dir = self.dataPath
        self.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 初始化目录
        self.data_dir.mkdir(exist_ok=True)

