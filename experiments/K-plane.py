!pip install mplcursors

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import numpy as np
import mplcursors

from pathlib import Path
   



class ETFDataLoader:
    def __init__(self):
        pass  # 不再需要初始化数据目录

    def load_etf_data(
        self,
        file_path: str,
        required_columns: list = ["DateTime", "OpenValue", "CloseValue", "HighValue", "LowValue", "Volume", "ChangeRate"]
    ) -> pd.DataFrame:
        """
        加载ETF数据
        :param file_path: 完整文件路径 如"D:/data/588000_Day.csv"
        """
        path_obj = Path(file_path)

        if not path_obj.exists():
            raise FileNotFoundError(f"数据文件不存在: {path_obj}")

        df = pd.read_csv(path_obj, parse_dates=['DateTime'])

        # 验证必要列
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"数据文件缺少必要列: {missing_cols}")

        return df[required_columns]




# 创建DataFrame
data = {
    'DateTime': pd.date_range(start='2024-12-01', periods=20),
    'OpenValue': [0.65, 0.658, 0.656, 0.643, 0.648, 0.656, 0.682, 0.651, 0.65, 0.651,
                  0.641, 0.632, 0.624, 0.627, 0.638, 0.653, 0.646, 0.658, 0.656, 0.662],
    'CloseValue': [0.657, 0.649, 0.646, 0.648, 0.655, 0.649, 0.654, 0.652, 0.653, 0.641,
                   0.629, 0.625, 0.635, 0.641, 0.652, 0.646, 0.654, 0.656, 0.662, 0.659],
    'HighValue': [0.661, 0.66, 0.665, 0.651, 0.663, 0.657, 0.684, 0.657, 0.656, 0.652,
                  0.641, 0.635, 0.636, 0.644, 0.661, 0.662, 0.656, 0.662, 0.666, 0.675],
    'LowValue': [0.648, 0.644, 0.643, 0.642, 0.643, 0.644, 0.651, 0.65, 0.646, 0.639,
                 0.628, 0.624, 0.624, 0.625, 0.638, 0.644, 0.641, 0.652, 0.653, 0.657],
    'Volume': [807779, 1115615, 771535, 494284, 1031512, 461245, 1390842, 577091, 651725, 791610,
              559065, 1020070, 648114, 739071, 1278075, 767816, 655081, 772554, 826443, 891653]
}

#df = pd.DataFrame(data)
code = "588180"
dataPath = f"/content/drive/MyDrive/guPiaoJiaoYi/guPiaoJiaoYi/stock_data/{code}/{code}_Day.csv"
print(dataPath)

# 2. 加载数据
loader = ETFDataLoader()
df = loader.load_etf_data(file_path=dataPath)


# 设置日期为索引
df.set_index('DateTime', inplace=True)

# 计算上涨和下跌
df['Status'] = df['CloseValue'] >= df['OpenValue']  # True为上涨，False为下跌
# 计算涨跌幅
df['Change'] = ((df['CloseValue'] - df['OpenValue']) / df['OpenValue'] * 100).round(2)

# 创建图表
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
fig.subplots_adjust(hspace=0)

# K线图
# 设置颜色
up_color = 'red'
down_color = 'green'

# 存储K线和成交量柱状图的引用，用于鼠标悬停
candles = []
volume_bars = []

# 绘制K线图
for i in range(len(df)):
    # 获取当前数据点
    date = df.index[i]
    status = df['Status'].iloc[i]
    open_price = df['OpenValue'].iloc[i]
    close_price = df['CloseValue'].iloc[i]
    high_price = df['HighValue'].iloc[i]
    low_price = df['LowValue'].iloc[i]
    change = df['Change'].iloc[i]
    
    # 设置颜色
    color = up_color if status else down_color
    
    # 绘制实体
    rect_height = abs(close_price - open_price)
    rect_bottom = min(close_price, open_price)
    rect = Rectangle(
        xy=(i-0.4, rect_bottom),
        width=0.8,
        height=rect_height,
        facecolor=color,
        edgecolor=color,
        alpha=0.8
    )
    ax1.add_patch(rect)
    candles.append(rect)
    
    # 绘制上下影线
    line, = ax1.plot([i, i], [low_price, high_price], color=color, linewidth=1.5)
    candles.append(line)

# 设置K线图格式
ax1.set_title('K线图', fontsize=15)
ax1.set_ylabel('价格', fontsize=12)
ax1.grid(True, linestyle='--', alpha=0.5)

# 成交量图
for i in range(len(df)):
    status = df['Status'].iloc[i]
    volume = df['Volume'].iloc[i]
    color = up_color if status else down_color
    bar = ax2.bar(i, volume, color=color, alpha=0.8, width=0.8)
    volume_bars.append(bar)

ax2.set_ylabel('成交量', fontsize=12)
ax2.grid(True, linestyle='--', alpha=0.5)

# 设置x轴刻度为日期
ax2.set_xticks(range(len(df)))
ax2.set_xticklabels([d.strftime('%Y-%m-%d') for d in df.index], rotation=45)

# 使用mplcursors添加交互式标注
cursor = mplcursors.cursor(hover=True)

@cursor.connect("add")
def on_add(sel):
    index = int(round(sel.target[0]))
    if 0 <= index < len(df):
        date = df.index[index].strftime('%Y-%m-%d')
        open_val = df['OpenValue'].iloc[index]
        close_val = df['CloseValue'].iloc[index]
        high_val = df['HighValue'].iloc[index]
        low_val = df['LowValue'].iloc[index]
        volume = df['Volume'].iloc[index]
        change = df['Change'].iloc[index]
        
        # 创建信息文本
        info = f"日期: {date}\n开盘: {open_val:.3f}\n收盘: {close_val:.3f}\n最高: {high_val:.3f}\n最低: {low_val:.3f}\n涨跌: {change}%\n成交量: {volume}"
        
        sel.annotation.set_text(info)
        sel.annotation.get_bbox_patch().set(fc="white", alpha=0.8)

# 调整布局
plt.tight_layout()
plt.show()