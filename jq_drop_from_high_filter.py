# -*- coding: utf-8 -*-
# ============================================================
# 版本: v15-20260806
# 相对 v14:
#   1) 增加作者信息：rouser / 569125965@qq.com（脚本头、报告页眉页脚、运行输出）
# 相对 v13:
#   - HTML 报告在「排序总览」上方增加窗口期大盘日K（默认上证指数+成交量）
#   - 标注窗口收益/最大回撤/高低点日期，方便对照个股
# 相对 v12:
#   - Notebook 可视化进度条（四阶段共用一条；不支持则 ASCII）
# ------------------------------------------------------------
# 作者: rouser / 569125965@qq.com
# ------------------------------------------------------------
# 【脚本功能说明】
# 1) 选股目标：
#    找出“无大雷 + 阶段超跌 + 低点后已拐头回升 + 回升放量”的A股，
#    类似江淮汽车这种：下行后开始反弹、且成交量放大的标的。
# 2) 核心规则（默认）：
#    - 近约8个月（168个交易日）窗口内寻找高点与后低
#    - 高点->后低回撤 >= 55%（曾超跌）
#    - 后低->现价反弹 >= 10%（已回升）
#    - 现价相对高点回撤仍在 35%~75%（没涨回去，也没跌废）
#    - 近5日均量 / 下跌期均量 >= 1.2（回升放量）
#    - 排除 ST/退市风险名、停牌、次新、北交所、高负债/资不抵债等
# 3) 排序：
#    量能放大倍数 -> 反弹幅度 -> 超跌深度（越大越靠前）
# 4) 板块对比：
#    取申万一级行业，生成板块归一日K，并计算：
#    窗口收益、回升段相对强弱、日收益相关性、契合标签
# 5) 输出：
#    - 研究环境用可视化进度条显示进度，不刷屏图文
#    - 生成可下载 HTML 报告：
#      a. 窗口期大盘日K（对照用）
#      b. 顶部“排序总览”（含个股/板块迷你走势，可点详情跳转）
#      c. 下方每只股票完整详情（指标卡 + 摘要 + 个股日K/板块日K/成交量）
#      d. 详情页可“回到顶部”
# 6) 使用方法：
#    复制到聚宽「投资研究」Notebook 整段运行；
#    确认首行输出版本号为 v15-20260806；
#    结束后下载生成的 oversold_rebound_report_v15_*.html
# 用法: 聚宽「投资研究」整段粘贴，确认版本号 v15-20260806
# ============================================================

from jqdata import *
import pandas as pd
import numpy as np
from datetime import datetime, date as date_cls, timedelta
from io import BytesIO
import base64
import warnings
import sys
import time as time_module

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from IPython.display import display, HTML, FileLink

VERSION = 'v15-20260806'
AUTHOR_NAME = 'rouser'
AUTHOR_EMAIL = '569125965@qq.com'
AUTHOR_LINE = '%s / %s' % (AUTHOR_NAME, AUTHOR_EMAIL)
warnings.filterwarnings('ignore', message='.*tight_layout.*')
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
# 无界面后端，避免生成图时在笔记本弹出/刷屏
try:
    plt.switch_backend('Agg')
except Exception:
    pass


class ProgressBar(object):
    """研究环境可视化进度条（优先 HTML 原地刷新；失败则回退 ASCII）。
    同一实例可 reset 切换阶段，避免 Notebook 叠出多条进度条。
    """

    def __init__(self, total=1, desc='进度'):
        self.total = max(int(total), 1)
        self.desc = desc
        self.n = 0
        self.info = ''
        self._t0 = time_module.time()
        self._stage_t0 = self._t0
        self._handle = None
        self._use_html = True
        self._last_draw = 0.0
        self._display_id = 'jq_progress_%s' % int(time_module.time() * 1000)
        try:
            self._handle = display(HTML(self._html()), display_id=self._display_id)
        except Exception:
            self._use_html = False
            self._print_text()

    def reset(self, total, desc=None, info=''):
        """切换到新阶段，复用同一条进度条。"""
        self.total = max(int(total), 1)
        if desc is not None:
            self.desc = desc
        self.n = 0
        self.info = info if info is not None else ''
        self._stage_t0 = time_module.time()
        self._last_draw = 0.0
        self._render(force=True)

    def _html(self):
        pct = 100.0 * self.n / self.total
        elapsed = time_module.time() - self._stage_t0
        eta = (elapsed / self.n * (self.total - self.n)) if self.n > 0 else 0
        return """
        <div style="margin:8px 0;padding:10px 12px;background:#121821;border:1px solid #2f3e52;
                    border-radius:10px;color:#e7ecf3;font-family:Menlo,Consolas,monospace;">
          <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px;">
            <span style="color:#4da3ff;font-weight:700;">{desc}</span>
            <span style="color:#9aabbf;">{n}/{total} ({pct:.1f}%)</span>
          </div>
          <div style="height:14px;background:#1a2332;border-radius:999px;overflow:hidden;border:1px solid #2a3a4f;">
            <div style="height:100%;width:{pct:.2f}%;background:linear-gradient(90deg,#2381e9,#3dd68c);
                        transition:width .15s linear;"></div>
          </div>
          <div style="margin-top:6px;font-size:11px;color:#9aabbf;">
            本阶段已用 {elapsed:.0f}s · 预计剩余 {eta:.0f}s
            <span style="color:#c5d0de;">{info}</span>
          </div>
        </div>
        """.format(
            desc=self.desc, n=self.n, total=self.total, pct=pct,
            elapsed=elapsed, eta=eta, info=(' · ' + self.info) if self.info else ''
        )

    def _print_text(self):
        pct = 100.0 * self.n / self.total
        bar_len = 30
        filled = int(bar_len * self.n / self.total)
        bar = '#' * filled + '-' * (bar_len - filled)
        msg = '\r[{desc}] |{bar}| {n}/{total} {pct:5.1f}% {info}'.format(
            desc=self.desc, bar=bar, n=self.n, total=self.total, pct=pct, info=self.info
        )
        sys.stdout.write(msg)
        sys.stdout.flush()

    def _render(self, force=False):
        now = time_module.time()
        # 节流：最快约 8 次/秒，减少 Notebook 卡顿；force / 完成时强制刷新
        if (not force) and (self.n < self.total) and (now - self._last_draw < 0.12):
            return
        self._last_draw = now
        if self._use_html and self._handle is not None:
            try:
                self._handle.update(HTML(self._html()))
            except Exception:
                self._use_html = False
                self._print_text()
        else:
            self._print_text()

    def set(self, n, info=''):
        self.n = max(0, min(int(n), self.total))
        if info is not None:
            self.info = str(info)
        force = (self.n >= self.total) or (self.n == 0)
        self._render(force=force)

    def update(self, step=1, info=''):
        self.set(self.n + step, info=info)

    def close(self, info='完成'):
        self.set(self.total, info=info)
        if not self._use_html:
            sys.stdout.write('\n')
            sys.stdout.flush()
# ===================== 参数 =====================
LOOKBACK_MAX_DAYS = 168
MIN_DD = 0.55
MIN_BOUNCE = 0.10
MIN_CUR_DD = 0.35
MAX_CUR_DD = 0.75
MIN_DAYS_AFTER_LOW = 3
RECENT_VOL_DAYS = 5
MIN_VOL_AMPLIFY = 1.2
MIN_LIST_DAYS = 120
EXCLUDE_BJ = True
EXCLUDE_KCB = False
EXCLUDE_CYB = False
CHECK_CODE = '600418.XSHG'
MAX_SHOW = 30
INDUSTRY_TYPE = 'sw_l1'
INDUSTRY_PEER_LIMIT = 40
# 报告顶部对照用大盘指数（聚宽指数代码）
MARKET_INDEX = '000001.XSHG'
MARKET_NAME = '上证指数'
# =================================================

plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.facecolor'] = '#0f1419'
plt.rcParams['axes.facecolor'] = '#1a2332'
plt.rcParams['savefig.facecolor'] = '#0f1419'
plt.rcParams['text.color'] = '#e7ecf3'
plt.rcParams['axes.labelcolor'] = '#c5d0de'
plt.rcParams['xtick.color'] = '#9aabbf'
plt.rcParams['ytick.color'] = '#9aabbf'
plt.rcParams['axes.edgecolor'] = '#2f3e52'

_INDUSTRY_CACHE = {}


def to_date(d):
    ts = pd.Timestamp(d)
    return date_cls(ts.year, ts.month, ts.day)


def to_date_str(d):
    return to_date(d).strftime('%Y-%m-%d')


def get_trade_date():
    days = get_trade_days(end_date=datetime.now().date(), count=5)
    print('最近交易日样本:', list(days), '类型:', type(days[-1]))
    return to_date(days[-1])


def is_st_or_risk_name(name):
    if name is None:
        return True
    s = str(name)
    return ('ST' in s[:4]) or ('退' in s) or s.startswith('PT')


def fetch_price(codes, end_date, count, fields):
    if isinstance(codes, str):
        codes = [codes]
    df = get_price(
        codes,
        end_date=to_date_str(end_date),
        count=count,
        fields=fields,
        panel=False
    )
    if df is None or df.empty:
        return pd.DataFrame()
    if 'time' not in df.columns:
        df = df.reset_index()
        for cand in ('time', 'date', 'index'):
            if cand in df.columns:
                if cand != 'time':
                    df = df.rename(columns={cand: 'time'})
                break
    if 'code' not in df.columns and len(codes) == 1:
        df['code'] = codes[0]
    return df


def get_universe(asof):
    asof = to_date(asof)
    asof_str = to_date_str(asof)
    s1 = get_all_securities(types=['stock'], date=asof_str)
    s2 = get_all_securities(types=['stock'], date=asof)
    s3 = get_all_securities(types=['stock'])
    print('get_all_securities(str/date/none):',
          0 if s1 is None else len(s1),
          0 if s2 is None else len(s2),
          0 if s3 is None else len(s3))

    stocks = None
    for cand in (s1, s2, s3):
        if cand is not None and not cand.empty:
            stocks = cand.copy()
            break
    if stocks is None or stocks.empty:
        return []

    stocks = stocks[(stocks['start_date'] <= asof) & (stocks['end_date'] >= asof)]
    cutoff = asof - timedelta(days=MIN_LIST_DAYS)
    keep_idx = [code for code, row in stocks.iterrows() if to_date(row['start_date']) <= cutoff]
    stocks = stocks.loc[keep_idx]

    codes = []
    for code, row in stocks.iterrows():
        c = str(code)
        if EXCLUDE_BJ and (c.endswith('.XBJ') or c.startswith(('83', '87', '88', '43', '92'))):
            continue
        if EXCLUDE_KCB and c.startswith('688'):
            continue
        if EXCLUDE_CYB and c.startswith('300'):
            continue
        if is_st_or_risk_name(row['display_name']):
            continue
        codes.append(code)
    print('初筛(去次新/ST/北交等):', len(codes), '样本:', codes[:5])
    return codes


def filter_paused(codes, asof):
    out = []
    for i in range(0, len(codes), 500):
        df = fetch_price(codes[i:i + 500], asof, 1, ['paused', 'volume'])
        if df.empty:
            continue
        df = df[(df['paused'] == 0) & (df['volume'] > 0)]
        out.extend(df['code'].tolist())
    return out


def filter_financial_risk(codes, asof):
    if not codes:
        return []
    q = query(
        valuation.code,
        valuation.market_cap,
        balance.total_assets,
        balance.total_liability,
        balance.equities_parent_company_owners,
        income.net_profit,
    ).filter(valuation.code.in_(codes))
    fund = get_fundamentals(q, date=to_date_str(asof))
    if fund is None or fund.empty:
        return codes
    fund = fund.set_index('code')
    debt = fund['total_liability'] / fund['total_assets'].replace(0, np.nan)
    loss_limit = -fund['market_cap'] * 1e8 * 0.3
    ok = (
        (fund['equities_parent_company_owners'] > 0) &
        (debt < 0.90) &
        (fund['market_cap'] > 15) &
        (fund['net_profit'] > loss_limit)
    )
    return fund.index[ok].tolist()


def calc_vol_amplify(window, idx_peak, idx_low):
    vol = window['volume'].astype(float).values
    n = len(vol)
    recent = vol[-RECENT_VOL_DAYS:]
    recent_mean = float(np.nanmean(recent)) if len(recent) else np.nan
    down = vol[idx_peak:idx_low + 1]
    if len(down) >= 5 and np.nanmean(down) > 0:
        base_mean = float(np.nanmean(down))
        base_tag = 'downtrend'
    else:
        base = vol[max(0, n - RECENT_VOL_DAYS - 60): n - RECENT_VOL_DAYS]
        base_mean = float(np.nanmean(base)) if len(base) and np.nanmean(base) > 0 else np.nan
        base_tag = 'ma60'
    if not np.isfinite(recent_mean) or not np.isfinite(base_mean) or base_mean <= 0:
        return np.nan, recent_mean, base_mean, base_tag
    return recent_mean / base_mean, recent_mean, base_mean, base_tag


def get_stock_industry(code, asof):
    try:
        info = get_industry(code, date=to_date_str(asof))
        if not info:
            return None, '未知行业'
        node = info.get(code, info)
        sw = node.get(INDUSTRY_TYPE) or node.get('sw_l1') or node.get('jq_l1')
        if not sw:
            for v in node.values():
                if isinstance(v, dict) and 'industry_code' in v:
                    sw = v
                    break
        if not sw:
            return None, '未知行业'
        return sw.get('industry_code'), sw.get('industry_name', '未知行业')
    except Exception as e:
        print('行业获取失败', code, e)
        return None, '未知行业'


def get_industry_ohlc(industry_code, asof, exclude_code=None):
    """
    板块日K：对成分股 OHLC 按各自窗口首日收盘价归一后等权平均
    返回 DataFrame: time, open, high, low, close
    """
    if industry_code is None:
        return pd.DataFrame()
    cache_key = (industry_code, to_date_str(asof), 'ohlc')
    if cache_key in _INDUSTRY_CACHE:
        return _INDUSTRY_CACHE[cache_key].copy()

    try:
        peers = list(get_industry_stocks(industry_code, date=to_date_str(asof)))
    except Exception:
        peers = []
    if exclude_code and exclude_code in peers:
        peers = [p for p in peers if p != exclude_code]
    if not peers:
        _INDUSTRY_CACHE[cache_key] = pd.DataFrame()
        return pd.DataFrame()
    if len(peers) > INDUSTRY_PEER_LIMIT:
        peers = peers[:INDUSTRY_PEER_LIMIT]

    px = fetch_price(peers, asof, LOOKBACK_MAX_DAYS + 5, ['open', 'high', 'low', 'close'])
    if px.empty:
        _INDUSTRY_CACHE[cache_key] = pd.DataFrame()
        return pd.DataFrame()

    # 各股按首日收盘归一，再等权
    frames = []
    for code, g in px.groupby('code'):
        g = g.sort_values('time')
        base = float(g['close'].iloc[0])
        if base <= 0:
            continue
        tmp = g[['time']].copy()
        for col in ('open', 'high', 'low', 'close'):
            tmp[col] = g[col].astype(float) / base
        frames.append(tmp.set_index('time'))
    if not frames:
        _INDUSTRY_CACHE[cache_key] = pd.DataFrame()
        return pd.DataFrame()

    panel = pd.concat(frames, axis=0, keys=range(len(frames)))
    # MultiIndex=(样本号, time) -> 按 time 等权
    ind = panel.groupby(level=1)[['open', 'high', 'low', 'close']].mean()
    ind['high'] = ind[['open', 'high', 'close']].max(axis=1)
    ind['low'] = ind[['open', 'low', 'close']].min(axis=1)
    ind = ind.reset_index()
    # 兼容不同pandas对index列命名
    if 'time' not in ind.columns:
        ind = ind.rename(columns={ind.columns[0]: 'time'})
    _INDUSTRY_CACHE[cache_key] = ind.copy()
    return ind


