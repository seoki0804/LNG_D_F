"""연구 과제 R11 (기후 시나리오): 겨울 HDD가 10% 줄면 국가별 연간 수요는 얼마나 줄어드는가.

- 민감도: R5의 국가별 로그 회귀 log(Y) ~ HDD + CDD + log(요금) + 위기 + HDD×위기 의 위기 후 HDD 계수
  (R/03_country_regression.R → outputs/r5_country_regression.csv, 95% 구간 포함).
- 기준 연도: 2023~2025년 월평균 수요와 HDD (위기 후 구조).
- 시나리오 A: 겨울(12~2월) HDD −10%.  시나리오 B: 난방철 전체(10~4월) HDD −10%.
- 연간 수요 변화(%) = Σ_m Ȳ_m (exp(β·ΔHDD_m) − 1) / Σ_all Ȳ_m,  ΔHDD_m = −0.1·HDD_m.
- 구간: β의 95% 구간 양 끝으로 계산 (다른 변수는 고정, 기온 외 요인 변화는 반영하지 않음).

출력: outputs/r11_climate.md, outputs/r11_climate.csv
실행: python python/r11_climate.py   (R/03_country_regression.R 결과 필요)
"""
import numpy as np
import pandas as pd

from config import ALL_GEOS, GEO_NAMES, OUTPUTS
from rolling_eval import load_country

SCENARIOS = {"겨울(12~2월) HDD −10%": [12, 1, 2], "난방철(10~4월) HDD −10%": [10, 11, 12, 1, 2, 3, 4]}


def beta(pct10):
    return np.log1p(pct10 / 100) / 10   # HDD 10당 % → 로그 기울기


def main():
    r5 = pd.read_csv(OUTPUTS / "r5_country_regression.csv").set_index("geo")
    rows = []
    for g in ALL_GEOS:
        d = load_country(g)
        d = d[(d.month >= "2023-01") & (d.month <= "2025-12")].copy()
        d["m"] = d.month.str[5:7].astype(int)
        base = d.groupby("m").agg(y=("y", "mean"), hdd=("hdd", "mean"))
        total = base.y.sum()
        b = {k: beta(r5.loc[g, c]) for k, c in (("mid", "hdd10_post"), ("lo", "hdd10_post_lo"),
                                                 ("hi", "hdd10_post_hi"))}
        for name, months in SCENARIOS.items():
            sel = base.loc[months]
            ch = {k: (sel.y * (np.exp(v * -0.1 * sel.hdd) - 1)).sum() / total * 100 for k, v in b.items()}
            hdd_cut = 0.1 * sel.hdd.sum()
            rows.append({"geo": g, "scenario": name, "annual_change_pct": ch["mid"],
                         "ci_low": min(ch["lo"], ch["hi"]), "ci_high": max(ch["lo"], ch["hi"]),
                         "hdd_cut_per_year": hdd_cut, "annual_hdd": base.hdd.sum(),
                         "annual_demand": total, "unit": d.y_unit.iloc[0]})
    tab = pd.DataFrame(rows)
    tab.to_csv(OUTPUTS / "r11_climate.csv", index=False, encoding="utf-8-sig")
    L = ["# R11 기후 시나리오: 난방 도일 감소 → 연간 수요 변화", "",
         "R5 국가별 로그 회귀의 위기 후 HDD 민감도(95% 구간)를 2023~2025년 월평균 수요·HDD에 적용. "
         "기온 외 요인(가격, 산업, 발전 믹스)은 고정.", "",
         "| 국가 | 연간 HDD | 겨울(12~2월) HDD −10% | 난방철(10~4월) HDD −10% |", "| --- | --- | --- | --- |"]
    for g in ALL_GEOS:
        s = tab[tab.geo == g].set_index("scenario")
        cells = [f"{s.loc[n, 'annual_change_pct']:.1f}% [{s.loc[n, 'ci_low']:.1f}, {s.loc[n, 'ci_high']:.1f}]"
                 for n in SCENARIOS]
        L.append(f"| {GEO_NAMES[g]} | {s.annual_hdd.iloc[0]:.0f} | " + " | ".join(cells) + " |")
    (OUTPUTS / "r11_climate.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
