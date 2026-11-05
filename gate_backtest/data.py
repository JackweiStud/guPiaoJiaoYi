"""真实数据下载、原样归档与日历对齐（仅允许沿用上一个已发布真实值）。"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

from gate_backtest.constants import SAMPLE_START

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_RAW = os.path.join(ROOT, "data_raw")
CACHE_DIR = os.path.join(ROOT, "cache")

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={cosd}&coed={coed}"

FRED_SERIES = {
    "DCOILBRENTEU": {"cosd": "1987-05-20", "role": "油价 Brent"},
    "DGS30": {"cosd": "1977-02-15", "role": "30年美债收益率"},
    "BAA10Y": {"cosd": "1986-01-02", "role": "BAA-10Y 信用利差代理"},
    "BAMLH0A0HYM2": {"cosd": "1996-12-31", "role": "HY OAS"},
    "DGS3MO": {"cosd": "1981-09-01", "role": "3月美债（现金收益）"},
}


@dataclass
class SeriesMeta:
    series_id: str
    source_url: str
    start_date: str
    end_date: str
    n_rows: int
    missing_days: int
    missing_calendar: str
    downloaded_at: str
    raw_path: str
    notes: str = ""
    carry_forward_days: int = 0
    max_carry_streak: int = 0


@dataclass
class DataBundle:
    prices: Dict[str, pd.DataFrame] = field(default_factory=dict)  # OHLCV, ETF calendar
    fred: Dict[str, pd.Series] = field(default_factory=dict)
    fund_nav: Optional[pd.Series] = None
    meta: List[SeriesMeta] = field(default_factory=list)
    gaps: Dict[str, dict] = field(default_factory=dict)


def _ensure_dirs() -> None:
    os.makedirs(DATA_RAW, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _weekday_missing(index: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp) -> int:
    """按工作日日历统计缺失天数（不含周末；不剔除节假日，故为上界口径）。"""
    all_bdays = pd.bdate_range(start, end)
    present = set(pd.DatetimeIndex(index).normalize())
    return int(sum(1 for d in all_bdays if d not in present))


def download_fred_raw(series_id: str, cosd: str, coed: Optional[str] = None) -> Tuple[pd.Series, SeriesMeta, str]:
    """下载 FRED 公开 CSV，原样写入 data_raw/，返回清洗后的数值序列（仅 to_numeric，不插值）。"""
    _ensure_dirs()
    if coed is None:
        coed = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = FRED_CSV.format(sid=series_id, cosd=cosd, coed=coed)
    downloaded_at = _now_iso()
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    raw_name = f"FRED_{series_id}.csv"
    raw_path = os.path.join(DATA_RAW, raw_name)
    with open(raw_path, "wb") as f:
        f.write(resp.content)

    df = pd.read_csv(raw_path)
    # FRED 列名可能是 observation_date 或 DATE
    date_col = df.columns[0]
    val_col = df.columns[1]
    df[date_col] = pd.to_datetime(df[date_col])
    raw_n = len(df)
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
    # '.' 等会被转为 NaN；这些是发布日历上的缺失点，如实丢掉，不插值
    valid = df.dropna(subset=[val_col]).copy()
    series = valid.set_index(date_col)[val_col].sort_index()
    series.index = pd.DatetimeIndex(series.index).tz_localize(None).normalize()
    series = series[~series.index.duplicated(keep="last")]

    start, end = series.index.min(), series.index.max()
    missing = _weekday_missing(series.index, start, end)
    meta = SeriesMeta(
        series_id=series_id,
        source_url=url,
        start_date=str(start.date()),
        end_date=str(end.date()),
        n_rows=int(len(series)),
        missing_days=missing,
        missing_calendar="工作日 bday（Mon–Fri，未剔除美国节假日；原 CSV 中非数值行已计为缺失）",
        downloaded_at=downloaded_at,
        raw_path=os.path.relpath(raw_path, os.path.dirname(ROOT)),
        notes=f"原 CSV 行数={raw_n}（含非数值）；有效数值行={len(series)}",
    )
    return series.astype(float), meta, raw_path


def download_yahoo_ohlcv(ticker: str, start: str = SAMPLE_START) -> Tuple[pd.DataFrame, SeriesMeta, str]:
    """经 yfinance 拉取 Yahoo 行情，将原样表写入 data_raw/。"""
    _ensure_dirs()
    import yfinance as yf

    downloaded_at = _now_iso()
    # 直接请求足够长历史；auto_adjust=True 得到复权 OHLC
    raw = yf.download(ticker, start=start, progress=False, auto_adjust=True, threads=False)
    if raw is None or raw.empty:
        raise RuntimeError(f"yfinance 未返回 {ticker} 数据")

    # 展平 MultiIndex 列
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]

    raw = raw.copy()
    raw.index = pd.DatetimeIndex(raw.index).tz_localize(None).normalize()
    raw_name = f"YAHOO_{ticker}.csv"
    raw_path = os.path.join(DATA_RAW, raw_name)
    # 原样落盘：下载得到的复权 OHLCV，不做插值/填补
    out = raw.reset_index()
    out.to_csv(raw_path, index=False)

    # 缺失：对照自身起止之间的美股工作日
    start_ts, end_ts = raw.index.min(), raw.index.max()
    missing = _weekday_missing(raw.index, start_ts, end_ts)
    url = f"https://finance.yahoo.com/quote/{ticker}/history"
    meta = SeriesMeta(
        series_id=ticker,
        source_url=url,
        start_date=str(start_ts.date()),
        end_date=str(end_ts.date()),
        n_rows=int(len(raw)),
        missing_days=missing,
        missing_calendar="工作日 bday（相对 Yahoo 返回的起止；未剔除美股休市日，故为上界）",
        downloaded_at=downloaded_at,
        raw_path=os.path.relpath(raw_path, os.path.dirname(ROOT)),
        notes="yfinance auto_adjust=True 复权 OHLCV；CSV 为下载后原表落盘",
    )
    return raw, meta, raw_path


def download_fund_539002() -> Tuple[pd.Series, SeriesMeta, str]:
    """经 akshare 拉取 539002 单位净值，原样 CSV 落盘。"""
    _ensure_dirs()
    import akshare as ak

    downloaded_at = _now_iso()
    df = ak.fund_open_fund_info_em(symbol="539002", indicator="单位净值走势")
    raw_path = os.path.join(DATA_RAW, "FUND_539002_nav.csv")
    df.to_csv(raw_path, index=False)

    date_col = "净值日期" if "净值日期" in df.columns else df.columns[0]
    nav_col = "单位净值" if "单位净值" in df.columns else df.columns[1]
    work = df[[date_col, nav_col]].copy()
    work[date_col] = pd.to_datetime(work[date_col])
    work[nav_col] = pd.to_numeric(work[nav_col], errors="coerce")
    work = work.dropna()
    series = work.set_index(date_col)[nav_col].sort_index()
    series.index = pd.DatetimeIndex(series.index).tz_localize(None).normalize()
    series = series[~series.index.duplicated(keep="last")]

    start_ts, end_ts = series.index.min(), series.index.max()
    missing = _weekday_missing(series.index, start_ts, end_ts)
    meta = SeriesMeta(
        series_id="539002",
        source_url="akshare.fund_open_fund_info_em(symbol='539002', indicator='单位净值走势') / 东方财富基金净值",
        start_date=str(start_ts.date()),
        end_date=str(end_ts.date()),
        n_rows=int(len(series)),
        missing_days=missing,
        missing_calendar="工作日 bday（相对净值序列起止；中国法定节假日未剔除，故为上界）",
        downloaded_at=downloaded_at,
        raw_path=os.path.relpath(raw_path, os.path.dirname(ROOT)),
        notes="场外参考仅用 2024+；每日申购额度按 10000 元",
    )
    return series.astype(float), meta, raw_path


def align_asof(
    signal_on_native: pd.Series,
    target_index: pd.DatetimeIndex,
) -> Tuple[pd.Series, int, int]:
    """
    将原生日历上的信号/数值对齐到目标交易日历：
    每个目标日 t 取「截至 t 的最后一个已发布真实值」。
    不插值、不生成数值。返回 (对齐序列, 沿用天数, 最长连续沿用)。
    """
    s = signal_on_native.dropna().sort_index()
    s.index = pd.DatetimeIndex(s.index).normalize()
    target = pd.DatetimeIndex(target_index).normalize()
    out = s.reindex(target.union(s.index)).sort_index()
    # 标记：目标日是否恰有原生发布
    native_set = set(s.index)
    carried = out.ffill()
    aligned = carried.reindex(target)

    carry_flags = pd.Series([d not in native_set for d in target], index=target)
    # 仅统计「有值且沿用」：首段尚无任何发布的 NaN 不算沿用
    valid = aligned.notna()
    carry_flags = carry_flags & valid
    carry_days = int(carry_flags.sum())

    max_streak = 0
    cur = 0
    for flag in carry_flags.tolist():
        if flag:
            cur += 1
            max_streak = max(max_streak, cur)
        else:
            cur = 0
    return aligned, carry_days, max_streak


def _load_fred_from_raw(series_id: str) -> Tuple[pd.Series, Optional[dict]]:
    """从已归档原样 CSV 读取 FRED 序列（不插值）。"""
    raw_path = os.path.join(DATA_RAW, f"FRED_{series_id}.csv")
    if not os.path.isfile(raw_path):
        raise FileNotFoundError(raw_path)
    df = pd.read_csv(raw_path)
    date_col, val_col = df.columns[0], df.columns[1]
    df[date_col] = pd.to_datetime(df[date_col])
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
    valid = df.dropna(subset=[val_col]).copy()
    series = valid.set_index(date_col)[val_col].sort_index()
    series.index = pd.DatetimeIndex(series.index).tz_localize(None).normalize()
    series = series[~series.index.duplicated(keep="last")].astype(float)
    return series, None


def _load_yahoo_from_raw(ticker: str) -> pd.DataFrame:
    raw_path = os.path.join(DATA_RAW, f"YAHOO_{ticker}.csv")
    if not os.path.isfile(raw_path):
        raise FileNotFoundError(raw_path)
    df = pd.read_csv(raw_path)
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    df.index = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
    df = df[~df.index.duplicated(keep="last")]
    return df


def _load_fund_from_raw() -> pd.Series:
    raw_path = os.path.join(DATA_RAW, "FUND_539002_nav.csv")
    if not os.path.isfile(raw_path):
        raise FileNotFoundError(raw_path)
    df = pd.read_csv(raw_path)
    date_col = "净值日期" if "净值日期" in df.columns else df.columns[0]
    nav_col = "单位净值" if "单位净值" in df.columns else df.columns[1]
    work = df[[date_col, nav_col]].copy()
    work[date_col] = pd.to_datetime(work[date_col])
    work[nav_col] = pd.to_numeric(work[nav_col], errors="coerce")
    work = work.dropna()
    series = work.set_index(date_col)[nav_col].sort_index()
    series.index = pd.DatetimeIndex(series.index).tz_localize(None).normalize()
    series = series[~series.index.duplicated(keep="last")].astype(float)
    return series


def load_from_raw() -> DataBundle:
    """
    复用已归档的原样 CSV（不重新下载）。元数据优先读 `_download_meta.json`。
    用于 v2 在不改动 v1 数据文件的前提下复现；缺文件则报错。
    """
    _ensure_dirs()
    bundle = DataBundle()
    meta_path = os.path.join(DATA_RAW, "_download_meta.json")
    meta_by_id: Dict[str, dict] = {}
    if os.path.isfile(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            for m in json.load(f):
                meta_by_id[m["series_id"]] = m

    for sid, info in FRED_SERIES.items():
        series, _ = _load_fred_from_raw(sid)
        bundle.fred[sid] = series
        if sid in meta_by_id:
            md = meta_by_id[sid]
            meta = SeriesMeta(
                series_id=md["series_id"],
                source_url=md["source_url"],
                start_date=md["start_date"],
                end_date=md["end_date"],
                n_rows=int(md["n_rows"]),
                missing_days=int(md["missing_days"]),
                missing_calendar=md["missing_calendar"],
                downloaded_at=md["downloaded_at"],
                raw_path=md["raw_path"],
                notes=md.get("notes", "") + "；load_from_raw 复用",
                carry_forward_days=int(md.get("carry_forward_days", 0)),
                max_carry_streak=int(md.get("max_carry_streak", 0)),
            )
        else:
            start, end = series.index.min(), series.index.max()
            missing = _weekday_missing(series.index, start, end)
            meta = SeriesMeta(
                series_id=sid,
                source_url=FRED_CSV.format(sid=sid, cosd=info["cosd"], coed=""),
                start_date=str(start.date()),
                end_date=str(end.date()),
                n_rows=int(len(series)),
                missing_days=missing,
                missing_calendar="工作日 bday（Mon–Fri，未剔除美国节假日；原 CSV 中非数值行已计为缺失）",
                downloaded_at="(from raw)",
                raw_path=os.path.relpath(os.path.join(DATA_RAW, f"FRED_{sid}.csv"), os.path.dirname(ROOT)),
                notes=f"角色={info['role']}；load_from_raw",
            )
        bundle.meta.append(meta)
        bundle.gaps[sid] = {
            "missing_days": meta.missing_days,
            "missing_calendar": meta.missing_calendar,
            "start": meta.start_date,
            "end": meta.end_date,
            "n_rows": meta.n_rows,
        }

    for ticker in ("SOXX", "SMH"):
        px = _load_yahoo_from_raw(ticker)
        bundle.prices[ticker] = px
        if ticker in meta_by_id:
            md = meta_by_id[ticker]
            meta = SeriesMeta(
                series_id=md["series_id"],
                source_url=md["source_url"],
                start_date=md["start_date"],
                end_date=md["end_date"],
                n_rows=int(md["n_rows"]),
                missing_days=int(md["missing_days"]),
                missing_calendar=md["missing_calendar"],
                downloaded_at=md["downloaded_at"],
                raw_path=md["raw_path"],
                notes=(md.get("notes", "") + "；load_from_raw 复用"),
                carry_forward_days=int(md.get("carry_forward_days", 0)),
                max_carry_streak=int(md.get("max_carry_streak", 0)),
            )
        else:
            start_ts, end_ts = px.index.min(), px.index.max()
            missing = _weekday_missing(px.index, start_ts, end_ts)
            meta = SeriesMeta(
                series_id=ticker,
                source_url=f"https://finance.yahoo.com/quote/{ticker}/history",
                start_date=str(start_ts.date()),
                end_date=str(end_ts.date()),
                n_rows=int(len(px)),
                missing_days=missing,
                missing_calendar="工作日 bday（相对 Yahoo 返回的起止；未剔除美股休市日，故为上界）",
                downloaded_at="(from raw)",
                raw_path=os.path.relpath(os.path.join(DATA_RAW, f"YAHOO_{ticker}.csv"), os.path.dirname(ROOT)),
                notes="load_from_raw",
            )
        bundle.meta.append(meta)
        bundle.gaps[ticker] = {
            "missing_days": meta.missing_days,
            "missing_calendar": meta.missing_calendar,
            "start": meta.start_date,
            "end": meta.end_date,
            "n_rows": meta.n_rows,
        }

    try:
        nav = _load_fund_from_raw()
        bundle.fund_nav = nav
        if "539002" in meta_by_id:
            md = meta_by_id["539002"]
            meta = SeriesMeta(
                series_id=md["series_id"],
                source_url=md["source_url"],
                start_date=md["start_date"],
                end_date=md["end_date"],
                n_rows=int(md["n_rows"]),
                missing_days=int(md["missing_days"]),
                missing_calendar=md["missing_calendar"],
                downloaded_at=md["downloaded_at"],
                raw_path=md["raw_path"],
                notes=(md.get("notes", "") + "；load_from_raw 复用"),
                carry_forward_days=int(md.get("carry_forward_days", 0)),
                max_carry_streak=int(md.get("max_carry_streak", 0)),
            )
        else:
            start_ts, end_ts = nav.index.min(), nav.index.max()
            missing = _weekday_missing(nav.index, start_ts, end_ts)
            meta = SeriesMeta(
                series_id="539002",
                source_url="akshare / 东方财富基金净值",
                start_date=str(start_ts.date()),
                end_date=str(end_ts.date()),
                n_rows=int(len(nav)),
                missing_days=missing,
                missing_calendar="工作日 bday（相对净值序列起止；中国法定节假日未剔除，故为上界）",
                downloaded_at="(from raw)",
                raw_path=os.path.relpath(os.path.join(DATA_RAW, "FUND_539002_nav.csv"), os.path.dirname(ROOT)),
                notes="load_from_raw",
            )
        bundle.meta.append(meta)
        bundle.gaps["539002"] = {
            "missing_days": meta.missing_days,
            "missing_calendar": meta.missing_calendar,
            "start": meta.start_date,
            "end": meta.end_date,
            "n_rows": meta.n_rows,
        }
    except Exception as exc:  # noqa: BLE001
        bundle.gaps["539002"] = {"error": str(exc), "missing": "全部不可用"}

    return bundle


def load_all(force_download: bool = True, prefer_raw: bool = False) -> DataBundle:
    """下载全部真实数据并归档原样 CSV。prefer_raw=True 时优先复用 data_raw。"""
    if prefer_raw and os.path.isfile(os.path.join(DATA_RAW, "FRED_DGS30.csv")):
        return load_from_raw()

    _ensure_dirs()
    bundle = DataBundle()
    coed = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for sid, info in FRED_SERIES.items():
        series, meta, _ = download_fred_raw(sid, info["cosd"], coed)
        meta.notes = (meta.notes + f"；角色={info['role']}").strip("；")
        bundle.fred[sid] = series
        bundle.meta.append(meta)
        bundle.gaps[sid] = {
            "missing_days": meta.missing_days,
            "missing_calendar": meta.missing_calendar,
            "start": meta.start_date,
            "end": meta.end_date,
            "n_rows": meta.n_rows,
        }

    for ticker in ("SOXX", "SMH"):
        px, meta, _ = download_yahoo_ohlcv(ticker, SAMPLE_START)
        bundle.prices[ticker] = px
        bundle.meta.append(meta)
        bundle.gaps[ticker] = {
            "missing_days": meta.missing_days,
            "missing_calendar": meta.missing_calendar,
            "start": meta.start_date,
            "end": meta.end_date,
            "n_rows": meta.n_rows,
        }

    try:
        nav, meta, _ = download_fund_539002()
        bundle.fund_nav = nav
        bundle.meta.append(meta)
        bundle.gaps["539002"] = {
            "missing_days": meta.missing_days,
            "missing_calendar": meta.missing_calendar,
            "start": meta.start_date,
            "end": meta.end_date,
            "n_rows": meta.n_rows,
        }
    except Exception as exc:  # noqa: BLE001 — 如实记录缺口
        bundle.gaps["539002"] = {"error": str(exc), "missing": "全部不可用"}

    # 元数据快照（便于 RESULTS）
    meta_path = os.path.join(DATA_RAW, "_download_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump([asdict(m) for m in bundle.meta], f, ensure_ascii=False, indent=2)

    return bundle


def copy_raw_to_artifacts(artifacts_root: str = "/opt/cursor/artifacts/data_raw") -> List[str]:
    """复制 data_raw 到 artifacts。"""
    import shutil
    import time

    for attempt in range(5):
        try:
            os.makedirs(artifacts_root, exist_ok=True)
            break
        except BlockingIOError:
            time.sleep(0.5 * (attempt + 1))
    else:
        os.makedirs(artifacts_root, exist_ok=True)

    copied = []
    for name in sorted(os.listdir(DATA_RAW)):
        src = os.path.join(DATA_RAW, name)
        if os.path.isfile(src):
            dst = os.path.join(artifacts_root, name)
            shutil.copy2(src, dst)
            copied.append(dst)
    return copied
