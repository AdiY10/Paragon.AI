"""Overture Maps places probe (docs/03 SRC-13, V15/V16).
Usage: pip install duckdb && python overture_places_probe.py <release e.g. 2026-10-21.0> <out.json>
Reads places within ~0.8 mi of Kingston Marketplace from the public Overture S3 bucket (no credentials).
Diff two outputs by `id` to see added/removed places and operating_status changes.
"""
import duckdb, time, json, sys
rel = sys.argv[1]
lat, lon = 41.9651857, -73.9889473  # Kingston Marketplace (Nominatim)
d = 0.012  # ~0.8 mi box
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
t=time.time()
q=f"""
SELECT id, names.primary AS name, basic_category, brand.names.primary AS brand, operating_status, confidence,
       addresses[1].freeform AS addr, ST_Y(geometry) lat, ST_X(geometry) lon
FROM read_parquet('s3://overturemaps-us-west-2/release/{rel}/theme=places/type=place/*', hive_partitioning=1)
WHERE bbox.xmin BETWEEN {lon-d} AND {lon+d} AND bbox.ymin BETWEEN {lat-d} AND {lat+d}
"""
rows = con.execute(q).fetchall()
cols=[c[0] for c in con.description]
print(f"release {rel}: {len(rows)} places in box, {time.time()-t:.1f}s")
import collections
print("operating_status:", collections.Counter(r[cols.index('operating_status')] for r in rows))
print("top basic_category:", collections.Counter(r[cols.index('basic_category')] for r in rows).most_common(8))
brands=sorted({r[cols.index('brand')] for r in rows if r[cols.index('brand')]})
print("brands sample:", brands[:40])
json.dump([dict(zip(cols,r)) for r in rows], open(f"{sys.argv[2]}", "w"), default=str)
