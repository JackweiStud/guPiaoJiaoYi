"""预登记写死的常量（含一次性 BAA10Y 映射结果）。"""

# 门 1：油价
OIL_THRESHOLD = 105.0
OIL_STREAK_DAYS = 5

# 门 2：利率
RATE_MA_WINDOW = 20

# 门 3：信用 — 一次性映射结果（见 PREREG；单独 commit 写入）
# 重叠期 2023-11-01 起，OAS=3.6 在经验分布中的分位数 q，以及 BAA10Y 第 q 分位数 τ
CREDIT_OAS_TARGET = 3.6
CREDIT_OVERLAP_START = "2023-11-01"
# 一次性映射写死（预登记规定；非看回测结果后调参）
# 重叠期有效样本 n=747（2023-11-06 ~ 2026-11-03），q 为 rank 分位数
CREDIT_Q = 0.9223560910307899
CREDIT_BAA_THRESHOLD = 1.8
CREDIT_MAPPING_ASOF = "2026-11-03"

# 主样本
SAMPLE_START = "2007-01-01"
# DGS30 停发段：剔除 2002–2006（主样本自 2007，不受影响）
DGS30_EXCLUDE_START = "2002-01-01"
DGS30_EXCLUDE_END = "2006-12-31"

# 交易成本
LISTED_COMMISSION = 0.001  # 场内单边 0.1%
FUND_SUBSCRIBE_FEE = 0.0016  # 539002 申购 0.16%
# 539002 赎回分档假设（官方分档未在本环境核验到完整表，报告中说明）：
# <7 日 1.5%；7–29 日 0.5%；≥30 日 0%
FUND_REDEEM_TIERS = (
    (7, 0.015),
    (30, 0.005),
    (10**9, 0.0),
)

# 随机组 / bootstrap
RANDOM_SEED = 20251105
N_RANDOM_PATHS = 1000
BOOTSTRAP_BLOCK = 20
BOOTSTRAP_N = 1000
BOOTSTRAP_SEED = 20251105

# 信号滞后（交易日）
SIGNAL_LAG_DAYS = 1

# 分段
SEGMENTS = {
    "2008": ("2008-01-01", "2008-12-31"),
    "2011-2012": ("2011-01-01", "2012-12-31"),
    "2018": ("2018-01-01", "2018-12-31"),
    "2020": ("2020-01-01", "2020-12-31"),
    "2022": ("2022-01-01", "2022-12-31"),
    "2023-2025": ("2023-01-01", "2025-12-31"),
    "全样本": (SAMPLE_START, None),
}