def calc_industry_fit(stock_window, ind_df, idx_peak, idx_low):
    out = {
        'corr': np.nan,
        'stock_ret_win': np.nan,
        'ind_ret_win': np.nan,
        'stock_ret_bounce': np.nan,
        'ind_ret_bounce': np.nan,
        'rel_strength': np.nan,
        'fit_label': '板块数据不足',
    }
    if ind_df is None or ind_df.empty:
        return out

    s = stock_window[['time', 'close']].copy()
    s['time'] = pd.to_datetime(s['time'])
    ind = ind_df.copy()
    ind['time'] = pd.to_datetime(ind['time'])
    m = pd.merge(s, ind[['time', 'close']].rename(columns={'close': 'ind_close'}), on='time', how='inner').dropna()
    if len(m) < 20:
        return out

    m['s_n'] = m['close'] / m['close'].iloc[0]
    m['i_n'] = m['ind_close'] / m['ind_close'].iloc[0]
    out['stock_ret_win'] = float(m['s_n'].iloc[-1] - 1.0)
    out['ind_ret_win'] = float(m['i_n'].iloc[-1] - 1.0)

    corr = m['close'].pct_change().corr(m['ind_close'].pct_change())
    out['corr'] = float(corr) if corr == corr else np.nan

    trough_time = pd.to_datetime(stock_window['time'].iloc[idx_low])
    mb = m[m['time'] >= trough_time]
    if len(mb) >= 3:
        out['stock_ret_bounce'] = float(mb['close'].iloc[-1] / mb['close'].iloc[0] - 1.0)
        out['ind_ret_bounce'] = float(mb['ind_close'].iloc[-1] / mb['ind_close'].iloc[0] - 1.0)
        out['rel_strength'] = out['stock_ret_bounce'] - out['ind_ret_bounce']

    c = out['corr']
    rs = out['rel_strength']
    if not np.isfinite(c):
        out['fit_label'] = '板块数据不足'
    elif c >= 0.6:
        out['fit_label'] = '高相关·强于板块' if (rs == rs and rs > 0.05) else (
            '高相关·弱于板块' if (rs == rs and rs < -0.05) else '高相关·同步板块')
    elif c >= 0.3:
        out['fit_label'] = '中相关·强于板块' if (rs == rs and rs > 0.05) else (
            '中相关·弱于板块' if (rs == rs and rs < -0.05) else '中相关·大致同步')
    else:
        out['fit_label'] = '低相关·走势独立'
    return out


def build_summary(name, info):
    slope_pct = info['down_slope_pct']
    slope_txt = '偏陡' if slope_pct >= 1.0 else ('中等' if slope_pct >= 0.5 else '偏缓')
    ind_part = ''
    if info.get('industry_name'):
        ind_part = (
            '；板块[{ind}]窗口收益{ind_ret:.1f}%/个股{stk_ret:.1f}%，'
            '回升段相对强弱{rs:+.1f}pct，相关性{corr:.2f}（{fit}）'
        ).format(
            ind=info.get('industry_name', '-'),
            ind_ret=(info.get('ind_ret_win') or 0) * 100,
            stk_ret=(info.get('stock_ret_win') or 0) * 100,
            rs=(info.get('rel_strength') or 0) * 100,
            corr=info.get('corr') if info.get('corr') == info.get('corr') else 0,
            fit=info.get('fit_label', '-'),
        )
    return (
        '{name}: 高点{peak:.2f}元({peak_date})，下行{decline_days}个交易日'
        '（回撤{max_dd:.1f}%，日均{slope_pct:.2f}个百分点/{slope_price:.2f}元，{slope_txt}），'
        '低点{trough:.2f}元({trough_date})；已回升{recovery_days}日，反弹{bounce:.1f}%至'
        '{close:.2f}元，距高点仍跌{cur_dd:.1f}%，近{rv}日量能为下跌期{vol:.2f}倍'
        '{ind_part}'
    ).format(
        name=name,
        peak=info['peak_high'], peak_date=info['peak_date'],
        decline_days=info['decline_days'], max_dd=info['max_dd_pct'],
        slope_pct=info['down_slope_pct'], slope_price=info['down_slope_price'],
        slope_txt=slope_txt, trough=info['trough_low'], trough_date=info['trough_date'],
        recovery_days=info['days_since_low'], bounce=info['bounce_pct'],
        close=info['last_close'], cur_dd=info['cur_dd_pct'],
        rv=RECENT_VOL_DAYS, vol=info['vol_amplify'], ind_part=ind_part,
    )


def score_one(g):
    g = g.sort_values('time').reset_index(drop=True)
    need = {'open', 'high', 'low', 'close', 'volume'}
    if len(g) < 30 or not need.issubset(set(g.columns)):
        return None

    window = g.iloc[-LOOKBACK_MAX_DAYS:].reset_index(drop=True)
    idx_peak = int(np.nanargmax(window['high'].values))
    peak = float(window['high'].iloc[idx_peak])
    if peak <= 0:
        return None

    after = window.iloc[idx_peak:]
    if len(after) < MIN_DAYS_AFTER_LOW + 2:
        return None
    idx_low_rel = int(np.nanargmin(after['low'].values))
    idx_low = idx_peak + idx_low_rel
    trough = float(after['low'].iloc[idx_low_rel])
    if trough <= 0 or idx_low <= idx_peak:
        return None

    days_since_low = len(window) - 1 - idx_low
    if days_since_low < MIN_DAYS_AFTER_LOW:
        return None

    last_close = float(window['close'].iloc[-1])
    max_dd = 1.0 - trough / peak
    bounce = last_close / trough - 1.0
    cur_dd = 1.0 - last_close / peak
    decline_days = int(idx_low - idx_peak)
    if decline_days <= 0:
        return None
    if max_dd < MIN_DD or bounce < MIN_BOUNCE:
        return None
    if cur_dd < MIN_CUR_DD or cur_dd > MAX_CUR_DD:
        return None

    vol_amp, vol_recent, vol_base, vol_tag = calc_vol_amplify(window, idx_peak, idx_low)
    if not np.isfinite(vol_amp) or vol_amp < MIN_VOL_AMPLIFY:
        return None

    return {
        'peak_high': round(peak, 3),
        'trough_low': round(trough, 3),
        'last_close': round(last_close, 3),
        'max_dd_pct': round(max_dd * 100, 2),
        'bounce_pct': round(bounce * 100, 2),
        'cur_dd_pct': round(cur_dd * 100, 2),
        'vol_amplify': round(float(vol_amp), 2),
        'vol_recent': int(vol_recent) if np.isfinite(vol_recent) else None,
        'vol_base': int(vol_base) if np.isfinite(vol_base) else None,
        'vol_base_type': vol_tag,
        'decline_days': decline_days,
        'days_since_high': int(len(window) - 1 - idx_peak),
        'days_since_low': int(days_since_low),
        'down_slope_pct': round((max_dd * 100.0) / decline_days, 3),
        'down_slope_price': round((peak - trough) / float(decline_days), 3),
        'peak_date': to_date_str(window['time'].iloc[idx_peak]),
        'trough_date': to_date_str(window['time'].iloc[idx_low]),
        'idx_peak': idx_peak,
        'idx_low': idx_low,
        '_window': window,
    }


