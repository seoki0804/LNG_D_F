# 한국 전국 용도별 수요의 회귀분석 (강의 Ch1~6)
#   A. 도시가스용 단순회귀 Y ~ HDD: 추론·ANOVA(Ch1~2), 진단·적합결여·Box-Cox(Ch3), 동시추론·역예측(Ch4~5)
#   B. 도시가스용 다중회귀 √Y ~ HDD + CDD + 영업일 + log(요금) + 추세: VIF, 모든 부분집합, HAC 표준오차(Ch6~)
#   C. 발전용 다중회귀 √Y ~ HDD + CDD + 전력거래량 + 석탄 상한제 + log(LNG 가격) + 추세: 부분 F 검정
#   D. 구조변화: 도시가스용 관계의 sup-F(HAC) 검정
#
# 입력: data/processed/national.csv (python/build.py), 2016-01~2025-12 (120개월, 2026년은 표본 외로 남김)
# 출력: outputs/regression/national_{coefs,tests,subsets,resid}.csv, national_regression.txt
# 실행: korea/ 에서  Rscript R/01_national_regression.R
# 필요 패키지: lmtest, sandwich, car, MASS, strucchange

suppressPackageStartupMessages({
  library(lmtest); library(sandwich); library(car); library(MASS); library(strucchange)
})
dir.create("outputs/regression", recursive = TRUE, showWarnings = FALSE)
d <- read.csv("data/processed/national.csv", stringsAsFactors = FALSE)
d <- subset(d, month >= "2016-01" & month <= "2025-12")
stopifnot(nrow(d) == 120, !anyNA(d[, c("city", "power", "hdd", "cdd", "cpi_city_gas", "elec_twh", "lng_usd")]))
d$trend <- seq_len(nrow(d)) / 12           # 연 단위 추세
d$log_cpi <- log(d$cpi_city_gas); d$log_lng <- log(d$lng_usd)
d$sq_city <- sqrt(d$city); d$sq_power <- sqrt(d$power)

out <- file("outputs/regression/national_regression.txt", open = "w", encoding = "UTF-8")
say <- function(...) { txt <- paste0(...); cat(txt, "\n"); writeLines(txt, out) }
coefs <- list(); tests <- list()
hac <- function(fit) NeweyWest(fit, lag = 3, prewhite = FALSE)
add_coefs <- function(name, fit) {
  s <- summary(fit)$coefficients; h <- coeftest(fit, vcov. = hac(fit))
  coefs[[name]] <<- data.frame(model = name, term = rownames(s), est = s[, 1], se = s[, 2], p = s[, 4],
                               se_hac = h[, 2], p_hac = h[, 4], row.names = NULL)
}
add_test <- function(model, test, stat, p, note = "") {
  tests[[length(tests) + 1]] <<- data.frame(model = model, test = test, stat = stat, p = p, note = note)
}
brown_forsythe <- function(e, x) { g <- x <= median(x); dd <- abs(e - ave(e, g, FUN = median)); t.test(dd[g], dd[!g], var.equal = TRUE) }
lack_of_fit <- function(fit) {   # 같은 HDD의 반복 관측이 없어, 3차 다항식을 허용한 모형과의 F 검정으로 대신한다
  f2 <- update(fit, . ~ . + I(hdd^2) + I(hdd^3)); a <- anova(fit, f2)
  c(F = a$F[2], p = a$`Pr(>F)`[2])
}
diagnose <- function(name, fit, x, lof = FALSE) {
  e <- resid(fit)
  add_test(name, "R2", summary(fit)$r.squared, NA)
  add_test(name, "BP(Koenker)", bptest(fit)$statistic, bptest(fit)$p.value)
  add_test(name, "Brown-Forsythe", brown_forsythe(e, x)$statistic, brown_forsythe(e, x)$p.value)
  add_test(name, "Shapiro-Wilk", shapiro.test(e)$statistic, shapiro.test(e)$p.value)
  dw <- dwtest(fit); add_test(name, "Durbin-Watson", dw$statistic, dw$p.value)
  lf <- if (lof) lack_of_fit(fit) else c(F = NA, p = NA)
  if (lof) add_test(name, "적합결여(3차항 F)", lf["F"], lf["p"])
  say(sprintf("[%s] R² %.3f | BP p %.3f | BF p %.3f | SW p %.3f | DW %.2f (p %.2g)%s",
              name, summary(fit)$r.squared, bptest(fit)$p.value, brown_forsythe(e, x)$p.value,
              shapiro.test(e)$p.value, dw$statistic, dw$p.value,
              if (lof) sprintf(" | 적합결여(3차항 F) p %.3g", lf["p"]) else ""))
}

