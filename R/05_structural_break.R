# 구조변화 검정: 2022년 위기 더미의 시점(2022-03)을 미리 정해 쓴 것이 자료로 뒷받침되는가
#   1) Chow 검정: 2022-03에서 회귀계수가 바뀌는가 (시점을 아는 경우)
#   2) sup-F (Andrews 1993): 시점을 모를 때 가장 강한 변화 시점과 유의성 (양 끝 15% 제외)
#   3) Bai-Perron: 여러 개의 변화 시점과 BIC로 고른 개수, 시점의 95% 구간
# 모형: log(Y) ~ HDD + CDD + log(소비자요금) (R5와 같은 구조에서 위기 항만 뺀 것)
# 주의: 잔차 자기상관이 있으면 표준 F 검정은 변화를 과대 탐지할 수 있어, sup-F는 HAC 공분산으로도 계산한다.
#
# 표본: 유럽 2008-01~2025-12, 한국 2016-01~2025-12
# 출력: outputs/r2_structural_break.txt, outputs/r2_structural_break.csv, outputs/figures/r2_supF_DE.png
# 실행: 저장소 루트에서  Rscript R/05_structural_break.R
# 필요 패키지: strucchange, sandwich

suppressPackageStartupMessages({
  library(strucchange)
  library(sandwich)
})

geos <- c(DE = "독일", IT = "이탈리아", FR = "프랑스", ES = "스페인", NL = "네덜란드", KR = "한국")
out <- file("outputs/r2_structural_break.txt", open = "w", encoding = "UTF-8")
say <- function(...) {
  txt <- paste0(...)
  cat(txt, "\n")
  writeLines(txt, out)
}
f <- log(y) ~ hdd + cdd + log(price_retail)
rows <- list()
for (g in names(geos)) {
  d <- read.csv(sprintf("data/processed/%s.csv", g), stringsAsFactors = FALSE)
  d <- subset(d, month >= "2008-01" & month <= "2025-12" & !is.na(y) & !is.na(price_retail))
  d <- d[order(d$month), ]
  yt <- ts(log(d$y), start = c(as.integer(substr(d$month[1], 1, 4)), as.integer(substr(d$month[1], 6, 7))),
           frequency = 12)
  d$t <- seq_len(nrow(d))
  idx <- which(d$month == "2022-03")
  chow <- sctest(f, data = d, type = "Chow", point = idx - 1)
  fs <- Fstats(f, data = d, from = 0.15)
  sup <- sctest(fs, type = "supF")
  fs_hac <- Fstats(f, data = d, from = 0.15, vcov. = function(x, ...) NeweyWest(x, prewhite = FALSE, ...))
  sup_hac <- sctest(fs_hac, type = "supF")
  bp_sup <- d$month[fs$breakpoint]
  bp_sup_hac <- d$month[fs_hac$breakpoint]
  bpm <- breakpoints(f, data = d, h = 0.15)
  nb <- summary(bpm)$RSS["BIC", ]
  k <- as.integer(names(nb)[which.min(nb)])
  dates <- if (k > 0) d$month[breakpoints(bpm, breaks = k)$breakpoints] else character(0)
  ci <- if (k > 0) tryCatch(confint(bpm, breaks = k)$confint, error = function(e) NULL) else NULL
  ci_txt <- if (!is.null(ci)) paste(sprintf("%s [%s, %s]", d$month[ci[, 2]], d$month[ci[, 1]], d$month[ci[, 3]]),
                                    collapse = "; ") else "-"
  rows[[g]] <- data.frame(geo = g, 국가 = geos[[g]], 기간 = paste(d$month[1], d$month[nrow(d)], sep = "~"),
                          chow_F = unname(chow$statistic), chow_p = chow$p.value,
                          supF = unname(sup$statistic), supF_p = sup$p.value, supF_date = bp_sup,
                          supF_hac = unname(sup_hac$statistic), supF_hac_p = sup_hac$p.value,
                          supF_hac_date = bp_sup_hac, bp_n = k, bp_dates = paste(dates, collapse = ", "),
                          bp_ci = ci_txt)
  say(sprintf("== %s: Chow(2022-03) F = %.1f, p = %.3g | sup-F = %.1f (p = %.3g) at %s | HAC sup-F = %.1f (p = %.3g) at %s",
              geos[[g]], chow$statistic, chow$p.value, sup$statistic, sup$p.value, bp_sup,
              sup_hac$statistic, sup_hac$p.value, bp_sup_hac))
  say(sprintf("   Bai-Perron (BIC): %d개 — %s", k, ci_txt))
  if (g == "DE") {
    png("outputs/figures/r2_supF_DE.png", width = 1200, height = 700, res = 140)
    plot(fs, main = "독일: 시점별 Chow F 통계량 (sup-F, 15% 절단)", xlab = "시점", ylab = "F 통계량")
    abline(v = time(fs$Fstats)[which(d$month[seq_along(fs$Fstats) + fs$from - 1] == "2022-03")], lty = 2, col = "red")
    invisible(dev.off())
  }
}
tab <- do.call(rbind, rows)
write.csv(tab, "outputs/r2_structural_break.csv", row.names = FALSE, fileEncoding = "UTF-8")
say("")
say("| 국가 | Chow 2022-03 p | sup-F 시점 (p) | HAC sup-F 시점 (p) | Bai-Perron 시점 (BIC) |")
say("| --- | --- | --- | --- | --- |")
for (r in split(tab, tab$geo)[names(geos)]) {
  say(sprintf("| %s | %.3g | %s (%.3g) | %s (%.3g) | %s |", r$국가, r$chow_p, r$supF_date, r$supF_p,
              r$supF_hac_date, r$supF_hac_p, ifelse(r$bp_n > 0, r$bp_dates, "없음")))
}
close(out)
cat("\n저장: outputs/r2_structural_break.txt, .csv, outputs/figures/r2_supF_DE.png\n")
