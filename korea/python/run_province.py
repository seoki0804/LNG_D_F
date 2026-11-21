"""지역별(17개 시도) 도시가스 판매량의 1~12개월 앞 계층 예측.

전국 판매량 = 17개 시도의 합. 각 시도와 전국을 같은 방법으로 따로 예측한 뒤(기본 예측), 합이 맞도록 조정한다.
  - 기본(조정 없음): 전국은 전국 모델로 직접 예측
  - 상향식(BU): 시도 예측의 합을 전국 예측으로
  - 하향식(TD): 전국 예측을 최근 3년 같은 달 시도 비중으로 나눔
  - MinT(shrink): 검증 구간의 예측 오차 공분산으로 가중해 모든 수준을 함께 조정 (Wickramasuriya et al., 2019)
기간: 학습 2006~, 검증 목표월 2017~2019(설정 선택·MinT 공분산), 평가 목표월 2020~2022.
시도별 판매량은 2023년 1월에 정의가 바뀌어(모든 시도 약 −25%) 2022년까지만 쓴다.

출력: outputs/province/{tuning,base_predictions,reconciled,summary}.csv
실행: python run_province.py   (Chronos-2는 foundation_mh.py --province 결과가 있으면 함께 조정)
"""
import itertools
import json

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

import models_mh as M
from config import OUTPUTS, PROVINCES
from mh import HORIZONS, rolling, summary
from province_data import EVAL_P, NODES, TOTAL, TRAIN_P, VAL_P, load_frames

OUT = OUTPUTS / "province"
OUT.mkdir(parents=True, exist_ok=True)
GRID = {
    "계절 naive": (M.snaive, [{}]),
    # 판매량은 검침 시점 기준이라 전월 기온(hdd_l1)에도 반응한다. 최근 8년만 적합하는 설정도 후보로 둔다
    "회귀 √Y": (M.reg, [{"feats": f, "recent": w} for f, w in itertools.product(
        [("hdd", "hdd_l1", "cdd", "cdd_l1"), ("hdd", "hdd_l1", "cdd", "cdd_l1", "trend"),
         ("hdd", "hdd_l1", "cdd", "cdd_l1", "workdays", "trend")], [None, 96])]),
    "ETS": (M.ets, [{"trend": None}, {"trend": "add", "damped": True}]),
}


def run_one(frames, node, model, fn, params, window):
    r = rolling(frames[node], "y", fn, window, train_start=TRAIN_P, **params)
    return r.assign(node=node, model=model, params=json.dumps(params, ensure_ascii=False, default=list))


# ---------------- 조정 ----------------
def s_matrix():
    return np.vstack([np.ones(len(PROVINCES)), np.eye(len(PROVINCES))])      # 전국 + 17개 시도


def shrink_cov(E):
    """Schäfer–Strimmer 수축 공분산 (대각 목표). E: 오차 행렬 (관측 × 노드)."""
    E = E - np.nanmean(E, axis=0)
    n = np.sum(~np.isnan(E).any(axis=1))
    E = E[~np.isnan(E).any(axis=1)]
    S = E.T @ E / n
    d = np.sqrt(np.diag(S))
    R = S / np.outer(d, d)
    Es = E / d
    W = np.einsum("ti,tj->tij", Es, Es)
    var_r = n / (n - 1) ** 3 * ((W - W.mean(0)) ** 2).sum(0)
    off = ~np.eye(len(d), dtype=bool)
    lam = np.clip(var_r[off].sum() / (R[off] ** 2).sum(), 0, 1)
    Rs = (1 - lam) * R
    np.fill_diagonal(Rs, 1)
    return Rs * np.outer(d, d)


