# 연구 과제 R5: 같은 회귀 구조를 6개국에 추정해 난방 민감도·가격 탄력성·2022년 위기 효과를 비교
#
# 모형 (국가 공통, 수요 단위가 달라도 비교되도록 로그):
#   log(Y) ~ HDD + CDD + log(소비자요금) + 위기 + HDD×위기
#   위기 = 2022-03 이후 1
#   - HDD 10당 수요 % = 100·(exp(10·β_HDD) − 1)   (위기 전 / 위기 후)
#   - 요금 탄력성 = β_log(요금)
# 표준오차: Newey-West (잔차 자기상관), 표본: 2015-01~2025-12 (한국 2016-01~)
#
# 입력: data/processed/<geo>.csv
# 출력: outputs/r5_country_regression.txt, outputs/r5_country_regression.csv,
#       outputs/figures/r5_hdd_sensitivity.png
# 실행: 저장소 루트에서  Rscript R/03_country_regression.R
# 필요 패키지: lmtest, sandwich

suppressPackageStartupMessages({
  library(lmtest)
  library(sandwich)
})

geos <- c(DE = "독일", IT = "이탈리아", FR = "프랑스", ES = "스페인", NL = "네덜란드", KR = "한국")
dir.create("outputs/figures", recursive = TRUE, showWarnings = FALSE)
out <- file("outputs/r5_country_regression.txt", open = "w", encoding = "UTF-8")
say <- function(...) {
  txt <- paste0(...)
  cat(txt, "\n")
  writeLines(txt, out)
}

pct <- function(b, k = 10) 100 * (exp(k * b) - 1)
rows <- list()
for (g in names(geos)) {
  d <- read.csv(sprintf("data/processed/%s.csv", g), stringsAsFactors = FALSE)
  d <- subset(d, month >= "2015-01" & month <= "2025-12" & !is.na(y) & !is.na(price_retail))
  d$crisis <- as.integer(d$month >= "2022-03")
  m <- lm(log(y) ~ hdd + cdd + log(price_retail) + crisis + hdd:crisis, data = d)
  V <- NeweyWest(m, prewhite = FALSE)
  ct <- coeftest(m, vcov. = V)
  b <- coef(m)
  # 위기 후 HDD 기울기 = β_hdd + β_hdd:crisis, 분산은 공분산 포함
  b_post <- b["hdd"] + b["hdd:crisis"]
  se_post <- sqrt(V["hdd", "hdd"] + V["hdd:crisis", "hdd:crisis"] + 2 * V["hdd", "hdd:crisis"])
  se_pre <- sqrt(V["hdd", "hdd"])
  rows[[g]] <- data.frame(
    geo = g, 국가 = geos[[g]], n = nrow(d), 기간 = paste(min(d$month), max(d$month), sep = "~"),
    R2 = summary(m)$r.squared, DW = unname(dwtest(m)$statistic),
    hdd10_pre = pct(b["hdd"]), hdd10_pre_lo = pct(b["hdd"] - 1.96 * se_pre),
    hdd10_pre_hi = pct(b["hdd"] + 1.96 * se_pre),
    hdd10_post = pct(b_post), hdd10_post_lo = pct(b_post - 1.96 * se_post),
    hdd10_post_hi = pct(b_post + 1.96 * se_post),
    p_hdd_change = ct["hdd:crisis", 4],
    cdd10 = pct(b["cdd"]), p_cdd = ct["cdd", 4],
    price_elast = b["log(price_retail)"], p_price = ct["log(price_retail)", 4],
    crisis_level_pct = 100 * (exp(b["crisis"]) - 1), p_crisis = ct["crisis", 4],
    row.names = NULL)
  say(sprintf("== %s (%s, n = %d)", geos[[g]], rows[[g]]$기간, nrow(d)))
  txt <- capture.output(print(signif(ct[, 1:4], 3)))
  cat(txt, sep = "\n")
  writeLines(txt, out)
}
tab <- do.call(rbind, rows)
write.csv(tab, "outputs/r5_country_regression.csv", row.names = FALSE, fileEncoding = "UTF-8")

say("")
say("## 국가 비교 (Newey-West 표준오차, * p<0.05)")
say("| 국가 | R² | DW | HDD 10당 % (위기 전) | HDD 10당 % (위기 후) | 변화 p | 요금 탄력성 | 위기 절편 % |")
say("| --- | --- | --- | --- | --- | --- | --- | --- |")
st <- function(p) ifelse(p < 0.05, "*", "")
for (r in split(tab, tab$geo)[names(geos)]) {
  say(sprintf("| %s | %.2f | %.2f | %.2f [%.2f, %.2f] | %.2f [%.2f, %.2f] | %.3f | %.2f%s | %+.0f%s |",
              r$국가, r$R2, r$DW, r$hdd10_pre, r$hdd10_pre_lo, r$hdd10_pre_hi,
              r$hdd10_post, r$hdd10_post_lo, r$hdd10_post_hi, r$p_hdd_change,
              r$price_elast, st(r$p_price), r$crisis_level_pct, st(r$p_crisis)))
}

# 그림: 국가별 HDD 민감도 (위기 전·후, 95% 구간)
png("outputs/figures/r5_hdd_sensitivity.png", width = 1300, height = 800, res = 140)
par(mar = c(4.5, 5, 3, 1))
k <- nrow(tab)
x <- seq_len(k)
ylim <- c(0, max(tab$hdd10_post_hi, tab$hdd10_pre_hi) * 1.1)
plot(NA, xlim = c(0.5, k + 0.5), ylim = ylim, xaxt = "n", xlab = "", ylab = "HDD 10 증가 시 월 수요 증가 (%)",
     main = "국가별 난방 민감도: 2022년 3월 전과 후 (95% 구간, Newey-West)")
axis(1, at = x, labels = tab$국가)
abline(h = seq(0, ylim[2], 1), col = "grey92")
cols <- c("#4C78A8", "#E45756")
points(x - 0.12, tab$hdd10_pre, pch = 19, col = cols[1], cex = 1.3)
arrows(x - 0.12, tab$hdd10_pre_lo, x - 0.12, tab$hdd10_pre_hi, angle = 90, code = 3, length = 0.04, col = cols[1])
points(x + 0.12, tab$hdd10_post, pch = 17, col = cols[2], cex = 1.3)
arrows(x + 0.12, tab$hdd10_post_lo, x + 0.12, tab$hdd10_post_hi, angle = 90, code = 3, length = 0.04, col = cols[2])
legend("topleft", c("위기 전 (~2022-02)", "위기 후 (2022-03~)"), pch = c(19, 17), col = cols, bty = "n")
invisible(dev.off())

close(out)
cat("\n저장: outputs/r5_country_regression.txt, .csv, outputs/figures/r5_hdd_sensitivity.png\n")
