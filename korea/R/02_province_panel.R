# 17개 시도 도시가스 판매량의 난방 민감도 (강의 Ch6~8: 지시변수·상호작용, 기울기 동일성 검정)
#   1) 시도·기간별 log(판매량) ~ HDD + CDD + 추세 → HDD 10 증가당 판매량 % (Newey-West 표준오차)
#      기간: 2000~2009, 2010~2019, 2020~2022 (판매량은 검침 시점 기준이라 당월·전월 HDD를 함께 넣는다)
#   2) 2010~2022 통합 모형에서 시도 지시변수 × HDD 상호작용 → 17개 시도의 기울기가 같은지 F 검정
#
# 입력: data/processed/province.csv (python/build.py)
# 출력: outputs/regression/province_sensitivity.csv, province_tests.csv
# 실행: korea/ 에서  Rscript R/02_province_panel.R

suppressPackageStartupMessages({ library(lmtest); library(sandwich) })
dir.create("outputs/regression", recursive = TRUE, showWarnings = FALSE)
p <- read.csv("data/processed/province.csv", stringsAsFactors = FALSE)
p <- p[order(p$province, p$month), ]
p$hdd_l1 <- ave(p$hdd, p$province, FUN = function(x) c(NA, head(x, -1)))   # 전월 HDD (검침 지연)
p$cdd_l1 <- ave(p$cdd, p$province, FUN = function(x) c(NA, head(x, -1)))
p <- subset(p, month >= "2000-01" & !is.na(sales) & sales > 0 & !is.na(hdd_l1))
p$t <- as.integer(substr(p$month, 1, 4)) + (as.integer(substr(p$month, 6, 7)) - 1) / 12
p$period <- cut(as.integer(substr(p$month, 1, 4)), c(1999, 2009, 2019, 2022), labels = c("2000~2009", "2010~2019", "2020~2022"))

rows <- list()
for (pr in unique(p$province)) for (pe in levels(p$period)) {
  s <- subset(p, province == pr & period == pe)
  if (nrow(s) < 30) next
  f <- lm(log(sales) ~ hdd + hdd_l1 + cdd + cdd_l1 + t, s)
  V <- NeweyWest(f, lag = 3, prewhite = FALSE)
  g <- c(0, 1, 1, 0, 0, 0)                              # 당월 + 전월 HDD 효과의 합
  b <- sum(g * coef(f)); se <- sqrt(drop(t(g) %*% V %*% g))
  rows[[length(rows) + 1]] <- data.frame(province = pr, period = pe, n = nrow(s), pct_per10 = 100 * (exp(10 * b) - 1),
                                         se_pct = 1000 * se, r2 = summary(f)$r.squared)
}
sens <- do.call(rbind, rows)
write.csv(sens, "outputs/regression/province_sensitivity.csv", row.names = FALSE, fileEncoding = "UTF-8")

# 기울기 동일성 (2010~2022): 시도 지시변수 + 시도별 추세 vs 여기에 시도 × (HDD, 전월 HDD) 상호작용 추가
q <- subset(p, month >= "2010-01")
q$province <- factor(q$province)
f0 <- lm(log(sales) ~ province * t + hdd + hdd_l1 + cdd + cdd_l1, q)
f1 <- lm(log(sales) ~ province * t + province * (hdd + hdd_l1) + cdd + cdd_l1, q)
a <- anova(f0, f1)
tests <- data.frame(test = c("시도 기울기 동일 F (2010~2022)", "통합 R² (공통 기울기)", "통합 R² (시도별 기울기)"),
                    stat = c(a$F[2], summary(f0)$r.squared, summary(f1)$r.squared), p = c(a$`Pr(>F)`[2], NA, NA))
write.csv(tests, "outputs/regression/province_tests.csv", row.names = FALSE, fileEncoding = "UTF-8")
cat(sprintf("시도 기울기 동일성: F = %.1f, p = %.2g\n", a$F[2], a$`Pr(>F)`[2]))
print(reshape(sens[, c("province", "period", "pct_per10")], idvar = "province", timevar = "period", direction = "wide"), digits = 3)
cat("저장: outputs/regression/province_sensitivity.csv, province_tests.csv\n")
