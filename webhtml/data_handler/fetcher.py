"""数据获取模块(fetcher)

首期实现策略：
- 优先尝试通过 akshare 获取核心快照；
- 若获取失败或依赖缺失，返回本地 mock 数据（保证页面可生成）。

返回数据为"原始数据字典"，供 analysis.calculator 处理为模板字段。
ref : https://akshare.akfamily.xyz/data/index/index.html
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime, date
import logging
import pandas as pd
import time
import random

from webhtml.config import market_watch_list as watch  # 监控清单(指数/风格/行业/风险/全球)
from webhtml.config import settings  # 路径与日期等配置

try:
    import akshare as ak  # type: ignore
except Exception:  # noqa: BLE001
    ak = None  # 允许在无 akshare 环境下运行（mock）

try:
    import yfinance as yf  # type: ignore
except Exception:  # noqa: BLE001
    yf = None  # 允许在无 yfinance 环境下运行

import requests
import re

# ============================================================
# 新浪实时行情接口 (作为东方财富接口的备用数据源)
# ============================================================
def _sina_realtime_quote(codes: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    通过新浪接口获取实时行情数据
    
    参数:
        codes: 股票/指数/ETF代码列表，格式如 ["sh000001", "sz300750", "sh510050"]
               - sh 开头: 上海市场
               - sz 开头: 深圳市场
    
    返回:
        {代码: {"name": 名称, "price": 最新价, "change_pct": 涨跌幅, "volume": 成交量, "amount": 成交额}}
    """
    if not codes:
        return {}
    
    codes_str = ",".join(codes)
    url = f"http://hq.sinajs.cn/list={codes_str}"
    
    headers = {
        "Referer": "http://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "gbk"
        
        result = {}
        lines = resp.text.strip().split("\n")
        
        for line in lines:
            # 解析格式: var hq_str_sh600036="招商银行,..."
            match = re.match(r'var hq_str_(\w+)="(.*)";', line)
            if match:
                code = match.group(1)
                data = match.group(2)
                if data:
                    parts = data.split(",")
                    if len(parts) >= 9:
                        name = parts[0]
                        # 指数: parts[1]=今开, parts[2]=昨收, parts[3]=当前价
                        # 个股: parts[1]=今开, parts[2]=昨收, parts[3]=当前价, parts[8]=成交量, parts[9]=成交额
                        try:
                            current = float(parts[3]) if parts[3] else 0
                            yesterday = float(parts[2]) if parts[2] else 0
                            if yesterday > 0:
                                change_pct = (current - yesterday) / yesterday * 100
                            else:
                                change_pct = 0.0
                            
                            volume = float(parts[8]) if len(parts) > 8 and parts[8] else 0
                            amount = float(parts[9]) if len(parts) > 9 and parts[9] else 0
                            
                            result[code] = {
                                "name": name,
                                "price": current,
                                "change_pct": round(change_pct, 2),
                                "volume": volume,
                                "amount": amount,
                                "yesterday": yesterday,
                            }
                        except (ValueError, IndexError):
                            continue
        
        return result
    except Exception as e:
        logging.warning("新浪接口请求失败: %s", e)
        return {}


def _convert_code_to_sina(code: str) -> str:
    """
    将普通代码转换为新浪接口格式
    
    输入: "000001" 或 "sh000001" 或 "510050"
    输出: "sh000001" 或 "sz000001"
    """
    code = str(code).strip().lower()
    
    # 已经是 sh/sz 开头
    if code.startswith("sh") or code.startswith("sz"):
        return code
    
    # 去掉可能的前缀
    code = code.lstrip("0")
    if not code:
        code = "000001"
    code = code.zfill(6)
    
    # 根据代码判断市场
    # 6开头 -> 上海, 0/3开头 -> 深圳, 5开头 -> 上海ETF, 1开头 -> 深圳ETF
    if code.startswith("6") or code.startswith("5"):
        return f"sh{code}"
    elif code.startswith("0") or code.startswith("3") or code.startswith("1"):
        return f"sz{code}"
    else:
        return f"sh{code}"


def _retry_call(func: Callable, max_retries: int = 5, delay_range: tuple = (2, 5), func_name: str = ""):
    """带重试机制的函数调用，应对网络不稳定"""
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                delay = random.uniform(*delay_range)
                logging.info("第 %d 次重试 %s，等待 %.1f 秒...", attempt + 1, func_name, delay)
                time.sleep(delay)
            return func()
        except Exception as e:
            logging.warning("第 %d 次尝试 %s 失败: %s", attempt + 1, func_name, e)
            if attempt == max_retries - 1:
                raise
    return None


def _mock_raw_data() -> Dict[str, Any]:
    now = datetime.now()
    return {
        "date": now.strftime("%Y-%m-%d"),
        "indexes": [
            {"name": "上证指数", "code": "sh000001", "close": 0, "change_pct": 0, "turnover_billion": 0},
            {"name": "创业板指", "code": "sz399006", "close": 0, "change_pct": 0, "turnover_billion": 0},
            {"name": "科创50指", "code": "sh000688", "close": 0, "change_pct": 0, "turnover_billion": 0},
        ],
        "up_down": {"up": 0, "down": 0, "activityPct": "0%"},
        "styles": [
            {"category": "大规模/价值", "name": "上证50ETF", "code": "510050", "change_pct": 0},
            {"category": "大规模/价值", "name": "沪深300ETF", "code": "510300", "change_pct": 0},
            {"category": "大规模/价值", "name": "红利ETF", "code": "510880", "change_pct": 0},
            {"category": "大规模/价值", "name": "科创50ETF", "code": "588000", "change_pct": 0},
            {"category": "中小规模/成长", "name": "中证500ETF", "code": "510500", "change_pct": 0},
            {"category": "中小规模/成长", "name": "中证1000ETF", "code": "159845", "change_pct": 0},
            {"category": "中小规模/成长", "name": "科创100ETF", "code": "588190", "change_pct": 0},
        ],
        "sectors": [
            {"etf_name": "券商ETF", "code": "512000", "change_pct": 0, "leaders": [
                {"name": "中信证券", "change_pct": 0},
                {"name": "东方财富", "change_pct": 0},
            ]},
            {"etf_name": "芯片ETF", "code": "512760", "change_pct": 0, "leaders": [
                {"name": "中芯国际", "change_pct": 0},
                {"name": "北方华创", "change_pct": 0},
            ]},
            {"etf_name": "人工智能AI ETF", "code": "560800", "change_pct": 0, "leaders": [
                {"name": "科大讯飞", "change_pct": 0},
                {"name": "浪潮信息", "change_pct": 0},
            ]},
            {"etf_name": "软件ETF", "code": "159852", "change_pct": 0, "leaders": [
                {"name": "金山办公", "change_pct": 0},
            ]},
            {"etf_name": "新能源车ETF", "code": "159806", "change_pct": 0, "leaders": [
                {"name": "宁德时代", "change_pct": 0},
                {"name": "比亚迪", "change_pct": 0},
            ]},
            {"etf_name": "保险主题ETF", "code": "512000", "change_pct": 0, "leaders": [
                {"name": "中国平安", "change_pct": 0},
            ]},
            {"etf_name": "银行ETF", "code": "512800", "change_pct": 0, "leaders": [
                {"name": "招商银行", "change_pct": 0},
            ]},
            {"etf_name": "有色金属ETF", "code": "512400", "change_pct": 0, "leaders": [
                {"name": "紫金矿业", "change_pct": 0},
            ]},
            {"etf_name": "煤炭ETF", "code": "515220", "change_pct": 0, "leaders": [
                {"name": "中国神华", "change_pct":0},
            ]},
            {"etf_name": "消费ETF", "code": "159928", "change_pct": 0, "leaders": [
                {"name": "贵州茅台", "change_pct": 0},
            ]},
            {"etf_name": "食品饮料ETF", "code": "159843", "change_pct": 0, "leaders": [
                {"name": "五粮液", "change_pct": 0},
                {"name": "泸州老窖", "change_pct":0},
            ]},
            {"etf_name": "医药ETF", "code": "512010", "change_pct": 0, "leaders": [
                {"name": "恒瑞医药", "change_pct": 0},
                {"name": "药明康德", "change_pct": 0},
            ]},
            {"etf_name": "医疗ETF", "code": "159828", "change_pct": 0, "leaders": [
                {"name": "迈瑞医疗", "change_pct": 0},
                {"name": "爱尔眼科", "change_pct": 0},
            ]},
        ],
        "risks": [
            {"category": "国内避险", "name": "黄金ETF", "code": "518880", "value_or_change": 0, "interpretation": "市场风险偏好提升"},
            {"category": "国内安全", "name": "30年国债ETF", "code": "511090", "value_or_change": 111, "interpretation": "资金流向风险资产"},
            {"category": "全球避险", "name": "COMEX黄金", "code": "GLOBAL_COMEX_GOLD", "value_or_change": 0, "interpretation": "避险情绪降温"},
            {"category": "全球风险锚", "name": "10年期美债收益率", "code": "US10Y", "value_or_change": 0, "interpretation": "对高估值成长股构成潜在压力"},
            {"category": "做多A股", "name": "YINN富时3倍做多中国", "code": "YINN", "value_or_change": 0, "interpretation": "外资看多看空"},
        ],
        "globals": [
            {"category": "关联圈 (香港)", "indicator": "恒生指数", "code": "HSI", "value_or_change": 0, "interpretation": "市场情绪联动"},
            {"category": "关联圈 (香港)", "indicator": "恒生科技指数", "code": "HSTECH.HK", "value_or_change": 0, "interpretation": "与A股科技板块形成共振"},
            {"category": "环境圈 (美股)", "indicator": "标普500", "code": "^GSPC", "value_or_change":0, "interpretation": "全球风险偏好向好"},
            {"category": "环境圈 (美股)", "indicator": "纳斯达克100", "code": "^NDX", "value_or_change": 0, "interpretation": "利好A股科技股开盘"},
            {"category": "环境圈 (美股)", "indicator": "英伟达(NVDA)", "code": "NVDA", "value_or_change": 0, "interpretation": "AI与半导体情绪高涨"},
            {"category": "环境圈 (美股)", "indicator": "金龙中国指数", "code": "PGJ", "value_or_change": 0, "interpretation": "提振中概股相关板块情绪"},
            {"category": "环境圈 (其他)", "indicator": "美元/离岸CNH", "code": "CNH=X", "value_or_change": 0, "interpretation": "人民币升值，利好外资流入"},
            {"category": "环境圈 (加密货币)", "indicator": "比特币 (BTC)", "code": "BTC-USD", "value_or_change": 0, "interpretation": "全球投机情绪回暖"},
            {"category": "环境圈 (加密货币)", "indicator": "以太坊 (ETH)", "code": "ETH-USD", "value_or_change": 0, "interpretation": "高风险偏好资产表现强势"},
        ],
        "_source": "mock",
    }

def lastTradeDateStr() -> str:
    """功能: 获取最近一个不晚于今日的交易日字符串。
    参数: 无。
    返回: YYYY-MM-DD 字符串。
    """
    try:
        d = ak.tool_trade_date_hist_sina()
        today_str = settings.today_str()
        if hasattr(d, "to_frame"):
            df = d.to_frame().reset_index(drop=True)
            if df.shape[1] == 1:
                values = df.iloc[:, 0].astype(str).tolist()
            else:
                values = [str(x) for x in df.astype(str).values.ravel().tolist()]
        else:
            values = [str(x) for x in list(d)]
        today = today_str
        candidates = [v[:10] for v in values]
        candidates = [v for v in candidates if v <= today]
        if not candidates:
            return today
        return candidates[-1]
    except Exception as e:  # noqa: BLE001
        logging.warning("获取最近交易日失败，使用今日: %s", e)
        return settings.today_str()


def firstCol(df, names: List[str]) -> Optional[str]:
    """功能: 返回 DataFrame 中按给定候选顺序出现的第一个列名。
    参数: df 为数据表, names 为候选列名列表。
    返回: 匹配的列名或 None。
    """
    for n in names:
        if n in df.columns:
            return n
    return None


def toFloatMaybe(x: Any) -> Optional[float]:
    """功能: 将输入安全转换为 float。
    参数: 字符串或数值 x。
    返回: float 或 None(转换失败)。
    """
    try:
        if isinstance(x, str):
            x2 = x.strip().replace("%", "").replace(",", "")
            if x2 == "":
                return None
            return float(x2)
        return float(x)
    except Exception:
        return None


def roundToInt(v: Optional[float]) -> int:
    """功能: 四舍五入并转为 int。
    参数: 可能为 None 的浮点数 v。
    返回: 转换后的整数，None 返回 0。
    """
    if v is None:
        return 0
    try:
        return int(round(v))
    except Exception:
        return 0

"""功能: 基于指数现货快照构造监控清单所需指数数据。
输入参数为：监控指数列表 watch_indexes 和回退指数列表 mock_indexes。
返回值为一个元组: (指数数据列表, 是否使用回退)。

优先使用新浪接口（更稳定），若失败则使用东方财富接口备用。
"""
def buildIndexes(watch_indexes: List[Dict[str, Any]],
                 mock_indexes: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:

    # ===== 方案1: 优先使用新浪接口 =====
    try:
        # 收集需要查询的代码
        sina_codes = [dct["code"] for dct in watch_indexes]
        
        # 调用新浪接口
        sina_data = _sina_realtime_quote(sina_codes)
        
        if sina_data:
            out: List[Dict[str, Any]] = []
            for dct in watch_indexes:
                code = dct["code"]
                data = sina_data.get(code)
                
                if data:
                    out.append({
                        "name": dct["name"],
                        "code": code,
                        "close": data.get("price", 0.0),
                        "change_pct": data.get("change_pct", 0.0),
                        "turnover_billion": roundToInt(data.get("amount", 0) / 1e8),
                        "volume": data.get("volume", 0.0),
                        "amplitude": 0.0,  # 新浪接口无振幅数据
                        "volume_ratio": 0.0,  # 新浪接口无量比数据
                    })
                else:
                    logging.warning(f"新浪接口未找到指数: {code}")
            
            if out:
                logging.info("指数数据获取成功 (新浪接口)")
                return out, False
    except Exception as e:
        logging.warning("新浪指数接口失败: %s", e)

    # ===== 方案2: 东方财富接口备用 =====
    try:
        logging.info("尝试使用东方财富接口获取指数数据...")
        all_index_data = []
        index_series = ["沪深重要指数", "上证系列指数", "深证系列指数", "中证系列指数"]
        
        for series in index_series:
            try:
                df = ak.stock_zh_index_spot_em(symbol=series)
                if not df.empty:
                    all_index_data.append(df)
            except Exception:
                continue
        
        if all_index_data:
            idx_df = pd.concat(all_index_data, ignore_index=True).drop_duplicates(subset=["代码"])
            
            code_to_data = {}
            for _, row in idx_df.iterrows():
                code = str(row["代码"]).strip()
                if code:
                    code_to_data[code] = row
            
            out: List[Dict[str, Any]] = []
            for dct in watch_indexes:
                code = dct["code"]
                row = code_to_data.get(code)

                if row is None:
                    for k, v in code_to_data.items():
                        if code in k or k in code:
                            row = v
                            break
                    if row is None:
                        continue
                
                out.append({
                    "name": dct["name"],
                    "code": code,
                    "close": toFloatMaybe(row.get("最新价")) or 0.0,
                    "change_pct": toFloatMaybe(row.get("涨跌幅")) or 0.0,
                    "turnover_billion": roundToInt((toFloatMaybe(row.get("成交额")) or 0.0) / 1e8),
                    "volume": toFloatMaybe(row.get("成交量")) or 0.0,
                    "amplitude": toFloatMaybe(row.get("振幅")) or 0.0,
                    "volume_ratio": toFloatMaybe(row.get("量比")) or 0.0,
                })
            
            if out:
                logging.info("指数数据获取成功 (东方财富接口备用)")
                return out, False
    except Exception as e:
        logging.warning("东方财富指数接口也失败: %s", e)

    # ===== 方案3: 使用 mock 数据 =====
    logging.warning("所有指数接口均失败，使用mock数据")
    return mock_indexes, True

"""功能: 统计全 A 股涨跌家数与活跃度。
输入参数为: mock_up_down 为回退数据。
返回: (字典 {up, down, activityPct}, 是否使用回退)。
"""
def buildUpDown(mock_up_down: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:

    try:
        if ak is None:
            raise RuntimeError("akshare 不可用")
        df = ak.stock_market_activity_legu()
        if df is None or getattr(df, "empty", True):
            raise RuntimeError("乐咕赚钱效应数据为空")

        # 映射 item->value
        item_to_value: Dict[str, Any] = {}
        for _, r in df.iterrows():
            item = str(r.get("item", "")).strip()
            val = r.get("value")
            item_to_value[item] = val

        up_v = toFloatMaybe(item_to_value.get("上涨"))
        down_v = toFloatMaybe(item_to_value.get("下跌"))
        act_v = toFloatMaybe(item_to_value.get("活跃度"))  # 百分数字符串 -> 浮点百分数

        if up_v is None or down_v is None:
            raise RuntimeError("缺少上涨/下跌字段")

        # 计算活跃度百分比，转换为字符串格式
        if act_v is not None:
            activity_pct_str = f"{act_v:.1f}%"
        else:
            activity_pct_str = f"{round((up_v / (up_v + down_v) * 100) if (up_v + down_v) > 0 else 0.0, 1)}%"
        
        result = {
            "up": int(up_v),
            "down": int(down_v),
            "activityPct": activity_pct_str,
        }
        print(result)
        print("涨跌家数获取成功")
        return result, False

    except Exception as e:  # noqa: BLE001
        logging.warning("涨跌家数获取失败(乐咕接口)，使用mock: %s", e)
        # 兜底保证包含 activityPct
        up = int(mock_up_down.get("up", 0))
        down = int(mock_up_down.get("down", 0))
        if "activityPct" in mock_up_down:
            activity = mock_up_down.get("activityPct", "0.0%")
        else:
            activity = f"{round((up / (up + down) * 100) if (up + down) > 0 else 0.0, 1)}%"
        return {"up": up, "down": down, "activityPct": activity}, True


"""功能: 生成风格ETF涨跌数据。
参数: watch_styles 为监控清单, mock_styles 为回退数据。
返回: (风格数据列表, 是否使用回退)。
支持新浪接口备用：优先东方财富，失败时用新浪。
"""
def buildStyles(watch_styles: List[Dict[str, Any]], mock_styles: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:

    try:
        # 构建输出数据
        rows: List[Dict[str, Any]] = []
        found_count = 0
        missing_codes = []
        
        for style_item in watch_styles:
            code = style_item["code"]
            sina_code = style_item.get("sina_code")  # 从配置读取新浪代码
            
            # 使用 getSpecificEtfChangePct 获取ETF涨跌幅（含新浪备用）
            pct_value = getSpecificEtfChangePct(code, sina_code)
            
            if pct_value is None:
                logging.warning(f'风格ETF未找到: {code}')
                missing_codes.append(code)
                pct_value = 0.0
            else:
                found_count += 1
                
            rows.append({
                "category": style_item["category"],
                "name": style_item["name"],
                "code": code,
                "change_pct": float(pct_value),
            })
        
        # 记录处理结果
        total_count = len(watch_styles)
        logging.info(f"风格ETF数据处理完成: 找到{found_count}/{total_count}个，缺失{len(missing_codes)}个")
        
        if missing_codes:
            logging.warning(f"未找到的ETF代码: {missing_codes}")
            
        return rows, False
    
    except Exception as e:  # noqa: BLE001
        logging.warning("风格获取失败，使用mock: %s", e)
        return mock_styles, True


"""功能: 生成行业与主题ETF及龙头个股涨跌数据。
参数: a_spot 为A股快照(来自ak.stock_zh_a_spot_em或新浪备用), watch_sectors 为监控清单, mock_sectors 为回退数据。
返回: (行业主题列表, 是否使用回退)。
支持新浪接口备用：ETF和龙头股均可从新浪获取。
"""
def buildSectors(a_spot: Any, watch_sectors: List[Dict[str, Any]], mock_sectors: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:

    try:
        # 构建龙头股名称到涨跌幅的映射
        a_map: Dict[str, float] = {}
        
        # 从 a_spot DataFrame 读取（东方财富或新浪备用数据）
        if a_spot is not None and hasattr(a_spot, 'iterrows'):
            a_name_col = firstCol(a_spot, ["名称"]) or "名称"
            a_pct_col = firstCol(a_spot, ["涨跌幅"]) or "涨跌幅"
            for _, r in a_spot.iterrows():
                n = str(r.get(a_name_col, "")).strip()
                v = toFloatMaybe(r.get(a_pct_col))
                if n:
                    a_map[n] = float(v or 0.0)
        
        # 如果 a_spot 为空，直接从新浪获取所有龙头股数据
        if not a_map:
            logging.info("A股快照为空，直接从新浪获取龙头股数据...")
            all_leader_codes = []
            leader_code_to_name = {}
            for s in watch_sectors:
                for leader in s.get("leaders", []):
                    # 支持新格式 {"name": "xxx", "sina_code": "shxxxxxx"}
                    if isinstance(leader, dict):
                        sina_code = leader.get("sina_code")
                        name = leader.get("name")
                        if sina_code and name:
                            all_leader_codes.append(sina_code)
                            leader_code_to_name[sina_code] = name
            
            if all_leader_codes:
                sina_data = _sina_realtime_quote(all_leader_codes)
                for code, data in sina_data.items():
                    name = leader_code_to_name.get(code, data.get("name", ""))
                    if name:
                        a_map[name] = data.get("change_pct", 0.0)

        out: List[Dict[str, Any]] = []
        for s in watch_sectors:
            # ETF信息 - 使用 getSpecificEtfChangePct 获取ETF涨跌幅（含新浪备用）
            code = s["code"]
            sina_code = s.get("sina_code")
            change_pct = getSpecificEtfChangePct(code, sina_code)
            if change_pct is None:
                logging.warning(f'行业ETF未找到: {code}')
                change_pct = 0.0
            
            # 龙头信息 - 支持新旧两种格式
            leaders = []
            for leader in s.get("leaders", []):
                if isinstance(leader, dict):
                    # 新格式: {"name": "xxx", "sina_code": "shxxxxxx"}
                    name = leader.get("name", "")
                    pct = float(a_map.get(name, 0.0))
                    leaders.append({"name": name, "change_pct": pct})
                else:
                    # 旧格式: 直接是字符串名称
                    pct = float(a_map.get(str(leader).strip(), 0.0))
                    leaders.append({"name": leader, "change_pct": pct})
                
            out.append({
                "etf_name": s["etf_name"],
                "code": code,
                "change_pct": float(change_pct),
                "leaders": leaders,
            })
        return out, False
    except Exception as e:  # noqa: BLE001
        logging.warning("行业与主题获取失败，使用mock: %s", e)
        return mock_sectors, True




def getComexGoldChangePct() -> Optional[float]:
    """功能: 获取 COMEX 黄金当日涨跌幅(%)。
    参数: 无。返回: 浮点数涨跌幅或 None(获取失败)。
    """
    try:
        if yf is None:
            return None
            
        # 使用 yfinance 获取 COMEX 黄金期货数据
        # GC=F 是 COMEX 黄金期货的 Yahoo Finance 代码
        gold_ticker = "GC=F"
        
        # 获取最近两天的数据来计算涨跌幅
        gold_data = yf.download(gold_ticker, period="2d", progress=False, auto_adjust=True)
        
        if gold_data is None or gold_data.empty or len(gold_data) < 2:
            return None
            
        # 获取最新两天的收盘价
        closes = gold_data['Close'].values
        if len(closes) < 2:
            return None
            
        yesterday_close = closes[-2]  # 昨日收盘价
        today_close = closes[-1]     # 今日收盘价
        
        # 计算涨跌幅: (今日收盘价 - 昨日收盘价) / 昨日收盘价 * 100
        change_pct = ((today_close - yesterday_close) / yesterday_close) * 100
        print(change_pct)
        print("COMEX黄金涨跌幅获取成功")
        
        return float(change_pct.item())
        
    except Exception as e:
        logging.warning(f"获取 COMEX 黄金涨跌幅失败: {e}")
        return None



def getUsStockChangePct(ticker: str) -> Optional[float]:
    """功能: 获取指定美股/ETF当日涨跌幅(%)。
    参数: ticker。返回: 浮点数涨跌幅或 None(获取失败)。
    """
    try:
        if yf is None:
            return None

        t = yf.Ticker(ticker)
        info = t.info

        if 'regularMarketPrice' in info and 'previousClose' in info:
            current_price = info['regularMarketPrice']
            previous_close = info['previousClose']

            if previous_close is None or previous_close == 0:
                if 'regularMarketChangePercent' in info and info['regularMarketChangePercent'] is not None:
                    return float(info['regularMarketChangePercent'] * 100)
                return 0.0

            change_percent = ((current_price - previous_close) / previous_close) * 100
            return float(change_percent)
        else:
            hist = t.history(period="2d")
            if hist is None or hist.empty or len(hist) < 2:
                return None

            last_close = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            change_percent = ((last_close - prev_close) / prev_close) * 100
            return float(change_percent)

    except Exception as e:
        logging.warning(f"获取美股 {ticker} 涨跌幅失败: {e}")
        return None


def getYinnChangePct() -> Optional[float]:
    """功能: 获取美股 ETF YINN 当日涨跌幅(%)。
    参数: 无。返回: 浮点数涨跌幅或 None(获取失败)。
    """
    return getUsStockChangePct("YINN")


def getUs10yChangePct() -> Optional[float]:
    """功能: 获取美国10年期国债收益率当日涨跌幅(%)。
    参数: 无。返回: 浮点数涨跌幅或 None(获取失败)。
    """
    return getUsStockChangePct("^TNX")


def getHkChangePct(code: str) -> Optional[float]:
    """功能: 获取香港市场指标当日涨跌幅(%)。
    参数: code(如 HSI、HSTECH)。返回: 浮点数涨跌幅或 None。
    """
    return getUsStockChangePct(code)


def getFxChangePct(code: str) -> Optional[float]:
    """功能: 获取外汇对当日涨跌幅(%)。
    参数: code(如 USDCNH)。返回: 浮点数涨跌幅或 None。
    """
    candidates_map = {
        "USDCNH": ["USDCNH=X", "CNH=X"],
    }
    candidates = candidates_map.get(code, [code])
    for t in candidates:
        v = getUsStockChangePct(t)
        if v is not None:
            return v
    return None


def getCryptoChangePct(code: str) -> Optional[float]:
    """功能: 获取加密货币当日涨跌幅(%)。
    参数: code(如 BTCUSDT、ETHUSDT)。返回: 浮点数涨跌幅或 None。
    """

    return  getUsStockChangePct(code)

def getSpecificEtfChangePct(code: str, sina_code: str = None) -> Optional[float]:
    """功能: 获取特定ETF最新一日涨跌幅(%)。
    优先使用新浪接口（更稳定），失败时使用东方财富接口备用。
    参数: code (ETF代码), sina_code (新浪代码，可选)。
    返回: 浮点数涨跌幅或 None(获取失败)。
    """
    # ===== 方案1: 优先使用新浪接口 =====
    target_sina_code = sina_code or _convert_code_to_sina(code)
    try:
        sina_data = _sina_realtime_quote([target_sina_code])
        if target_sina_code in sina_data:
            return sina_data[target_sina_code].get("change_pct", 0.0)
    except Exception as e:
        logging.debug(f"新浪ETF {target_sina_code} 接口失败: {e}")
    
    # ===== 方案2: 东方财富接口备用 =====
    try:
        if ak is not None:
            df = ak.fund_etf_hist_em(symbol=code, adjust="qfq")
            if df is not None and not getattr(df, "empty", True) and len(df) >= 1:
                latest = df.iloc[-1]
                change = toFloatMaybe(latest.get("涨跌幅"))
                if change is not None:
                    return float(change)
    except Exception as e:
        logging.debug(f"东方财富ETF {code} 接口也失败: {e}")
    
    logging.warning(f"ETF {code} 所有接口均失败")
    return None

def buildRisks(watch_risks: List[Dict[str, Any]], mock_risks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    """功能: 汇总风险偏好与风险锚指标。
    参数: watch_risks 为监控清单, mock_risks 为回退数据。
    返回: (风险列表, 是否使用回退)。
    """
    try:
        # 逐项构建，单项失败仅回退该项
        out: List[Dict[str, Any]] = []
        mock_map = {m.get("code"): m for m in mock_risks}

        for r in watch_risks:
            code = r["code"]
            val: Optional[float] = None

            try:
                if code == "GLOBAL_COMEX_GOLD":
                    val = getComexGoldChangePct() 
                elif code == "US10Y":
                    val = getUsStockChangePct("^TNX")
                elif code == "YINN":
                    val = getUsStockChangePct("YINN")
                else:
                    val = getSpecificEtfChangePct(code)
                    print(f'{code} 涨幅：{val} \n')
            except Exception:
                val = None

            if val is None:
                mv = mock_map.get(code, {})
                val = toFloatMaybe(mv.get("value_or_change", 0.0)) or 0.0

            out.append({
                "category": r["category"],
                "name": r["name"],
                "code": code,
                "value_or_change": float(val or 0.0),
                "interpretation": str(mock_map.get(code, {}).get("interpretation", "")), #市场解读说明，帮助用户理解数据背后的市场含义
            })

        return out, False
    except Exception as e:  # noqa: BLE001
        logging.warning("风险偏好获取失败，使用mock: %s", e)
        return mock_risks, True


def buildGlobals(watch_globals: List[Dict[str, Any]], mock_globals: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    """功能: 汇总全球与关联圈指标(仅使用 yfinance 获取，且不使用兜底)。
    参数: watch_globals 为监控清单, mock_globals 参数保留但不使用。
    返回: (全球关联列表, 是否回退)。
    """
    try:
        out: List[Dict[str, Any]] = []
        for g in watch_globals:
            code = g["code"]
            category = g["category"]

            val: Optional[float] = None
            try:
                if category == "香港":
                    val = getHkChangePct(code)
                elif category == "美股":
                    val = getUsStockChangePct(code)
                elif category == "汇率":
                    val = getFxChangePct(code)
                elif category == "加密货币":
                    val = getCryptoChangePct(code)
            except Exception:
                val = None

             # 逐项构建，单项失败仅回退该项
            mock_map = {m.get("code"): m for m in mock_globals}
            if val is None:
                mv = mock_map.get(code, {})
                val = toFloatMaybe(mv.get("value_or_change", 0.0)) or 0.0

            out.append({
                "category": category,
                "indicator": g["indicator"],
                "code": code,
                "value_or_change": float(val or 0.0),
                "interpretation": str(mock_map.get(code, {}).get("interpretation", "")),
            })
        return out, False
    except Exception as e:  # noqa: BLE001
        logging.warning("全球与关联获取失败: %s", e)
        return mock_globals, True


def fetch_all_data() -> Dict[str, Any]:
    """获取全部原始数据快照；失败时按片段回退到 mock，并标记来源。

    功能:
    - 汇总当日或最近交易日的市场原始数据，覆盖指数、涨跌家数、风格ETF、行业与主题ETF(含龙头)、风险偏好、全球关联。
    - 结果直接供上层 analysis 与报表模板使用。

    参数:
    - 无

    返回:
    - 类型: Dict[str, Any]，结构参考 _mock_raw_data。
    """
    # 若 ak 不可用，直接返回 mock
    if ak is None:
        return _mock_raw_data()

    # 调用一次 mock，供回退时复用片段
    mock = _mock_raw_data()

    # 日期
    report_date = lastTradeDateStr()

    # 拉取龙头股数据：优先使用新浪接口（更稳定）
    a_spot = None
    
    # ===== 方案1: 优先使用新浪接口获取龙头股数据 =====
    try:
        logging.info("使用新浪接口获取龙头股数据...")
        # 从配置中读取龙头股的新浪代码（自动同步，无需手动维护）
        codes_to_fetch = []
        code_to_name = {}
        
        for sector in watch.SECTORS:
            for leader in sector.get("leaders", []):
                if isinstance(leader, dict):
                    sina_code = leader.get("sina_code")
                    name = leader.get("name")
                    if sina_code and name:
                        codes_to_fetch.append(sina_code)
                        code_to_name[sina_code] = name
        
        if codes_to_fetch:
            sina_data = _sina_realtime_quote(codes_to_fetch)
            
            if sina_data:
                rows = []
                for sina_code, name in code_to_name.items():
                    if sina_code in sina_data:
                        data = sina_data[sina_code]
                        rows.append({
                            "名称": name,
                            "涨跌幅": data.get("change_pct", 0.0),
                        })
                
                if rows:
                    a_spot = pd.DataFrame(rows)
                    logging.info("A股龙头股数据获取成功 (新浪接口), 共 %d 条", len(a_spot))
    except Exception as e:
        logging.warning("新浪接口获取龙头股失败: %s", e)
    
    # ===== 方案2: 东方财富接口备用 =====
    if a_spot is None or (hasattr(a_spot, 'empty') and a_spot.empty):
        try:
            logging.info("尝试使用东方财富接口获取A股快照...")
            a_spot = _retry_call(ak.stock_zh_a_spot_em, max_retries=2, delay_range=(1, 2), func_name="stock_zh_a_spot_em")
            if a_spot is not None and not a_spot.empty:
                logging.info("A股快照获取成功 (东方财富接口备用), 共 %d 条", len(a_spot))
        except Exception as e:
            logging.warning("东方财富A股快照也失败: %s", e)
            a_spot = None



    # 构造各段
  
    logging.info("开始构建指数数据...")
    indexes, fb_idx = buildIndexes(watch.INDEXES, mock["indexes"])                   # 构建指数数据，fb_idx为是否回退到mock
    logging.info("开始构建涨跌家数数据...")
    up_down, fb_ud = buildUpDown(mock["up_down"])                                     # 构建涨跌家数，fb_ud为是否回退到mock
    logging.info("开始构建风格ETF数据...")
    styles, fb_st = buildStyles(watch.STYLES, mock["styles"])              # 构建风格ETF数据，fb_st为是否回退到mock
    logging.info("开始构建行业与主题ETF数据...")
    sectors, fb_sc = buildSectors(a_spot, watch.SECTORS, mock["sectors"])  # 构建行业与主题ETF数据，fb_sc为是否回退到mock
    logging.info("开始构建风险偏好数据...")
    risks, fb_rk = buildRisks(watch.RISKS, mock["risks"])                  # 构建风险偏好数据，fb_rk为是否回退到mock
    logging.info("开始构建全球关联数据...")
    globals_list, fb_gl = buildGlobals(watch.GLOBALS, mock["globals"])               # 构建全球关联数据，fb_gl为是否回退到mock
    # 创建回退标志字典，记录各个数据源的回退状态
    # 每个键值对表示对应数据类别是否使用了回退数据源
    fallback_flags: Dict[str, bool] = {
        "indexes": fb_idx,    # 指数数据回退标志
        "up_down": fb_ud,     # 涨跌数据回退标志
        "styles": fb_st,      # 风格数据回退标志
        "sectors": fb_sc,     # 行业数据回退标志
        "risks": fb_rk,       # 风险数据回退标志
        "globals": fb_gl,     # 全球数据回退标志
    }

    # 统计使用回退数据源的数据类别数量
    fb_count = sum(1 for v in fallback_flags.values() if v)
    
    # 根据回退数据源的使用情况确定数据源标签
    if fb_count == 0:
        source_tag = "akshare"    # 无回退：全部使用akshare数据源
    elif fb_count >= len(fallback_flags):
        source_tag = "mock"       # 全部回退：全部使用模拟数据
    else:
        source_tag = "mixed"      # 部分回退：混合使用akshare和模拟数据

    return {
        "date": report_date,
        "indexes": indexes,
        "up_down": up_down,
        "styles": styles,
        "sectors": sectors,
        "risks": risks,
        "globals": globals_list,
        "_source": source_tag,
    }

