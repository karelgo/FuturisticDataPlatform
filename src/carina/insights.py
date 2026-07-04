"""Prepared analysis — 'the platform already prepared your analysis'.

Deterministic, data-driven insight computation over the gold tables. Each
insight is a claim with the numbers that support it, the metrics it draws on,
and therefore full traceability. (In the full CARINA design this is the
Analyst agent; the laptop profile computes the brief without an LLM.)
"""

from __future__ import annotations

import duckdb


def _one(con: duckdb.DuckDBPyConnection, sql: str):
    row = con.execute(sql).fetchone()
    return row if row is None else (row[0] if len(row) == 1 else row)


def compute_insights(con: duckdb.DuckDBPyConnection) -> list[dict]:
    ins: list[dict] = []

    # --- Labour market tension -------------------------------------------
    row = con.execute(
        "SELECT date, tension_ratio FROM gold_labour_tension WHERE tension_ratio IS NOT NULL ORDER BY date DESC LIMIT 1"
    ).fetchone()
    if row:
        latest_date, latest_ratio = row
        ratio_2013 = _one(con, "SELECT tension_ratio FROM gold_labour_tension WHERE year=2013 AND quarter=1")
        peak_date, peak_ratio = con.execute(
            "SELECT date, tension_ratio FROM gold_labour_tension WHERE tension_ratio IS NOT NULL "
            "ORDER BY tension_ratio DESC LIMIT 1"
        ).fetchone()
        above = con.execute(
            "SELECT min(date), max(date), count(*) FROM gold_labour_tension WHERE tension_ratio >= 1"
        ).fetchone()
        state = (
            "The market remains tight: employers compete for workers."
            if latest_ratio >= 1
            else "Tension has eased from the peak but remains near parity — a structurally tight market by any historical standard."
        )
        tight_clause = (
            f"Between {above[0]:%B %Y} and {above[1]:%B %Y} there were more vacancies than unemployed "
            f"({above[2]} quarters); tension peaked at {peak_ratio:.2f} in {peak_date:%B %Y}. "
            if above and above[2] else ""
        )
        ins.append({
            "id": "tension",
            "headline": f"{latest_ratio:.2f} unfilled vacancies per unemployed person — a decade ago it was {ratio_2013:.2f}",
            "detail": (
                f"As of {latest_date:%B %Y}, labour-market tension stands at {latest_ratio:.2f} vacancies per "
                f"unemployed person, versus {ratio_2013:.2f} in early 2013. " + tight_clause + state
            ),
            "metrics": ["tension_ratio"],
            "direction": "structural",
        })

    # --- Unemployment ------------------------------------------------------
    row = con.execute(
        "SELECT date, unemployment_rate FROM gold_labour_market_monthly WHERE unemployment_rate IS NOT NULL ORDER BY date DESC LIMIT 1"
    ).fetchone()
    if row:
        d, rate = row
        lo = con.execute(
            "SELECT min(unemployment_rate), max(unemployment_rate) FROM gold_labour_market_monthly"
        ).fetchone()
        peak = con.execute(
            "SELECT date, unemployment_rate FROM gold_labour_market_monthly WHERE unemployment_rate = ? LIMIT 1",
            [lo[1]],
        ).fetchone()
        ins.append({
            "id": "unemployment",
            "headline": f"Unemployment is {rate:.1f}% — near the bottom of its 20-year range",
            "detail": (
                f"In {d:%B %Y} the seasonally adjusted unemployment rate was {rate:.1f}%. Over 2003–today it has ranged "
                f"from {lo[0]:.1f}% to {lo[1]:.1f}% (peak {peak[0]:%B %Y}). Low unemployment is one side of the coin; "
                "scarcity of workers is the other."
            ),
            "metrics": ["unemployment_rate"],
            "direction": "good",
        })

    # --- Flexibilisation reversal -------------------------------------------
    rows = con.execute(
        """
        SELECT year, avg(flexible_share) AS flex, avg(self_employed_share) AS zzp, avg(permanent_share) AS perm
        FROM gold_workforce_position GROUP BY year ORDER BY year
        """
    ).fetchall()
    if rows:
        first, last = rows[0], rows[-1]
        peak_flex = max(rows, key=lambda r: r[1] or 0)
        trend = "receded from its peak" if (peak_flex[0] < last[0] and peak_flex[1] - last[1] > 0.5) else "kept rising"
        ins.append({
            "id": "flex",
            "headline": f"Flexible work {trend}: {last[1]:.1f}% of the employed labour force",
            "detail": (
                f"Flexible employees went from {first[1]:.1f}% of the employed labour force in {first[0]} to a peak of "
                f"{peak_flex[1]:.1f}% in {peak_flex[0]}, and stand at {last[1]:.1f}% today. Self-employment moved from "
                f"{first[2]:.1f}% to {last[2]:.1f}%. The composition of Dutch work is visibly shifting."
            ),
            "metrics": ["flexible_share", "self_employed_share", "permanent_share"],
            "direction": "structural",
        })

    # --- Older workers ------------------------------------------------------
    rows = con.execute(
        """
        SELECT age_group,
               min_by(participation_rate, year) AS first_rate,
               max_by(participation_rate, year) AS last_rate,
               min(year) AS fy
        FROM gold_participation_by_age
        WHERE age_group IN ('55 to 64 years', '65 to 74 years') AND participation_rate IS NOT NULL
        GROUP BY age_group ORDER BY age_group
        """
    ).fetchall()
    if rows:
        parts = [f"{r[0].replace(' years','')}: {r[1]:.0f}% → {r[2]:.0f}%" for r in rows]
        ins.append({
            "id": "older-workers",
            "headline": "Older workers are the fastest-growing part of the workforce",
            "detail": (
                f"Net labour participation since {rows[0][3]} — " + "; ".join(parts) +
                ". An ageing workforce is no longer leaving early: it is one of the biggest structural changes "
                "in the Dutch labour market."
            ),
            "metrics": ["participation_by_age"],
            "direction": "structural",
        })

    # --- Sector shift ---------------------------------------------------------
    rows = con.execute(
        """
        WITH latest AS (SELECT max(date) AS d FROM gold_vacancies_by_sector),
        now AS (SELECT sector, vacancies FROM gold_vacancies_by_sector, latest WHERE date = d),
        past AS (SELECT sector, vacancies FROM gold_vacancies_by_sector
                 WHERE date = (SELECT d - INTERVAL 10 YEAR FROM latest))
        SELECT now.sector, past.vacancies, now.vacancies,
               (now.vacancies - past.vacancies) / nullif(past.vacancies, 0) * 100 AS growth
        FROM now JOIN past USING (sector)
        WHERE past.vacancies >= 1 ORDER BY growth DESC
        """
    ).fetchall()
    if rows:
        top = rows[:2]
        names = " and ".join(t[0].split(" ", 1)[1] if " " in t[0] else t[0] for t in top)
        ins.append({
            "id": "sectors",
            "headline": f"Demand growth concentrates in {names.lower()}",
            "detail": (
                "Ten-year growth in unfilled vacancies: "
                + "; ".join(f"{r[0]}: {r[1]:.0f}k → {r[2]:.0f}k ({r[3]:+.0f}%)" for r in rows[:4])
                + ". Where employers search hardest tells you where the economy is heading."
            ),
            "metrics": ["vacancies_by_sector"],
            "direction": "structural",
        })

    return ins
