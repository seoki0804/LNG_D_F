"""보고서·발표 자료의 수치를 outputs/에서 모아 report/numbers.json으로 저장한다 (문서 숫자를 손으로 옮기지 않는다).

실행: python python/report_numbers.py   (evaluate.py, run_province.py, R 스크립트 결과 필요)
"""
import json
import re

import numpy as np
import pandas as pd

from config import OUTPUTS, PROCESSED, ROOT

NAT, PROV, REG = OUTPUTS / "national", OUTPUTS / "province", OUTPUTS / "regression"


def r(x, d=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), d)


def main():
    N = {}
    # ---- 자료
    d = pd.read_csv(PROCESSED / "national.csv")
    obs = d[d.total.notna()]
    y25 = obs[obs.month.str[:4] == "2025"]
    N["data"] = {"start": obs.month.min(), "end": obs.month.max(), "n": int(len(obs)),
                 "city_2025": r(y25.city.sum() / 1000), "power_2025": r(y25.power.sum() / 1000),
                 "city_share_2025": r(y25.city.sum() / y25.total.sum() * 100),
                 "city_peak_ratio": r(obs.groupby(obs.month.str[:4]).city.max().mean()
                                      / obs.groupby(obs.month.str[:4]).city.min().mean(), 2),
                 "power_peak_ratio": r(obs.groupby(obs.month.str[:4]).power.max().mean()
                                       / obs.groupby(obs.month.str[:4]).power.min().mean(), 2)}
    raw = pd.read_csv(sorted((ROOT / "data" / "raw").glob("*/kogas_national.csv"))[-1])
    jul19 = raw[(raw["연도"] == 2019) & (raw["월"] == 7) & (raw["용도"] == "도시가스")]["공급량"].iloc[0] / 1000
    N["data"]["fix2019"] = {"before": r(jul19, 0), "after": r(d.loc[d.month == "2019-07", "city"].iloc[0], 0)}

    # ---- 회귀
    c = pd.read_csv(REG / "national_coefs.csv")
    t = pd.read_csv(REG / "national_tests.csv")
    get = lambda m, term, col="est": float(c[(c.model == m) & (c.term == term)][col].iloc[0])
    tst = lambda m, name, col="stat": t[(t.model == m) & (t.test == name)][col].iloc[0]
    N["reg"] = {
        "b1": r(get("A: Y~HDD", "hdd"), 2), "b1_se": r(get("A: Y~HDD", "hdd", "se"), 3),
        "b1_se_hac": r(get("A: Y~HDD", "hdd", "se_hac"), 3), "r2_simple": r(tst("A: Y~HDD", "R2"), 3),
        "bp_y": r(tst("A: Y~HDD", "BP(Koenker)", "p"), 3), "bp_sqrt": r(tst("A: √Y~HDD", "BP(Koenker)", "p"), 3),
        "dw_sqrt": r(tst("A: √Y~HDD", "Durbin-Watson"), 2), "boxcox": r(tst("A: Y~HDD", "Box-Cox λ"), 2),
        "boxcox_ci": t[(t.model == "A: Y~HDD") & (t.test == "Box-Cox λ")].note.iloc[0],
        "lof_sqrt_p": float(tst("A: √Y~HDD", "적합결여(3차항 F)", "p")),
        "inverse": t[(t.model == "A: Y~HDD") & (t.test == "역예측 Y=3000")].note.iloc[0],
        "inverse_hdd": r(tst("A: Y~HDD", "역예측 Y=3000"), 0),
        "r2_city_multi": r(tst("B: 도시가스용", "R2"), 3), "r2_power": r(tst("C: 발전용", "R2"), 2),
        "r2_power_weather": r(tst("C: 발전용", "R2 기온만"), 2),
        "p_elec": float(tst("C: 발전용", "부분 F: elec_twh", "p")), "p_coal": float(tst("C: 발전용", "부분 F: coal_cap", "p")),
        "p_weather_power": float(tst("C: 발전용", "부분 F: hdd+cdd", "p")),
        "break_date": t[(t.model == "D: 구조변화")].note.iloc[0], "break_p": float(tst("D: 구조변화", "sup-F", "p")),
        "break2_date": t[(t.model == "D: 구조변화 2020~2025")].note.iloc[0],
        "break2_p": float(tst("D: 구조변화 2020~2025", "sup-F", "p")),
        # √Y 모형의 요금 계수 → 평균 수준에서의 탄력성: dY/Y = 2·b·d(log P)/√Y
        "price_elast": r(2 * get("B: 도시가스용", "log_cpi") / np.sqrt(d[(d.month >= "2016-01") & (d.month <= "2025-12")].city).mean(), 2),
        "lng_coef_p": float(c[(c.model == "C: 발전용") & (c.term == "log_lng")].p_hac.iloc[0]),
        "vif_elec": r(tst("C: 발전용", "VIF elec_twh"), 1),
        "cpi_coef_hac_p": float(c[(c.model == "B: 도시가스용") & (c.term == "log_cpi")].p_hac.iloc[0]),
        "cpi_coef": r(get("B: 도시가스용", "log_cpi"), 2),
    }
    s = pd.read_csv(REG / "province_sensitivity.csv")
    N["province_sens"] = {f"{a}|{b}": r(v, 2) for a, b, v in zip(s.province, s.period, s.pct_per10)}
    mid = s[s.period == "2010~2019"].set_index("province").pct_per10
    N["province_sens_range"] = {"min_prov": mid.idxmin(), "min": r(mid.min(), 1), "max_prov": mid.idxmax(), "max": r(mid.max(), 1)}
    pt = pd.read_csv(REG / "province_tests.csv")
    N["province_F"] = r(pt.stat.iloc[0], 0)

    # ---- 전국 예측
    sa = pd.read_csv(NAT / "summary_all.csv")
    hc = [f"h{h}" for h in range(1, 13)] + ["h1-3", "h4-6", "h7-12", "all"]
    N["nat"] = {f"{s_}|{m}|{i}|{w}": {k: r(v) for k, v in zip(hc, row)}
                for s_, m, i, w, row in zip(sa.series, sa.model, sa["info"], sa.window, sa[hc].values.tolist())}
    mcs = pd.read_csv(NAT / "mcs.csv")
    N["mcs"] = {f"{s_}|{i}|{h}": g[g.in_mcs].model.tolist() for (s_, i, h), g in mcs.groupby(["series", "info", "horizon"])}
    dm = pd.read_csv(NAT / "dm.csv")
    N["dm_beats_snaive"] = {f"{s_}|{i}|{m}": int(((g.p < 0.05) & (g.dm < 0)).sum())
                            for (s_, i, m), g in dm.groupby(["series", "info", "model"])}
    # ---- 시도 계층
    ps = pd.read_csv(PROV / "summary.csv")
    N["prov"] = {f"{m}|{me}|{lv}": {k: r(v) for k, v in zip(hc, row)}
                 for m, me, lv, row in zip(ps.model, ps.method, ps.level, ps[hc].values.tolist())}
    # ---- 추가 변수 점검 (r_variables.py → variables.md 표)
    vf = NAT / "variables.md"
    if vf.exists():
        rows = [l.split("|")[1:-1] for l in vf.read_text(encoding="utf-8").splitlines()
                if l.startswith("| ") and "검증 MAPE" not in l and "---" not in l]
        rows = [[c.strip() for c in r] for r in rows]
        adopted = [r for r in rows if r[7] == "✓"]
        gains = [float(r[5]) for r in adopted]
        sig_better = [r for r in rows if r[5] and r[6] not in ("", "nan") and float(r[5]) > 0 and float(r[6]) < 0.05]
        N["vars"] = {"n_adopted": len(adopted), "avg_eval_gain": r(sum(gains) / len(gains), 2) if gains else None,
                     "n_eval_better": sum(g > 0 for g in gains),
                     "n_sig_better_adopted": sum(1 for x in adopted if float(x[5]) > 0 and float(x[6]) < 0.05),
                     "n_sig_worse_adopted": sum(1 for x in adopted if float(x[5]) < 0 and float(x[6]) < 0.05)}
    # ---- 누수
    lk = (OUTPUTS / "leakage_check.md").read_text(encoding="utf-8") if (OUTPUTS / "leakage_check.md").exists() else ""
    m = re.search(r"(\d+)건 중 통과 (\d+)건", lk)
    N["leakage"] = {"n": int(m.group(1)), "ok": int(m.group(2))} if m else None
    # ---- 6개국 비교 (multicountry)
    mc = ROOT.parent / "multicountry" / "report" / "numbers.json"
    if mc.exists():
        M = json.loads(mc.read_text(encoding="utf-8"))
        N["six"] = {"r5": M["r5"], "main_ex_post": M["main"]["ex_post"], "mcs_all6_ex_post": M.get("mcs_all6_ex_post"),
                    "long_mcs": M.get("long_mcs"), "oos": M.get("oos")}
    out = ROOT / "report" / "numbers.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(N, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"저장: {out} ({len(N)}개 항목)")


if __name__ == "__main__":
    main()
