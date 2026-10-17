from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.eastmoney.com/",
    "Accept": "*/*",
}


def _client() -> httpx.Client:
    return httpx.Client(timeout=20.0, headers=HEADERS, follow_redirects=True)


def secid(code: str) -> str:
    code = code.zfill(6)
    # 沪市: 6/5/9 开头；其余按深市
    prefix = "1" if code.startswith(("5", "6", "9")) else "0"
    return f"{prefix}.{code}"


def market_of(code: str) -> str:
    code = code.zfill(6)
    return "SH" if code.startswith(("5", "6", "9")) else "SZ"


def search_stocks(q: str, limit: int = 20) -> list[dict[str, str]]:
    q = (q or "").strip()
    if not q:
        q = "6"
    url = (
        "https://searchapi.eastmoney.com/api/suggest/get"
        f"?input={quote(q)}&type=14&token=D43BF722C8E33BDC906FB84D85E326E8&count={limit}"
    )
    with _client() as c:
        r = c.get(url)
        r.raise_for_status()
        data = r.json()
    rows = (((data or {}).get("QuotationCodeTable") or {}).get("Data")) or []
    out: list[dict[str, str]] = []
    for row in rows:
        code = str(row.get("Code") or "").zfill(6)
        name = str(row.get("Name") or "")
        classify = str(row.get("Classify") or "")
        if not code.isdigit() or not name:
            continue
        # 只要 A 股 / ETF 等常见品种
        if classify and classify not in ("AStock", "ETF", "Index"):
            # still allow if looks like A-share code
            if not code.startswith(("0", "1", "2", "3", "5", "6", "8", "9")):
                continue
        out.append({"code": code, "name": name, "market": market_of(code)})
    return out[:limit]


def get_quote(code: str) -> dict[str, Any]:
    code = code.zfill(6)
    fields = "f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f15,f16,f17,f18,f20,f21,f23"
    url = (
        "https://push2delay.eastmoney.com/api/qt/ulist.np/get"
        f"?fltt=2&invt=2&secids={secid(code)}&fields={fields}"
    )
    with _client() as c:
        r = c.get(url)
        r.raise_for_status()
        payload = r.json()
    diff = (((payload or {}).get("data") or {}).get("diff")) or []
    if not diff:
        raise RuntimeError(f"empty quote for {code}")
    d = diff[0]

    def num(key: str, default: float = 0.0) -> float:
        v = d.get(key)
        if v is None or v == "-" or v == "":
            return default
        try:
            return float(v)
        except Exception:
            return default

    price = num("f2")
    pre = num("f18")
    return {
        "code": code,
        "name": str(d.get("f14") or code).replace(" ", "").replace("\u3000", ""),
        "market": market_of(code),
        "price": price,
        "open": num("f17"),
        "high": num("f15"),
        "low": num("f16"),
        "pre_close": pre,
        "change": round(num("f4"), 2),
        "change_pct": round(num("f3"), 2),
        "volume": int(num("f5")),
        "amount": num("f6"),
        "turnover_rate": round(num("f8"), 2),
        "amplitude": round(num("f7"), 2),
        "volume_ratio": round(num("f10"), 2),
        "pe_ttm": round(num("f9"), 2),
        "pb": round(num("f23"), 2),
        "total_mv": num("f20"),
        "as_of": date.today().isoformat(),
        "degraded": False,
        "source": "eastmoney",
    }


def get_kline(code: str, limit: int = 180) -> list[dict[str, Any]]:
    """日K前复权：多源重试，保证实盘可用。"""
    code = code.zfill(6)
    errors: list[str] = []

    # 腾讯源在云环境更稳，优先；东财/akshare 兜底
    for name, fn in (
        ("tencent", lambda: _kline_tencent(code, limit)),
        ("eastmoney", lambda: _kline_eastmoney_his(code, limit)),
        ("akshare_em", lambda: _kline_akshare_em(code, limit)),
    ):
        try:
            rows = fn()
            if rows:
                logger.info("kline source=%s code=%s bars=%s", name, code, len(rows))
                return rows
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}:{exc}")
            logger.warning("kline %s failed: %s", name, exc)

    raise RuntimeError("kline empty: " + " | ".join(errors[-4:]))


def _kline_eastmoney_his(code: str, limit: int) -> list[dict[str, Any]]:
    end = date.today()
    start = end - timedelta(days=int(limit * 1.8) + 40)
    beg = start.strftime("%Y%m%d")
    end_s = end.strftime("%Y%m%d")
    # 官方历史域名偶发断开，双主机重试
    hosts = (
        "https://push2his.eastmoney.com",
        "https://push2delay.eastmoney.com",
    )
    last_err: Exception | None = None
    for host in hosts:
        url = (
            f"{host}/api/qt/stock/kline/get"
            f"?secid={secid(code)}&fields1=f1,f2,f3,f4,f5,f6"
            f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
            f"&klt=101&fqt=1&beg={beg}&end={end_s}&lmt={max(limit, 200)}"
        )
        try:
            with _client() as c:
                r = c.get(url)
                r.raise_for_status()
                payload = r.json()
            kl = (((payload or {}).get("data") or {}).get("klines")) or []
            rows: list[dict[str, Any]] = []
            for line in kl[-limit:]:
                parts = str(line).split(",")
                if len(parts) < 7:
                    continue
                rows.append(
                    {
                        "date": parts[0][:10],
                        "open": float(parts[1]),
                        "close": float(parts[2]),
                        "high": float(parts[3]),
                        "low": float(parts[4]),
                        "volume": int(float(parts[5])),
                        "amount": float(parts[6]),
                    }
                )
            if rows:
                return rows
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.warning("eastmoney kline %s failed: %s", host, exc)
    if last_err:
        raise last_err
    return []