def draw_candles(ax, x, o, h, l, c, width=0.6):
    """兼容旧matplotlib的手工K线"""
    for i in range(len(x)):
        up = c[i] >= o[i]
        color = '#3dd68c' if up else '#ff6b6b'
        ax.vlines(x[i], l[i], h[i], color=color, linewidth=0.8, zorder=2)
        body_low = min(o[i], c[i])
        body_h = abs(c[i] - o[i])
        if body_h < 1e-8:
            body_h = max((h[i] - l[i]) * 0.02, 1e-6)
        ax.add_patch(Rectangle(
            (x[i] - width / 2.0, body_low),
            width, body_h,
            facecolor=color, edgecolor=color, linewidth=0.6, zorder=3, alpha=0.95
        ))


def fig_to_base64(fig):
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('ascii')


def fetch_market_ohlc(asof, count=LOOKBACK_MAX_DAYS):
    """取窗口期大盘日K（OHLCV）。"""
    df = fetch_price(
        [MARKET_INDEX], asof, count,
        ['open', 'high', 'low', 'close', 'volume']
    )
    if df is None or df.empty:
        return pd.DataFrame()
    g = df.copy()
    if 'code' in g.columns:
        g = g[g['code'] == MARKET_INDEX]
    g = g.sort_values('time').reset_index(drop=True)
    if len(g) > count:
        g = g.iloc[-count:].reset_index(drop=True)
    return g


def calc_market_stats(df):
    """窗口收益、峰值回撤、高低点日期。"""
    if df is None or df.empty or len(df) < 5:
        return None
    c = df['close'].astype(float).values
    h = df['high'].astype(float).values
    l = df['low'].astype(float).values
    times = pd.to_datetime(df['time'])
    ret = float(c[-1] / c[0] - 1.0) if c[0] else float('nan')
    # 用收盘价滚动峰值回撤
    peak_so_far = np.maximum.accumulate(c)
    dd = 1.0 - c / peak_so_far
    max_dd = float(np.nanmax(dd))
    idx_hi = int(np.nanargmax(h))
    idx_lo = int(np.nanargmin(l))
    # 若低点在高点前，仍保留真实高低点；另找高点后的最低点作「峰后回撤」参考
    after = l[idx_hi:]
    idx_lo_after = idx_hi + int(np.nanargmin(after)) if len(after) else idx_lo
    peak_to_trough = float(1.0 - l[idx_lo_after] / h[idx_hi]) if h[idx_hi] else float('nan')
    return {
        'ret_pct': round(ret * 100, 2) if ret == ret else None,
        'max_dd_pct': round(max_dd * 100, 2) if max_dd == max_dd else None,
        'peak_to_trough_pct': round(peak_to_trough * 100, 2) if peak_to_trough == peak_to_trough else None,
        'start': float(c[0]),
        'end': float(c[-1]),
        'high': float(h[idx_hi]),
        'low': float(l[idx_lo]),
        'high_date': to_date_str(times.iloc[idx_hi]),
        'low_date': to_date_str(times.iloc[idx_lo]),
        'start_date': to_date_str(times.iloc[0]),
        'end_date': to_date_str(times.iloc[-1]),
        'n': len(df),
        'idx_hi': idx_hi,
        'idx_lo': idx_lo,
        'idx_lo_after': idx_lo_after,
    }


def plot_market_kline(asof, return_base64=True):
    """
    绘制窗口期大盘日K + 成交量。
    返回 (base64_png 或 None, stats_dict 或 None)
    """
    df = fetch_market_ohlc(asof, LOOKBACK_MAX_DAYS)
    stats = calc_market_stats(df)
    if stats is None:
        return None, None

    times = pd.to_datetime(df['time'])
    x = np.arange(len(df))
    o = df['open'].astype(float).values
    h = df['high'].astype(float).values
    l = df['low'].astype(float).values
    c = df['close'].astype(float).values
    vol = df['volume'].astype(float).values if 'volume' in df.columns else np.zeros(len(df))

    fig = plt.figure(figsize=(11.8, 4.6))
    gs = fig.add_gridspec(2, 1, height_ratios=[2.6, 1.0], hspace=0.08)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0], sharex=ax1)

    draw_candles(ax1, x, o, h, l, c, width=0.65)
    ax1.axvline(stats['idx_hi'], color='#ff6b6b', ls='--', lw=1, alpha=0.85)
    ax1.axvline(stats['idx_lo_after'], color='#3dd68c', ls='--', lw=1, alpha=0.85)
    ax1.axvspan(stats['idx_hi'], stats['idx_lo_after'], color='#ff6b6b', alpha=0.05)
    ax1.set_ylabel('指数点位')
    ax1.grid(True, alpha=0.18, color='#6b7c93')
    ax1.tick_params(labelbottom=False)
    ret_s = ('%+.2f%%' % stats['ret_pct']) if stats.get('ret_pct') is not None else 'N/A'
    dd_s = ('%.2f%%' % stats['max_dd_pct']) if stats.get('max_dd_pct') is not None else 'N/A'
    pt_s = ('%.2f%%' % stats['peak_to_trough_pct']) if stats.get('peak_to_trough_pct') is not None else 'N/A'
    ax1.set_title(
        '大盘对照  %s（%s）  |  %s ~ %s  |  窗口收益 %s  |  收盘最大回撤 %s  |  峰→谷 %s' % (
            MARKET_NAME, MARKET_INDEX,
            stats['start_date'], stats['end_date'],
            ret_s, dd_s, pt_s
        ),
        loc='left', fontsize=12, color='#e7ecf3', pad=8
    )
    # 高低点标注
    ax1.annotate(
        '高 %.0f' % stats['high'],
        xy=(stats['idx_hi'], stats['high']),
        xytext=(0, 8), textcoords='offset points',
        color='#ff6b6b', fontsize=8, ha='center'
    )
    ax1.annotate(
        '低 %.0f' % float(l[stats['idx_lo_after']]),
        xy=(stats['idx_lo_after'], float(l[stats['idx_lo_after']])),
        xytext=(0, -12), textcoords='offset points',
        color='#3dd68c', fontsize=8, ha='center'
    )

    delta = np.diff(c)
    delta = np.concatenate([[0.0], delta])
    colors = np.where(delta >= 0, '#3dd68c', '#ff6b6b')
    ax2.bar(x, vol, color=colors, width=0.7, alpha=0.8)
    ax2.set_ylabel('成交量')
    ax2.grid(True, alpha=0.15, color='#6b7c93')
    ticks = np.linspace(0, len(x) - 1, num=6, dtype=int)
    ax2.set_xticks(ticks)
    ax2.set_xticklabels([times.iloc[i].strftime('%Y-%m-%d') for i in ticks], fontsize=8)

    fig.subplots_adjust(left=0.07, right=0.985, top=0.90, bottom=0.10, hspace=0.10)
    b64 = fig_to_base64(fig) if return_base64 else None
    plt.close(fig)
    return b64, stats


