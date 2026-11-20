"""보고서·발표 자료에 들어갈 수치를 outputs/에서 모아 report/numbers.json으로 저장한다.
문서의 숫자를 손으로 옮기지 않고 결과 파일에서 직접 가져와, 재실행하면 문서도 같은 숫자로 다시 만들 수 있다.

실행: python python/report_numbers.py   (run_all.py, long_eval.py, oos_2026.py 결과 필요)
"""
import json
import re

import numpy as np
import pandas as pd

from config import ALL_GEOS, OUTPUTS, ROOT

E = OUTPUTS / "experiment"
ENS = {"앙상블: 회귀(위기)+ML+Chronos": "ENS", "앙상블 (회귀·ML·Chronos)": "ENS"}


def r(x, d=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), d)


def text_num(path, pattern, group=1, cast=float):
    m = re.search(pattern, path.read_text(encoding="utf-8"))
    return cast(m.group(group)) if m else None


def main():
    N = {}
    # ---- 회귀 추론 (독일)
    st = OUTPUTS / "de_simple_regression.txt"
    N["simple"] = {
        "r2": text_num(st, r"\[Y ~ HDD\] R² = ([\d.]+)"),
        "b1": text_num(st, r"HDD가 1 늘면 월 수요는 ([\d.]+) PJ"),
        "b1_lo": text_num(st, r"95% CI ([\d.]+)~"), "b1_hi": text_num(st, r"95% CI [\d.]+~([\d.]+)\)"),
        "bp_y": text_num(st, r"\[Y ~ HDD\][\s\S]*?BP\(Koenker\) p = ([\d.]+)"),
        "bp_sqrt": text_num(st, r"\[√Y ~ HDD\][\s\S]*?BP\(Koenker\) p = ([\d.]+)"),
        "dw_y": text_num(st, r"\[Y ~ HDD\][\s\S]*?Durbin-Watson = ([\d.]+)"),
        "dw_sqrt": text_num(st, r"\[√Y ~ HDD\][\s\S]*?Durbin-Watson = ([\d.]+)"),
        "lof_y": text_num(st, r"\[Y ~ HDD\][\s\S]*?적합결여.*?p = ([\d.]+)"),
        "lof_sqrt": text_num(st, r"\[√Y ~ HDD\][\s\S]*?적합결여.*?p = ([\d.]+)"),
        "boxcox": text_num(st, r"최적 λ = ([\d.]+)"),
        "boxcox_lo": text_num(st, r"최적 λ = [\d.]+ \(95% CI ([\d.]+)~"),
        "boxcox_hi": text_num(st, r"최적 λ = [\d.]+ \(95% CI [\d.]+~([\d.]+)\)"),
    }
    mm = OUTPUTS / "de_multiple_regression.txt"
    N["multiple"] = {
        "hdd_pre": text_num(mm, r"HDD 1 증가 → 월 수요 ([\d.]+) PJ"),
        "hdd_post": text_num(mm, r"위기 후 HDD 효과: ([\d.]+) PJ"),
        "workdays_t": text_num(mm, r"영업일 t = ([\d.]+) \(OLS\)"),
        "r2": text_num(mm, r"## 4\.[\s\S]*?Multiple R-squared:\s+([\d.]+)"),
    }
    sm = OUTPUTS / "de_simultaneous_matrix.txt"
    N["ch45"] = {"W": text_num(sm, r"W = .*? = ([\d.]+), B"), "B": text_num(sm, r"B\(g=4\) = ([\d.]+)"),
                 "hac_ratio_b1": text_num(sm, r"OLS의 [\d.]+배\(β0\)·([\d.]+)배\(β1\)")}
    # ---- 국가별 회귀 (R5), 구조변화
    r5 = pd.read_csv(OUTPUTS / "r5_country_regression.csv").set_index("geo")
    N["r5"] = {g: {k: r(r5.loc[g, k], 2) for k in ("hdd10_pre", "hdd10_post", "p_hdd_change", "price_elast",
                                                   "crisis_level_pct", "R2")} for g in ALL_GEOS}
    br = pd.read_csv(OUTPUTS / "r2_structural_break.csv").set_index("geo")
    N["break"] = {g: {"chow_p": float(br.loc[g, "chow_p"]), "supF_hac_date": br.loc[g, "supF_hac_date"],
                      "bp_dates": br.loc[g, "bp_dates"]} for g in ALL_GEOS}
    # ---- 본 실험·MCS
    mcs = pd.read_csv(OUTPUTS / "r4_mcs.csv").replace({"model": ENS})
    for mode in ("ex_post", "ex_ante"):
        a = mcs[(mcs.geo == "ALL") & (mcs["mode"] == mode)].sort_values("MAPE")
        N[f"mcs_{mode}"] = {"n": int(len(a)), "in": a[a.in_mcs].model.tolist(),
                            "mape": {m: r(v) for m, v in zip(a.model, a.MAPE)}}
        per = mcs[(mcs.geo != "ALL") & (mcs["mode"] == mode)]
        N[f"mcs_size_{mode}"] = per.groupby("geo").in_mcs.sum().astype(int).to_dict()
        N[f"mcs_all6_{mode}"] = per.groupby("model").in_mcs.sum().pipe(lambda s: s[s == 6].index.tolist())
    summ = pd.read_csv(E / "summary.csv")
    N["main"] = {mode: summ[summ["mode"] == mode].pivot(index="model", columns="geo", values="MAPE")
                 .round(1).to_dict(orient="index") for mode in ("ex_post", "ex_ante")}
    # ---- 견고성
    rt = pd.read_csv(OUTPUTS / "realtime_check.csv").replace({"model": ENS})
    N["realtime"] = rt.groupby("model")[["MAPE_realtime", "MAPE_exante"]].mean().round(1).to_dict(orient="index")
    le = OUTPUTS / "long_eval"
    if (le / "summary_all.csv").exists():
        sa = pd.read_csv(le / "summary_all.csv").replace({"model": ENS})
        lm = pd.read_csv(le / "mcs.csv").replace({"model": ENS})
        rg = pd.read_csv(le / "regimes.csv").replace({"model": ENS})
        N["long"] = {mode: sa[sa["mode"] == mode].groupby("model").MAPE.mean().round(1).to_dict()
                     for mode in ("ex_post", "ex_ante")}
        N["long_mcs"] = {mode: lm[(lm.geo == "ALL") & (lm["mode"] == mode) & lm.in_mcs].model.tolist()
                         for mode in ("ex_post", "ex_ante")}
        N["long_mcs_size"] = {mode: lm[(lm.geo != "ALL") & (lm["mode"] == mode)].groupby("geo").in_mcs.sum()
                              .astype(int).to_dict() for mode in ("ex_post", "ex_ante")}
        N["regimes"] = (rg[rg["mode"] == "ex_post"].groupby(["model", "regime"]).MAPE.mean().unstack()
                        .round(1).to_dict(orient="index"))
    if (OUTPUTS / "oos_2026.csv").exists():
        oo = pd.read_csv(OUTPUTS / "oos_2026.csv").replace({"model": ENS})
        N["oos"] = oo.groupby("model")[["MAPE_ex_post", "MAPE_ex_ante", "MAPE_2023_2025"]].mean().round(1).to_dict(
            orient="index")
        N["oos_by_geo"] = oo.pivot(index="model", columns="geo", values="MAPE_ex_post").round(1).to_dict(orient="index")
        txt = (OUTPUTS / "oos_2026.md").read_text(encoding="utf-8")
        N["oos_rho"] = text_num(OUTPUTS / "oos_2026.md", r"Spearman 상관: (-?\d+\.\d+)")
    # ---- 기타 연구 과제
    r9 = pd.read_csv(OUTPUTS / "r9_intervals.csv")
    N["intervals"] = r9.groupby(["method", "level"])[["cover", "width"]].mean().round(1).reset_index().to_dict(
        orient="records")
    r6 = pd.read_csv(OUTPUTS / "r6_global.csv")
    N["global"] = r6.groupby("model")[["global_ex_post", "local_ex_post", "global_ex_ante", "local_ex_ante"]].mean() \
        .round(1).to_dict(orient="index")
    r7 = pd.read_csv(OUTPUTS / "r7_sector_sensitivity.csv")
    N["sector"] = {f"{a}|{b}": r(c, 2) for a, b, c in zip(r7.geo, r7["부문"], r7["HDD 10당 %"])}
    r11 = pd.read_csv(OUTPUTS / "r11_climate.csv")
    N["climate"] = {f"{g}|{s}": r(v, 1) for g, s, v in zip(r11.geo, r11.scenario, r11.annual_change_pct)}
    r3 = pd.read_csv(OUTPUTS / "r3_shap.csv")
    N["shap_rho"] = r3.groupby("geo").spearman.first().round(2).to_dict()
    N["shap_hdd"] = {g: [r(a), r(b)] for g, a, b in
                     r3[r3.feature == "hdd"][["geo", "ridge_shap_pct", "lgbm_shap_pct"]].itertuples(index=False)}
    # 2026년 HDD 보정의 연도별 교차검증 오차 (fetch_dwd.py, fetch_openmeteo.py → degree_days.py)
    from config import INTERIM
    cal = pd.concat([pd.read_csv(INTERIM / "dwd_de_degree_days.csv").assign(geo="DE"),
                     pd.read_csv(INTERIM / "openmeteo_degree_days.csv")])
    N["hdd_cal"] = cal.groupby("geo")[["cv_mae", "cv_mae_linear", "delta"]].first().to_dict(orient="index")
    N["leakage"] = text_num(OUTPUTS / "leakage_check.md", r"통과 (\d+)건", cast=int)
    # 평가 설계별 6개국 평균 MAPE와 통합 MCS (그림 5와 같은 표 — 발표 자료의 표로 쓴다)
    from figures import design_table, yearly_mape
    N["de_yearly"] = {ENS.get(k, k): {y: r(v) for y, v in d.items()} for k, d in yearly_mape("DE").items()}
    if "oos" in N:   # 2026년 6개국 평균 순위 (상위 모델이 얼마나 붙어 있는지 문서에 쓴다)
        N["oos_rank"] = sorted(([m, v["MAPE_ex_post"]] for m, v in N["oos"].items()), key=lambda x: x[1])
    mat, dots = design_table()
    N["design"] = {"columns": [c.replace("\n", " ") for c in mat.columns], "models": list(mat.index),
                   "values": [[r(v) for v in row] for row in mat.values.tolist()],
                   "mcs": dots.values.tolist()}
    out = ROOT / "report" / "numbers.json"
    out.write_text(json.dumps(N, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"저장: {out} ({len(N)}개 항목)")


if __name__ == "__main__":
    main()