# ---------------- A. 도시가스용 단순회귀 ----------------
say("## A. 도시가스용 단순회귀 (천 톤, 2016~2025, n = 120)")
fa <- lm(city ~ hdd, d); add_coefs("A: Y~HDD", fa); diagnose("A: Y~HDD", fa, d$hdd, lof = TRUE)
ci <- confint(fa)["hdd", ]; b1 <- coef(fa)["hdd"]; se_h <- sqrt(diag(hac(fa)))["hdd"]
say(sprintf("HDD 1 증가 → 월 %.2f 천 톤 (95%% CI %.2f~%.2f, HAC CI %.2f~%.2f)", b1, ci[1], ci[2],
            b1 - qt(.975, 118) * se_h, b1 + qt(.975, 118) * se_h))
av <- anova(fa); add_test("A: Y~HDD", "ANOVA F", av$`F value`[1], av$`Pr(>F)`[1])
bc <- boxcox(fa, lambda = seq(-1, 2, 0.01), plotit = FALSE)
lam <- bc$x[which.max(bc$y)]; lci <- range(bc$x[bc$y > max(bc$y) - qchisq(.95, 1) / 2])
add_test("A: Y~HDD", "Box-Cox λ", lam, NA, sprintf("95%% CI %.2f~%.2f", lci[1], lci[2]))
say(sprintf("Box-Cox 최적 λ = %.2f (95%% CI %.2f~%.2f)", lam, lci[1], lci[2]))
fs <- lm(sq_city ~ hdd, d); add_coefs("A: √Y~HDD", fs); diagnose("A: √Y~HDD", fs, d$hdd, lof = TRUE)

# Ch4~5: β 동시구간(Bonferroni), Working-Hotelling 신뢰대, 역예측
bon <- confint(fa, level = 1 - 0.05 / 2)
say(sprintf("Bonferroni 90%% 동시구간(β0, β1 각 97.5%%): β0 %.1f~%.1f, β1 %.2f~%.2f",
            bon[1, 1], bon[1, 2], bon[2, 1], bon[2, 2]))
W <- sqrt(2 * qf(.95, 2, 118))
for (x0 in c(100, 300, 500)) {
  p <- predict(fa, data.frame(hdd = x0), se.fit = TRUE)
  add_test("A: Y~HDD", sprintf("WH 신뢰대 HDD=%d", x0), p$fit, NA, sprintf("%.0f~%.0f", p$fit - W * p$se.fit, p$fit + W * p$se.fit))
}
y0 <- 3000; xh <- (y0 - coef(fa)[1]) / b1
s_inv <- summary(fa)$sigma / abs(b1) * sqrt(1 + 1 / 120 + (xh - mean(d$hdd))^2 / sum((d$hdd - mean(d$hdd))^2))
add_test("A: Y~HDD", "역예측 Y=3000", xh, NA, sprintf("HDD %.0f~%.0f", xh - qt(.975, 118) * s_inv, xh + qt(.975, 118) * s_inv))
say(sprintf("역예측: 도시가스용 3,000천 톤이 되는 HDD = %.0f (95%% 구간 %.0f~%.0f)", xh,
            xh - qt(.975, 118) * s_inv, xh + qt(.975, 118) * s_inv))
write.csv(data.frame(month = d$month, fitted = fitted(fs), resid = resid(fs), rstudent = rstudent(fs), hdd = d$hdd,
                     y = d$sq_city), "outputs/regression/national_resid.csv", row.names = FALSE, fileEncoding = "UTF-8")