def market_panel_html(img_b64, stats):
    """排序总览上方的大盘对照面板。"""
    if not img_b64 or not stats:
        return """
        <div class="market-panel" id="top">
          <div class="market-head">
            <div class="market-title">窗口期大盘对照</div>
            <div class="market-sub">未能获取 %s（%s）行情，跳过本图。</div>
          </div>
        </div>
        """ % (_esc(MARKET_NAME), _esc(MARKET_INDEX))

    ret_s = ('%+.2f%%' % stats['ret_pct']) if stats.get('ret_pct') is not None else 'N/A'
    dd_s = ('%.2f%%' % stats['max_dd_pct']) if stats.get('max_dd_pct') is not None else 'N/A'
    pt_s = ('%.2f%%' % stats['peak_to_trough_pct']) if stats.get('peak_to_trough_pct') is not None else 'N/A'
    ret_cls = 'green' if (stats.get('ret_pct') or 0) >= 0 else 'red'
    return """
    <div class="market-panel" id="top">
      <div class="market-head">
        <div>
          <div class="market-title">窗口期大盘对照 · {name}</div>
          <div class="market-sub">
            {start} ~ {end}（{n} 个交易日）· 与下方个股同一回看窗口，便于对照大盘环境
          </div>
        </div>
        <div class="market-metrics">
          <div class="mm"><div class="lab">窗口收益</div><div class="val {ret_cls}">{ret}</div></div>
          <div class="mm"><div class="lab">收盘最大回撤</div><div class="val red">{dd}</div></div>
          <div class="mm"><div class="lab">峰→谷</div><div class="val red">{pt}</div></div>
          <div class="mm"><div class="lab">高点 / 低点</div><div class="val small">{hi} / {lo}</div></div>
        </div>
      </div>
      <img class="chart" src="data:image/png;base64,{img}" alt="market-kline"/>
    </div>
    """.format(
        name=_esc(MARKET_NAME),
        start=_esc(stats['start_date']), end=_esc(stats['end_date']), n=stats['n'],
        ret=_esc(ret_s), dd=_esc(dd_s), pt=_esc(pt_s), ret_cls=ret_cls,
        hi=_esc(stats['high_date']), lo=_esc(stats['low_date']),
        img=img_b64
    )


def plot_stock_card(rank, info, asof, return_base64=False, show=False):
    """个股日K + 板块日K + 成交量；默认不在笔记本显示，只用于生成HTML"""
    window = info['_window']
    times = pd.to_datetime(window['time'])
    x = np.arange(len(window))
    o = window['open'].astype(float).values
    h = window['high'].astype(float).values
    l = window['low'].astype(float).values
    c = window['close'].astype(float).values
    vol = window['volume'].astype(float).values
    idx_peak = info['idx_peak']
    idx_low = info['idx_low']

    ind_df = info.get('_ind_df')
    ind_aligned = None
    if ind_df is not None and not ind_df.empty:
        ind = ind_df.copy()
        ind['time'] = pd.to_datetime(ind['time'])
        m = pd.DataFrame({'time': times})
        m = pd.merge(m, ind, on='time', how='left')
        if m[['open', 'high', 'low', 'close']].notna().all(axis=1).sum() >= 20:
            ind_aligned = m

    fig = plt.figure(figsize=(11.8, 7.2))
    gs = fig.add_gridspec(3, 1, height_ratios=[2.2, 2.0, 1.0], hspace=0.08)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0], sharex=ax1)
    ax3 = fig.add_subplot(gs[2, 0], sharex=ax1)

    # 个股K
    draw_candles(ax1, x, o, h, l, c, width=0.65)
    ax1.axvline(idx_peak, color='#ff6b6b', ls='--', lw=1, alpha=0.85)
    ax1.axvline(idx_low, color='#3dd68c', ls='--', lw=1, alpha=0.85)
    ax1.axvspan(idx_peak, idx_low, color='#ff6b6b', alpha=0.05)
    ax1.axvspan(idx_low, x[-1], color='#3dd68c', alpha=0.06)
    ax1.set_ylabel('个股价格')
    ax1.grid(True, alpha=0.18, color='#6b7c93')
    ax1.tick_params(labelbottom=False)
    ax1.set_title(
        '%s  %s  |  %s  |  %s' % (
            info['code'], info['name'],
            info.get('industry_name', '-'),
            info.get('fit_label', '-')
        ),
        loc='left', fontsize=13, color='#e7ecf3', pad=8
    )

    # 板块K
    if ind_aligned is not None:
        io = ind_aligned['open'].astype(float).values
        ih = ind_aligned['high'].astype(float).values
        il = ind_aligned['low'].astype(float).values
        ic = ind_aligned['close'].astype(float).values
        # 用前值填充少量缺口，避免K线断裂太狠
        for arr in (io, ih, il, ic):
            mask = ~np.isfinite(arr)
            if mask.any():
                s = pd.Series(arr).fillna(method='ffill').fillna(method='bfill')
                arr[:] = s.values
        draw_candles(ax2, x, io, ih, il, ic, width=0.65)
        ax2.set_ylabel('板块归一K')
    else:
        ax2.text(0.5, 0.5, '板块K线数据不足', ha='center', va='center',
                 transform=ax2.transAxes, color='#9aabbf')
        ax2.set_ylabel('板块归一K')
    ax2.axvline(idx_peak, color='#ff6b6b', ls='--', lw=1, alpha=0.7)
    ax2.axvline(idx_low, color='#3dd68c', ls='--', lw=1, alpha=0.7)
    ax2.grid(True, alpha=0.18, color='#6b7c93')
    ax2.tick_params(labelbottom=False)

    # 成交量（兼容旧numpy）
    delta = np.diff(c)
    delta = np.concatenate([[0.0], delta])
    colors = np.where(delta >= 0, '#3dd68c', '#ff6b6b')
    ax3.bar(x, vol, color=colors, width=0.7, alpha=0.8)
    ax3.set_ylabel('成交量')
    ax3.grid(True, alpha=0.15, color='#6b7c93')

    # x轴日期标签
    ticks = np.linspace(0, len(x) - 1, num=6, dtype=int)
    ax3.set_xticks(ticks)
    ax3.set_xticklabels([times.iloc[i].strftime('%Y-%m-%d') for i in ticks], fontsize=8)

    metrics = (
        'RANK #%02d   量能 %.2fx   反弹 %.1f%%   超跌 %.1f%%   现回撤 %.1f%%   相关 %s   相对强弱 %s'
    ) % (
        rank, info['vol_amplify'], info['bounce_pct'], info['max_dd_pct'], info['cur_dd_pct'],
        ('%.2f' % info['corr']) if info.get('corr') == info.get('corr') else 'N/A',
        ('%+.1f pct' % (info['rel_strength'] * 100)) if info.get('rel_strength') == info.get('rel_strength') else 'N/A'
    )
    fig.text(0.01, 0.01, metrics, fontsize=9, color='#9aabbf')
    # 不用 tight_layout，避免 sharex + GridSpec 警告
    fig.subplots_adjust(left=0.07, right=0.985, top=0.93, bottom=0.08, hspace=0.10)

    b64 = None
    if return_base64:
        b64 = fig_to_base64(fig)
    if show:
        display(fig)
    plt.close(fig)
    return b64


def _fmt_metrics(info):
    corr = info.get('corr')
    corr_s = ('%.2f' % corr) if corr == corr else 'N/A'
    rs = info.get('rel_strength')
    rs_s = ('%+.1f' % (rs * 100)) if rs == rs else 'N/A'
    ind_ret = info.get('ind_ret_win')
    ind_ret_s = ('%+.1f%%' % (ind_ret * 100)) if ind_ret == ind_ret else 'N/A'
    stk_ret = info.get('stock_ret_win')
    stk_ret_s = ('%+.1f%%' % (stk_ret * 100)) if stk_ret == stk_ret else 'N/A'
    return corr_s, rs_s, ind_ret_s, stk_ret_s


