

# ---- R2 item 6: closure de-noising, stage 1 --------------------------------------------

def _rec(pid, name, cat, conf=0.95, lat=41.1, lon=-73.4, brand=None, status=None):
    return {'id': pid, 'name': name, 'brand': brand, 'basic_category': cat, 'confidence': conf,
        'operating_status': status, 'lat': lat, 'lon': lon}


def test_noise_categories_and_names_never_become_closures():
    from apps.area import businesses as b
    center = (41.1, -73.4)
    prior = [_rec('a', 'Jeff Gomes at Rate - NMLS #2611', 'financial_service', brand='Rate'),
        _rec('b', 'PNC Bank', 'bank_or_credit_union', brand='PNC'),
        _rec('c', 'Minute Clinic', 'outpatient_care_facility', brand='CVS'),
        _rec('d', 'Shell ATM', 'shopping', brand='Shell')]
    assert b.changes(prior, [], center)['closures'] == []


def test_same_place_under_new_id_or_parent_store_is_not_a_closure():
    from apps.area import businesses as b
    center = (41.1, -73.4)
    prior = [_rec('old', 'Dollar Tree', 'discount_store', brand='Dollar Tree'),
        _rec('dept', 'Stop & Shop Pharmacy', 'pharmacy_and_drug_store', brand='Stop & Shop', lat=41.1003)]
    current = [_rec('new', 'Dollar Tree', 'discount_store', brand='Dollar Tree', lat=41.1005),
        _rec('store', 'Stop & Shop', 'food_and_beverage_store', brand='Stop & Shop', lat=41.1004)]
    assert b.changes(prior, current, center)['closures'] == []


def test_disappearance_bars_differ_for_anchors_and_others():
    from apps.area import businesses as b
    center = (41.1, -73.4)
    prior = [_rec('r', 'Regal Moorestown Mall', 'movie_theater', conf=0.8, brand='Regal'),
        _rec('s', 'Small Boutique', 'fashion_and_apparel_store', conf=0.8, brand='Boutique Co')]
    closures = b.changes(prior, [], center)['closures']
    assert [c['id'] for c in closures] == ['r']
    prior[1]['confidence'] = 0.95
    assert {c['id'] for c in b.changes(prior, [], center)['closures']} == {'r', 's'}


def test_brand_matching_handles_punctuation_and_rejects_longer_brands():
    from apps.area.businesses import brand_in, ANCHOR_BRANDS, GROCERY_BRANDS
    assert brand_in('T.J.Maxx', ANCHOR_BRANDS) and brand_in("Lowe's Home Improvement", ANCHOR_BRANDS)
    assert brand_in('The Home Depot', ANCHOR_BRANDS) and brand_in('CVS Pharmacy #1234', ANCHOR_BRANDS)
    assert brand_in('Giant', GROCERY_BRANDS) and not brand_in('Giant Eagle', GROCERY_BRANDS)
