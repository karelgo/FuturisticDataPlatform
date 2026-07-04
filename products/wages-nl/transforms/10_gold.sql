-- Gold marts for the wages-nl product.
-- Every table here reads only silver tables built from contracted sources.
-- Transforms run Write-Audit-Publish: staged, audited, then published.

-- Total across all CAO sectors, monthly.
CREATE OR REPLACE TABLE gold_wages_monthly AS
SELECT
    date, year,
    wage_index_monthly,
    wage_index_hourly,
    wage_growth_yoy,
    wage_cost_growth_yoy
FROM silver_cao_wages
WHERE cao_sector_code = 'T001020'
  AND wage_index_hourly IS NOT NULL
ORDER BY date;

-- Year-on-year wage growth per CAO sector (private / subsidised / government).
CREATE OR REPLACE TABLE gold_wage_growth_by_sector AS
SELECT
    date, year,
    cao_sector_code,
    cao_sector,
    wage_growth_yoy
FROM silver_cao_wages
WHERE cao_sector_code <> 'T001020'
  AND wage_growth_yoy IS NOT NULL
ORDER BY date, cao_sector;