def plot_mini_pair(info):
    """总览表用的两个迷你走势图：个股收盘 / 板块收盘（归一）"""
    window = info['_window']
    c = window['close'].astype(float).values
    idx_peak = info['idx_peak']
    idx_low = info['idx_low']
    x = np.arange(len(c))
    s_norm = c / c[0] * 100.0 if c[0] else c

    i_norm = None
    ind_df = info.get('_ind_df')
    if ind_df is not None and not ind_df.empty:
        times = pd.to_datetime(window['time'])
        ind = ind_df.copy()
        ind['time'] = pd.to_datetime(ind['time'])
        m = pd.merge(pd.DataFrame({'time': times}), ind[['time', 'close']], on='time', how='left')
        series = m['close'].fillna(method='ffill').fillna(method='bfill')
        if series.notna().sum() >= 5 and float(series.iloc[0]) != 0:
            i_norm = (series.astype(float) / float(series.iloc[0]) * 100.0).values

    fig, axes = plt.subplots(1, 2, figsize=(3.6, 1.15))
    for ax in axes:
        ax.set_facecolor('#1a2332')
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        for spine in ax.spines.values():
            spine.set_color('#2f3e52')

    axes[0].plot(x, s_norm, color='#4da3ff', lw=1.2)
    axes[0].axvline(idx_peak, color='#ff6b6b', lw=0.7, alpha=0.9)
    axes[0].axvline(idx_low, color='#3dd68c', lw=0.7, alpha=0.9)
    axes[0].set_title('个股', fontsize=8, color='#9aabbf', pad=2)

    if i_norm is not None:
        axes[1].plot(x, i_norm, color='#f0b429', lw=1.2)
        axes[1].axvline(idx_peak, color='#ff6b6b', lw=0.7, alpha=0.8)
        axes[1].axvline(idx_low, color='#3dd68c', lw=0.7, alpha=0.8)
    else:
        axes[1].text(0.5, 0.5, 'N/A', ha='center', va='center', color='#667788', fontsize=9,
                     transform=axes[1].transAxes)
    axes[1].set_title('板块', fontsize=8, color='#9aabbf', pad=2)

    fig.subplots_adjust(left=0.02, right=0.98, top=0.78, bottom=0.08, wspace=0.08)
    b64 = fig_to_base64(fig)
    plt.close(fig)
    return b64


def _esc(s):
    """简易HTML转义，避免名称里特殊字符弄坏页面"""
    if s is None:
        return ''
    s = str(s)
    return (s.replace('&', '&amp;')
             .replace('<', '&lt;')
             .replace('>', '&gt;')
             .replace('"', '&quot;'))


def summary_table_html(rows):
    """
    排序总览（div列表，不用table，兼容性更好）
    含迷你走势 + 详情锚点跳转
    """
    items = []
    for r in rows:
        corr_s, rs_s, ind_ret_s, stk_ret_s = _fmt_metrics(r)
        anchor = 'detail-%02d' % r['rank']
        items.append("""
        <div class="ov-row">
          <div class="ov-rank">#{rank:02d}</div>
          <div class="ov-name">
            <div class="n1">{code}</div>
            <div class="n2">{name}</div>
            <div class="n3">{industry}</div>
          </div>
          <div class="ov-mini"><img src="data:image/png;base64,{mini}" alt="mini"/></div>
          <div class="ov-m"><div class="lab">量能</div><div class="val blue">{vol:.2f}x</div></div>
          <div class="ov-m"><div class="lab">反弹</div><div class="val green">{bounce:.1f}%</div></div>
          <div class="ov-m"><div class="lab">超跌</div><div class="val red">{dd:.1f}%</div></div>
          <div class="ov-m"><div class="lab">距高点</div><div class="val">{cur:.1f}%</div></div>
          <div class="ov-m"><div class="lab">窗口个股/板块</div><div class="val small">{stk} / {ind}</div></div>
          <div class="ov-m"><div class="lab">相关/强弱</div><div class="val small">{corr} / {rs}</div></div>
          <div class="ov-act"><a class="btn" href="#{anchor}">详情</a></div>
        </div>
        """.format(
            rank=r['rank'],
            code=_esc(r['code']),
            name=_esc(r['name']),
            industry=_esc(r.get('industry_name', '-')),
            mini=r.get('mini_b64', ''),
            vol=r['vol_amplify'], bounce=r['bounce_pct'], dd=r['max_dd_pct'],
            cur=r['cur_dd_pct'], stk=_esc(stk_ret_s), ind=_esc(ind_ret_s),
            corr=_esc(corr_s), rs=_esc(rs_s + ' pct'), anchor=anchor
        ))

    return """
    <div id="overview" class="overview">
      <div class="overview-head">
        <div>
          <div class="overview-title">排序总览</div>
          <div class="overview-sub">上方为大盘窗口期日K对照；先看列表比较，再点「详情」跳到下方完整K线；任一详情页可点「回到顶部」返回大盘与总览。</div>
        </div>
        <div class="overview-count">共 {n} 只</div>
      </div>
      <div class="ov-head">
        <div class="ov-rank">排名</div>
        <div class="ov-name">股票</div>
        <div class="ov-mini">个股 / 板块</div>
        <div class="ov-m">量能</div>
        <div class="ov-m">反弹</div>
        <div class="ov-m">超跌</div>
        <div class="ov-m">距高点</div>
        <div class="ov-m">窗口收益</div>
        <div class="ov-m">相关强弱</div>
        <div class="ov-act">操作</div>
      </div>
      {items}
    </div>
    """.format(n=len(rows), items='\n'.join(items))


def stock_block_html(rank, info, img_b64):
    corr_s, rs_s, ind_ret_s, stk_ret_s = _fmt_metrics(info)
    anchor = 'detail-%02d' % rank
    return """
    <div class="card" id="{anchor}">
      <div class="card-head">
        <div class="title">#{rank:02d}&nbsp; {code}&nbsp; {name}</div>
        <div class="right-actions">
          <span class="tag">{industry} · {fit}</span>
          <a class="btn back" href="#top">回到顶部</a>
        </div>
      </div>
      <div class="metrics">
        <div class="metric"><div class="k">量能放大</div><div class="v blue">{vol:.2f}x</div></div>
        <div class="metric"><div class="k">回升反弹</div><div class="v green">{bounce:.1f}%</div></div>
        <div class="metric"><div class="k">超跌深度</div><div class="v red">{dd:.1f}%</div></div>
        <div class="metric"><div class="k">距高点</div><div class="v">{cur:.1f}%</div></div>
        <div class="metric"><div class="k">个股/板块窗口</div><div class="v small">{stk} / {ind}</div></div>
        <div class="metric"><div class="k">相关 / 相对强弱</div><div class="v small">{corr} / {rs} pct</div></div>
      </div>
      <div class="summary">{summary}</div>
      <img class="chart" src="data:image/png;base64,{img}" />
      <div class="card-foot"><a class="btn back" href="#top">↑ 回到顶部总览</a></div>
    </div>
    """.format(
        anchor=anchor, rank=rank, code=info['code'], name=info['name'],
        industry=info.get('industry_name', '-'), fit=info.get('fit_label', '-'),
        vol=info['vol_amplify'], bounce=info['bounce_pct'], dd=info['max_dd_pct'],
        cur=info['cur_dd_pct'], stk=stk_ret_s, ind=ind_ret_s, corr=corr_s, rs=rs_s,
        summary=info.get('summary', ''), img=img_b64 or ''
    )


