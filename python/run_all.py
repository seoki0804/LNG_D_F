"""분석 전체를 의존 순서대로 다시 실행한다 (데이터 수집은 제외 — fetch_*.py, build_dataset.py를 먼저).

    python python/run_all.py            # 전부 (12코어 약 30분)
    python python/run_all.py --from r9  # 특정 단계부터

R 스크립트는 Rscript가 PATH에 없으면 RSCRIPT 환경변수나 아래 기본 경로를 쓴다.
파운데이션 모델(R8)은 .venv-fm이 있으면 그 파이썬으로 실행하고, 없으면 건너뛴다 (README 참고).
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
FM_PY = ROOT / ".venv-fm" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
RSCRIPT = (os.environ.get("RSCRIPT") or shutil.which("Rscript")
           or r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe")

STEPS = [  # (이름, 명령)
    ("main", [PY, "python/run_experiment.py"]),
    ("leakage", [PY, "python/leakage_check.py"]),
    ("r_simple", [RSCRIPT, "R/01_de_simple_regression.R"]),
    ("r_multiple", [RSCRIPT, "R/02_de_multiple_regression.R"]),
    ("r5", [RSCRIPT, "R/03_country_regression.R"]),
    ("r_ch45", [RSCRIPT, "R/04_de_simultaneous_matrix.R"]),
    ("r_break", [RSCRIPT, "R/05_structural_break.R"]),
    ("r1", [PY, "python/r1_variables_de.py"]),
    ("r2", [PY, "python/r2_structural.py"]),
    ("r3", [PY, "python/r3_shap.py"]),
    ("r6", [PY, "python/r6_global.py"]),
    ("r7", [PY, "python/r7_sector.py"]),
    ("r8", [str(FM_PY), "python/r8_foundation.py"]),
    ("r8_2026", [str(FM_PY), "python/r8_foundation.py", "--geos", "DE", "--start", "2026-01", "--end", "2026-09",
                 "--tag", "de2026"]),
    ("r8_rt", [str(FM_PY), "python/r8_foundation.py", "--realtime", "--tag", "realtime"]),
    ("r9", [PY, "python/r9_intervals.py"]),
    ("r10", [PY, "python/r10_ensemble.py"]),
    ("r11", [PY, "python/r11_climate.py"]),
    ("mcs", [PY, "python/r4_mcs.py"]),
    ("realtime", [PY, "python/realtime_check.py"]),
    ("oos2026", [PY, "python/oos_de2026.py"]),
]


def main():
    start = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv else STEPS[0][0]
    names = [s[0] for s in STEPS]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
           "PYTHONPATH": str(ROOT / "python")}
    t0 = time.time()
    for name, cmd in STEPS[names.index(start):]:
        if cmd[0] == str(FM_PY) and not FM_PY.exists():
            print(f"[건너뜀] {name}: .venv-fm 없음", flush=True)
            continue
        t = time.time()
        r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        status = "완료" if r.returncode == 0 else f"실패 (코드 {r.returncode})"
        print(f"[{status}] {name} {time.time() - t:.0f}s", flush=True)
        if r.returncode != 0:
            print(r.stdout[-2000:], r.stderr[-3000:], sep="\n")
            sys.exit(r.returncode)
    print(f"전체 {(time.time() - t0) / 60:.1f}분")


if __name__ == "__main__":
    main()
