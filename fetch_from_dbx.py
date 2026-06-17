#!/usr/bin/env python3
"""Fetch the 'Active Stores tracking' dataset straight from Databricks
(no Looker CSV export needed).

Reproduces the Looker explore: weekly snapshot of UA *store* providers that were
ACTIVE (online / available > 0) during the week, with the same columns as the
Looker CSV export, plus City. Output CSV is consumed by build.py.

Active Merchant definition (validated vs Looker export, ~99% match):
  a store provider is "active" in a week if SUM(active_time) > 0 in
  etl_delivery_provider_daily_availability for that Mon–Sun week.
"""
import csv, os, sys
from pathlib import Path
from databricks import sql as dbsql

ROOT = Path(__file__).parent
ENV = Path("/Users/yuliia.nikolaieva/Downloads/Reports GIT HUB/VARUS/.env")
OUT = ROOT / "active_stores_from_dbx.csv"
START = "2026-01-05"   # first Monday snapshot

def load_env():
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_env()
kw = {}
if os.environ.get("DATABRICKS_TLS_NO_VERIFY", "").lower() in ("1","true","yes"):
    kw["_tls_no_verify"] = True

QUERY = f"""
SELECT
    DATE_FORMAT(DATE_TRUNC('week', a.created_date), 'yyyy-MM-dd') AS report_time,
    p.country_name,
    p.delivery_vertical,
    p.provider_name,
    p.group_name           AS brand_name,
    p.business_segment_code_v2,
    p.business_segment,
    p.city_name,
    1                      AS active_merchant_count
FROM hive_metastore.ng_delivery_spark.etl_delivery_provider_daily_availability a
JOIN hive_metastore.ng_delivery_spark.dim_provider_v2 p ON a.provider_id = p.provider_id
WHERE p.country_code = 'ua'
  AND p.delivery_vertical LIKE 'store%'
  AND a.created_date >= DATE'{START}'
  AND a.created_date <= DATE_SUB(DATE_TRUNC('week', CURRENT_DATE()), 1)  -- only complete weeks
GROUP BY 1,2,3,4,5,6,7,8
HAVING SUM(a.active_time) > 0
ORDER BY report_time, brand_name, provider_name
"""

def main():
    conn = dbsql.connect(server_hostname=os.environ["DATABRICKS_HOST"],
                         http_path=f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}",
                         access_token=os.environ["DATABRICKS_TOKEN"], **kw)
    cur = conn.cursor()
    cur.execute(QUERY)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    conn.close()

    header = ["", "Report Time (dynamic)", "Country Name", "Delivery Vertical",
              "Provider Name", "Brand Name", "Business Segment Code V2",
              "Business Segment", "City Name", "Active Merchant Count, #"]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for i, r in enumerate(rows, 1):
            w.writerow([i, r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]])
    print(f"Wrote {len(rows)} rows -> {OUT}")

if __name__ == "__main__":
    main()
