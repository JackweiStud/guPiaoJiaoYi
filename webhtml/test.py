"""
测试 fetcher.py - 新浪接口备用功能（ETF + 龙头股）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

print("=" * 70)
print("测试新浪接口备用功能")
print("=" * 70)

# ============================================================
# 测试1: 验证配置文件格式
# ============================================================
print("\n[测试1] 验证 market_watch_list.py 配置格式")
print("-" * 50)

from webhtml.config import market_watch_list as watch

print(f"  INDEXES: {len(watch.INDEXES)} 条")
print(f"  STYLES: {len(watch.STYLES)} 条")
print(f"  SECTORS: {len(watch.SECTORS)} 条")

# 检查新格式
print("\n  检查 STYLES 新浪代码:")
for style in watch.STYLES[:3]:
    sina = style.get("sina_code", "无")
    print(f"    {style['name']}: code={style['code']}, sina_code={sina}")

print("\n  检查 SECTORS 龙头股配置:")
for sector in watch.SECTORS[:3]:
    print(f"    {sector['etf_name']}:")
    for leader in sector.get("leaders", []):
        if isinstance(leader, dict):
            print(f"      - {leader['name']}: {leader['sina_code']}")
        else:
            print(f"      - {leader} (旧格式)")

print("\n  ✓ 配置格式检查完成")

# ============================================================
# 测试2: 测试新浪 ETF 接口
# ============================================================
print("\n" + "=" * 70)
print("[测试2] 测试新浪 ETF 接口")
print("-" * 50)

from webhtml.data_handler.fetcher import _sina_realtime_quote

# 收集所有 ETF 的新浪代码
etf_codes = [s.get("sina_code") for s in watch.STYLES if s.get("sina_code")]
print(f"\n>>> 获取 {len(etf_codes)} 只风格ETF: {etf_codes}")

result = _sina_realtime_quote(etf_codes)
print(f"    成功获取 {len(result)} 只\n")

for code, data in result.items():
    print(f"    {code}: {data['name']} 涨跌={data['change_pct']:+.2f}%")

# ============================================================
# 测试3: 测试 getSpecificEtfChangePct 新浪备用
# ============================================================
print("\n" + "=" * 70)
print("[测试3] 测试 getSpecificEtfChangePct (含新浪备用)")
print("-" * 50)

from webhtml.data_handler.fetcher import getSpecificEtfChangePct

test_etfs = [
    ("510050", "sh510050", "上证50ETF"),
    ("159915", "sz159915", "创业板ETF"),
    ("518880", "sh518880", "黄金ETF"),
]

for code, sina_code, name in test_etfs:
    pct = getSpecificEtfChangePct(code, sina_code)
    if pct is not None:
        print(f"    {name}({code}): {pct:+.2f}% ✓")
    else:
        print(f"    {name}({code}): 获取失败 ✗")

# ============================================================
# 测试4: 测试完整数据获取
# ============================================================
print("\n" + "=" * 70)
print("[测试4] 测试完整 fetch_all_data")
print("-" * 50)

from webhtml.data_handler.fetcher import fetch_all_data

print("\n>>> 调用 fetch_all_data()...")
print("    (获取所有数据，可能需要一些时间...)\n")

try:
    data = fetch_all_data()
    
    print("返回数据:")
    print(f"    indexes: {len(data.get('indexes', []))} 条")
    print(f"    styles: {len(data.get('styles', []))} 条")
    print(f"    sectors: {len(data.get('sectors', []))} 条")
    
    # 显示风格ETF
    print("\n风格ETF:")
    for s in data.get('styles', []):
        pct = s.get('change_pct', 0)
        status = "✓" if pct != 0 else "✗"
        print(f"    {s['name']}: {pct:+.2f}% {status}")
    
    # 显示行业ETF
    print("\n行业ETF (前5条):")
    for sec in data.get('sectors', [])[:5]:
        leaders_str = ", ".join([f"{l['name']}({l['change_pct']:+.2f}%)" for l in sec.get('leaders', [])])
        status = "✓" if sec.get('change_pct', 0) != 0 else "✗"
        print(f"    {sec['etf_name']}: {sec['change_pct']:+.2f}% {status} | 龙头: {leaders_str}")

except Exception as e:
    print(f"✗ 获取失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("测试完成")
print("=" * 70)
