# 독일 √Y ~ HDD (Ch3에서 고른 변환 모형)의 동시추론(Ch4)과 행렬 접근(Ch5)
#   Ch4  1) β0·β1 동시 신뢰구간 (Bonferroni)
#        2) 평균 반응 신뢰대 (Working-Hotelling) vs 개별 신뢰구간
#        3) 겨울 3개월(12·1·2월 평년 HDD) 동시 예측구간 (Bonferroni vs Scheffé, 작은 쪽 채택)
#        4) 역예측(calibration): 관측 수요로 HDD 추정과 구간
#   Ch5  5) 행렬 계산: b = (X'X)^-1 X'Y, 모자 행렬 H, SSE·SSR·SSTO, s²{b}, s²{Ŷh} → lm()과 일치 확인
# 표본: 2008-01~2025-12 (n = 216). 구간은 √Y 척도에서 만든 뒤 제곱해 PJ로 되돌린다.
#
# 입력: data/processed/DE.csv
# 출력: outputs/de_simultaneous_matrix.txt, outputs/figures/de_working_hotelling.png
# 실행: 저장소 루트에서  Rscript R/04_de_simultaneous_matrix.R

dir.create("outputs/figures", recursive = TRUE, showWarnings = FALSE)
de <- read.csv("data/processed/DE.csv", stringsAsFactors = FALSE)
de <- subset(de, month >= "2008-01" & month <= "2025-12")
de$sy <- sqrt(de$gas_pj)
n <- nrow(de)
stopifnot(n == 216)

out <- file("outputs/de_simultaneous_matrix.txt", open = "w", encoding = "UTF-8")
say <- function(...) {
  txt <- paste0(...)
  cat(txt, "\n")
  writeLines(txt, out)
}
show <- function(x) {
  txt <- capture.output(print(x))
  cat(txt, sep = "\n")
  writeLines(txt, out)
}

fit <- lm(sy ~ hdd, data = de)
b <- coef(fit)
mse <- summary(fit)$sigma^2
xbar <- mean(de$hdd)
sxx <- sum((de$hdd - xbar)^2)
say("# 독일 √Y ~ HDD 동시추론(Ch4)·행렬 접근(Ch5), 2008-01~2025-12 (n = 216)")
say(sprintf("b0 = %.4f, b1 = %.6f, MSE = %.4f", b[1], b[2], mse))
say("")

# ---- 1) β0, β1 동시 신뢰구간 (Bonferroni, 가족 신뢰계수 95%) ----
say("## 1. β0·β1 동시 신뢰구간 (Bonferroni, 가족 95%)")
B <- qt(1 - 0.05 / (2 * 2), n - 2)
se <- sqrt(diag(vcov(fit)))
tab <- data.frame(개별_하한 = b - qt(0.975, n - 2) * se, 개별_상한 = b + qt(0.975, n - 2) * se,
                  동시_하한 = b - B * se, 동시_상한 = b + B * se)
show(signif(tab, 5))
say(sprintf("Bonferroni 배수 B = t(1 − 0.05/4; %d) = %.3f (개별 t = %.3f)", n - 2, B, qt(0.975, n - 2)))
se_hac <- sqrt(diag(sandwich::NeweyWest(fit, prewhite = FALSE)))
say(sprintf("주의: 잔차 자기상관(DW 0.89) 때문에 Newey-West 표준오차가 OLS의 %.2f배(β0)·%.2f배(β1)다.",
            se_hac[1] / se[1], se_hac[2] / se[2]))
say("      아래 Ch4 구간은 교재 가정(독립 오차)을 따른 것으로, 실제 불확실성보다 좁게 나올 수 있다.")
say("")

# ---- 2) Working-Hotelling 신뢰대 ----
say("## 2. 평균 반응 신뢰대 (Working-Hotelling, 95%) vs Bonferroni (g = 4)")
W <- sqrt(2 * qf(0.95, 2, n - 2))
xh <- c(50, 200, 350, 500)
pr <- predict(fit, data.frame(hdd = xh), se.fit = TRUE)
Bg <- qt(1 - 0.05 / (2 * length(xh)), n - 2)
wh <- data.frame(HDD = xh, 적합_PJ = pr$fit^2,
                 WH_하한 = (pr$fit - W * pr$se.fit)^2, WH_상한 = (pr$fit + W * pr$se.fit)^2,
                 Bonf_하한 = (pr$fit - Bg * pr$se.fit)^2, Bonf_상한 = (pr$fit + Bg * pr$se.fit)^2)
show(round(wh, 1))
say(sprintf("W = √(2F(0.95; 2, %d)) = %.3f, B(g=4) = %.3f → %s 쪽이 좁다", n - 2, W, Bg,
            ifelse(W < Bg, "Working-Hotelling", "Bonferroni")))
grid <- seq(0, max(de$hdd), length.out = 200)
pg <- predict(fit, data.frame(hdd = grid), se.fit = TRUE)
png("outputs/figures/de_working_hotelling.png", width = 1200, height = 800, res = 140)
par(mar = c(4.5, 4.5, 3, 1))
plot(de$hdd, de$gas_pj, pch = 20, col = "grey55", xlab = "HDD", ylab = "월 수요 (PJ)",
     main = "독일 √Y ~ HDD: 평균 반응 95% Working-Hotelling 신뢰대 (PJ로 역변환)")
