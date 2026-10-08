-- Signal stage: proportional reporting ratio (PRR) per company x side effect,
-- the statistic drug regulators run on adverse-event reports.
--
--             with this side effect   all other reports
--   company          a                      b
--   peers            c                      d
--
--   PRR = (a / (a + b)) / (c / (c + d))
--   95% CI = exp(ln PRR +/- 1.96 * sqrt(1/a - 1/(a+b) + 1/c - 1/(c+d)))
--   Signal (Evans rule): a >= 3 AND PRR >= 2 AND Yates chi-square >= 4
--
-- Peers = other companies in the same product family. Templates and credit bureaus are excluded.
WITH reports AS (
  SELECT company_name AS company, product, code
  FROM `PROJECT.side_effects.coded_complaints`, UNNEST(codes) AS code
  WHERE NOT is_template
    AND company_name NOT IN ('TRANSUNION INTERMEDIATE HOLDINGS, INC.', 'EQUIFAX, INC.',
                             'Experian Information Solutions Inc.')
),
company_totals AS (
  SELECT company, product, COUNT(*) AS n FROM reports GROUP BY company, product
),
cells AS (
  SELECT r.company, r.product, r.code, COUNT(*) AS a, ANY_VALUE(t.n) AS company_n
  FROM reports r JOIN company_totals t USING (company, product)
  GROUP BY r.company, r.product, r.code
),
product_totals AS (
  SELECT product, code, COUNT(*) AS code_n FROM reports GROUP BY product, code
),
all_totals AS (
  SELECT product, COUNT(*) AS n FROM reports GROUP BY product
),
table2x2 AS (
  SELECT c.company, c.product, c.code,
    c.a,
    c.company_n - c.a AS b,
    p.code_n - c.a AS c_,
    (t.n - c.company_n) - (p.code_n - c.a) AS d
  FROM cells c JOIN product_totals p USING (product, code) JOIN all_totals t USING (product)
  WHERE c.company_n >= 300
)
SELECT *,
  SAFE_DIVIDE(a / (a + b), c_ / (c_ + d)) AS prr,
  EXP(LN(SAFE_DIVIDE(a / (a + b), c_ / (c_ + d))) - 1.96 * SQRT(1/a - 1/(a+b) + 1/c_ - 1/(c_+d))) AS ci95_low,
  EXP(LN(SAFE_DIVIDE(a / (a + b), c_ / (c_ + d))) + 1.96 * SQRT(1/a - 1/(a+b) + 1/c_ - 1/(c_+d))) AS ci95_high,
  (a + b + c_ + d) * POW(ABS(a * d - b * c_) - (a + b + c_ + d) / 2, 2)
    / ((a + b) * (c_ + d) * (a + c_) * (b + d)) AS chi2_yates,
  (a >= 3
   AND SAFE_DIVIDE(a / (a + b), c_ / (c_ + d)) >= 2
   AND (a + b + c_ + d) * POW(ABS(a * d - b * c_) - (a + b + c_ + d) / 2, 2)
       / ((a + b) * (c_ + d) * (a + c_) * (b + d)) >= 4) AS signal_evans
FROM table2x2
WHERE a > 0 AND c_ > 0
ORDER BY prr DESC;
