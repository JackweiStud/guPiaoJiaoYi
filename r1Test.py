import os
import requests

url = "https://api.siliconflow.cn/v1/chat/completions"

payload = {
    "model": "Pro/deepseek-ai/DeepSeek-R1",
    "stream": False,
    "max_tokens": 4096,
    "temperature": 0.4,
    "top_p": 0.7,
    "top_k": 50,
    "frequency_penalty": 0.5,
    "n": 1,
    "messages": [
        {
            "content": "经济分析师",
            "role": "system"
        },
        {
            "content": "\\u8bf7\\u5206\\u6790\\u6700\\u8fd1\\u8d70\\u52bf\\uff0c\\u7ed9\\u51fa\\u672a\\u67653\\u5929\\u7684\\u64cd\\u4f5c\\u5efa\\u8bae\\n\\u6570\\u636e\\u65f6\\u95f4\\u8303\\u56f4\\uff1a2024-09-20 00:00:00 \\u81f3 2025-03-14 00:00:00\\n\\u6837\\u672c\\u6570\\u636e\\uff1a\\n|     | DateTime            |   OpenValue |   CloseValue |   HighValue |   LowValue |   Volume |   ChangeRate |\\n|----:|:--------------------|------------:|-------------:|------------:|-----------:|---------:|-------------:|\\n| 109 | 2025-03-10 00:00:00 |       1.164 |        1.163 |       1.171 |      1.146 | 36072034 |         4.98 |\\n| 110 | 2025-03-11 00:00:00 |       1.147 |        1.158 |       1.161 |      1.144 | 34232739 |         4.72 |\\n| 111 | 2025-03-12 00:00:00 |       1.164 |        1.15  |       1.17  |      1.15  | 33358712 |         4.6  |\\n| 112 | 2025-03-13 00:00:00 |       1.147 |        1.126 |       1.153 |      1.12  | 39166034 |         5.4  |\\n| 113 | 2025-03-14 00:00:00 |       1.126 |        1.146 |       1.146 |      1.124 | 40925221 |         5.65 |",
            "role": "user"
        }
    ]
}
headers = {
    "Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY', '')}",
    "Content-Type": "application/json"
}

response = requests.request("POST", url, json=payload, headers=headers)

print(response.text)


"""gitHub\
{"id":"01959f02771a00d3061e10d22e90dfc6",
"object":"chat.completion",
"created":1742129493,
"model":"Pro/deepseek-ai/DeepSeek-R1",
"choices":[{"index":0,
"message":{
"role":"assistant",
"content":"您好！看起来您提到了一些参数数据（xxx），
但具体内容似乎没有完整显示或上传成功。为了更好地帮助您分析或解答相关问题，
能否请您补充具体的参数数据或详细描述您的需求？例如：\n\n- 数据类型（经济指标、财务数据、实验参数等）\n
- 需要分析的目标（预测、对比、趋势分析等）\n- 任何额外的背景信息\n\n
这将有助于我为您提供更精准的分析和建议！",


"reasoning_content":"嗯，用户给了一个参数数据，但具体内容被省略了，只显示为“xxx”。
首先，我需要确定用户的需求是什么。他们可能是在进行某种数据分析、经济预测，
或者是需要根据给定的参数生成报告或建议。不过由于参数数据被隐藏了，
我需要先请求用户提供更详细的信息才能继续分析。\n\n
接下来，我应该考虑用户可能的背景。他们可能是学生、研究人员，或者商业分析师。
不同的身份可能需要不同的分析方法。例如，学生可能需要基础的解释和步骤指导，
而商业分析师可能更关注实际应用和决策支持。\n\n另外，用户可能没有正确输入数据，
或者误操作导致信息被隐藏。这时候需要友好地提醒他们补充数据，同时保持专业和耐心。确保回复清晰，
避免使用过于技术化的术语，除非确定用户具备相关知识。\n\n还要考虑可能的后续问题。一旦用户提供了具体参数，
我需要准备好处理不同类型的数据，比如时间序列、横截面数据，或者是宏观经济指标等。可能需要使用统计方法、
回归分析、预测模型等工具来分析这些数据。\n\n最后，确保回复的结构合理，先确认问题，再请求补充信息，
并表达愿意进一步帮助的意愿。这样可以有效促进沟通，帮助用户解决问题。"},
"finish_reason":"stop"}],
"usage":
{
"prompt_tokens":12,"completion_tokens":336,"total_tokens":348},"system_fingerprint":""}

"""