import aiohttp
import asyncio
import os
import sys
import math
import random
import statistics
from collections import deque, defaultdict, Counter
from datetime import datetime, timezone, timedelta

VN_TZ = timezone(timedelta(hours=7))

APIS = {
    "sunwin": [
        {"label": "Tài Xỉu", "url": "https://markers-amenities-vertex-gratuit.trycloudflare.com/api/tx", "type": "normal"},
    ],
    "xocdia88": [
        {"label": "TX MD5", "url": "https://acres-scientists-balanced-paso.trycloudflare.com/api/taixiu", "type": "md5"},
    ],
    "hitclub": [
        {"label": "TX MD5", "url": "https://nirvana-corners-discussing-treating.trycloudflare.com/api/tx", "type": "md5_hitclub"},
    ],
    "lc79": [
        {"label": "TX Thường", "url": "https://living-telecommunications-start-consoles.trycloudflare.com/api/tx", "type": "normal"},
        {"label": "TX MD5", "url": "https://living-telecommunications-start-consoles.trycloudflare.com/api/txmd5", "type": "md5"},
        {"label": "Xóc Đĩa MD5", "url": "https://living-telecommunications-start-consoles.trycloudflare.com/api/xocdia", "type": "xocdia"},
    ],
    "betvip": [
        {"label": "TX Thường", "url": "https://wide-epic-steve-file.trycloudflare.com/api/tx", "type": "normal"},
        {"label": "TX MD5", "url": "https://wide-epic-steve-file.trycloudflare.com/api/txmd5", "type": "md5"},
    ],
}

BRAND_EMOJI = {
    "sunwin": "☀️", "xocdia88": "🎯", "hitclub": "🎪", "lc79": "🎲", "betvip": "💎",
}

SESSION_RANGES = {
    "sang":  (5,  11,  "🌅", "BUỔI SÁNG",  "05:00-11:00"),
    "trua":  (11, 13,  "☀️", "BUỔI TRƯA",  "11:00-13:00"),
    "chieu": (13, 18,  "🌤️", "BUỔI CHIỀU", "13:00-18:00"),
    "toi":   (18, 23,  "🌙", "BUỔI TỐI",   "18:00-23:00"),
    "khuya": (23, 5,   "🌃", "KHUYA",       "23:00-05:00"),
}

DICE_EMOJI = {1:"⚀",2:"⚁",3:"⚂",4:"⚃",5:"⚄",6:"⚅"}
RESULT_EMOJI = {"Tài":"🔴","Xỉu":"🔵","Chẵn":"🟢","Lẻ":"🟡"}

history_data = {
    app: {api["label"]: deque(maxlen=80) for api in apis}
    for app, apis in APIS.items()
}

session_history = {
    app: {api["label"]: {s: deque(maxlen=200) for s in SESSION_RANGES} for api in apis}
    for app, apis in APIS.items()
}

session_stats = {
    app: {api["label"]: {s: {"dung": 0, "sai": 0} for s in SESSION_RANGES} for api in apis}
    for app, apis in APIS.items()
}

stats = {
    app: {api["label"]: {"dung": 0, "sai": 0} for api in apis}
    for app, apis in APIS.items()
}

last_phien = {
    app: {api["label"]: None for api in apis}
    for app, apis in APIS.items()
}

pending_pred = {
    app: {api["label"]: None for api in apis}
    for app, apis in APIS.items()
}

def _now_vn():
    return datetime.now(VN_TZ)

def _get_current_session():
    h = _now_vn().hour
    for key, (start, end, icon, name, time_str) in SESSION_RANGES.items():
        if key == "khuya":
            if h >= 23 or h < 5:
                return key, icon, name, time_str
        else:
            if start <= h < end:
                return key, icon, name, time_str
    return "toi", "🌙", "BUỔI TỐI", "18:00-23:00"

def _normalize(scores, labels):
    total = sum(scores.get(l, 0) for l in labels) or 1
    return {l: scores.get(l, 0) / total for l in labels}

def _weighted_freq(results, labels):
    scores = {l: 0.0 for l in labels}
    n = len(results)
    for i, r in enumerate(results):
        if r in scores:
            scores[r] += math.exp((i - n + 1) * 0.10)
    return _normalize(scores, labels)

