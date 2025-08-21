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
    model: str = Field("deepseek-ai/DeepSeek-R1", description="官方指定模型名称R1")  # 修正模型名称
    max_tokens: int = 1024*160  # 与官方示例一致
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
        self.client = httpx.Client(timeout=2400, verify=False)  # 总超时120秒

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
            print("user_prompt:" + f"{user_prompt}\n")

            print("------------process_response 开始--------------------")

            response = self.client.post(
                f"{self.config.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                json={
                    "messages": [
                        {"role": "system", "content": self.config.system_prompt},
                        #{"role": "user", "content": f"{user_prompt}\n{data_summary}\n样本数据：\n{data_str}"}
                        {"role": "user", "content": f"{user_prompt}\n"}
                    ],
                    "model": self.config.model,
                    "max_tokens": self.config.max_tokens,
                    "temperature": self.config.temperature,
                    "top_p": self.config.top_p,
                    "stream": False,
                    "response_format": {"type": "text"},
                    "stop": ["</分析结束>"]  # 添加停止标记
                },
                timeout=5000  # 适当延长超时时间
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
        api_key="",
        system_prompt="你是一位严谨的ETF量化分析师和交易员,根据用户提供的行情数据给出核心分析和2~5天的建议,默认成功率大于66%，言辞犀利，语言精简"
    )

    # 2. 加载数据
    loader = ETFDataLoader()
    #dataPath = "D:/code-touzi/gitHub/guPiaoJiaoYi/stock_data/588180/588180_Day.csv"
    #dataPath = "/content/guPiaoJiaoYi/stock_data/588180/588180_Day.csv"
    #D:\code-touzi\gitHub\guPiaoJiaoYi\stock_data
    dataPath = f"D:/code-touzi/gitHub/guPiaoJiaoYi/stock_data/{code}/{code}_Day.csv"
    #dataPath = f"/content/guPia
    # oJiaoYi/stock_data/{code}/{code}_60.csv"
    #print(dataPath)
    df = loader.load_etf_data(file_path=dataPath)

    # 3. 创建分析器
    analyzer = DeepSeekAnalyzer(config)

    # 4. 执行分析

    data_sample = df.tail(80)
    data_str = data_sample.to_markdown()
    data_summary = f"数据时间范围：{df['DateTime'].min()} 至 {df['DateTime'].max()}"

    user_prompt = f"""
    你是一位专业且严谨的金融量化分析师，需要基于提供的股票日线数据进行多维度技术分析(如缠论、均线、MACD、RSI、量价关系等)。请严格按照以下流程处理，最终输出指定格式结果：

1、股票的已按照日线排序后的日线输入数据如下
<输入数据>
    某个股票的{data_summary}\n，最新80条样本数据
    <stock_data>
        {data_str}
    </stock_data>

   数据字段包括：
    - 日期(DateTime)
    - 开盘价(OpenValue)
    - 收盘价(CloseValue)
    - 最高价(HighValue)
    - 最低价(LowValue)
    - 成交量(Volume)
    - 换手率(ChangeRate)
</输入数据>

2、请按以下步骤执行和分析：
<分析步骤>
    ### 1. 缠论分析预处理
    在<分型验证>标签中执行：
    a) 处理K线包含关系：
    - 初始方向根据前两根实体K线阴阳判定
    - 合并规则：
    ```python
    if 上涨处理: new_high = max(high1, high2), new_low = max(low1, low2)
    if 下跌处理: new_high = min(high1, high2), new_low = min(low1, low2)
    ```
    - 保留跳空≥3%的原始K线

    b) 分型验证：
    - 顶分型：中间K线高点前后K线高点，且低点为三者最高
    - 底分型：中间K线低点<前后K线低点，且高点为三者最低
    - 过滤条件：分型间隔≥5根K线且波动≥1.5%

    ### 2. 趋势结构判定
    在<中枢计算>标签中：
    a) 验证笔的有效性：
    - 顶底间隔≥5根原始K线
    - 价格波动幅度=(顶高-底低)/底低≥1.5%

    b) 中枢构建：
    - 取连续三笔的极值交集：
    - 在<中枢计算>标签中记录：  
        ```  
        [重叠区间] = 连续三笔的最高低价交集  
        ZG（中枢高点）= 重叠区间最高价
        ZD（中枢低点）= 重叠区间最低价 
        ``` 

    c) 买卖点判决：
    第一类	趋势末端背驰点	MACD面积/高度背离 或 量能萎缩30%
    第二类	第一类后的次级别回抽	回调不破前低/反弹不破前高
    第三类	中枢突破回踩确认	回踩幅度＜中枢高度的1/3
    扩展情形	中枢延伸≥9段时	按扩展中枢重新计算ZG/ZD

    ### 3. 技术指标计算
    a) 均线系统：
    - 计算5/8/16日EMA，标记金叉(5>8>16)或死叉(5<8<16)
    - 计算20日平均Volume

    b) MACD背驰验证：
    - 对比相邻两段DIFF峰值和柱状面积

    c) 动量指标：
    - RSI超买(>70)/超卖(<30)持续时间
    - 突破关键位时量能≥20日均量150%

    ### 4. 市场情绪分析
    - 量价比：上涨日/下跌日平均成交量比值
    - 换手率：连续3日＞5%标记为异动
    - 极端行情：单日涨跌幅＞7%且成交量创20日新高
</分析步骤>


3、请严格按照如下格式进行markdown输出
<输出规范>
在<分析报告>标签内按以下结构输出：

<分析报告>
    ##根据用户提供的X条数据分析，最新收盘时间XX，收盘价为：收盘价

    ### 趋势结构
    - 当前笔方向：[上涨/下跌]笔（持续X天）
    - 中枢区间：ZG-X价格元 | ZD-X价格元
    - 买卖点信号：当前的买卖类型（一/二/三） @对应触发价

    ### 关键位置  
    支撑位：`计算值X~X元`（基于中枢ZD±百分比）
    阻力位：`计算值X~X元`（基于中枢ZG±百分比）

    ### 操作建议
    | 场景                | 多头策略                          | 空头策略                          |
    |---------------------|-----------------------------------|-----------------------------------|
    | 中枢上沿放量突破    | 突破价+X%追涨，止损中枢中轴       | 观望或反抽中枢上沿短空            |
    | 中枢下沿缩量跌破    | 反弹至中枢下沿减仓                | 跌破价X%追空，止损前低           |
    | RSI连续X日超买或者超卖 | 多头建仓、持仓建议          | 空头建仓、持仓建议    |


    **持仓策略（目前100%仓位）**  
    趋势状态：当前处于上涨笔，中枢区间，RSI、MACD
    关键位置：支撑[] | 阻力[]
    操作建议：XX策略，[]加仓，止损XX@X%(对应当前最新收盘价的百分比)
    X日预期：看X概率X%（放量突破X确认），目标X（X%）
    风控提示：XXX

    ```

</分析报告>
    请先执行所有计算验证，确认无误后在<分析报告>标签输出最终结果。所有中间验证过程请记录在对应子标签中。

</输出规范>
"""

    result = analyzer.analyze_data(df, user_prompt)

    # 打印内容和推理内容
    # 在main函数中添加：
    if result['is_complete']:
        print(f"Token消耗：输入{result['usage']['prompt_tokens']}，输出{result['usage']['completion_tokens']}")
        if result['usage']['total_tokens'] > 4000:
            print("警告：接近token上限，建议简化请求")


        #print("--------------推理内容-------------------------")
        print("推理内容：", result["reasoning"])

        print("--------------分析结果-------------------------")

        print("分析结果：", result["content"])

    else:
       print("警告：分析结果可能不完整，建议缩小数据范围或简化问题")

if __name__ == "__main__":
    
    #print("-----------561560---------------")
    #r1test("561560")  # 直接调用同步函数
    #print("---------588180-----------------")
    #r1test("588180")
    #r1test("511090")
    r1test("159843")


    