polygon(c(grid, rev(grid)), c((pg$fit - W * pg$se.fit)^2, rev((pg$fit + W * pg$se.fit)^2)),
        col = adjustcolor("#4C78A8", 0.25), border = NA)
lines(grid, pg$fit^2, col = "#4C78A8", lwd = 2)
legend("topleft", c("관측값 2008~2025", "적합선 (√Y 모형, 제곱해 역변환)", "Working-Hotelling 95% 신뢰대"),
       pch = c(20, NA, 15), lty = c(NA, 1, NA), col = c("grey55", "#4C78A8", adjustcolor("#4C78A8", 0.4)),
       bty = "n")
invisible(dev.off())
say("")

# ---- 3) 겨울 3개월 동시 예측구간 ----
say("## 3. 겨울 3개월 동시 예측구간 (평년 HDD = 2016~2025 같은 달 평균, 가족 95%)")
nm <- subset(de, month >= "2016-01")
winter <- c("12", "01", "02")
xw <- sapply(winter, function(m) mean(nm$hdd[substr(nm$month, 6, 7) == m]))
g <- length(xw)
pw <- predict(fit, data.frame(hdd = xw), se.fit = TRUE)
spred <- sqrt(mse + pw$se.fit^2)
Bp <- qt(1 - 0.05 / (2 * g), n - 2)
Sp <- sqrt(g * qf(0.95, g, n - 2))
mult <- min(Bp, Sp)
pi_tab <- data.frame(월 = c("12월", "1월", "2월"), 평년_HDD = round(xw, 1), 예측_PJ = round(pw$fit^2, 1),
                     하한_PJ = round((pw$fit - mult * spred)^2, 1), 상한_PJ = round((pw$fit + mult * spred)^2, 1))
show(pi_tab)
say(sprintf("Bonferroni B = %.3f, Scheffé S = %.3f → %s 사용", Bp, Sp, ifelse(Bp <= Sp, "Bonferroni", "Scheffé")))
say(sprintf("겨울 3개월 합계 예측 %.0f PJ (각 달 구간을 동시에 95%%로 보장)", sum(pw$fit^2)))
say("")

# ---- 4) 역예측 ----
say("## 4. 역예측: 관측 수요 → HDD 추정 (Kutner 4.6, 95%)")
for (yh in c(250, 350, 450)) {
  xh_hat <- (sqrt(yh) - b[1]) / b[2]
  s_pred <- sqrt(mse / b[2]^2 * (1 + 1 / n + (xh_hat - xbar)^2 / sxx))
  cond <- qt(0.975, n - 2)^2 * mse / (b[2]^2 * sxx)
  say(sprintf("  수요 %d PJ → HDD %.0f, 95%% 구간 [%.0f, %.0f] (근사 조건 t²MSE/(b1²Sxx) = %.4f < 0.1)",
              yh, xh_hat, xh_hat - qt(0.975, n - 2) * s_pred, xh_hat + qt(0.975, n - 2) * s_pred, cond))
}
say("")

# ---- 5) 행렬 접근 (Ch5) ----
say("## 5. 행렬 접근 (Ch5) — lm()과 일치 확인")
X <- cbind(1, de$hdd)
Y <- de$sy
XtX <- t(X) %*% X
XtX_inv <- solve(XtX)
bm <- XtX_inv %*% t(X) %*% Y
H <- X %*% XtX_inv %*% t(X)
e <- (diag(n) - H) %*% Y
J <- matrix(1, n, n)
SSE <- as.numeric(t(Y) %*% Y - t(bm) %*% t(X) %*% Y)
SSTO <- as.numeric(t(Y) %*% Y - (1 / n) * t(Y) %*% J %*% Y)
SSR <- SSTO - SSE
MSE <- SSE / (n - 2)
s2b <- MSE * XtX_inv
Xh <- c(1, 350)
s2yh <- as.numeric(MSE * t(Xh) %*% XtX_inv %*% Xh)
say("X'X ="); show(XtX)
say("(X'X)^-1 ="); show(signif(XtX_inv, 4))
say(sprintf("b = (X'X)^-1 X'Y = [%.6f, %.8f]", bm[1], bm[2]))
say(sprintf("SSTO = %.3f, SSR = %.3f, SSE = %.3f, MSE = %.5f, R² = %.4f", SSTO, SSR, SSE, MSE, SSR / SSTO))
say("s²{b} = MSE (X'X)^-1 ="); show(signif(s2b, 4))
say(sprintf("Xh = (1, 350): Ŷh = %.4f, s²{Ŷh} = MSE·Xh'(X'X)^-1 Xh = %.6f", sum(Xh * bm), s2yh))
checks <- c(
  b = max(abs(bm - b)),
  e = max(abs(e - resid(fit))),
  vcov = max(abs(s2b - vcov(fit))),
  hat = max(abs(diag(H) - hatvalues(fit))),
  H_symmetric = max(abs(H - t(H))),
  H_idempotent = max(abs(H %*% H - H)),
  trace_H_minus_p = abs(sum(diag(H)) - 2),
  s2yh = abs(s2yh - predict(fit, data.frame(hdd = 350), se.fit = TRUE)$se.fit^2))
say("lm() 대비 최대 절대 차이 (모두 0에 가까워야 함):")
show(signif(checks, 3))
stopifnot(all(checks < 1e-6))
close(out)
cat("\n저장: outputs/de_simultaneous_matrix.txt, outputs/figures/de_working_hotelling.png\n")
