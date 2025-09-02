# 监控清单：按需求文档定义用于生成报告的对象集合

# A股市场温度 - 指数
INDEXES = [
    {"name": "上证指数", "code": "sh000001"},
    {"name": "创业板指", "code": "sz399006"},
    {"name": "科创50指", "code": "sh000688"},
]

# 市场风格与规模 - 示例ETF（可按需增减）
STYLES = [
    {"category": "大规模/价值", "name": "上证50ETF", "code": "510050"},
    {"category": "大规模/价值", "name": "沪深300ETF", "code": "510300"},
    {"category": "大规模/价值", "name": "红利ETF", "code": "510880"},
    {"category": "大规模/价值", "name": "科创50ETF", "code": "588000"},
    {"category": "中小规模/成长", "name": "中证500ETF", "code": "510500"},
    {"category": "中小规模/成长", "name": "中证1000ETF", "code": "159845"},
    {"category": "中小规模/成长", "name": "科创100ETF", "code": "588190"},
]

# 行业与主题板块 - 仅示例，后续可扩至完整清单
SECTORS = [
    {"etf_name": "券商ETF", "code": "512000", "leaders": ["中信证券", "东方财富"]},
    {"etf_name": "芯片ETF", "code": "512760", "leaders": ["中芯国际", "北方华创"]},
    {"etf_name": "人工智能AI ETF", "code": "560800", "leaders": ["科大讯飞", "浪潮信息"]},
    {"etf_name": "软件ETF", "code": "159852", "leaders": ["金山办公"]},
    {"etf_name": "新能源车ETF", "code": "159806", "leaders": ["宁德时代", "比亚迪"]},
    {"etf_name": "保险主题ETF", "code": "512000", "leaders": ["中国平安"]},
    {"etf_name": "银行ETF", "code": "512800", "leaders": ["招商银行"]},
    {"etf_name": "有色金属ETF", "code": "512400", "leaders": ["紫金矿业"]},
    {"etf_name": "煤炭ETF", "code": "515220", "leaders": ["中国神华"]},
    {"etf_name": "消费ETF", "code": "159928", "leaders": ["贵州茅台"]},
    {"etf_name": "食品饮料ETF", "code": "159843", "leaders": ["五粮液", "泸州老窖"]},
    {"etf_name": "医药ETF", "code": "512010", "leaders": ["恒瑞医药", "药明康德"]},
    {"etf_name": "医疗ETF", "code": "159828", "leaders": ["迈瑞医疗", "爱尔眼科"]},
]

# 风险偏好
RISKS = [
    {"category": "国内避险", "name": "黄金ETF", "code": "518880"},
    {"category": "国内安全", "name": "30年国债ETF", "code": "511260"},
    {"category": "全球避险", "name": "COMEX黄金", "code": "GLOBAL_COMEX_GOLD"},
    {"category": "全球风险锚", "name": "10年期美债收益率", "code": "US10Y"},
    {"category": "做多A股", "name": "YINN富时3倍做多中国", "code": "YINN"},
]

# 全球环境与关联市场
GLOBALS = [
    {"category": "关联圈 (香港)", "indicator": "恒生指数", "code": "HSI"},
    {"category": "关联圈 (香港)", "indicator": "恒生科技指数", "code": "HSTECH"},
    {"category": "环境圈 (美股)", "indicator": "标普500", "code": "^GSPC"},
    {"category": "环境圈 (美股)", "indicator": "纳斯达克100", "code": "^NDX"},
    {"category": "环境圈 (美股)", "indicator": "英伟达(NVDA)", "code": "NVDA"},
    {"category": "环境圈 (美股)", "indicator": "金龙中国指数", "code": "PGJ"},
    {"category": "环境圈 (其他)", "indicator": "美元/离岸CNH", "code": "USDCNH"},
    {"category": "环境圈 (加密货币)", "indicator": "比特币(BTC)", "code": "BTCUSDT"},
    {"category": "环境圈 (加密货币)", "indicator": "以太坊(ETH)", "code": "ETHUSDT"},
]


