-- Gold marts for the labour-market-nl product.
-- Every table here reads only silver tables built from contracted sources.

CREATE OR REPLACE TABLE gold_labour_market_monthly AS
SELECT
    date,
    year,
    labour_force_sa      AS labour_force,
    employed_sa          AS employed,
    unemployed_sa        AS unemployed,
    unemployment_rate_sa AS unemployment_rate,
    gross_participation_sa AS gross_participation,
    net_participation_sa   AS net_participation
FROM silver_labour_monthly
WHERE unemployment_rate_sa IS NOT NULL
ORDER BY date;

CREATE OR REPLACE TABLE gold_vacancies_quarterly AS
SELECT
    date, year, period_num AS quarter,
    vacancies_unfilled, vacancies_new, vacancies_filled
FROM silver_vacancies_sector
WHERE sector_code = 'T001081'
ORDER BY date;

-- Letter-level SIC sections only (titles like 'A Agriculture...', 'Q Health...').
CREATE OR REPLACE TABLE gold_vacancies_by_sector AS
SELECT
    date, year, period_num AS quarter,
    sector_code,
    sector,
    vacancies_unfilled AS vacancies
FROM silver_vacancies_sector
WHERE regexp_matches(sector, '^[A-Z] ')
ORDER BY date, sector;

-- Labour-market tension: unfilled vacancies per unemployed person.
-- Vacancies are quarterly; unemployment is averaged into the quarter.
CREATE OR REPLACE TABLE gold_labour_tension AS
WITH unemployed_q AS (
    SELECT
        make_date(year, ((month(date) - 1) // 3) * 3 + 1, 1) AS qdate,
        avg(unemployed) AS unemployed_avg
    FROM gold_labour_market_monthly
    GROUP BY 1
)
SELECT
    v.date, v.year, v.quarter,
    v.vacancies_unfilled,
    u.unemployed_avg,
    v.vacancies_unfilled / nullif(u.unemployed_avg, 0) AS tension_ratio,
    u.unemployed_avg / nullif(v.vacancies_unfilled, 0) AS unemployed_per_vacancy
FROM gold_vacancies_quarterly v
LEFT JOIN unemployed_q u ON u.qdate = v.date
ORDER BY v.date;

-- Composition of employed labour force (age 15-74 total), quarterly.
CREATE OR REPLACE TABLE gold_workforce_position AS
SELECT
    date, year,
    employed,
    permanent_employee,
    flexible_employee,
    self_employed,
    part_time,
    full_time,
    permanent_employee / nullif(employed, 0) * 100 AS permanent_share,
    flexible_employee  / nullif(employed, 0) * 100 AS flexible_share,
    self_employed      / nullif(employed, 0) * 100 AS self_employed_share,
    part_time          / nullif(employed, 0) * 100 AS part_time_share
FROM silver_participation
WHERE age_code = '52052' AND period_type = 'KW'
ORDER BY date;

-- Net participation rate by 10-year age band, yearly.
CREATE OR REPLACE TABLE gold_participation_by_age AS
SELECT
    date, year,
    age_group,
    net_participation AS participation_rate,
    unemployment_rate
FROM silver_participation
WHERE period_type = 'JJ'
  AND age_code IN ('53050', '53500', '53700', '53800', '53900', '53925')
ORDER BY date, age_group;

-- Employment (persons, seasonally adjusted) by main sector, quarterly.
CREATE OR REPLACE TABLE gold_employment_by_sector AS
SELECT
    date, year, period_num AS quarter,
    sector_code,
    sector,
    employed_persons_sa AS employed_persons,
    hours_worked
FROM silver_employment_sector
WHERE sector_code <> 'T001081'
  AND regexp_matches(sector, '^([A-Z]|[A-Z]-[A-Z]) ')
ORDER BY date, sector;