def _kline_tencent(code: str, limit: int) -> list[dict[str, Any]]:
    import akshare as ak

    symbol = f"{'sh' if market_of(code) == 'SH' else 'sz'}{code}"
    end = date.today()
    start = end - timedelta(days=int(limit * 2.2) + 60)
    df = ak.stock_zh_a_hist_tx(
        symbol=symbol,
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        adjust="qfq",
    )
    if df is None or df.empty:
        return []
    # columns: date open close high low amount
    df = df.tail(limit)
    rows = []
    for _, r in df.iterrows():
        vol = r["amount"] if "amount" in r else 0
        rows.append(
            {
                "date": str(r["date"])[:10],
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": int(float(vol)),
                "amount": float(vol) * float(r["close"]),
            }
        )
    return rows


def _kline_akshare_em(code: str, limit: int) -> list[dict[str, Any]]:
    import akshare as ak

    df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
    if df is None or df.empty:
        return []
    df = df.tail(limit)
    rows = []
    for _, r in df.iterrows():
        rows.append(
            {
                "date": str(r["日期"])[:10],
                "open": float(r["开盘"]),
                "high": float(r["最高"]),
                "low": float(r["最低"]),
                "close": float(r["收盘"]),
                "volume": int(float(r["成交量"])),
                "amount": float(r["成交额"]),
            }
        )
    return rows


def get_fundamental(code: str) -> dict[str, Any]:
    code = code.zfill(6)
    mkt = market_of(code)
    em_code = f"{mkt}{code}"
    with _client() as c:
        survey = c.get(
            "https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax"
            f"?code={em_code}"
        )
        survey.raise_for_status()
        survey_j = survey.json()
        concept = c.get(
            "https://emweb.securities.eastmoney.com/PC_HSF10/CoreConception/PageAjax"
            f"?code={em_code}"
        )
        concept.raise_for_status()
        concept_j = concept.json()

    jbzl = (survey_j.get("jbzl") or [{}])[0]
    name = str(jbzl.get("SECURITY_NAME_ABBR") or code)
    industry = str(jbzl.get("INDUSTRYCUSRC") or jbzl.get("INDUSTRY_CSRC") or "")
    if not industry:
        boards = concept_j.get("ssbk") or []
        if boards:
            industry = str(boards[0].get("BOARD_NAME") or "未知")
    if not industry:
        industry = "未知"

    concepts = []
    for b in (concept_j.get("ssbk") or [])[:8]:
        bn = str(b.get("BOARD_NAME") or "").strip()
        if bn and bn not in concepts:
            concepts.append(bn)

    # 主营构成（若有）
    products = []
    for row in (survey_j.get("zygcfx") or survey_j.get("zygc") or [])[:6]:
        pname = str(row.get("PRODUCT_NAME") or row.get("MAIN_BUSINESS") or "").strip()
        if not pname:
            continue
        share = row.get("RATIO") or row.get("MB_RATIO") or 0
        try:
            share_f = float(share)
            if share_f > 1:
                share_f = share_f / 100.0
        except Exception:
            share_f = 0.0
        products.append(
            {
                "name": pname,
                "share": round(share_f, 4),
                "desc": str(row.get("MAIN_BUSINESS") or row.get("PRODUCT_NAME") or ""),
            }
        )
    if not products:
        profile = str(jbzl.get("ORG_PROFILE") or jbzl.get("BUSINESSSCOPE") or "")[:180]
        products = [
            {"name": "主营业务", "share": 1.0, "desc": profile or f"{name} 主营业务详见公司公告"}
        ]

    summary = str(jbzl.get("ORG_PROFILE") or "").strip()
    if not summary:
        summary = f"{name} 所属行业 {industry}，概念/板块：{'、'.join(concepts[:4]) or '—'}"

    # 同业：取同行业板块成分前几只（尽力）
    peers: list[dict[str, Any]] = []
    board_code = None
    for b in concept_j.get("ssbk") or []:
        if str(b.get("IS_PRECISE")) == "0" or b.get("BOARD_RANK") == 1:
            board_code = str(b.get("BOARD_CODE") or "")
            break
    if not board_code and (concept_j.get("ssbk") or []):
        board_code = str(concept_j["ssbk"][0].get("BOARD_CODE") or "")

    if board_code:
        try:
            peers = _board_peers(board_code, exclude=code, limit=5)
        except Exception as exc:  # noqa: BLE001
            logger.warning("peers failed: %s", exc)

    return {
        "code": code,
        "name": name,
        "industry": industry,
        "concepts": concepts or [industry],
        "products": products,
        "business_summary": summary[:500],
        "peers": peers,
        "degraded": False,
        "source": "eastmoney",
    }


