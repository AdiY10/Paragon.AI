#!/usr/bin/env bash
# Re-runs the core data-source feasibility probes from docs/03_DATA_SOURCES.md §5.
# Requires: bash, curl, jq. No API keys needed. Set SEC_USER_AGENT="AppName contact@example.org" for SEC calls.
# Results change over time as sources publish revisions; compare against docs/03 §5 with tolerance.
set -u
UA_SEC="${SEC_USER_AGENT:-ParagonFeasibilityProbe/0.1 (research prototype)}"
ok(){ printf '  \033[32mOK\033[0m  %s\n' "$1"; }; bad(){ printf '  \033[31mFAIL\033[0m %s\n' "$1"; }
LON=-73.388299; LAT=41.126611   # 444 Westport Ave, Norwalk CT (Staples Plaza)

echo "V1 Census Geocoder (single)"
r=$(curl -s -m 30 "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=444%20Westport%20Avenue%2C%20Norwalk%2C%20CT%2006851&benchmark=Public_AR_Current&vintage=Current_Current&layers=10&format=json" | jq -r '.result.addressMatches[0] | "\(.coordinates.y),\(.coordinates.x) BG=\(.geographies["Census Block Groups"][0].GEOID)"')
[[ "$r" == *091900435001* ]] && ok "$r" || bad "$r"

echo "V3 Census Data API keyless (expect 302 missing key)"
c=$(curl -s -m 30 -o /dev/null -w "%{http_code}" "https://api.census.gov/data/2024/acs/acs5?get=B01003_001E&for=state:09")
echo "  HTTP $c (302 = key required; 200 = keyless works again)"

echo "V4 ACS 2020-2024 bulk B01003 for BG 091900435001 (expect 1103|172)"
r=$(curl -s -m 120 "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b01003.dat" | grep "^1500000US091900435001|")
[[ "$r" == *"|1103|172"* ]] && ok "$r" || bad "$r"

echo "V6 TIGERweb 2020 blocks within 1 mi (block internal points) population (expect ~11,521)"
curl -s -m 60 "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/10/query?geometry=$LON,$LAT&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&distance=1&units=esriSRUnit_StatuteMile&outFields=POP100,INTPTLAT,INTPTLON&returnGeometry=false&f=json" \
 | jq --argjson la $LAT --argjson lo $LON '[.features[].attributes | select((((.INTPTLAT|tonumber)-$la)*69.0)*(((.INTPTLAT|tonumber)-$la)*69.0) + (((.INTPTLON|tonumber)-$lo)*52.0)*(((.INTPTLON|tonumber)-$lo)*52.0) <= 1) | .POP100] | add' | sed 's/^/  approx 1-mi block population: /'

echo "V7 BLS QCEW 2025Q4 Ulster County NY private total (expect 47329, +1.9%)"
curl -s -m 30 "https://data.bls.gov/cew/data/api/2025/4/area/36111.csv" | awk -F, '$2=="\"5\"" && $3=="\"10\"" {print "  emp_m3="$12" oty_pct="$(NF-6)}' | head -1

echo "V8 BLS LAUS v1 (keyless) Ulster Co NY unemployment"
curl -s -m 30 -X POST -H 'Content-Type: application/json' -d '{"seriesid":["LAUCN361110000000003"]}' https://api.bls.gov/publicAPI/v1/timeseries/data/ | jq -r '.status, (.Results.series[0].data[0] | "  latest \(.year)-\(.period) = \(.value)")'

echo "V9 Census BPS county monthly file (latest Sep 2026 = co2609c.txt)"
curl -s -m 30 "https://www2.census.gov/econ/bps/County/co2609c.txt" | grep -E "^[0-9]+,36,111," | cut -d, -f1-8 | sed 's/^/  /'

echo "V10 LODES8 WAC files for CT"
curl -s -m 30 "https://lehd.ces.census.gov/data/lodes/LODES8/ct/wac/" | grep -oE 'ct_wac_S000_JT00_20[0-9]+\.csv\.gz' | sort -u | tail -2 | sed 's/^/  /'

echo "V11 HPMS NY 2024 AADT near Kingston Marketplace (expect ULSTER AVE US 9W 22523)"
curl -s -m 60 "https://geo.dot.gov/server/rest/services/Hosted/HPMS_FULL_NY_2024/FeatureServer/0/query?geometry=-73.9889473,41.9651857&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&distance=250&units=esriSRUnit_Meter&outFields=routename,aadt,data_year&returnGeometry=false&f=json" | jq -c '[.features[].attributes] | unique | .[:3]' | sed 's/^/  /'

echo "V12 FEMA NFHL flood zone, Cypress Lake Shopping Center (expect AE, SFHA T) — envelope query"
curl -s -m 60 --retry 2 "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query?geometry=%7B%22xmin%22%3A-81.8770%2C%22ymin%22%3A26.5458%2C%22xmax%22%3A-81.8763%2C%22ymax%22%3A26.5463%7D&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=FLD_ZONE,SFHA_TF,STATIC_BFE&returnGeometry=false&f=json" | jq -c '[.features[]?.attributes] // .error' | sed 's/^/  /'

echo "V14 FEMA NRI tract 12071000303"
curl -s -m 30 "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Census_Tracts/FeatureServer/0/query?where=TRACTFIPS%3D%2712071000303%27&outFields=*&returnGeometry=false&f=json" | jq -c '.features[0].attributes | {RISK_RATNG,HRCN_RISKR,CFLD_RISKR,NRI_VER}' | sed 's/^/  /'

echo "V17 SEC EDGAR Rite Aid (CIK 84129) 8-Ks with item 1.03"
curl -s -m 30 -A "$UA_SEC" "https://data.sec.gov/submissions/CIK0000084129.json" | jq -r '.filings.recent as $r | [range(0; ($r.form|length)) | select($r.items[.] | test("1\\.03")) | "\($r.filingDate[.]) \($r.form[.]) \($r.items[.])"] | .[:3][]' | sed 's/^/  /'

echo "Overture: latest releases in bucket (run overture_places_probe.py for a places query)"
curl -s -m 30 "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/?list-type=2&prefix=release/&delimiter=/" | grep -oE '<Prefix>release/[^<]+' | sed 's/<Prefix>/  /'
