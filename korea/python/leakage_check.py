"""데이터 누수 자동 점검: 예측 시점 T 이후의 수요·기온·가격을 ×10으로 망가뜨려도 사전예측이 그대로인지 본다.

평년 기온 열(hdd_clim 등)은 T 이전 해의 값으로 이미 계산돼 있어 그대로 둔다. 사후예측은 실제 기온을 쓰도록 설계했으므로
값이 바뀌어야 정상이다(검사가 누수를 실제로 잡아내는지 확인하는 음성 대조군).

출력: outputs/leakage_check.md
"""
import json

import numpy as np
import pandas as pd

import models_mh as M
from config import OUTPUTS, PROCESSED
from mh import future_frame

T_LIST = ["2022-06", "2023-11", "2025-03"]
CORRUPT = ["city", "power", "total", "hdd", "cdd", "tmean", "cpi_city_gas", "ip", "lng_usd", "elec_twh"]
FN = {"계절 naive": M.snaive, "회귀 √Y": M.reg, "SARIMAX": M.sarimax, "ETS": M.ets, "Ridge": M.ridge, "LightGBM": M.lgbm,
      "하이브리드 (회귀+Ridge)": M.hybrid_ridge, "하이브리드 (회귀+LightGBM)": M.hybrid_lgbm}


def predict(df, series, fn, params, T, info):
    d = df.rename(columns={series: "y"})
    d = d[d.month >= "2016-01"].reset_index(drop=True)
    return np.asarray(fn(d[(d.month <= T) & d.y.notna()], future_frame(d, T, info), **params), float)


def main():
    df = pd.read_csv(PROCESSED / "national.csv")
    tun = pd.read_csv(OUTPUTS / "national" / "tuning.csv")
    best = tun.dropna().sort_values(["val_MAPE", "params"]).groupby(["series", "model"]).first().reset_index()
    rows = []
    for b in best.itertuples():
        params = {k: tuple(v) if isinstance(v, list) else v for k, v in json.loads(b.params).items()}
        for T in T_LIST:
            bad = df.copy()
            bad.loc[bad.month > T, [c for c in CORRUPT if c in bad]] *= 10
            for info in ("ex_ante", "ex_post"):
                a = predict(df, b.series, FN[b.model], params, T, info)
                z = predict(bad, b.series, FN[b.model], params, T, info)
                rows.append({"series": b.series, "model": b.model, "T": T, "info": info,
                             "max_rel_change": float(np.nanmax(np.abs(z - a) / np.abs(a)))})
    r = pd.DataFrame(rows)
    ante = r[r["info"] == "ex_ante"]
    ok = (ante.max_rel_change < 1e-9).sum()
    post_changed = (r[(r["info"] == "ex_post") & ~r.model.isin(["계절 naive", "ETS"])]
                    .max_rel_change > 1e-6).sum()
    L = ["# 데이터 누수 점검", "",
         f"사전예측: {len(ante)}건 중 통과 {ok}건 (예측 시점 이후 자료를 ×10으로 바꿔도 예측 불변).",
         f"음성 대조군: 사후예측(실제 기온 사용)은 기온을 쓰는 모델 {post_changed}건에서 예측이 바뀌어 검사가 변화를 잡아낸다.", ""]
    if ok < len(ante):
        L += ["## 실패", "", ante[ante.max_rel_change >= 1e-9].to_markdown(index=False)]
    (OUTPUTS / "leakage_check.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    if ok < len(ante):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
