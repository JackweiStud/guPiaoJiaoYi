# 监控清单：按需求文档定义用于生成报告的对象集合
# 注意：新浪接口代码格式为 sh/sz + 6位数字

# A股市场温度 - 指数
INDEXES = [
    {"name": "上证指数", "code": "sh000001"},
    {"name": "创业板指", "code": "sz399006"},
    {"name": "科创50指", "code": "sh000688"},
]

# 市场风格与规模 - 示例ETF（可按需增减）
# sina_code 用于新浪接口备用
STYLES = [
    {"category": "大规模/价值", "name": "上证50ETF", "code": "510050", "sina_code": "sh510050"},
    {"category": "大规模/价值", "name": "沪深300ETF", "code": "510300", "sina_code": "sh510300"},
    {"category": "大规模/价值", "name": "红利ETF", "code": "510880", "sina_code": "sh510880"},
    {"category": "大规模/价值", "name": "科创50ETF", "code": "588000", "sina_code": "sh588000"},
    {"category": "中小规模/成长", "name": "中证500ETF", "code": "510500", "sina_code": "sh510500"},
    {"category": "中小规模/成长", "name": "中证1000ETF", "code": "159845", "sina_code": "sz159845"},
    {"category": "中小规模/成长", "name": "科创100ETF", "code": "588190", "sina_code": "sh588190"},
]

# 行业与主题板块 - 仅示例，后续可扩至完整清单
# leaders 格式: {"name": 名称, "sina_code": 新浪代码}
SECTORS = [
    {"etf_name": "券商ETF", "code": "512000", "sina_code": "sh512000",
     "leaders": [{"name": "中信证券", "sina_code": "sh600030"}, {"name": "东方财富", "sina_code": "sz300059"}]},
    {"etf_name": "芯片ETF", "code": "512760", "sina_code": "sh512760",
     "leaders": [{"name": "中芯国际", "sina_code": "sh688981"}, {"name": "北方华创", "sina_code": "sz002371"}]},
    {"etf_name": "人工智能AI ETF", "code": "560800", "sina_code": "sh560800",
     "leaders": [{"name": "科大讯飞", "sina_code": "sz002230"}, {"name": "浪潮信息", "sina_code": "sz000977"}]},
    {"etf_name": "软件ETF", "code": "159852", "sina_code": "sz159852",
     "leaders": [{"name": "金山办公", "sina_code": "sh688111"}]},
    {"etf_name": "新能源车ETF", "code": "159806", "sina_code": "sz159806",
     "leaders": [{"name": "宁德时代", "sina_code": "sz300750"}, {"name": "比亚迪", "sina_code": "sz002594"}]},
    {"etf_name": "保险主题ETF", "code": "512070", "sina_code": "sh512070",
     "leaders": [{"name": "中国平安", "sina_code": "sh601318"}]},
    {"etf_name": "银行ETF", "code": "512800", "sina_code": "sh512800",
     "leaders": [{"name": "招商银行", "sina_code": "sh600036"}]},
    {"etf_name": "有色金属ETF", "code": "512400", "sina_code": "sh512400",
     "leaders": [{"name": "紫金矿业", "sina_code": "sh601899"}]},
    {"etf_name": "煤炭ETF", "code": "515220", "sina_code": "sh515220",
     "leaders": [{"name": "中国神华", "sina_code": "sh601088"}]},
    {"etf_name": "消费ETF", "code": "159928", "sina_code": "sz159928",
     "leaders": [{"name": "贵州茅台", "sina_code": "sh600519"}]},
    {"etf_name": "食品饮料ETF", "code": "159843", "sina_code": "sz159843",
     "leaders": [{"name": "五粮液", "sina_code": "sz000858"}, {"name": "泸州老窖", "sina_code": "sz000568"}]},
    {"etf_name": "医药ETF", "code": "512010", "sina_code": "sh512010",
     "leaders": [{"name": "恒瑞医药", "sina_code": "sh600276"}, {"name": "药明康德", "sina_code": "sh603259"}]},
    {"etf_name": "医疗ETF", "code": "159828", "sina_code": "sz159828",
     "leaders": [{"name": "迈瑞医疗", "sina_code": "sz300760"}, {"name": "爱尔眼科", "sina_code": "sz300015"}]},
]

# 风险偏好
RISKS = [
    {"category": "国内避险", "name": "黄金ETF", "code": "518880"},
    {"category": "国内安全", "name": "30年国债ETF", "code": "511090"},
    {"category": "全球避险", "name": "COMEX黄金", "code": "GLOBAL_COMEX_GOLD"},
    {"category": "全球风险锚", "name": "10年期美债收益率", "code": "US10Y"},
    {"category": "做多A股", "name": "YINN富时3倍做多中国", "code": "YINN"},
]

# 全球环境与关联市场
GLOBALS = [
    {"category": "香港", "indicator": "恒生指数", "code": "^HSI"},
    {"category": "香港", "indicator": "恒生科技指数", "code": "HSTECH.HK"},
    {"category": "美股", "indicator": "标普500", "code": "^GSPC"},
    {"category": "美股", "indicator": "纳斯达克100", "code": "^NDX"},
    {"category": "美股", "indicator": "英伟达(NVDA)", "code": "NVDA"},
    {"category": "美股", "indicator": "金龙中国指数", "code": "PGJ"},
    {"category": "汇率", "indicator": "美元/离岸CNH", "code": "CNH=X"},
    {"category": "加密货币", "indicator": "比特币(BTC)", "code": "BTC-USD"},
    {"category": "加密货币", "indicator": "以太坊(ETH)", "code": "ETH-USD"},
]


