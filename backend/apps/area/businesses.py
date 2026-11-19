"""Nearby businesses (Overture Maps Places, SRC-13): landscape and month-to-month changes.

Implements MET-15 (counts by category group), MET-16 (anchors and key brands with
distance) and the evidence for SIG-09 (possible closure) and SIG-10 (new key
business) from docs/04 §3.7, §5.2 and §5.3. Map data is not a business registry:
a record appearing is not proof of an opening, and changes are "possible, verify".
"""
import re
import unicodedata
from apps.demographics.rings import haversine_miles

MIN_COUNT_CONFIDENCE = 0.5
CLOSURE_PRIOR_CONFIDENCE = 0.7
OPENING_CONFIDENCE = 0.8

GROUPS = {
    'Grocery and food stores': {'food_and_beverage_store', 'convenience_store', 'market', 'farmers_market'},
    'Pharmacy': {'pharmacy_and_drug_store'},
    'General merchandise and big box': {'department_store', 'discount_store', 'warehouse_club_store',
        'shopping_mall', 'shopping', 'second_hand_store'},
    'Apparel and specialty retail': {'fashion_and_apparel_store', 'personal_care_and_beauty_store',
        'electronics_store', 'sporting_goods_store', 'books_music_and_video_store', 'toys_and_games_store',
        'arts_crafts_and_hobby_store', 'flowers_and_gifts_store', 'specialty_store', 'animal_and_pet_store',
        'office_supply_store', 'musical_instrument_and_pro_audio_store'},
    'Home and hardware': {'hardware_home_and_garden_store'},
    'Restaurants and cafés': {'restaurant', 'casual_eatery', 'fast_food_restaurant', 'coffee_shop', 'cafe',
        'bar', 'smoothie_juice_bar', 'food_truck_stand', 'food_service', 'food_and_drink',
        'non_alcoholic_beverage_venue', 'brewery', 'lounge'},
    'Personal services': {'personal_or_beauty_service', 'laundry_service', 'wellness_service'},
    'Medical and health': {'dental_clinic', 'health_care', 'specialized_health_care', 'medical_service',
        'primary_care_or_general_clinic', 'urgent_care_clinic', 'outpatient_care_facility', 'hospital',
        'vision_or_eye_care_clinic', 'physical_medicine_and_rehabilitation', 'diagnostics_imaging_or_lab_service',
        'pediatric_clinic', 'behavioral_or_mental_health_clinic', 'surgery', 'reproductive_perinatal_and_womens_care',
        'emergency_department', 'emergency_or_urgent_care_facility', 'specialty_hospital',
        'specialized_medical_facility', 'complementary_and_alternative_medicine'},
    'Banks and financial': {'bank_or_credit_union', 'financial_service'},
    'Fitness and entertainment': {'gym', 'fitness_studio', 'sport_or_fitness_facility', 'movie_theater', 'arcade',
        'gaming_venue', 'performing_arts_venue', 'theatre_venue', 'music_venue', 'comedy_club', 'skating_rink'},
    'Auto services': {'automotive_service', 'vehicle_service', 'gas_station', 'fueling_station',
        'vehicle_parts_store', 'auto_dealer', 'vehicle_dealer'},
}
CATEGORY_GROUP = {cat: group for group, cats in GROUPS.items() for cat in cats}
KEY_CATEGORIES = {'pharmacy_and_drug_store', 'department_store', 'discount_store', 'warehouse_club_store',
    'movie_theater', 'shopping_mall'}

# Curated anchor brands (normalized). Extend as configuration; never inferred.
GROCERY_BRANDS = {'stop shop', 'shoprite', 'big y', 'price chopper', 'market 32', 'hannaford', 'kroger', 'weis markets',
    'whole foods market', 'trader joes', 'aldi', 'lidl', 'wegmans', 'publix', 'giant', 'giant food', 'safeway',
    'food lion', 'harris teeter', 'acme markets', 'market basket', 'stew leonards', 'fairway market',
    'key food', 'c town', 'foodtown', 'tops', 'tops friendly markets', 'save a lot', 'sprouts farmers market',
    'the fresh market', 'mother earths storehouse', 'adams fairacre farms', 'patel brothers', 'h mart',
    'hy vee', 'meijer', 'winn dixie', 'fresh thyme market', 'grocery outlet', 'shaws', 'star market',
    'balduccis', 'hmart'}
BIG_BOX_BRANDS = {'walmart', 'target', 'costco', 'costco wholesale', 'bjs wholesale club', 'sams club', 'the home depot',
    'home depot', 'lowes', 'kohls', 'marshalls', 'tj maxx', 'homegoods', 'ross dress for less', 'burlington',
    'best buy', 'dicks sporting goods', 'ulta beauty', 'petsmart', 'petco', 'staples', 'cvs pharmacy', 'cvs',
    'walgreens', 'rite aid', 'dollar tree', 'dollar general', 'family dollar', 'five below',
    'ocean state job lot', 'tractor supply', 'tractor supply co', 'planet fitness', 'ollies bargain outlet',
    'big lots', 'barnes noble', 'old navy', 'michaels', 'hobby lobby', 'at home', 'bed bath beyond',
    'regal', 'amc', 'bow tie cinemas', 'kinney drugs', 'harbor freight tools', 'aldi', 'lidl'}
ANCHOR_BRANDS = GROCERY_BRANDS | BIG_BOX_BRANDS


def normalize_brand(name):
    """Casefold, strip accents/punctuation and legal suffixes: "DICK'S Sporting Goods" -> "dicks sporting goods"."""
    if not name:
        return None
    text = unicodedata.normalize('NFKD', str(name)).encode('ascii', 'ignore').decode().casefold()
    text = text.replace('&', ' ').replace("'", '').replace('’', '')
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    text = re.sub(r'\b(inc|llc|co|corp|corporation|company|stores?)\b$', '', text.strip()).strip()
    return re.sub(r'\s+', ' ', text) or None