def _markov1(results, labels):
    if not results: return {l: 0.5 for l in labels}
    trans = {l: defaultdict(float) for l in labels}
    for i in range(len(results) - 1):
        a, b = results[i], results[i+1]
        if a in trans and b in labels:
            trans[a][b] += 1
    last = results[-1]
    if last in trans and sum(trans[last].values()) > 0:
        return _normalize(dict(trans[last]), labels)
    return {l: 0.5 for l in labels}

def _markov2(results, labels):
    if len(results) < 3: return {l: 0.5 for l in labels}
    trans = defaultdict(lambda: defaultdict(float))
    for i in range(len(results) - 2):
        key = (results[i], results[i+1])
        nxt = results[i+2]
        if nxt in labels: trans[key][nxt] += 1
    key = tuple(results[-2:]) if len(results) >= 2 else None
    if key and key in trans and sum(trans[key].values()) > 0:
        return _normalize(dict(trans[key]), labels)
    return {l: 0.5 for l in labels}

def _markov3(results, labels):
    if len(results) < 4: return {l: 0.5 for l in labels}
    trans = defaultdict(lambda: defaultdict(float))
    for i in range(len(results) - 3):
        key = (results[i], results[i+1], results[i+2])
        nxt = results[i+3]
        if nxt in labels: trans[key][nxt] += 1
    key = tuple(results[-3:]) if len(results) >= 3 else None
    if key and key in trans and sum(trans[key].values()) > 0:
        return _normalize(dict(trans[key]), labels)
    return {l: 0.5 for l in labels}

def _get_streak(results):
    if not results: return 0
    streak = 1
    for i in range(len(results) - 2, -1, -1):
        if results[i] == results[-1]: streak += 1
        else: break
    return streak

def _streak_bias(results, labels):
    streak = _get_streak(results)
    last = results[-1] if results else None
    scores = {l: 0.5 for l in labels}
    if last not in labels: return scores
    other = [l for l in labels if l != last][0]
    if streak >= 7: scores[other] = 0.86; scores[last] = 0.14
    elif streak >= 5: scores[other] = 0.73; scores[last] = 0.27
    elif streak >= 4: scores[other] = 0.65; scores[last] = 0.35
    elif streak >= 3: scores[other] = 0.58; scores[last] = 0.42
    elif streak == 2: scores[last] = 0.54; scores[other] = 0.46
    return scores

def _alternating(results, labels):
    if len(results) < 4: return {l: 0.5 for l in labels}
    alt_count = sum(1 for i in range(len(results)-1) if results[i] != results[i+1])
    same_count = len(results) - 1 - alt_count
    total = alt_count + same_count or 1
    alt_ratio = alt_count / total
    last = results[-1]
    other = [l for l in labels if l != last][0]
    if alt_ratio > 0.6:
        scores = {other: 0.55 + (alt_ratio - 0.6) * 0.5, last: 0}
        scores[last] = 1 - scores[other]
    elif alt_ratio < 0.4:
        scores = {last: 0.55 + (0.4 - alt_ratio) * 0.5, other: 0}
        scores[other] = 1 - scores[last]
    else:
        scores = {l: 0.5 for l in labels}
    return _normalize(scores, labels)

def _window_vote(results, labels, windows=(3, 5, 8)):
    votes = {l: 0.0 for l in labels}
    for w in windows:
        if len(results) < w: continue
        sub = results[-w:]
        counts = {l: sub.count(l) for l in labels}
        best = max(labels, key=lambda l: counts[l])
        votes[best] += 1.0
    return _normalize(votes, labels) if any(v > 0 for v in votes.values()) else {l: 0.5 for l in labels}

def _bayesian_recent(results, labels):
    if not results: return {l: 0.5 for l in labels}
    sub = results[-15:]
    counts = {l: sub.count(l) + 1 for l in labels}
    total = sum(counts.values())
    return {l: counts[l] / total for l in labels}

def _ema_signal(results, labels):
    if len(results) < 8: return {l: 0.5 for l in labels}
    binary = [1 if r == labels[0] else 0 for r in results]
    alpha = 0.3; ema = binary[0]
    for v in binary[1:]: ema = alpha * v + (1 - alpha) * ema
    if ema > 0.6: return _normalize({labels[0]: 0.65, labels[1]: 0.35}, labels)
    elif ema < 0.4: return _normalize({labels[1]: 0.65, labels[0]: 0.35}, labels)
    return {l: 0.5 for l in labels}

