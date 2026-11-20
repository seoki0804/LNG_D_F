# 독일 다중회귀 (Ch6~): √Y ~ 기상·가격·산업·달력·발전 변수
#   1) 전체 모형 적합, 순차 ANOVA, 변수 묶음별 부분 F 검정
#   2) 상관행렬, VIF
#   3) 변수선택: 모든 부분집합 (수정 R², AIC, BIC, Mallows Cp, PRESS) + 단계적 AIC
#   4) 최종 모형: OLS 표준오차와 Newey-West(HAC) 표준오차 비교 (잔차 자기상관 때문)
#   5) 추가변수 plot (added-variable plot), 최종 모형 진단
#
# 입력: data/processed/DE.csv
# 출력: outputs/de_multiple_regression.txt, outputs/de_subset_selection.csv,
#       outputs/figures/de_avplots.png, outputs/figures/de_mlr_diag.png
# 실행: 저장소 루트에서  Rscript R/02_de_multiple_regression.R
# 필요 패키지: car, lmtest, sandwich

suppressPackageStartupMessages({
  library(car)
  library(lmtest)
  library(sandwich)
})

dir.create("outputs/figures", recursive = TRUE, showWarnings = FALSE)
raw <- read.csv("data/processed/DE.csv", stringsAsFactors = FALSE)
raw <- raw[order(raw$month), ]
raw$ttf_lag1 <- c(NA, head(raw$ttf_usd, -1))
de <- subset(raw, month >= "2008-02" & month <= "2025-12")
de$sqrtY <- sqrt(de$gas_pj)
# 2022년 위기: 러시아 침공(2022-02) 이후 가격 급등·수요 감축 (EU 규정 2022/1369)
de$crisis <- as.integer(de$month >= "2022-03")
de$nuclear_twh <- de$nuclear_gwh / 1000
de$wind_twh <- de$wind_gwh / 1000
stopifnot(!anyNA(de[, c("sqrtY", "hdd", "cdd", "hicp_gas", "ttf_lag1", "ip", "ip_chem",
                         "workdays", "nuclear_twh", "wind_twh")]))
n <- nrow(de)

out <- file("outputs/de_multiple_regression.txt", open = "w", encoding = "UTF-8")
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

say(sprintf("# 독일 다중회귀 √Y(PJ) ~ X, %s~%s (n = %d)", de$month[1], de$month[n], n))
say("변수: hdd·cdd(도일), hicp_gas(소비자 가스요금 지수), ttf_lag1(전월 도매가 USD/MMBtu),")
say("      ip(산업생산 B-D), ip_chem(화학 생산 C20), workdays(영업일), nuclear_twh·wind_twh(발전량 TWh),")
say("      crisis(2022-03 이후 = 1), hdd:crisis(위기 후 난방 민감도 변화)")
say("")

# ---- 1) 전체 모형 ----
full_f <- sqrtY ~ hdd + cdd + hicp_gas + ttf_lag1 + ip + ip_chem + workdays + nuclear_twh + wind_twh +
  crisis + hdd:crisis
full <- lm(full_f, data = de)
say("## 1. 전체 모형")
show(summary(full))
say("순차 ANOVA (Type I):")
show(anova(full))

partial_f <- function(drop, label) {
  reduced <- update(full, as.formula(paste(". ~ . -", paste(drop, collapse = " - "))))
  a <- anova(reduced, full)
  say(sprintf("  %-28s F = %6.2f, df = (%d, %d), p = %.4g", label, a$F[2], a$Df[2], a$Res.Df[2], a$`Pr(>F)`[2]))
}
say("묶음별 부분 F 검정 (해당 변수들을 빼면 설명력이 유의하게 주는가):")
partial_f(c("hicp_gas", "ttf_lag1"), "가격 (요금·도매가)")
partial_f(c("ip", "ip_chem"), "산업 (산업생산·화학)")
partial_f(c("nuclear_twh", "wind_twh"), "발전 (원자력·풍력)")
partial_f(c("crisis", "hdd:crisis"), "2022년 위기 (절편·기울기)")
partial_f("workdays", "영업일")
say("")