def brand_in(name, brands):
    """Exact or prefix match on whole words: "lowes home improvement" matches "lowes"."""
    b = normalize_brand(name)
    return bool(b) and (b in brands or any(b.startswith(x + ' ') for x in brands))


def _distance(center, record):
    return haversine_miles(center[0], center[1], record['lat'], record['lon'])


def is_present(r):
    return r.get('operating_status') != 'permanently_closed'


def countable(r):
    c = r.get('confidence')
    return is_present(r) and c is not None and c >= MIN_COUNT_CONFIDENCE


def is_key(r):
    return r.get('basic_category') in KEY_CATEGORIES or brand_in(r.get('brand'), ANCHOR_BRANDS)


def _place(center, r):
    return {'id': r['id'], 'name': r.get('name'), 'brand': r.get('brand'), 'category': r.get('basic_category'),
        'group': CATEGORY_GROUP.get(r.get('basic_category'), 'Other'),
        'distance_mi': round(_distance(center, r), 2), 'status': r.get('operating_status'),
        'confidence': None if r.get('confidence') is None else round(r['confidence'], 2),
        'lat': r['lat'], 'lon': r['lon'], 'grocery': brand_in(r.get('brand'), GROCERY_BRANDS)}


def landscape(records, center, radii=(1, 3)):
    """MET-15/16 for one release."""
    counts = {f'{r}mi': {} for r in radii}
    totals = {f'{r}mi': 0 for r in radii}
    anchors, closed_nearby = {}, 0
    for rec in records:
        d = _distance(center, rec)
        if not countable(rec):
            if rec.get('operating_status') == 'permanently_closed' and d <= 1:
                closed_nearby += 1
            continue
        group = CATEGORY_GROUP.get(rec.get('basic_category'))
        for r in radii:
            if d <= r and group:
                counts[f'{r}mi'][group] = counts[f'{r}mi'].get(group, 0) + 1
                totals[f'{r}mi'] += 1
        # Anchors shown to users must be named chains; unbranded "plazas" or clinics
        # filed under key categories stay countable but are not listed as anchors.
        if rec.get('brand') and is_key(rec) and d <= max(radii):
            key = normalize_brand(rec.get('brand')) or rec['id']
            place = _place(center, rec)
            if key not in anchors or place['distance_mi'] < anchors[key]['distance_mi']:
                anchors[key] = place
    anchor_list = sorted(anchors.values(), key=lambda p: p['distance_mi'])
    grocery = [a for a in anchor_list if a['grocery']]
    ordered = {k: dict(sorted(v.items(), key=lambda kv: -kv[1])) for k, v in counts.items()}
    return {'counts': ordered, 'retail_and_services_total': totals, 'anchors': anchor_list[:25],
        'nearest_supermarket': grocery[0] if grocery else None, 'closed_within_1mi': closed_nearby,
        'records': len(records)}


def _severity_down(level):
    return {'High': 'Watch', 'Watch': 'FYI', 'FYI': 'FYI'}[level]


def changes(prior, current, center, tenant_brands=()):
    """Possible closures (SIG-09) and new key businesses (SIG-10) between two releases."""
    tenants = {normalize_brand(t) for t in tenant_brands if normalize_brand(t)}
    now = {r['id']: r for r in current}
    before = {r['id']: r for r in prior}
    closures, openings = [], []
    for pid, old in before.items():
        conf = old.get('confidence')
        if old.get('operating_status') == 'permanently_closed' or conf is None or conf < CLOSURE_PRIOR_CONFIDENCE:
            continue
        branded, key = bool(old.get('brand')), is_key(old)
        retail = old.get('basic_category') in CATEGORY_GROUP
        d = _distance(center, old)
        # Retail-relevant only: branded government offices or lockers are not co-tenancy.
        if not (key or (branded and retail)) or d > (3 if key else 1):
            continue
        new = now.get(pid)
        if new is not None and new.get('operating_status') != 'permanently_closed':
            continue  # still present (null -> open transitions are enrichment, ignored)
        explicit = new is not None
        brand = normalize_brand(old.get('brand'))
        tenant_match = bool(brand) and brand_in(brand, tenants) if tenants else False
        if tenant_match and d <= 0.093:  # ~150 m: likely the tenant's own store
            level = 'High'
        elif d <= 0.5:
            level = 'Watch'
        else:
            level = 'FYI'
        if not explicit:
            level = _severity_down(level)
        closures.append({**_place(center, old), 'severity': level,
            'evidence': 'marked permanently closed' if explicit else 'no longer in the dataset',
            'tenant_match': tenant_match})
    for pid, new in now.items():
        if pid in before or not is_present(new) or not is_key(new):
            continue
        if new.get('confidence') is None or new['confidence'] < OPENING_CONFIDENCE or _distance(center, new) > 3:
            continue
        openings.append({**_place(center, new), 'severity': 'FYI'})
    order = {'High': 0, 'Watch': 1, 'FYI': 2}
    closures.sort(key=lambda c: (order[c['severity']], c['distance_mi']))
    openings.sort(key=lambda c: c['distance_mi'])
    return {'closures': closures, 'openings': openings}


def broad_change(cohort):
    """docs/04 §5.3 guard. ``cohort`` is a list of (prior 1-mile count, current 1-mile count) per location."""
    usable = [(a, b) for a, b in cohort if a]
    if len(usable) < 5:
        return None
    up = sum(1 for a, b in usable if (b - a) / a > 0.15)
    down = sum(1 for a, b in usable if (b - a) / a < -0.15)
    return max(up, down) / len(usable) >= 0.30
