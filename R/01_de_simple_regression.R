# 독일 단순회귀 Y ~ HDD: 적합·추론(Ch1~2), 진단 plot 6종·검정·Box-Cox 변환(Ch3)
#
# 입력: data/processed/DE.csv (python/build_dataset.py 결과)
# 출력: outputs/de_simple_regression.txt, outputs/figures/de_diag_*.png
# 실행: 저장소 루트에서  Rscript R/01_de_simple_regression.R
# 필요 패키지: lmtest, MASS

suppressPackageStartupMessages({
  library(lmtest)
  library(MASS)
})

dir.create("outputs/figures", recursive = TRUE, showWarnings = FALSE)
de <- read.csv("data/processed/DE.csv", stringsAsFactors = FALSE)
de <- subset(de, month >= "2008-01" & month <= "2025-12")
de$t <- seq_len(nrow(de))
de$mon <- as.integer(substr(de$month, 6, 7))
stopifnot(nrow(de) == 216, !anyNA(de$gas_pj), !anyNA(de$hdd))

out <- file("outputs/de_simple_regression.txt", open = "w", encoding = "UTF-8")
say <- function(...) { txt <- paste0(...); cat(txt, "\n"); writeLines(txt, out) }
show <- function(x) { txt <- capture.output(print(x)); cat(txt, sep = "\n"); writeLines(txt, out) }

# ---- Brown-Forsythe 검정 (Kutner 3.6): HDD 중앙값으로 두 집단을 나눠 |e - 집단 중앙값| 비교
brown_forsythe <- function(e, x) {
  g <- x <= median(x)
  d <- abs(e - ave(e, g, FUN = median))
  t.test(d[g], d[!g], var.equal = TRUE)
}

diagnose <- function(fit, label) {
  e <- resid(fit)
  bp_k <- bptest(fit)                      # Koenker (studentized)
  bp_o <- bptest(fit, studentize = FALSE)  # 원래 Breusch-Pagan
  bf <- brown_forsythe(e, de$hdd)
  sw <- shapiro.test(e)
  dw <- dwtest(fit)
  say(sprintf("[%s] R² = %.3f, 수정 R² = %.3f, 잔차 표준오차 = %.3f",
              label, summary(fit)$r.squared, summary(fit)$adj.r.squared, summary(fit)$sigma))
  say(sprintf("  등분산: BP(Koenker) p = %.4f, BP(원래) p = %.4f, Brown-Forsythe p = %.4f",
              bp_k$p.value, bp_o$p.value, bf$p.value))
  say(sprintf("  정규성: Shapiro-Wilk p = %.4f", sw$p.value))
  say(sprintf("  자기상관: Durbin-Watson = %.3f, p = %.4g", dw$statistic, dw$p.value))
  invisible(list(bp_k = bp_k, bp_o = bp_o, bf = bf, sw = sw, dw = dw))
}

# 진단 plot 6종 (Kutner 3.3): 잔차 vs X, |잔차| vs X, 잔차 vs 적합값, 잔차 vs 시간, 상자그림, 정규확률그림
diag_plots <- function(fit, file, title) {
  e <- resid(fit)
  png(file, width = 1500, height = 950, res = 130)
  par(mfrow = c(2, 3), mar = c(4.2, 4.2, 2.5, 1), oma = c(0, 0, 2.2, 0))
  plot(de$hdd, e, xlab = "HDD", ylab = "잔차", main = "(a) 잔차 vs HDD"); abline(h = 0, lty = 2)
  plot(de$hdd, abs(e), xlab = "HDD", ylab = "|잔차|", main = "(b) |잔차| vs HDD")
  lines(lowess(de$hdd, abs(e)), col = "red")
  plot(fitted(fit), e, xlab = "적합값", ylab = "잔차", main = "(c) 잔차 vs 적합값"); abline(h = 0, lty = 2)
  plot(de$t, e, type = "b", pch = 20, cex = 0.6, xaxt = "n", xlab = "연도", ylab = "잔차",
       main = "(d) 잔차 vs 시간"); abline(h = 0, lty = 2)
  yrs <- which(de$mon == 1); axis(1, at = yrs[seq(1, length(yrs), 2)],
                                  labels = substr(de$month[yrs[seq(1, length(yrs), 2)]], 1, 4))
  boxplot(e, horizontal = TRUE, xlab = "잔차", main = "(e) 잔차 상자그림")
  qqnorm(e, main = "(f) 정규확률그림"); qqline(e, col = "red")
  mtext(title, outer = TRUE, line = 0.6, cex = 1.0, font = 2)
  invisible(dev.off())
}

