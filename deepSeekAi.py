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
    model: str = Field("deepseek-ai/DeepSeek-V3.1", description="官方指定模型名称R1")  # 修正模型名称deepseek-ai/DeepSeek-V3.1  deepseek-ai/DeepSeek-R1
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
        # 优化超时设置：分层超时策略
        self.client = httpx.Client(
            timeout=httpx.Timeout(
                connect=10.0,      # 连接超时：10秒
                read=400.0,        # 读取超时：300秒
                write=30.0,        # 写入超时：30秒
                pool=60.0          # 连接池超时：60秒
            ),
            verify=False,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10
            )
        )

    @retry(
        stop=stop_after_attempt(2),  # 增加到3次重试
        wait=wait_exponential(multiplier=2, min=4, max=30),  # 指数退避：4-30秒
        reraise=True
    )
    def analyze_data(self, df: pd.DataFrame, user_prompt: str) -> Dict[str, str]:
        """
        同步版本的数据分析方法
        :return: 包含内容和推理内容的字典
        """
        try:
            data_sample = df.tail(80)
            data_str = data_sample.to_markdown()
            data_summary = f"数据时间范围：{df['DateTime'].min()} 至 {df['DateTime'].max()}"
            print("content" + f"{data_summary}\n样本数据：\n{data_str}")
            #print("user_prompt:" + f"{user_prompt}\n")

            print("------------process_response 开始--------------------")
            print(f"开始调用DeepSeek API，超时设置：连接10s，读取300s")

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
                    "stop": ["</分析结束>"]
                }
                # 移除timeout参数，使用httpx.Timeout配置
            )
            response.raise_for_status()

            response_data = response.json()
            print("API调用成功，开始处理响应...")

            temp = self._process_response(response_data)
            print("------------_process_response 完成--------------------")
            #print(temp)

            return temp

        except httpx.ConnectTimeout:
            print("连接超时：无法连接到DeepSeek API服务器")
            return {"content": "连接超时：无法连接到API服务器，请检查网络连接", "reasoning_content": "网络连接问题", "is_complete": False}
        except httpx.ReadTimeout:
            print("读取超时：API响应时间过长")
            return {"content": "读取超时：API响应时间过长，建议简化请求内容", "reasoning_content": "响应超时", "is_complete": False}
        except httpx.HTTPStatusError as e:
            print(f"HTTP状态错误：{e.response.status_code} - {e.response.text}")
            return {"content": f"API请求失败: {e.response.status_code} {e.response.text}", "reasoning_content": "HTTP错误", "is_complete": False}
        except httpx.RequestError as e:
            print(f"请求错误：{str(e)}")
            return {"content": f"网络请求错误: {str(e)}", "reasoning_content": "网络问题", "is_complete": False}
        except Exception as e:
            print(f"未知错误：{str(e)}")
            return {"content": f"分析失败: {str(e)}", "reasoning_content": "系统错误", "is_complete": False}
        finally:
            self.client.close()

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
def extract_analysis_report(content: str) -> str:
    """
    从返回内容中提取分析报告部分
    优先提取 <分析报告> 和 </分析报告> 之间的内容
    如果没有结束标签，则提取从 <分析报告> 到结尾的内容
    """
    if not content:
        return ""
    
    # 查找开始标签
    start_tag = "<分析报告>"
    end_tag = "</分析报告>"
    
    start_idx = content.find(start_tag)
    if start_idx == -1:
        return content  # 没有开始标签，返回原内容
    
    # 从开始标签后开始查找
    start_pos = start_idx + len(start_tag)
    
    # 查找结束标签
    end_idx = content.find(end_tag, start_pos)
    
    if end_idx != -1:
        # 找到结束标签，提取标签间内容
        return content[start_pos:end_idx].strip()
    else:
        # 没有结束标签，提取从开始标签到结尾
        return content[start_pos:].strip()