def _board_peers(board_code: str, exclude: str, limit: int = 5) -> list[dict[str, Any]]:
    # 板块代码规范化：438 -> BK0438
    bc = board_code.strip().upper()
    if bc.isdigit():
        bc = f"BK{bc.zfill(4)}"
    elif not bc.startswith("BK"):
        bc = f"BK{bc}"

    for host in (
        "https://push2delay.eastmoney.com",
        "https://push2.eastmoney.com",
    ):
        url = (
            f"{host}/api/qt/clist/get"
            f"?pn=1&pz={limit + 3}&po=1&np=1&fltt=2&invt=2"
            f"&fid=f3&fs=b:{bc}&fields=f12,f14,f2,f3"
        )
        try:
            with _client() as c:
                r = c.get(url)
                if r.status_code != 200 or not r.content:
                    continue
                data = r.json()
            diff = (((data or {}).get("data") or {}).get("diff")) or []
            out = []
            for d in diff:
                code = str(d.get("f12") or "").zfill(6)
                if code == exclude or not code.isdigit():
                    continue
                try:
                    chg = float(d.get("f3") or 0)
                    price = float(d.get("f2") or 0)
                except Exception:
                    chg, price = 0.0, 0.0
                out.append(
                    {
                        "code": code,
                        "name": str(d.get("f14") or code),
                        "change_pct": round(chg, 2),
                        "price": price,
                    }
                )
                if len(out) >= limit:
                    break
            if out:
                return out
        except Exception as exc:  # noqa: BLE001
            logger.warning("board peers %s failed: %s", host, exc)
    return []


def get_news(code: str, limit: int = 20) -> list[dict[str, Any]]:
    code = code.zfill(6)
    items: list[dict[str, Any]] = []

    # 1) 公告
    try:
        url = (
            "https://np-anotice-stock.eastmoney.com/api/security/ann"
            f"?sr=-1&page_size={min(limit, 10)}&page_index=1&ann_type=A"
            f"&client_source=web&stock_list={code}"
        )
        with _client() as c:
            r = c.get(url)
            r.raise_for_status()
            data = r.json()
        for i, row in enumerate(((data.get("data") or {}).get("list")) or []):
            title = str(row.get("title") or "").strip()
            if not title:
                continue
            art = str(row.get("art_code") or i)
            items.append(
                {
                    "id": f"ann-{art}",
                    "title": title,
                    "source": "公司公告",
                    "published_at": str(row.get("notice_date") or row.get("display_time") or "")[:19],
                    "summary": title,
                    "sentiment": _sentiment(title),
                    "url": f"https://data.eastmoney.com/notices/detail/{code}/{art}.html",
                }
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("announcements failed: %s", exc)

    # 2) 资讯搜索
    try:
        param = {
            "uid": "",
            "keyword": code,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "default",
                    "sort": "default",
                    "pageIndex": 1,
                    "pageSize": min(limit, 12),
                    "preTag": "",
                    "postTag": "",
                }
            },
        }
        url = (
            "https://search-api-web.eastmoney.com/search/jsonp"
            f"?cb=jQuery&param={quote(json.dumps(param, ensure_ascii=False))}"
        )
        with _client() as c:
            r = c.get(url, headers={**HEADERS, "Referer": "https://so.eastmoney.com/"})
            r.raise_for_status()
            text = r.text
        m = re.search(r"jQuery\((.*)\)\s*$", text, re.S)
        body = json.loads(m.group(1) if m else text)
        arts = (((body.get("result") or {}).get("cmsArticleWebOld")) or [])
        for i, a in enumerate(arts):
            title = re.sub(r"</?em>", "", str(a.get("title") or ""))
            content = re.sub(r"</?em>", "", str(a.get("content") or ""))[:180]
            if not title:
                continue
            items.append(
                {
                    "id": f"news-{a.get('code') or i}",
                    "title": title,
                    "source": str(a.get("mediaName") or "东方财富"),
                    "published_at": str(a.get("date") or "")[:19],
                    "summary": content or title,
                    "sentiment": _sentiment(title + content),
                    "url": str(a.get("url") or ""),
                }
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("news search failed: %s", exc)

    # 去重保序
    seen = set()
    uniq = []
    for it in items:
        key = it["title"]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    return uniq[:limit]


def _sentiment(text: str) -> str:
    pos = ("增长", "超预期", "签约", "中标", "回购", "上调", "创新高", "盈利", "分红")
    neg = ("下滑", "亏损", "调查", "减持", "风险", "处罚", "下跌", "下调", "爆雷")
    p = sum(1 for w in pos if w in text)
    n = sum(1 for w in neg if w in text)
    if p > n:
        return "positive"
    if n > p:
        return "negative"
    return "neutral"