# ---- 2) 다중공선성 ----
say("## 2. 다중공선성")
xs <- c("hdd", "cdd", "hicp_gas", "ttf_lag1", "ip", "ip_chem", "workdays", "nuclear_twh", "wind_twh")
say("상관행렬:")
show(round(cor(de[, xs]), 2))
say("VIF (상호작용 제외 모형):")
v <- vif(lm(sqrtY ~ hdd + cdd + hicp_gas + ttf_lag1 + ip + ip_chem + workdays + nuclear_twh + wind_twh + crisis,
            data = de))
show(round(sort(v, decreasing = TRUE), 2))
say(sprintf("VIF > 10: %s", paste(names(v)[v > 10], collapse = ", ")))
say("")

# ---- 3) 변수선택: 모든 부분집합 ----
say("## 3. 변수선택 (모든 부분집합, hdd는 항상 포함, hdd:crisis는 crisis가 있을 때만)")
cands <- c("cdd", "hicp_gas", "ttf_lag1", "ip", "ip_chem", "workdays", "nuclear_twh", "wind_twh", "crisis")
mse_full <- summary(full)$sigma^2
press <- function(m) sum((resid(m) / (1 - hatvalues(m)))^2)
rows <- list()
for (k in 0:length(cands)) {
  for (s in if (k == 0) list(character(0)) else combn(cands, k, simplify = FALSE)) {
    terms_sets <- list(c("hdd", s))
    if ("crisis" %in% s) terms_sets <- c(terms_sets, list(c("hdd", s, "hdd:crisis")))
    for (tm in terms_sets) {
      m <- lm(reformulate(tm, "sqrtY"), data = de)
      p <- length(coef(m))
      rows[[length(rows) + 1]] <- data.frame(
        model = paste(tm, collapse = " + "), p = p,
        adjR2 = summary(m)$adj.r.squared, AIC = AIC(m), BIC = BIC(m),
        Cp = sum(resid(m)^2) / mse_full - (n - 2 * p), PRESS = press(m))
    }
  }
}
sel <- do.call(rbind, rows)
write.csv(sel[order(sel$BIC), ], "outputs/de_subset_selection.csv", row.names = FALSE, fileEncoding = "UTF-8")
say(sprintf("후보 모형 %d개 (outputs/de_subset_selection.csv)", nrow(sel)))
best <- function(col, fun = which.min) sel[fun(sel[[col]]), ]
for (crit in c("adjR2", "AIC", "BIC", "Cp", "PRESS")) {
  b <- if (crit == "adjR2") best(crit, which.max) else if (crit == "Cp") {
    sel[which.min(abs(sel$Cp - sel$p)), ]
  } else best(crit)
  say(sprintf("  %-6s 최적: p = %2d | %s", crit, b$p, b$model))
}
say("단계적 선택 (AIC, 양방향, 시작: hdd만):")
step_m <- step(lm(sqrtY ~ hdd, data = de), scope = list(lower = ~hdd, upper = full_f), direction = "both",
               trace = 0)
say("  ", paste(deparse(formula(step_m)), collapse = ""))
say("")

# ---- 4) 최종 모형: BIC 최적 ----
final_terms <- strsplit(sel$model[which.min(sel$BIC)], " \\+ ")[[1]]
final <- lm(reformulate(final_terms, "sqrtY"), data = de)
say("## 4. 최종 모형 (BIC 최적)")
show(summary(final))
nw <- NeweyWest(final, prewhite = FALSE)
say(sprintf("OLS 표준오차 vs Newey-West(HAC, 시차 %d) 표준오차:",
            floor(4 * (n / 100)^(2 / 9))))
ct <- coeftest(final, vcov. = nw)
comp <- data.frame(coef = coef(final), se_OLS = sqrt(diag(vcov(final))), se_HAC = ct[, 2],
                   t_OLS = coef(final) / sqrt(diag(vcov(final))), t_HAC = ct[, 3], p_HAC = ct[, 4])
