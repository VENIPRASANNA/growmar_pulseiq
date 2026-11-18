
#!/usr/bin/env python3
"""Generate a read-only summary of the latest PulseIQ DQ run."""

import os
import sys
from pathlib import Path
from datetime import datetime

import psycopg

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"


def main():
    if not os.getenv("PGPASSWORD"):
        print("Error: Set PGPASSWORD before running this script.")
        return 1

    try:
        with psycopg.connect(
            host="127.0.0.1",
            dbname="pulseiq_analytics",
            user="pulseiq_user",
            connect_timeout=10,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT run_id, MAX(run_time)
                    FROM public.dq_results
                    GROUP BY run_id
                    ORDER BY MAX(run_time) DESC
                    LIMIT 1
                """)
                latest = cur.fetchone()

                if not latest:
                    print("No DQ results found.")
                    return 1

                run_id, run_time = latest

                cur.execute("""
                    SELECT check_id, check_name, status,
                           bad_rows, severity, details
                    FROM public.dq_results
                    WHERE run_id = %s
                    ORDER BY
                        CASE severity
                            WHEN 'Critical' THEN 1
                            ELSE 2
                        END,
                        check_id
                """, (run_id,))

                results = cur.fetchall()

        passed = sum(r[2] == "PASS" for r in results)
        failed = sum(r[2] == "FAIL" for r in results)
        errors = sum(r[2] == "ERROR" for r in results)

        critical_failures = [
            r for r in results
            if r[2] != "PASS" and r[4] == "Critical"
        ]

        if errors:
            overall = "ERROR - Review required"
        elif failed:
            overall = "ATTENTION - Data-quality failures found"
        else:
            overall = "PASS - All checks passed"

        lines = [
            "# PulseIQ Data Quality Summary",
            "",
            f"**DQ Run ID:** `{run_id}`",
            f"**Run timestamp:** {run_time}",
            f"**Generated:** {datetime.now().astimezone().isoformat()}",
            "",
            "## Overall Status",
            "",
            f"**{overall}**",
            "",
            "## Validation Summary",
            "",
            "| Metric | Count |",
            "|---|---:|",
            f"| Total checks | {len(results)} |",
            f"| PASS | {passed} |",
            f"| FAIL | {failed} |",
            f"| ERROR | {errors} |",
            "",
            "## Critical Failures",
            "",
        ]

        if critical_failures:
            lines.extend([
                "| Check | Name | Bad Rows |",
                "|---|---|---:|",
            ])
            for r in critical_failures:
                lines.append(f"| {r[0]} | {r[1]} | {r[3]} |")
        else:
            lines.append("No critical failures.")

        lines.extend([
            "",
            "## Detailed Results",
            "",
            "| Check | Name | Severity | Status | Bad Rows |",
            "|---|---|---|---|---:|",
        ])

        for r in results:
            lines.append(
                f"| {r[0]} | {r[1]} | {r[4]} | {r[2]} | {r[3]} |"
            )

        lines.extend([
            "",
            "## Notes",
            "",
            "This report reads existing DQ results only. "
            "It does not modify warehouse source records or DQ rules.",
            "",
        ])

        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        output = REPORT_DIR / f"dq_summary_{str(run_id)[:8]}.md"
        output.write_text("\n".join(lines), encoding="utf-8")

        print(f"DQ summary generated: {output}")
        print(f"Total: {len(results)} | PASS: {passed} | "
              f"FAIL: {failed} | ERROR: {errors}")
        print(f"Critical failures: {len(critical_failures)}")

        return 0

    except Exception as exc:
        print(f"Error generating DQ summary: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