def render_header(asof, total, show=False):
    html = """
    <div style="background:linear-gradient(135deg,#0f1419 0%,#1a2332 100%);
                border:1px solid #2f3e52;border-radius:12px;padding:18px 22px;margin:8px 0 16px 0;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">
        <div style="color:#4da3ff;font-size:12px;letter-spacing:1px;">JOINQUANT RESEARCH REPORT</div>
        <div style="color:#9aabbf;font-size:12px;text-align:right;">
          作者 <span style="color:#e7ecf3;font-weight:700;">{author_name}</span>
          &nbsp;·&nbsp;
          <a href="mailto:{author_email}" style="color:#4da3ff;text-decoration:none;">{author_email}</a>
        </div>
      </div>
      <div style="color:#e7ecf3;font-size:22px;font-weight:700;margin-top:4px;">
        超跌回升 · 量能确认选股报告
      </div>
      <div style="color:#9aabbf;margin-top:8px;font-size:13px;line-height:1.6;">
        版本 {ver} | 运行日 {asof} | 窗口 {lb} 交易日<br>
        规则：曾超跌≥{dd:.0f}% · 回升≥{bounce:.0f}% · 距高点回撤[{cur1:.0f}%,{cur2:.0f}%] · 量能放大≥{vol:.1f}x<br>
        排序：量能放大 → 反弹幅度 → 超跌深度 | 本次入选 <b style="color:#3dd68c">{n}</b> 只（展示前 {show}）
      </div>
    </div>
    """.format(
        author_name=_esc(AUTHOR_NAME), author_email=_esc(AUTHOR_EMAIL),
        ver=VERSION, asof=asof, lb=LOOKBACK_MAX_DAYS,
        dd=MIN_DD * 100, bounce=MIN_BOUNCE * 100,
        cur1=MIN_CUR_DD * 100, cur2=MAX_CUR_DD * 100,
        vol=MIN_VOL_AMPLIFY, n=total, show=min(total, MAX_SHOW)
    )
    if show:
        display(HTML(html))
    return html


def enrich_industry(info, asof):
    code = info['code']
    ind_code, ind_name = get_stock_industry(code, asof)
    info['industry_code'] = ind_code
    info['industry_name'] = ind_name
    ind_df = get_industry_ohlc(ind_code, asof, exclude_code=code)
    info['_ind_df'] = ind_df
    fit = calc_industry_fit(info['_window'], ind_df, info['idx_peak'], info['idx_low'])
    info.update(fit)
    info['summary'] = build_summary(info['name'], info)
    return info


def select_stocks(codes, asof, pbar=None):
    rows = []
    # 按批取行情；进度按股票数推进
    done = 0
    for i in range(0, len(codes), 250):
        part = codes[i:i + 250]
        hist = fetch_price(part, asof, LOOKBACK_MAX_DAYS + 5, ['open', 'high', 'low', 'close', 'volume'])
        if hist is None or hist.empty:
            done += len(part)
            if pbar is not None:
                pbar.set(done, info='批次无行情，跳过')
            continue
        grouped = list(hist.groupby('code'))
        for code, g in grouped:
            info = score_one(g)
            if info is not None:
                info['code'] = code
                info['name'] = get_security_info(code).display_name
                rows.append(info)
            done += 1
            if pbar is not None and (done % 40 == 0 or done >= len(codes)):
                pbar.set(min(done, len(codes)), info='已入选 %d' % len(rows))
        # 本批若有股票未出现在行情中，补齐计数
        got = set([c for c, _ in grouped])
        miss = [c for c in part if c not in got]
        if miss:
            done += len(miss)
            if pbar is not None:
                pbar.set(min(done, len(codes)), info='已入选 %d' % len(rows))
    if pbar is not None:
        pbar.close(info='筛选完成，入选 %d' % len(rows))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.sort_values(
        ['vol_amplify', 'bounce_pct', 'max_dd_pct'],
        ascending=[False, False, False]
    ).reset_index(drop=True)


def analyze_one(code, asof):
    hist = fetch_price([code], asof, LOOKBACK_MAX_DAYS + 5, ['open', 'high', 'low', 'close', 'volume'])
    if hist.empty:
        print(code, '无行情')
        return
    name = get_security_info(code).display_name
    info = score_one(hist)
    print('\n----- 单票诊断: %s %s -----' % (code, name))
    if info is None:
        print('未满足v9入选条件')
        return
    info['code'] = code
    info['name'] = name
    info = enrich_industry(info, asof)
    print(info['summary'])
    print('=> 按v9规则是否应入选: True')


def save_html_report(asof, total, header_html, summary_html, blocks_html, code_list):
    css = """
    html{scroll-behavior:smooth;}
    body{margin:0;padding:24px;background:#0b0f14;color:#e7ecf3;
         font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;}
    .wrap{max-width:1220px;margin:0 auto;}
    .overview{background:#121821;border:2px solid #4da3ff;border-radius:14px;padding:16px;margin:14px 0 24px 0;}
    .overview-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px;}
    .overview-title{font-size:20px;font-weight:800;color:#4da3ff;}
    .overview-sub{color:#9aabbf;font-size:12.5px;margin-top:4px;line-height:1.5;}
    .overview-count{background:#1a2332;border:1px solid #2f3e52;border-radius:999px;padding:6px 12px;color:#3dd68c;font-weight:700;white-space:nowrap;}
    .market-panel{background:#121821;border:1px solid #2f3e52;border-radius:14px;padding:16px;margin:8px 0 18px 0;}
    .market-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;margin-bottom:10px;flex-wrap:wrap;}
    .market-title{font-size:18px;font-weight:800;color:#f0b429;}
    .market-sub{color:#9aabbf;font-size:12.5px;margin-top:4px;line-height:1.5;}
    .market-metrics{display:flex;gap:10px;flex-wrap:wrap;}
    .market-metrics .mm{background:#1a2332;border:1px solid #2a3a4f;border-radius:8px;padding:8px 10px;min-width:110px;}
    .market-metrics .lab{color:#8fa0b5;font-size:11px;}
    .market-metrics .val{font-weight:700;margin-top:2px;font-size:16px;}
    .market-metrics .val.small{font-size:12px;font-weight:600;}
    .ov-head,.ov-row{display:grid;grid-template-columns:54px 120px 170px repeat(6,1fr) 72px;gap:8px;align-items:center;}
    .ov-head{padding:8px;color:#8fa0b5;font-size:12px;border-bottom:1px solid #2f3e52;margin-bottom:4px;}
    .ov-row{padding:10px 8px;border-bottom:1px solid #243247;}
    .ov-row:hover{background:#182131;}
    .ov-rank{font-weight:800;color:#e7ecf3;}
    .ov-name .n1{font-weight:700;}
    .ov-name .n2{color:#c5d0de;font-size:12px;}
    .ov-name .n3{color:#8fa0b5;font-size:11px;margin-top:2px;}
    .ov-mini img{height:44px;width:100%;object-fit:contain;background:#0f1419;border:1px solid #2a3a4f;border-radius:4px;}
    .ov-m .lab{color:#8fa0b5;font-size:11px;}
    .ov-m .val{font-weight:700;margin-top:2px;}
    .ov-m .val.small{font-size:12px;font-weight:600;line-height:1.3;}
    .ov-act{text-align:center;}
    .btn{display:inline-block;padding:6px 10px;border-radius:6px;background:#243247;color:#4da3ff;
         text-decoration:none;font-weight:700;border:1px solid #35506e;}
    .btn:hover{background:#2d3f59;}
    .btn.back{background:#1a2332;color:#9aabbf;border-color:#2f3e52;margin-left:8px;}
    .card{background:#121821;border:1px solid #2f3e52;border-radius:12px;padding:14px 16px;margin:18px 0;scroll-margin-top:12px;}
    .card-head{display:flex;justify-content:space-between;align-items:center;gap:10px;}
    .right-actions{display:flex;align-items:center;gap:6px;}
    .title{font-size:18px;font-weight:700;}
    .tag{color:#f0b429;font-size:13px;}
    .metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:12px;}
    .metric{background:#1a2332;border-radius:8px;padding:8px;}
    .k{color:#9aabbf;font-size:11px;}
    .v{font-size:18px;font-weight:700;margin-top:2px;}
    .v.small{font-size:14px;}
    .blue{color:#4da3ff;} .green{color:#3dd68c;} .red{color:#ff6b6b;}
    .summary{color:#c5d0de;font-size:12.5px;line-height:1.55;margin-top:10px;}
    .chart{width:100%;border-radius:8px;margin-top:10px;border:1px solid #243247;}
    .card-foot{margin-top:10px;text-align:right;}
    .codes{background:#121821;border:1px solid #2f3e52;border-radius:12px;padding:14px 16px;margin-top:20px;}
    .codes pre{white-space:pre-wrap;word-break:break-all;color:#9aabbf;font-size:12px;}
    .section-title{margin:26px 0 8px;font-size:16px;font-weight:700;color:#e7ecf3;}
    """
    # 用占位符替换，避免 CSS/内容里的 {} 触发 str.format
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>超跌回升选股报告 __VER__</title>
<style>__CSS__</style>
</head>
<body><div class="wrap">
__HEADER__
__SUMMARY__
<div class="section-title" id="details">详细图文（共 __SHOWN__ 只）</div>
__BLOCKS__
<div class="codes">
  <div style="font-weight:700;margin-bottom:8px;">全部代码列表（__N__）</div>
  <pre>__CODES__</pre>
