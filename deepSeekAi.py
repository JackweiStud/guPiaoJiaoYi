'''
背景：
    在stock_data文件下的存了ETF的分钟和日线数据，比如

要求：
    1、获取指定csv文件的(DateTime,OpenValue,CloseValue,HighValue,LowValue,Volume,ChangeRate)数据
    2、配置好硅基流动API，可访问deepSeekR1模型，系统提示词可参数配置
    3、将步骤1的数据，组装好后调用步骤2的R1模型，获取结果，并输出结果
'''

import os
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any
import httpx
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

class DeepSeekConfig(BaseModel):
    """深度求索API配置"""
    api_key: str = Field(..., description="API密钥")
    base_url: str = "https://api.siliconflow.cn/v1"
    system_prompt: str = "你是一位专业的、严谨的量化分析师,必须根据数据客观分析市场，成功率80%，短线之王，言辞犀利，语言精简, 根据用户提供的行情数据给出核心分析和2~5天的建议,默认成功率大于66%"
    model: str = Field("Pro/deepseek-ai/DeepSeek-R1", description="官方指定模型名称R1")  # 修正模型名称
    max_tokens: int = 4096  # 与官方示例一致
    temperature: float = 0
    top_p: float = 0



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

class DeepSeekAnalyzer:
    def __init__(self, config: DeepSeekConfig):
        self.config = config
        self.client = httpx.Client(timeout=1200, verify=False)  # 总超时120秒

    @retry(stop=stop_after_attempt(1), wait=wait_exponential(multiplier=1, min=4, max=10))
    def analyze_data(self, df: pd.DataFrame, user_prompt: str) -> Dict[str, str]:
        """
        同步版本的数据分析方法
        :return: 包含内容和推理内容的字典
        """
        try:
            data_sample = df.tail(80)
            data_str = data_sample.to_markdown()
            data_summary = f"数据时间范围：{df['DateTime'].min()} 至 {df['DateTime'].max()}"
            #print("content" + f"{user_prompt}\n{data_summary}\n样本数据：\n{data_str}")

            print("------------process_response 开始--------------------")

            response = self.client.post(
                f"{self.config.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                json={
                    "messages": [
                        {"role": "system", "content": self.config.system_prompt},
                        {"role": "user", "content": f"{user_prompt}\n{data_summary}\n样本数据：\n{data_str}"}
                    ],
                    "model": self.config.model,
                    "max_tokens": self.config.max_tokens,
                    "temperature": self.config.temperature,
                    "top_p": self.config.top_p,
                    "stream": False,
                    "response_format": {"type": "text"},
                    "stop": ["</分析结束>"]  # 添加停止标记
                },
                timeout=500  # 适当延长超时时间
            )
            response.raise_for_status()

            response_data = response.json()

            temp = self._process_response(response_data)
            #print("------------_process_response 完成--------------------")
            #print(temp)

            return temp



        except httpx.HTTPStatusError as e:
            return {"content": f"API请求失败: {e.response.status_code} {e.response.text}", "reasoning_content": "无推理内容", "is_complete": False}
        except Exception as e:
            return {"content": f"分析失败: {str(e)}", "reasoning_content": "无推理内容", "is_complete": False}
        finally:
            self.client.close()  # 同步关闭客户端

    def _process_response(self, response_data: dict) -> dict:
        """改进响应处理"""
        if not response_data.get("choices"):
            return {"content": "无有效响应", "reasoning": "无推理过程", "is_complete": False}

        choice = response_data["choices"][0]
        message = choice.get("message", {})

        # 处理不同完成状态
        finish_reason = choice.get("finish_reason", "unknown")
        completion_status = {
            "stop": (True, "完整响应"),
            "length": (False, "响应因长度限制被截断"),
            "content_filter": (False, "内容被安全策略过滤"),
            "null": (False, "响应未完成")
        }.get(finish_reason, (False, "未知状态"))

        content = message.get("content", "")
        if not completion_status[0]:
            content += f"\n[注意：{completion_status[1]}]"

        return {
            "content": content,
            "reasoning": message.get("reasoning_content", "无详细推理"),
            "is_complete": completion_status[0],
            "usage": response_data.get("usage", {})
        }