def reconcile(base, val_base, frames):
    """base: 평가 구간 기본 예측 (node, origin, month, h, pred). 반환: 방법별 조정 예측."""
    S = s_matrix()
    wide = base.pivot_table(index=["origin", "month", "h"], columns="node", values="pred")[NODES]
    out = {"기본": wide.copy()}
    # 상향식
    bu = wide.copy()
    bu[TOTAL] = wide[PROVINCES].sum(axis=1)
    out["상향식"] = bu
    # 하향식: 예측 시점 직전 3년의 같은 달 시도 비중
    y = pd.DataFrame({k: f.set_index("month").y for k, f in frames.items()})
    td = wide.copy()
    for (o, m, h), _ in wide.iterrows():
        past = [(pd.Period(m, "M") - 12 * k).strftime("%Y-%m") for k in (1, 2, 3)]
        past = [p for p in past if p <= o]
        sh = y.loc[past, PROVINCES].sum() / y.loc[past, PROVINCES].sum().sum()
        td.loc[(o, m, h), PROVINCES] = wide.loc[(o, m, h), TOTAL] * sh.values
    out["하향식"] = td
    # MinT: 검증 구간 오차(전 예측 시계)의 수축 공분산
    vw = val_base.pivot_table(index=["origin", "month", "h"], columns="node", values="pred")[NODES]
    va = val_base.pivot_table(index=["origin", "month", "h"], columns="node", values="actual")[NODES]
    Wm = shrink_cov((va - vw).values)
    Wi = np.linalg.inv(Wm)
    P = S @ np.linalg.solve(S.T @ Wi @ S, S.T @ Wi)
    out["MinT"] = pd.DataFrame(wide.values @ P.T, index=wide.index, columns=pd.Index(NODES, name="node"))
    return out


def main():
    frames = load_frames()
    tasks = [(n, m, fn, p) for n in NODES for m, (fn, ps) in GRID.items() for p in ps]
    print(f"튜닝 {len(tasks)}개", flush=True)
    val = Parallel(n_jobs=8)(delayed(run_one)(frames, *t, VAL_P) for t in tasks)
    val = pd.concat(val, ignore_index=True)
    tun = val.groupby(["node", "model", "params"]).apply(lambda g: summary(g)["all"]).rename("val_MAPE").reset_index()
    tun.to_csv(OUT / "tuning.csv", index=False, encoding="utf-8-sig")
    best = tun.sort_values(["val_MAPE", "params"]).groupby(["node", "model"]).first().reset_index()
    val_best = val.merge(best[["node", "model", "params"]], on=["node", "model", "params"])
    fns = {m: fn for m, (fn, _) in GRID.items()}
    ev = Parallel(n_jobs=8)(delayed(run_one)(frames, b.node, b.model, fns[b.model],
                                             {k: tuple(v) if isinstance(v, list) else v
                                              for k, v in json.loads(b.params).items()}, EVAL_P)
                            for b in best.itertuples())
    ev = pd.concat(ev, ignore_index=True)
    fm = OUT / "foundation.csv"
    if fm.exists():   # Chronos-2 (학습 없음): 검증·평가 구간 모두 있다
        f = pd.read_csv(fm)
        f = f[(f.model == "Chronos-2 + 공변량") & (f["info"] == "ex_ante")].rename(columns={"name": "node"})
        for win, store in ((VAL_P, "val"), (EVAL_P, "ev")):
            part = f[(f.month >= win[0]) & (f.month <= win[1])][["node", "origin", "month", "h", "pred", "actual"]]
            part = part.assign(model="Chronos-2 + 공변량", params="{}")
            if store == "val":
                val_best = pd.concat([val_best, part], ignore_index=True)
            else:
                ev = pd.concat([ev, part], ignore_index=True)
    ev.to_csv(OUT / "base_predictions.csv", index=False, encoding="utf-8-sig")

    rows, rec_all = [], []
    for model in ev.model.unique():
        base, vb = ev[ev.model == model], val_best[val_best.model == model]
        act = base.pivot_table(index=["origin", "month", "h"], columns="node", values="actual")[NODES]
        for method, pr in reconcile(base, vb, frames).items():
            long = pr.stack().rename("pred").reset_index().merge(
                act.stack().rename("actual").reset_index(), on=["origin", "month", "h", "node"])
            rec_all.append(long.assign(model=model, method=method))
            for level, sub in (("전국", long[long.node == TOTAL]), ("시도 평균", long[long.node != TOTAL])):
                rows.append({"model": model, "method": method, "level": level, **summary(sub)})
    pd.concat(rec_all).to_csv(OUT / "reconciled.csv", index=False, encoding="utf-8-sig")
    summ = pd.DataFrame(rows)
    summ.to_csv(OUT / "summary.csv", index=False, encoding="utf-8-sig")
    print(summ[["model", "method", "level", "h1", "h3", "h6", "h12", "all"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