say("# 독일 단순회귀 Y(PJ) ~ HDD, 2008-01~2025-12 (n = 216)")
say("")

# ---- Ch1~2: 적합과 추론 ----
fit <- lm(gas_pj ~ hdd, data = de)
show(summary(fit))
say("β 95% 신뢰구간:")
show(confint(fit))
say("분산분석표:")
show(anova(fit))
say(sprintf("해석: HDD가 1 늘면 월 수요는 %.3f PJ 늘어난다 (95%% CI %.3f~%.3f).",
            coef(fit)[2], confint(fit)[2, 1], confint(fit)[2, 2]))

new <- data.frame(hdd = c(50, 200, 350, 500))
ci <- predict(fit, new, interval = "confidence")
pi <- predict(fit, new, interval = "prediction")
say("평균 반응 신뢰구간과 예측구간 (95%):")
show(data.frame(HDD = new$hdd, 적합 = round(ci[, 1], 1),
                CI_하한 = round(ci[, 2], 1), CI_상한 = round(ci[, 3], 1),
                PI_하한 = round(pi[, 2], 1), PI_상한 = round(pi[, 3], 1)))

# 기간별 관계 안정성
say("기간별 기울기·절편 (PJ):")
for (p in list(c("2008", "2013"), c("2014", "2021"), c("2022", "2025"))) {
  s <- subset(de, substr(month, 1, 4) >= p[1] & substr(month, 1, 4) <= p[2])
  b <- coef(lm(gas_pj ~ hdd, data = s))
  say(sprintf("  %s~%s: 기울기 %.2f, 절편 %.0f", p[1], p[2], b[2], b[1]))
}

# 이상치: 외적 스튜던트화 잔차
rs <- rstudent(fit)
top <- order(abs(rs), decreasing = TRUE)[1:3]
say(sprintf("외적 스튜던트화 잔차 상위 3: %s", paste(sprintf("%s (%+.2f)", de$month[top], rs[top]), collapse = ", ")))
say(sprintf("|t| > 3 인 관측치: %d개", sum(abs(rs) > 3)))
say("")

# ---- Ch3: 진단과 변환 ----
say("## 진단 (변환 전)")
diagnose(fit, "Y ~ HDD")
diag_plots(fit, "outputs/figures/de_diag_Y.png", "Y ~ HDD 진단 plot (독일, 2008~2025)")

bc <- boxcox(gas_pj ~ hdd, data = de, lambda = seq(-1, 2, 0.01), plotit = FALSE)
lam <- bc$x[which.max(bc$y)]
ci_lam <- range(bc$x[bc$y > max(bc$y) - qchisq(0.95, 1) / 2])
say(sprintf("Box-Cox: 최적 λ = %.2f (95%% CI %.2f~%.2f) → √Y(λ = 0.5) 선택",
            lam, ci_lam[1], ci_lam[2]))
png("outputs/figures/de_boxcox.png", width = 900, height = 650, res = 130)
boxcox(gas_pj ~ hdd, data = de, lambda = seq(-1, 2, 0.01))
title("Box-Cox 로그우도 (독일 Y ~ HDD)")
invisible(dev.off())
say("")

say("## 진단 (√Y 변환 후)")
fit_s <- lm(sqrt(gas_pj) ~ hdd, data = de)
show(summary(fit_s)$coefficients)
diagnose(fit_s, "√Y ~ HDD")
diag_plots(fit_s, "outputs/figures/de_diag_sqrtY.png", "√Y ~ HDD 진단 plot (독일, 2008~2025)")

close(out)
cat("\n저장: outputs/de_simple_regression.txt, outputs/figures/de_diag_Y.png, de_diag_sqrtY.png, de_boxcox.png\n")