# 使用示例
def r1test(code):
    # 1. 配置参数
    config = DeepSeekConfig(
        api_key="sk-muzyalwgqothjfvsdmzfdjsuiszgqvbgzsvijfteyoesaxdy",
        system_prompt="你是一位专业的ETF市场分析师和交易员,言辞犀利，语言精简, 根据用户提供的行情数据给出核心分析和2~5天的建议,默认成功率大于66%"
    )

    # 2. 加载数据
    loader = ETFDataLoader()
    #dataPath = "D:/code-touzi/gitHub/guPiaoJiaoYi/stock_data/588180/588180_Day.csv"
    #dataPath = "/content/guPiaoJiaoYi/stock_data/588180/588180_Day.csv"
    dataPath = f"/content/drive/MyDrive/guPiaoJiaoYi/guPiaoJiaoYi/stock_data/{code}/{code}_Day.csv"
    #dataPath = f"/content/guPiaoJiaoYi/stock_data/{code}/{code}_60.csv"
    #print(dataPath)
    df = loader.load_etf_data(file_path=dataPath)

    # 3. 创建分析器
    analyzer = DeepSeekAnalyzer(config)

    # 4. 执行分析
    user_prompt1 = f"""
        一、将给你一段数据, 数据包括(DateTime,OpenValue,CloseValue,HighValue,LowValue,Volume,ChangeRate)
        二、可参考以下步骤分析：
            1. 识别关键趋势 (使用缠论（笔、顶底分型（涉及合并）、线段、中枢、3类买卖点）、均线、macd、RSI技术指标)
            2. 评估市场情绪 (基于成交量、换手率变化)
            3. 给出具体建议 (明确买卖区间、阻力、支持位)]
            4. 结合你的实际策略，明确2~3天看多还是看空
        三、最终按照markDown格式输出, [注意：结论请用</分析结束>标记]"""
    user_prompt = f"""
## 一、用户输入xxx股票的日线级别数据，格式如下：
- **数据字段**：DateTime, OpenValue, CloseValue, HighValue, LowValue, Volume, ChangeRate
- **数据已按时间升序排列

## 二、请按照下面的流程进行多维度、技术点、详细、迭代分析（缠论核心、、均线、macd、RSI技术指标、成交量、换手率变化）
### 1. 趋势结构分析（缠论核心包括：K线预处理、分型识别、中枢（Central Pivot）、三类买卖点）
#### 1.1 预处理
a. K线包含关系处理
规则：按当前走势方向合并相邻包含关系的K线。
说明：
步骤1 - 初始方向判定
在开始处理前，需明确当前处理方向：
首次处理：若前两根无包含K线为阳线（Close≥Open），默认向上处理；阴线则向下处理
后续处理：依据最近有效分型方向（如当前处于下跌笔，则向下处理）

步骤2 - 合并规则应用
趋势方向	    合并方法	          图形表现
上涨处理	取两K线最高价为新高，较高低价为新低	合并后K线高点≥原K线
下跌处理	取两K线最低价为新低，较低高价为新高	合并后K线低点≤原K线

步骤3 - 连续包含处理
3根及以上包含K线时：逐级合并（先合并前两根，再与第三根判断）
跳空处理：合并导致缺口≥3%时，保留原始K线

步骤4 - 方向切换验证
若合并后新K线突破原处理方向极值：
上涨处理中出现更低的低点 → 切换下跌处理重新合并
下跌处理中出现更高的高点 → 切换上涨处理重新合并
验证条件：合并后振幅≥原K线平均值的80%

b. 分型识别
有效分型标准：
顶分型：处理后连续三根K线中，第二根高点为最高，且低点为三者最高。
底分型：处理后连续三根K线中，第二根低点为最低，且高点为三者最低。
过滤无效分型：
排除包含关系后的分型需满足“一顶一底交替”原则，避免连续同类分型（中继分型例外：间隔≥5根K线且幅度＞3%）
强度分级：
强顶分型：第三根K线收盘价＜第一根最低价
弱顶分型：仅满足形态未破位

#### 1.2 关键结构识别
1. 笔（Segment）
构成条件：
相邻顶分型与底分型之间至少包含5根未处理的独立K线。
幅度要求：顶底分型间价格波动需＞1.5%
方向性：向上笔连接底分型至顶分型，向下笔反之。

2. 线段（Line Segment）
构成条件：
至少由3笔构成，且前三笔必须有重叠区域。
线段终结：需出现反向破坏笔（如上升线段被向下笔有效击穿前低点）。
特征序列：通过分析笔的特征序列（缺口与非缺口）判断线段延续或终结。

3. 中枢（Central Pivot）
构成条件：至少由三个连续次级别走势（如线段或笔）的重叠区间构成。
关键点：
ZG（中枢高点）= 重叠区间最高价
ZD（中枢低点）= 重叠区间最低价
级别递归：
日线中枢由4小时线段构成

4、三类买卖点的判决条件
类型	定位标准	验证条件
第一类	趋势末端背驰点	MACD面积/高度背离 或 量能萎缩30%
第二类	第一类后的次级别回抽	回调不破前低/反弹不破前高
第三类	中枢突破回踩确认	回踩幅度＜中枢高度的1/3
扩展情形	中枢延伸≥9段时	按扩展中枢重新计算ZG/ZD


### 2. 根据数据分析技术指标判断趋势（趋势指标、动量指标、市场情绪量化）
#### 2.1 趋势指标
- **均线系统**：5/8/16日均线交叉状态（金叉/死叉/缠绕）
- **MACD**：DIFF-DEA柱状体面积变化，重点观察跨中枢段的柱体背驰

#### 2.2 动量指标
- **RSI**：超买/超卖区间持续时间
- **成交量验证**：突破关键位时量能是否达到20日均量150%

### 3. 市场情绪量化
- **量价健康度**：上涨日平均成交量/下跌日平均成交量比值
- **筹码稳定性**：连续3日换手率＞5%视为异动信号
- **极端情绪**：单日涨跌幅＞7%且成交量创20日新高

## 三、要求综合一、二汇总信息后做出决策，输出规范如下（（markdown格式））
### 1. 关键位标注
- **支撑区间**：最近有效底分型低点±1%、中枢ZD位
- **阻力区间**：最近有效顶分型高点±1%、中枢ZG位
- **趋势通道**：连接最近两个同向笔的高低点绘制动态轨道

### 2. 输出最终操作建议（markdown格式）
</分析开始>
| 场景                | 多头策略                          | 空头策略                          |
|---------------------|-----------------------------------|-----------------------------------|
| 中枢上沿放量突破    | 突破价+1%追涨，止损中枢中轴       | 观望或反抽中枢上沿短空            |
| 中枢下沿缩量跌破    | 反弹至中枢下沿减仓                | 跌破价-1%追空，止损前低           |
| RSI连续X日超买或者超卖（你要给出） | 多头建仓、持仓建议          | 空头建仓、持仓建议    |


**假设现在已有50%仓位，最终策略，参考如下**
- 趋势状态：`当前处于[上涨/下跌/震荡]笔，中枢区间[XX-XX]`
- 关键位置：`支撑[XX-XX] | 阻力[XX-XX]`
- 操作建议：`[多头/空头/观望]策略，建仓区间XX-XX，止损XX`
- X日预期：`看多或者看空概率（满足XX条件则反转），若是你,你会怎么操作，目标收益x%`
- 1、若看多，请给出当前价格、目标价格、收益x%
  2、若看震荡，请给出震荡区间，和操作方式，震荡幅度X%
  3、若看空，请给出当前价格、目标价格、收益x%

</分析结束>


    """
    result = analyzer.analyze_data(df, user_prompt)

    # 打印内容和推理内容
    # 在main函数中添加：
    if result['is_complete']:
        print(f"Token消耗：输入{result['usage']['prompt_tokens']}，输出{result['usage']['completion_tokens']}")
        if result['usage']['total_tokens'] > 4000:
            print("警告：接近token上限，建议简化请求")


        #print("--------------推理内容-------------------------")
        #print("推理内容：", result["reasoning"])

        print("--------------分析结果-------------------------")

        print("分析结果：", result["content"])

    else:
       print("警告：分析结果可能不完整，建议缩小数据范围或简化问题")

if __name__ == "__main__":
    
    print("-----------561560---------------")
    r1test("561560")  # 直接调用同步函数
    print("---------588180-----------------")
    r1test("588180")
    #print("-----------159655----------")
    #r1test("159655")