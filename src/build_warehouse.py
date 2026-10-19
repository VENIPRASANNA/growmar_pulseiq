from pathlib import Path

import duckdb

DB_PATH = "05_Starter/pulseiq.duckdb"
EXPORT_DIR = Path("data/warehouse_export")

DIMENSIONS = [
    "dim_department",
    "dim_role",
    "dim_location",
    "dim_leave_type",
    "dim_account",
    "dim_client",
    "dim_vendor",
    "dim_team",
    "dim_sprint",
    "dim_employee",
    "dim_date",
]


def main():
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH, read_only=True)

    try:
        for table in DIMENSIONS:
            destination = (EXPORT_DIR / f"{table}.csv").resolve()
            con.execute(
                f"COPY (SELECT * FROM raw.{table}) "
                f"TO '{destination.as_posix()}' (HEADER, DELIMITER ',')"
            )
            count = con.execute(
                f"SELECT COUNT(*) FROM raw.{table}"
            ).fetchone()[0]
            print(f"Exported {table}: {count:,} rows -> {destination}")

        print("\nDimension exports completed.")
        print("Original DuckDB tables were read-only.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
