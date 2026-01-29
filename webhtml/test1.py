"""
测试修复后的 Yahoo Finance ticker
"""

import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

print("=" * 60)
print("测试修复后的全球数据 ticker")
print("=" * 60)

# 修复后的 ticker 列表
tickers = [
    ("^HSI", "恒生指数"),
    ("HSTECH.HK", "恒生科技指数"),      # 替代恒生科技指数
    ("^GSPC", "标普500"),
    ("^NDX", "纳斯达克100"),
    ("NVDA", "英伟达"),
    ("PGJ", "金龙中国"),
    ("DX-Y.NYB", "美元指数"),     # 替代离岸人民币
    ("CNH=X", "离岸人民币"),
    ("BTC-USD", "比特币"),
    ("ETH-USD", "以太坊"),
]

print(f"\n批量获取 {len(tickers)} 个 ticker...")
print("-" * 60)

# 批量下载
all_codes = [t[0] for t in tickers]
try:
    data = yf.download(
        tickers=all_codes,
        period="5d",
        progress=False,
        auto_adjust=False,  # 避免 FutureWarning
        threads=True
    )
    
    success = 0
    failed = []
    
    for code, name in tickers:
        try:
            if len(all_codes) > 1:
                # 多个 ticker，数据在 MultiIndex
                close_data = data['Close'][code]
            else:
                close_data = data['Close']
            
            if close_data is not None and not close_data.empty and len(close_data) >= 2:
                last = float(close_data.iloc[-1])
                prev = float(close_data.iloc[-2])
                pct = (last - prev) / prev * 100
                print(f"  {code:<12} {name:<10} ✓ 价格: {last:>10.2f}  涨跌: {pct:>+6.2f}%")
                success += 1
            else:
                print(f"  {code:<12} {name:<10} ✗ 数据为空")
                failed.append(code)
        except Exception as e:
            print(f"  {code:<12} {name:<10} ✗ 失败: {str(e)[:30]}")
            failed.append(code)
    
    print("-" * 60)
    print(f"成功: {success}/{len(tickers)}")
    if failed:
        print(f"失败: {failed}")

except Exception as e:
    print(f"批量下载失败: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
