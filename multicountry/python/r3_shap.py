"""연구 과제 R3 (해석가능성): 회귀계수와 SHAP 기여도가 같은 결론을 내는가.

- 국가마다 본 실험에서 고른 설정으로 Ridge(선형)와 LightGBM(트리)을 2015-01~2025-12 전체로 적합한다.
- 두 모델 모두 같은 방법(순열 SHAP, 수요 원 단위)으로 변수 기여도를 구한다 → 평균 |SHAP|의 비중(%).
- Ridge는 표준화 계수(|β|)도 함께 보고한다 (√Y 타깃이면 √Y 공간의 계수).
- 두 모델의 변수 순위 일치도: Spearman 순위상관.

출력: outputs/r3_shap.md, outputs/r3_shap.csv, outputs/figures/r3_shap.png
실행: python python/r3_shap.py   (run_experiment.py 결과 필요)
"""
import json
import warnings

warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from lightgbm import LGBMRegressor
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from config import ALL_GEOS, GEO_NAMES, OUTPUTS
from rolling_eval import BASE_FEATURES, load_country
from run_experiment import OUT as EXP_OUT

LABELS = {"hdd": "HDD", "cdd": "CDD", "price_retail": "소비자요금", "price_wholesale_lag1": "도매가(전월)",
          "ip": "산업생산", "msin": "월 sin", "mcos": "월 cos", "lag1": "전월 수요", "lag12": "12개월 전 수요"}
plt.rcParams["font.family"] = [f for f in ("Malgun Gothic", "AppleGothic", "NanumGothic")
                              if any(f == x.name for x in matplotlib.font_manager.fontManager.ttflist)] or ["DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def fit_ridge(X, y, p):
    sc = StandardScaler().fit(X)
    sqrt = p.get("target") == "sqrt"
    r = Ridge(alpha=p["alpha"]).fit(sc.transform(X), np.sqrt(y) if sqrt else y)

    def predict(Z):
        out = r.predict(sc.transform(pd.DataFrame(Z, columns=X.columns)))
        return out ** 2 if sqrt else out
    return predict, np.abs(r.coef_)


def fit_lgbm(X, y, p):
    m = LGBMRegressor(learning_rate=0.05, n_estimators=200, random_state=0, n_jobs=4, verbose=-1, **p).fit(X, y)
    return lambda Z: m.predict(pd.DataFrame(Z, columns=X.columns))


def shap_share(predict, X):
    ex = shap.PermutationExplainer(predict, shap.maskers.Independent(X, max_samples=100), seed=0)
    sv = ex(X.to_numpy(), max_evals=2 * X.shape[1] + 1 + 200, silent=True).values
    imp = np.abs(sv).mean(axis=0)
    return imp / imp.sum() * 100


def main():
    s = pd.read_csv(EXP_OUT / "summary.csv")
    s = s[s["mode"] == "ex_post"].set_index(["geo", "model"])
    rows, shares = [], {}
    for g in ALL_GEOS:
        df = load_country(g)
        d = df[(df.month >= "2015-01") & (df.month <= "2025-12")].dropna(subset=BASE_FEATURES + ["y"])
        X, y = d[BASE_FEATURES].reset_index(drop=True), d["y"].to_numpy()
        pr, coef = fit_ridge(X, y, json.loads(s.loc[(g, "Ridge"), "params"]))
        pl = fit_lgbm(X, y, json.loads(s.loc[(g, "LightGBM"), "params"]))
        sh_r, sh_l = shap_share(pr, X), shap_share(pl, X)
        coef_share = coef / coef.sum() * 100
        rho = spearmanr(sh_r, sh_l).statistic
        shares[g] = (sh_r, sh_l)
        for f, a, b, c in zip(BASE_FEATURES, sh_r, sh_l, coef_share):
            rows.append({"geo": g, "feature": f, "ridge_shap_pct": a, "lgbm_shap_pct": b, "ridge_coef_pct": c,
                         "spearman": rho})
        print(f"{g}: Spearman {rho:.2f}, Ridge 상위 {[LABELS[BASE_FEATURES[i]] for i in np.argsort(-sh_r)[:3]]}, "
              f"LightGBM 상위 {[LABELS[BASE_FEATURES[i]] for i in np.argsort(-sh_l)[:3]]}", flush=True)
    tab = pd.DataFrame(rows)
    tab.to_csv(OUTPUTS / "r3_shap.csv", index=False, encoding="utf-8-sig")

    # 표: 국가별 변수 기여도 비중 (Ridge / LightGBM)
    L = ["# R3 해석가능성: Ridge vs LightGBM 변수 기여도 (평균 |SHAP| 비중 %)", "",
         "2015-01~2025-12 전체 적합, 순열 SHAP(수요 원 단위). 칸 = 'Ridge / LightGBM'.", "",
         "| 변수 | " + " | ".join(GEO_NAMES[g] for g in ALL_GEOS) + " |", "| --- |" + " --- |" * len(ALL_GEOS)]
    for f in BASE_FEATURES:
        cells = []
        for g in ALL_GEOS:
            r = tab[(tab.geo == g) & (tab.feature == f)].iloc[0]
            cells.append(f"{r.ridge_shap_pct:.0f} / {r.lgbm_shap_pct:.0f}")
        L.append(f"| {LABELS[f]} | " + " | ".join(cells) + " |")
    L.append("| 순위상관 (Spearman) | " + " | ".join(
        f"{tab[tab.geo == g].spearman.iloc[0]:.2f}" for g in ALL_GEOS) + " |")
    (OUTPUTS / "r3_shap.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    # 그림: 국가별 두 모델의 기여도 비중
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5), sharex=True)
    ypos = np.arange(len(BASE_FEATURES))
    for ax, g in zip(axes.ravel(), ALL_GEOS):
        a, b = shares[g]
        ax.barh(ypos + 0.2, a, height=0.4, color="#4C78A8", label="Ridge")
        ax.barh(ypos - 0.2, b, height=0.4, color="#F58518", label="LightGBM")
        ax.set_yticks(ypos, [LABELS[f] for f in BASE_FEATURES])
        ax.invert_yaxis()
        ax.set_title(f"{GEO_NAMES[g]} (순위상관 {tab[tab.geo == g].spearman.iloc[0]:.2f})")
        ax.grid(axis="x", color="#eeeeee")
        ax.set_axisbelow(True)
    for ax in axes[1]:
        ax.set_xlabel("평균 |SHAP| 비중 (%)")
    axes[0, 0].legend(loc="lower right")
    fig.suptitle("변수 기여도: Ridge(선형) vs LightGBM(트리), 순열 SHAP", fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUTPUTS / "figures" / "r3_shap.png", dpi=130)
    print("\n".join(L))
    print("저장: outputs/r3_shap.md, outputs/figures/r3_shap.png")


if __name__ == "__main__":
    main()