def _trend_detector(results, labels):
    if len(results) < 10: return {l: 0.5 for l in labels}
    first_half = results[:len(results)//2]
    second_half = results[len(results)//2:]
    c1, c2 = Counter(first_half), Counter(second_half)
    trending = {}
    for l in labels:
        r1 = c1.get(l, 0) / len(first_half) if first_half else 0.5
        r2 = c2.get(l, 0) / len(second_half) if second_half else 0.5
        trending[l] = r2 + (r2 - r1) * 0.5
    return _normalize(trending, labels)

def _zigzag_analysis(results, labels):
    if len(results) < 4: return {l: 0.5 for l in labels}
    zz = sum(1 for i in range(len(results)-1) if results[i] != results[i+1])
    ratio = zz / (len(results) - 1)
    last = results[-1]
    other = [l for l in labels if l != last][0]
    if ratio >= 0.75: return _normalize({other: 0.65, last: 0.35}, labels)
    elif ratio <= 0.25: return _normalize({last: 0.65, other: 0.35}, labels)
    return {l: 0.5 for l in labels}

def _regression_trend(results, labels):
    if len(results) < 8: return {l: 0.5 for l in labels}
    binary = [1 if r == labels[0] else 0 for r in results[-15:]]
    n = len(binary); x_mean = (n - 1) / 2; y_mean = sum(binary) / n
    num = sum((i - x_mean) * (binary[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    slope = num / den if den != 0 else 0
    predicted = max(0.1, min(0.9, y_mean + slope * (n - x_mean)))
    if predicted > 0.55: return _normalize({labels[0]: predicted, labels[1]: 1 - predicted}, labels)
    elif predicted < 0.45: return _normalize({labels[1]: 1 - predicted, labels[0]: predicted}, labels)
    return {l: 0.5 for l in labels}

def _rsi_signal(results, labels):
    if len(results) < 14: return {l: 0.5 for l in labels}
    binary = [1 if r == labels[0] else 0 for r in results[-14:]]
    gains = [max(binary[i]-binary[i-1], 0) for i in range(1, len(binary))]
    losses = [max(binary[i-1]-binary[i], 0) for i in range(1, len(binary))]
    avg_gain = sum(gains)/len(gains) if gains else 0
    avg_loss = sum(losses)/len(losses) if losses else 1e-9
    rs = avg_gain / (avg_loss + 1e-9)
    rsi = 100 - 100 / (1 + rs)
    last = results[-1]; other = [l for l in labels if l != last][0]
    if rsi > 70: return _normalize({other: 0.65, last: 0.35}, labels)
    elif rsi < 30: return _normalize({last: 0.65, other: 0.35}, labels)
    return {l: 0.5 for l in labels}

def _bollinger_band(results, labels):
    if len(results) < 20: return {l: 0.5 for l in labels}
    binary = [1 if r == labels[0] else 0 for r in results[-20:]]
    mean = sum(binary) / len(binary)
    std = (sum((x - mean)**2 for x in binary) / len(binary))**0.5
    last_val = binary[-1]; last = results[-1]; other = [l for l in labels if l != last][0]
    if last_val > mean + 2 * std: return _normalize({other: 0.65, last: 0.35}, labels)
    elif last_val < mean - 2 * std: return _normalize({last: 0.65, other: 0.35}, labels)
    return {l: 0.5 for l in labels}

def _kalman_filter(results, labels):
    if len(results) < 8: return {l: 0.5 for l in labels}
    binary = [1 if r == labels[0] else 0 for r in results[-15:]]
    x, P, Q, R = 0.5, 1.0, 0.02, 0.15
    for v in binary:
        P_pred = P + Q
        K = P_pred / (P_pred + R)
        x = x + K * (v - x)
        P = (1 - K) * P_pred
    x = max(0.1, min(0.9, x))
    if x > 0.58: return _normalize({labels[0]: x, labels[1]: 1-x}, labels)
    elif x < 0.42: return _normalize({labels[1]: 1-x, labels[0]: x}, labels)
    return {l: 0.5 for l in labels}

def _entropy_signal(results, labels):
    if len(results) < 8: return {l: 0.5 for l in labels}
    counts = Counter(results[-20:])
    total = sum(counts.values()) or 1
    probs = [counts.get(l, 0) / total for l in labels]
    entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    if entropy > 0.97: return {l: 0.5 for l in labels}
    elif entropy < 0.5:
        dominant = max(labels, key=lambda l: counts.get(l, 0))
        return _normalize({dominant: 0.7, [x for x in labels if x != dominant][0]: 0.3}, labels)
    return {l: 0.5 for l in labels}

def _last5_vote(results, labels):
    if len(results) < 5: return {l: 0.5 for l in labels}
    sub = results[-5:]; counts = Counter(sub)
    best = max(labels, key=lambda l: counts.get(l, 0))
    other = [l for l in labels if l != best][0]
    ratio = counts.get(best, 0) / 5
    return _normalize({best: 0.35 + ratio * 0.35, other: 0.65 - ratio * 0.35}, labels)

def _backtest_method(fn, results, labels, window=15, min_obs=6):
    if len(results) < min_obs + 2: return 0.5
    correct = 0; total = 0
    start = max(min_obs, len(results) - min(window, 15))
    for i in range(start, len(results) - 1):
        sub = results[:i]
        try: scores = fn(sub, labels)
        except: scores = {l: 0.5 for l in labels}
        pred = max(labels, key=lambda l: scores.get(l, 0))
        if pred == results[i]: correct += 1
        total += 1
    return correct / total if total > 0 else 0.5

def _ensemble_simple(results, labels, use_sum=False, session_bonus=1.0):
    results = [r for r in results if r in labels]
    n = len(results)
    if n < 5: return None, 0, 0, 0, "?", 0, {}

    methods = {
        "wf": _weighted_freq, "mk1": _markov1, "mk2": _markov2, "mk3": _markov3,
        "sb": _streak_bias, "alt": _alternating, "wv": _window_vote,
        "bay_r": _bayesian_recent, "ema": _ema_signal, "trend": _trend_detector,
        "zz": _zigzag_analysis, "reg": _regression_trend, "rsi": _rsi_signal,
        "bb": _bollinger_band, "kalman": _kalman_filter, "ent": _entropy_signal,
        "l5v": _last5_vote,
    }

    raw_scores = {}
    for name, fn in methods.items():
        try: raw_scores[name] = fn(results, labels)
        except: raw_scores[name] = {l: 0.5 for l in labels}

    bt_acc = {}
    for name, fn in methods.items():
        bt_acc[name] = _backtest_method(fn, results, labels)

    min_acc = min(bt_acc.values())
    adj = {name: max(acc - min_acc, 0.005) ** 1.5 for name, acc in bt_acc.items()}
    total_adj = sum(adj.values()) or 1
    w = {name: adj[name] / total_adj for name in adj}

    final = {l: 0.0 for l in labels}
    for name, scores in raw_scores.items():
        for l in labels:
            final[l] += scores.get(l, 0.5) * w[name]

    final = _normalize(final, labels)

    if session_bonus != 1.0:
        best_c = max(labels, key=lambda l: final[l])
        other_c = [l for l in labels if l != best_c][0]
        margin = final[best_c] - final[other_c]
        adjusted = margin * session_bonus
        final[best_c] = 0.5 + adjusted / 2
        final[other_c] = 0.5 - adjusted / 2
        final = _normalize(final, labels)

    best = max(labels, key=lambda l: final[l])
    other = [l for l in labels if l != best][0]
    margin = final[best] - final[other]
    votes = sum(1 for s in raw_scores.values() if max(labels, key=lambda l: s.get(l, 0)) == best)
    avg_acc = sum(bt_acc.values()) / len(bt_acc) if bt_acc else 0.5
    conf_raw = final[best] * 0.30 + (votes/len(methods)) * 0.25 + avg_acc * 0.28 + margin * 0.17
    conf = int(min(conf_raw * 100, 94))
    top_m = max(bt_acc, key=bt_acc.get)
    top_acc = int(bt_acc[top_m] * 100)

    return best, conf, votes, len(methods), top_m, top_acc, bt_acc

def _session_weight_bonus(app, label, session_key):
    st = session_stats[app][label][session_key]
    d, s = st["dung"], st["sai"]
    total = d + s
    if total < 5: return 1.0
    rate = d / total
    if rate >= 0.72: return 1.35
    elif rate >= 0.62: return 1.20
    elif rate >= 0.52: return 1.05
    elif rate >= 0.42: return 0.90
    else: return 0.75

def _check_prev_pred(app, label, actual_kq):
    p = pending_pred[app][label]
    if not p or actual_kq is None: return None
    predicted = p["pred"]
    correct = (predicted == actual_kq)
    session_key, _, _, _ = _get_current_session()
    if correct:
        stats[app][label]["dung"] += 1
        session_stats[app][label][session_key]["dung"] += 1
        msg = ("dung", predicted, actual_kq)
    else:
        stats[app][label]["sai"] += 1
        session_stats[app][label][session_key]["sai"] += 1
        msg = ("sai", predicted, actual_kq)
    pending_pred[app][label] = None
    return msg

async def fetch_data(session, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8, connect=3)) as resp:
            if resp.status == 200:
                return await resp.json(content_type=None)
    except: pass
    return None

def _conf_bar(conf):
    filled = round(conf / 10)
    return "█" * filled + "░" * (10 - filled)

def _render_result_bar(hist, is_xocdia=False):
    items = list(hist)[-15:]
    bar = []
    for r in items:
        if is_xocdia:
            kq = r.get("ket_qua_truyen_thong", "?")
        else:
            kq = r.get("ket_qua", "?")
        bar.append(RESULT_EMOJI.get(kq, "⬜"))
    return " ".join(bar) if bar else "—"

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def print_header():
    now = _now_vn()
    sess_key, sess_icon, sess_name, sess_time = _get_current_session()
    date_str = now.strftime("%d/%m/%Y")
    time_str = now.strftime("%H:%M:%S")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║      🎰  TOOL TÀI XỈU BY DZI  —  AI PREDICTION ENGINE      ║")
    print(f"║   📅 {date_str}   ⏰ {time_str}   {sess_icon} {sess_name:<12}        ║")
    print("╚══════════════════════════════════════════════════════════════╝")

def print_menu():
    print_header()
    print()
    print("  CHỌN SÂN:")
    print()
    apps = list(APIS.items())
    for idx, (app, apis) in enumerate(apps, 1):
        emoji = BRAND_EMOJI.get(app, "🎰")
        labels = " | ".join(f"[{i}] {a['label']}" for i, a in enumerate(apis, 1)) if len(apis) > 1 else apis[0]["label"]
        print(f"  [{idx}] {emoji}  {app.upper():<12}  {labels}")
    print()
    print("  [0] Thoát")
    print()
    print("─" * 65)

def print_api_menu(app, apis):
    clear()
    print_header()
    emoji = BRAND_EMOJI.get(app, "🎰")
    print()
    print(f"  {emoji}  {app.upper()}  —  CHỌN LOẠI:")
    print()
    for i, api in enumerate(apis, 1):
        print(f"  [{i}] {api['label']}")
    print()
    print("  [0] Quay lại")
    print()
    print("─" * 65)

def format_prediction_block(app, api_label, api_type, data, hist):
    lines = []
    now = _now_vn()
    sess_key, sess_icon, sess_name, sess_time = _get_current_session()
    session_bonus = _session_weight_bonus(app, api_label, sess_key)

    phien = data.get("phien", "?")
    kq = data.get("ket_qua", "?")
    tong = data.get("tong", "?")
    d1 = DICE_EMOJI.get(data.get("xuc_xac_1"), "▪")
    d2 = DICE_EMOJI.get(data.get("xuc_xac_2"), "▪")
    d3 = DICE_EMOJI.get(data.get("xuc_xac_3"), "▪")

    lines.append("╔══════════════════════════════════════════════════════════════╗")
    emoji = BRAND_EMOJI.get(app, "🎰")
    title = f"{emoji}  {app.upper()}  —  {api_label}"
    lines.append(f"║  {title:<61}║")
    lines.append("╠══════════════════════════════════════════════════════════════╣")

    time_display = now.strftime("%H:%M:%S  %d/%m/%Y")
    lines.append(f"║  ⏰ {time_display:<58}║")
    lines.append(f"║  {sess_icon} {sess_name}  ({sess_time}){'':<35}║")
    lines.append("╠══════════════════════════════════════════════════════════════╣")

    if api_type in ("normal",):
        kq_emoji = RESULT_EMOJI.get(kq, "⬜")
        lines.append(f"║  🎲 PHIÊN #{phien:<8}  {kq_emoji} {kq:<8} {d1}{d2}{d3}  TỔNG: {tong:<5}    ║")
    elif api_type in ("md5", "md5_hitclub"):
        md5 = data.get("md5") or data.get("md5_raw") or "?"
        kq_emoji = RESULT_EMOJI.get(kq, "⬜")
        lines.append(f"║  🎲 PHIÊN #{phien:<8}  {kq_emoji} {kq:<8} {d1}{d2}{d3}  TỔNG: {tong:<5}    ║")
        lines.append(f"║  🔐 MD5: {str(md5)[:52]:<52}║")
    elif api_type == "xocdia":
        kq_td = data.get("ket_qua_truyen_thong", "?")
        kq_emoji = RESULT_EMOJI.get(kq_td, "⬜")
        chi_tiet = data.get("ket_qua_chi_tiet", "?")
        md5 = data.get("betting_info", {}).get("md5") or data.get("md5_raw") or "?"
        lines.append(f"║  🎲 PHIÊN #{phien:<8}  {kq_emoji} {kq_td:<8} Chi tiết: {chi_tiet:<10}║")
        lines.append(f"║  🔐 MD5: {str(md5)[:52]:<52}║")

    lines.append("╠══════════════════════════════════════════════════════════════╣")

    bar = _render_result_bar(hist, is_xocdia=(api_type == "xocdia"))
    lines.append(f"║  📜 LỊCH SỬ 15 PHIÊN GẦN:                                   ║")
    lines.append(f"║  {bar:<62}║")

    lines.append("╠══════════════════════════════════════════════════════════════╣")

    hist_list = list(hist)
    if api_type == "xocdia":
        results_list = [r.get("ket_qua_truyen_thong") for r in hist_list if r.get("ket_qua_truyen_thong") in ("Chẵn", "Lẻ")]
        labels = ["Chẵn", "Lẻ"]
    else:
        results_list = [r.get("ket_qua") for r in hist_list if r.get("ket_qua") in ("Tài", "Xỉu")]
        labels = ["Tài", "Xỉu"]

    streak = _get_streak(results_list) if results_list else 0
    streak_label = results_list[-1] if results_list else "?"
    streak_e = RESULT_EMOJI.get(streak_label, "⬜")
    lines.append(f"║  🔁 STREAK: {streak} phiên liên tiếp {streak_e} {streak_label:<6}              ║")

    st = stats[app][api_label]
    total_pred = st["dung"] + st["sai"]
    acc_str = f"{int(st['dung']/total_pred*100)}%" if total_pred > 0 else "Chưa có"
    lines.append(f"║  📊 ĐỘ CHÍNH XÁC: {acc_str:<6} ({st['dung']}✅ {st['sai']}❌ / {total_pred} phiên)        ║")

    lines.append("╠══════════════════════════════════════════════════════════════╣")
    lines.append("║  🧠 DỰ ĐOÁN PHIÊN TIẾP:                                     ║")

    if len(results_list) >= 5:
        best, conf, votes, total_m, top_m, top_acc, bt_acc = _ensemble_simple(
            results_list, labels, use_sum=(api_type != "xocdia"), session_bonus=session_bonus
        )
        if best:
            best_emoji = RESULT_EMOJI.get(best, "⬜")
            conf_bar = _conf_bar(conf)
            lines.append(f"║  {best_emoji} {best:<8}  Tin cậy: [{conf_bar}] {conf}%             ║")
            lines.append(f"║  🗳️  Votes: {votes}/{total_m} phương pháp đồng thuận               ║")
            pending_pred[app][api_label] = {"pred": best, "phien": phien, "time": now}
        else:
            lines.append(f"║  ⏳ Chưa đủ dữ liệu để dự đoán...                           ║")
    else:
        lines.append(f"║  ⏳ Đang thu thập dữ liệu ({len(results_list)}/5 phiên)...              ║")

    lines.append("╚══════════════════════════════════════════════════════════════╝")
    return "\n".join(lines)

async def fetch_and_show(app, api_info):
    async with aiohttp.ClientSession() as session:
        data = await fetch_data(session, api_info["url"])

    if not data:
        print(f"\n  ❌ Không lấy được dữ liệu từ {app} — {api_info['label']}")
        print("     Có thể API đang tắt hoặc mạng có vấn đề.")
        return False

    label = api_info["label"]
    api_type = api_info["type"]
    phien = data.get("phien")
    if phien is None:
        print(f"\n  ❌ Dữ liệu không hợp lệ (thiếu trường phien)")
        return False

    actual_kq = data.get("ket_qua") if api_type != "xocdia" else data.get("ket_qua_truyen_thong")
    verdict = _check_prev_pred(app, label, actual_kq)

    if last_phien[app][label] != phien:
        last_phien[app][label] = phien
        record = {
            "phien": phien,
            "ket_qua": data.get("ket_qua"),
            "tong": data.get("tong"),
            "xuc_xac_1": data.get("xuc_xac_1"),
            "xuc_xac_2": data.get("xuc_xac_2"),
            "xuc_xac_3": data.get("xuc_xac_3"),
        }
        if api_type == "xocdia":
            record["ket_qua_truyen_thong"] = data.get("ket_qua_truyen_thong")
            record["ket_qua_chi_tiet"] = data.get("ket_qua_chi_tiet")
        history_data[app][label].append(record)
        sess_key, _, _, _ = _get_current_session()
        session_history[app][label][sess_key].append(dict(record))

    clear()
    if verdict:
        status, pred, actual = verdict
        if status == "dung":
            print(f"  ✅  DỰ ĐOÁN ĐÚNG!  Đã đoán: {pred}  —  Kết quả: {actual}")
        else:
            print(f"  ❌  DỰ ĐOÁN SAI.   Đã đoán: {pred}  —  Kết quả: {actual}")
        print()

    print(format_prediction_block(app, label, api_type, data, history_data[app][label]))
    return True

async def watch_loop(app, api_info):
    print(f"\n  🔄 Đang theo dõi {app.upper()} — {api_info['label']} (cập nhật mỗi 15 giây)")
    print("  Nhấn Ctrl+C để quay lại menu...\n")
    await asyncio.sleep(1)

    try:
        while True:
            ok = await fetch_and_show(app, api_info)
            if not ok:
                print("\n  Thử lại sau 30 giây...")
                await asyncio.sleep(30)
            else:
                print(f"\n  🔄 Cập nhật lần tiếp: {15}s  |  Ctrl+C để quay lại menu")
                await asyncio.sleep(15)
    except KeyboardInterrupt:
        pass

async def single_fetch(app, api_info):
    print(f"\n  📡 Đang lấy dữ liệu...")
    await fetch_and_show(app, api_info)
    print()
    input("  Nhấn Enter để tiếp tục...")

async def main_loop():
    while True:
        clear()
        print_menu()
        apps = list(APIS.items())
        choice = input("  Nhập lựa chọn: ").strip()

        if choice == "0":
            clear()
            print("\n  👋 Tạm biệt! Chúc may mắn — by Dzi\n")
            break

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(apps):
                raise ValueError()
        except ValueError:
            continue

        app, apis = apps[idx]

        if len(apis) == 1:
            api_info = apis[0]
        else:
            while True:
                print_api_menu(app, apis)
                c2 = input("  Nhập lựa chọn: ").strip()
                if c2 == "0":
                    api_info = None
                    break
                try:
                    i2 = int(c2) - 1
                    if 0 <= i2 < len(apis):
                        api_info = apis[i2]
                        break
                except ValueError:
                    pass

            if api_info is None:
                continue

        clear()
        print_header()
        emoji = BRAND_EMOJI.get(app, "🎰")
        print(f"\n  {emoji}  {app.upper()} — {api_info['label']}")
        print()
        print("  [1] Xem 1 lần")
        print("  [2] Theo dõi tự động (cập nhật mỗi 15s)")
        print("  [0] Quay lại")
        print()
        print("─" * 65)
        mode = input("  Nhập lựa chọn: ").strip()

        if mode == "1":
            await single_fetch(app, api_info)
        elif mode == "2":
            await watch_loop(app, api_info)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\n\n  👋 Đã thoát.\n")
