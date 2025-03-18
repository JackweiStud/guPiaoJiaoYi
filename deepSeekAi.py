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
    system_prompt: str = "你是一位专业的ETF市场分析师和交易员,言辞犀利，语言精简, 根据用户提供的行情数据给出核心分析和2~5天的建议,默认成功率大于66%"
    model: str = Field("Pro/deepseek-ai/DeepSeek-R1", description="官方指定模型名称R1")  # 修正模型名称
    max_tokens: int = 4096  # 与官方示例一致
    temperature: float = 0.2
    top_p: float = 0.7



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
            data_sample = df.tail(50)
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
    dataPath = f"/content/guPiaoJiaoYi/stock_data/{code}/{code}_Day.csv"
    #print(dataPath)
    df = loader.load_etf_data(file_path=dataPath)

    # 3. 创建分析器
    analyzer = DeepSeekAnalyzer(config)

    # 4. 执行分析
    user_prompt = f"""
        一、将给你一段数据, 数据包括(DateTime,OpenValue,CloseValue,HighValue,LowValue,Volume,ChangeRate)
        二、可参考以下步骤分析：
            1. 识别关键趋势 (使用缠论（笔、顶底分型（涉及合并）、线段、中枢、3类买卖点）、均线、macd、RSI技术指标)
            2. 评估市场情绪 (基于成交量、换手率变化)
            3. 给出具体建议 (明确买卖区间、阻力、支持位)]
            4. 结合你的实际策略，明确2~3天看多还是看空
        三、最终按照markDown格式输出, [注意：结论请用</分析结束>标记]"""

    result = analyzer.analyze_data(df, user_prompt)

    # 打印内容和推理内容
    # 在main函数中添加：
    if result['is_complete']:
        print(f"Token消耗：输入{result['usage']['prompt_tokens']}，输出{result['usage']['completion_tokens']}")
        if result['usage']['total_tokens'] > 4000:
            print("警告：接近token上限，建议简化请求")


        print("--------------推理内容-------------------------")
        print("推理内容：", result["reasoning"])
        print("--------------分析结果-------------------------")

        print("分析结果：", result["content"])

    else:
       print("警告：分析结果可能不完整，建议缩小数据范围或简化问题")

if __name__ == "__main__":
    
    print("-----------561560---------------")
    r1test("561560")  # 直接调用同步函数
    print("---------588180-----------------")
    r1test("588180")
    print("-----------159655----------")
    r1test("159655")