show(signif(comp, 3))
say("HAC 표준오차가 OLS보다 크면 잔차 자기상관 때문에 OLS가 정밀도를 과대평가한 것이다.")
ybar <- mean(de$sqrtY)
say(sprintf("해석(평균 수준 √Y = %.2f에서 dY/dX = 2·√Y·β): HDD 1 증가 → 월 수요 %.3f PJ", ybar,
            2 * ybar * coef(final)["hdd"]))
if ("hdd:crisis" %in% names(coef(final))) {
  say(sprintf("  위기 후 HDD 효과: %.3f PJ (위기 전 대비 %+.3f PJ)",
              2 * ybar * (coef(final)["hdd"] + coef(final)["hdd:crisis"]),
              2 * ybar * coef(final)["hdd:crisis"]))
}

# 계획서 확인: √Y ~ HDD + 소비자가격 + 영업일의 영업일 t값
wd <- lm(sqrtY ~ hdd + hicp_gas + workdays, data = de)
say(sprintf("참고: √Y ~ HDD + 소비자가격 + 영업일 에서 영업일 t = %.2f (OLS), %.2f (HAC)",
            summary(wd)$coefficients["workdays", 3],
            coeftest(wd, vcov. = NeweyWest(wd, prewhite = FALSE))["workdays", 3]))
say("")

# ---- 5) 진단 ----
say("## 5. 최종 모형 진단")
say(sprintf("BP(Koenker) p = %.4f, Shapiro-Wilk p = %.4f, Durbin-Watson = %.3f (p = %.3g)",
            bptest(final)$p.value, shapiro.test(resid(final))$p.value,
            dwtest(final)$statistic, dwtest(final)$p.value))
rs <- rstudent(final)
top <- order(abs(rs), decreasing = TRUE)[1:3]
say(sprintf("외적 스튜던트화 잔차 상위 3: %s",
            paste(sprintf("%s (%+.2f)", de$month[top], rs[top]), collapse = ", ")))
h <- hatvalues(final)
say(sprintf("레버리지 > 2p/n (%.3f): %d개, Cook's D > 4/n: %d개", 2 * length(coef(final)) / n,
            sum(h > 2 * length(coef(final)) / n), sum(cooks.distance(final) > 4 / n)))

png("outputs/figures/de_avplots.png", width = 1600, height = 1100, res = 130)
avPlots(final, main = "추가변수 plot (독일 최종 다중회귀)", grid = FALSE)
invisible(dev.off())

png("outputs/figures/de_mlr_diag.png", width = 1500, height = 950, res = 130)
par(mfrow = c(2, 3), mar = c(4.2, 4.2, 2.5, 1), oma = c(0, 0, 2.2, 0))
e <- resid(final)
plot(fitted(final), e, xlab = "적합값", ylab = "잔차", main = "잔차 vs 적합값"); abline(h = 0, lty = 2)
plot(seq_len(n), e, type = "b", pch = 20, cex = 0.6, xlab = "시간 (월)", ylab = "잔차", main = "잔차 vs 시간")
abline(h = 0, lty = 2)
qqnorm(e, main = "정규확률그림"); qqline(e, col = "red")
acf(e, main = "잔차 자기상관 (ACF)")
plot(h, cooks.distance(final), xlab = "레버리지", ylab = "Cook's D", main = "영향점")
abline(h = 4 / n, lty = 2)
plot(de$hdd, e, xlab = "HDD", ylab = "잔차", main = "잔차 vs HDD"); abline(h = 0, lty = 2)
mtext("독일 최종 다중회귀 진단", outer = TRUE, line = 0.6, font = 2)
invisible(dev.off())

close(out)
cat("\n저장: outputs/de_multiple_regression.txt, outputs/de_subset_selection.csv, outputs/figures/de_avplots.png, de_mlr_diag.png\n")