</div>
<div style="color:#667788;font-size:12px;margin:18px 0;">Generated by __VER__ · Author __AUTHOR__ @ __ASOF__</div>
</div></body></html>
"""
    html = (html
            .replace('__VER__', VERSION)
            .replace('__AUTHOR__', _esc(AUTHOR_LINE))
            .replace('__CSS__', css)
            .replace('__HEADER__', header_html or '')
            .replace('__SUMMARY__', summary_html or '<div class="overview">总览生成失败</div>')
            .replace('__SHOWN__', str(len(blocks_html)))
            .replace('__BLOCKS__', '\n'.join(blocks_html))
            .replace('__N__', str(len(code_list)))
            .replace('__CODES__', _esc(str(code_list)))
            .replace('__ASOF__', str(asof)))

    fname = 'oversold_rebound_report_%s_%s.html' % (VERSION.replace('-', '_'), to_date_str(asof).replace('-', ''))
    with open(fname, 'w', encoding='utf-8') as f:
        f.write(html)
    print('      总览HTML长度:', len(summary_html or ''), '完整报告长度:', len(html))
    return fname, len(html)


def main():
    print('======== 脚本版本: %s ========' % VERSION)
    print('作者:', AUTHOR_LINE)
    asof = get_trade_date()
    print('运行日期:', asof)

    # 整条流水线共用一条可视化进度条
    pbar = ProgressBar(1, desc='准备中')

    print('[1/4] 构建股票池...')
    codes = get_universe(asof)
    if not codes:
        pbar.close(info='股票池为空')
        print('股票池为空')
        return pd.DataFrame()

    pbar.reset(max(len(codes), 1), desc='1/4 剔除停牌', info='待处理 %d' % len(codes))
    alive = []
    for i in range(0, len(codes), 500):
        part = codes[i:i + 500]
        alive.extend(filter_paused(part, asof))
        pbar.set(min(i + 500, len(codes)), info='保留 %d' % len(alive))
    pbar.close(info='剔除停牌后 %d' % len(alive))
    codes = alive

    print('[2/4] 财务过滤...')
    safe = []
    pbar.reset(max(len(codes), 1), desc='2/4 财务过滤', info='待处理 %d' % len(codes))
    for i in range(0, len(codes), 800):
        part = codes[i:i + 800]
        safe.extend(filter_financial_risk(part, asof))
        pbar.set(min(i + 800, len(codes)), info='保留 %d' % len(safe))
    pbar.close(info='财务过滤后 %d' % len(safe))

    print('[3/4] 超跌回升+量能筛选...')
    pbar.reset(max(len(safe), 1), desc='3/4 超跌回升筛选', info='待筛选 %d' % len(safe))
    result = select_stocks(safe, asof, pbar=pbar)
    if result.empty:
        print('未找到符合条件的股票')
        return result
    print('      入选 %d 只；将生成前 %d 只图文报告' % (len(result), min(len(result), MAX_SHOW)))
    if CHECK_CODE in set(result['code'].tolist()):
        print('      对照票 %s 排名: %d' % (
            CHECK_CODE, int(result.index[result['code'] == CHECK_CODE][0]) + 1))
    else:
        print('      对照票 %s 未进榜' % CHECK_CODE)

    show_n = min(len(result), MAX_SHOW)
    header_html = render_header(asof, len(result), show=False)

    print('[4/4] 生成HTML报告...')
    pbar.reset(max(show_n + 1, 1), desc='4/4 生成报告图文', info='先绘大盘对照')
    market_b64, market_stats = plot_market_kline(asof, return_base64=True)
    market_html = market_panel_html(market_b64, market_stats)
    pbar.set(1, info='大盘图完成，开始个股')

    blocks_html = []
    overview_rows = []
    for i in range(show_n):
        row = result.iloc[i].to_dict()
        info = enrich_industry(row, asof)
        info['rank'] = i + 1
        info['mini_b64'] = plot_mini_pair(info)
        img_b64 = plot_stock_card(
            i + 1, info, asof, return_base64=True, show=False
        )
        overview_rows.append(info)
        blocks_html.append(stock_block_html(i + 1, info, img_b64))
        pbar.set(i + 2, info='%s %s' % (info['code'], info['name']))
    pbar.close(info='报告图文已生成')

    summary_html = market_html + summary_table_html(overview_rows)
    fname, nbytes = save_html_report(
        asof, len(result), header_html, summary_html, blocks_html, result['code'].tolist()
    )

    print('\n======== 完成 ========')
    print('入选总数:', len(result))
    print('报告文件:', fname)
    print('文件大小: %.1f KB' % (nbytes / 1024.0))
    print('代码列表:')
    print(result['code'].tolist())

    display(HTML(
        '<div style="margin:14px 0;padding:14px 16px;border:1px solid #2f3e52;'
        'border-radius:10px;background:#121821;color:#e7ecf3;">'
        '<div style="color:#3dd68c;font-weight:700;margin-bottom:6px;">HTML报告已生成，可下载</div>'
        '<div>文件：<code style="color:#4da3ff;">%s</code>（%.1f KB）</div>'
        '<div style="margin-top:8px;color:#9aabbf;">点击下方链接下载；若无反应，也可在左侧文件列表找到同名文件。</div>'
        '</div>' % (fname, nbytes / 1024.0)
    ))
    try:
        display(FileLink(fname, result_html_prefix='下载报告：'))
    except Exception:
        display(HTML('<a href="%s" download="%s" style="color:#4da3ff;font-size:16px;">点击下载 %s</a>' % (
            fname, fname, fname)))

    slim_cols = [c for c in result.columns if not str(c).startswith('_')]
    return result[slim_cols]


df = main()
