"""한국 연구 전체를 의존 순서대로 실행한다 (자료 수집 fetch.py는 제외 — 먼저 python fetch.py all).

    python python/run_all.py            # korea/ 에서, 전부
    python python/run_all.py --from evaluate

R은 Rscript가 PATH에 없으면 RSCRIPT 환경변수나 기본 경로를 쓴다. 파운데이션 모델은 저장소 루트의 .venv-fm으로 실행한다.
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
FM_PY = ROOT.parent / ".venv-fm" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
RSCRIPT = os.environ.get("RSCRIPT") or shutil.which("Rscript") or r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe"

STEPS = [
    ("build", [PY, "python/build.py"]),
    ("r_national", [RSCRIPT, "R/01_national_regression.R"]),
    ("r_province", [RSCRIPT, "R/02_province_panel.R"]),
    ("national", [PY, "python/run_national.py"]),
    ("val", [PY, "python/val_predictions.py"]),
    ("variables", [PY, "python/r_variables.py"]),
    ("fm_national", [str(FM_PY), "python/foundation_mh.py"]),
    ("fm_val", [str(FM_PY), "python/foundation_mh.py", "--val"]),
    ("fm_province", [str(FM_PY), "python/foundation_mh.py", "--province"]),
    ("province", [PY, "python/run_province.py"]),
    ("evaluate", [PY, "python/evaluate.py"]),
    ("paper", [PY, "python/paper_metrics.py"]),
    ("leakage", [PY, "python/leakage_check.py"]),
    ("figures", [PY, "python/figures.py"]),
    ("numbers", [PY, "python/report_numbers.py"]),
    ("slide_figures", [PY, "python/slide_figures.py"]),
    ("report", ["node", "report/build_report.js"]),
    ("deck", ["node", "report/build_deck.js"]),
]


def main():
    start = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv else STEPS[0][0]
    names = [s[0] for s in STEPS]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
           "PYTHONPATH": str(ROOT / "python"), "NODE_PATH": str(ROOT / "report" / "node_modules")}
    t0 = time.time()
    for name, cmd in STEPS[names.index(start):]:
        if cmd[0] == str(FM_PY) and not FM_PY.exists():
            print(f"[건너뜀] {name}: .venv-fm 없음", flush=True)
            continue
        if not (ROOT / cmd[1]).exists():
            print(f"[건너뜀] {name}: {cmd[1]} 없음", flush=True)
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