# ---------------- B. 도시가스용 다중회귀 ----------------
say("\n## B. 도시가스용 다중회귀 √Y")
xb <- c("hdd", "cdd", "workdays", "log_cpi", "trend")
fb <- lm(reformulate(xb, "sq_city"), d); add_coefs("B: 도시가스용", fb); diagnose("B: 도시가스용", fb, d$hdd)
v <- vif(fb); say("VIF: ", paste(sprintf("%s %.1f", names(v), v), collapse = ", "))
for (nm in names(v)) add_test("B: 도시가스용", paste("VIF", nm), v[[nm]], NA)
subsets <- do.call(rbind, lapply(1:length(xb), function(k) do.call(rbind, lapply(combn(xb, k, simplify = FALSE), function(v) {
  f <- lm(reformulate(v, "sq_city"), d); n <- nrow(d); p <- length(v) + 1
  data.frame(vars = paste(v, collapse = " + "), p = p, adjR2 = summary(f)$adj.r.squared, AIC = AIC(f), BIC = BIC(f),
             Cp = sum(resid(f)^2) / summary(fb)$sigma^2 - (n - 2 * p),
             PRESS = sum((resid(f) / (1 - hatvalues(f)))^2))
}))))
write.csv(subsets[order(subsets$BIC), ], "outputs/regression/national_subsets.csv", row.names = FALSE, fileEncoding = "UTF-8")
say("BIC 최적: ", subsets$vars[which.min(subsets$BIC)], " | 수정 R² 최적: ", subsets$vars[which.max(subsets$adjR2)])

# ---------------- C. 발전용 다중회귀 ----------------
say("\n## C. 발전용 다중회귀 √Y")
xc <- c("hdd", "cdd", "elec_twh", "coal_cap", "log_lng", "trend")
fc <- lm(reformulate(xc, "sq_power"), d); add_coefs("C: 발전용", fc); diagnose("C: 발전용", fc, d$hdd)
v <- vif(fc); for (nm in names(v)) add_test("C: 발전용", paste("VIF", nm), v[[nm]], NA)
for (drop in list(c("elec_twh"), c("coal_cap"), c("hdd", "cdd"))) {   # 부분 F: 이 변수들이 함께 필요한가
  f0 <- lm(reformulate(setdiff(xc, drop), "sq_power"), d); a <- anova(f0, fc)
  add_test("C: 발전용", paste("부분 F:", paste(drop, collapse = "+")), a$F[2], a$`Pr(>F)`[2])
  say(sprintf("부분 F (%s): F = %.1f, p = %.2g", paste(drop, collapse = "+"), a$F[2], a$`Pr(>F)`[2]))
}
fc0 <- lm(sq_power ~ hdd + cdd, d); add_test("C: 발전용", "R2 기온만", summary(fc0)$r.squared, NA)
say(sprintf("발전용 R²: 기온만 %.2f → 전력·정책 변수 추가 %.2f", summary(fc0)$r.squared, summary(fc)$r.squared))

# ---------------- D. 구조변화 (도시가스용) ----------------
say("\n## D. 구조변화: √도시가스용 ~ HDD + CDD + 영업일 + 추세 (꾸준한 증감을 구조변화로 오인하지 않게 추세 포함)")
fd <- Fstats(sq_city ~ hdd + cdd + workdays + trend, data = d, from = 0.15)
st <- sctest(fd); bp <- d$month[fd$breakpoint]
add_test("D: 구조변화", "sup-F", st$statistic, st$p.value, bp)
say(sprintf("sup-F = %.1f, p = %.3g, 추정 시점 %s", st$statistic, st$p.value, bp))
# 2019년은 복원한 값이라, 복원 구간을 뺀 2020~2025년만으로 다시 검정한다
d2 <- subset(d, month >= "2020-01")
fd2 <- Fstats(sq_city ~ hdd + cdd + workdays + trend, data = d2, from = 0.15)
st2 <- sctest(fd2); bp2 <- d2$month[fd2$breakpoint]
add_test("D: 구조변화 2020~2025", "sup-F", st2$statistic, st2$p.value, bp2)
say(sprintf("2020~2025만: sup-F = %.1f, p = %.3g, 추정 시점 %s (2019년 복원값 제외)", st2$statistic, st2$p.value, bp2))

write.csv(do.call(rbind, coefs), "outputs/regression/national_coefs.csv", row.names = FALSE, fileEncoding = "UTF-8")
write.csv(do.call(rbind, tests), "outputs/regression/national_tests.csv", row.names = FALSE, fileEncoding = "UTF-8")
close(out)
cat("저장: outputs/regression/national_*.csv, national_regression.txt\n")
