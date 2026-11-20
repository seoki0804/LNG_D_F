"""독일 부문별 수요: Trading Hub Europe(THE) 일별 집계 소비량 → 월별 SLP·RLM (PJ). 키 불필요.

- SLP (Standardlastprofil): 가정·소상공 등 소규모 수요. 합성(syn)+분석(ana) 프로파일, H·L 가스 합계
- RLM (registrierende Leistungsmessung): 계량되는 산업·발전 등 대규모 수요. 일 단위 계량(mT)+그 외(oT), H·L 합계
- 단위 kWh → PJ (1 kWh = 3.6e-9 PJ). 가스일은 06:00~익일 06:00, 시작일 기준으로 월에 넣는다.
- 날마다 가장 확정된 값 하나가 온다 (corrected > final(clearing) > preliminary(allocation)).
- THE 통합 시장은 2021-10 출범 → 자료는 2021-10부터.

출력: data/raw/<호출일>/the_daily.csv, data/interim/the_sector.csv
실행: python python/fetch_the.py
"""
import datetime as dt

import pandas as pd
import requests

from config import INTERIM, RAW

URL = "https://api.tradinghub.eu/api/website/evoq/GetAggregierteVerbrauchsdatenTabelle"
START = dt.date(2021, 10, 1)
SLP = ["slPsyn_H_Gas", "slPsyn_L_Gas", "slPana_H_Gas", "slPana_L_Gas"]
RLM = ["rlMmT_H_Gas", "rlMmT_L_Gas", "rlMoT_H_Gas", "rlMoT_L_Gas"]
KWH_TO_PJ = 3.6e-9


def fetch(start, end):
    r = requests.get(URL, params={"DatumStart": start.isoformat(), "DatumEnde": end.isoformat(),
                                  "GasXType_Id": "all"}, timeout=120)
    r.raise_for_status()
    return pd.DataFrame(r.json())


def main():
    today = dt.date.today()
    frames = []
    for y in range(START.year, today.year + 1):
        a = max(START, dt.date(y, 1, 1))
        b = min(dt.date(y, 12, 31), today - dt.timedelta(days=1))
        df = fetch(a, b)
        print(f"THE {a}~{b}: {len(df)}일, 상태 {df.statusEN.value_counts().to_dict()}")
        frames.append(df)
    daily = pd.concat(frames, ignore_index=True)
    daily["date"] = daily.gastag.str[:10]
    daily = daily.drop_duplicates("date").sort_values("date")
    out_raw = RAW / today.strftime("%Y%m%d")
    out_raw.mkdir(parents=True, exist_ok=True)
    daily[["date", "statusEN"] + SLP + RLM].to_csv(out_raw / "the_daily.csv", index=False, encoding="utf-8")

    daily["month"] = daily.date.str[:7]
    daily["slp_pj"] = daily[SLP].sum(axis=1, min_count=len(SLP)) * KWH_TO_PJ
    daily["rlm_pj"] = daily[RLM].sum(axis=1, min_count=len(RLM)) * KWH_TO_PJ
    m = daily.groupby("month").agg(slp_pj=("slp_pj", "sum"), rlm_pj=("rlm_pj", "sum"), n=("date", "size"),
                                   n_na=("slp_pj", lambda s: s.isna().sum()),
                                   status=("statusEN", lambda s: "/".join(sorted(s.unique()))))
    m["days"] = [pd.Period(i).days_in_month for i in m.index]
    full = m[(m.n == m.days) & (m.n_na == 0)]
    dropped = sorted(set(m.index) - set(full.index))
    if dropped:
        print(f"불완전한 달 제외: {dropped}")
    out = full.reset_index()[["month", "slp_pj", "rlm_pj", "status"]]
    out.to_csv(INTERIM / "the_sector.csv", index=False, encoding="utf-8")
    print(f"저장: {INTERIM / 'the_sector.csv'} ({out.month.min()}~{out.month.max()}, {len(out)}개월)")


if __name__ == "__main__":
    main()