def extract_position_strategy(content: str) -> str:
    """
    从返回内容中提取持仓策略部分
    提取从 "**持仓策略（目前100%仓位）**" 到结尾的内容
    如果没有找到开始标记，则返回空字符串
    """
    if not content:
        return ""
    
    # 查找开始标记
    start_marker = "**持仓策略（目前100%仓位）**"
    
    start_idx = content.find(start_marker)
    if start_idx == -1:
        return ""  # 没有找到开始标记，返回空字符串
    
    # 从开始标记后开始提取到结尾
    start_pos = start_idx + len(start_marker)
    
    # 提取从开始标记到结尾的内容
    return content[start_pos:].strip()

def aiDeepSeekAnly(code):
   
    # 1. 配置参数
    config = DeepSeekConfig(
        api_key="sk-rmfaxultndibttfndnfxmwryoatbjwtbzyvumrbiamjhhbns",
        system_prompt="你是一位严谨的ETF量化分析师和交易员,根据用户提供的行情数据给出核心分析和2~5天的建议,默认成功率大于66%，言辞犀利，语言精简"
    )

    # 2. 加载数据
    loader = ETFDataLoader()
    # 使用相对路径，基于脚本所在目录
    script_dir = Path(__file__).parent
    dataPath = script_dir / "stock_data" / code / f"{code}_Day.csv"
    
    try:
        print(f"开始加载{code}数据文件：{dataPath}")
        df = loader.load_etf_data(file_path=dataPath)
        print(f"数据加载成功，共{len(df)}条记录")
    except FileNotFoundError:
        print(f"错误：找不到数据文件 {dataPath}")
        return ""
    except Exception as e:
        print(f"数据加载失败：{str(e)}")
        return ""

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


        3、请严格按照如下格式进行markdown输出,输出规范如下
        在<分析报告> 。。。 </分析报告>标签内按以下结构输出：

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



        请先执行所有计算验证，确认无误后在<分析报告></分析报告>  标签输出最终结果。所有中间验证过程请记录在对应子标签中。

              
        """

    import time
    start_time = time.time()
    
    print(f"开始调用DeepSeek API分析{code}...")
    print(f"超时配置：连接10s，读取300s，总超时320s")
    
    try:
        result = analyzer.analyze_data(df, user_prompt)
        
        if result['is_complete']:
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            print(f"DeepSeek API调用成功！")
            print(f"⏱总耗时：{elapsed_time:.2f}秒")
            
            if 'usage' in result and result['usage']:
                print(f"Token消耗：输入{result['usage'].get('prompt_tokens', 'N/A')}，输出{result['usage'].get('completion_tokens', 'N/A')}")
                total_tokens = result['usage'].get('total_tokens', 0)
                if total_tokens > 8000:
                    print("警告：接近token上限，建议简化请求")
            else:
                print("警告：未获取到Token使用信息")

            print("--------------分析结果-------------------------")
            analysis_report = extract_analysis_report(result["content"])
            
            if analysis_report:
                print(f"{code}分析完成，已提取分析报告")
                print(analysis_report)
                return analysis_report
            else:
                print(f"{code}分析完成，但未提取到有效报告")
                print(result["content"])
                return result["content"]
        else:
            print(f"{code}分析结果不完整")
            print(f"原因：{result.get('reasoning_content', '未知')}")
            
            # 打印不完整result的详细信息
            print("不完整Result详情:")
            if isinstance(result, dict):
                for key, value in result.items():
                    if key == 'content':
                        print(f"{key}: {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
                    else:
                        print(f"{key}: {value}")
            else:
                print(f"  Result: {result}")
            
            return ""
            
    except Exception as e:
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"{code}分析过程中发生异常：{str(e)}")
        print(f"异常发生时间：{elapsed_time:.2f}秒")
        return ""


if __name__ == "__main__":
    
    #print("-----------561560---------------")
    #aiDeepSeekAnly("561560")  # 直接调用同步函数
    #print("---------588180-----------------")
    #aiDeepSeekAnly("588180")
    print("---------511090-----------------")
    aiDeepSeekAnly("511090")
    print("---------159843-----------------")
    aiDeepSeekAnly("159843")


    