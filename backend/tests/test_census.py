from email.message import Message
import hashlib
import io
import json
from pathlib import Path
from urllib.error import HTTPError,URLError
import pytest
from apps.locations.census import fetch_census,parse_census,normalized_address,GeocoderError,MAX_BYTES

FIXTURES=Path('tests/fixtures/real/census_geocoder')

def raw(name='norwalk'):
    return (FIXTURES/(name+'.json')).read_bytes()


def test_real_reference_match_and_mixed_connecticut_vintages():
    result=parse_census(raw())
    assert result.status=='matched' and len(result.candidates)==1
    item=result.candidates[0]
    assert item['lat']==pytest.approx(41.12661107292)
    assert item['lon']==pytest.approx(-73.388299045728)
    assert item['method']=='census_interpolated'
    assert item['match_quality']=='not_reported'
    assert item['geographies']['block_group']['geoid']=='091900435001'
    assert item['geographies']['county']['geoid']=='09190'
    assert item['geographies']['block']['geoid']=='090010435001001'
    assert item['geographies']['block']['geography_vintage']=='Census2020'
    assert item['geographies']['county']['geography_vintage']=='Current_Current'


def test_real_ambiguity_and_no_match_are_not_successful_pin_selection():
    assert parse_census(raw('mount_kisco')).status=='ambiguous'
    assert len(parse_census(raw('mount_kisco')).candidates)==2
    result=parse_census(raw('kingston'))
    assert result.status=='no_match' and result.candidates==()


@pytest.mark.parametrize('value',[True,'41',float('nan'),float('inf'),91,-91,None])
def test_bad_coordinates_fail_closed(value):
    payload=json.loads(raw());payload['result']['addressMatches'][0]['coordinates']['y']=value
    with pytest.raises(GeocoderError,match='SCHEMA_ERROR'):
        parse_census(json.dumps(payload).encode())


@pytest.mark.parametrize('value',['09190043500','0919004350010',True,91900435001,'٠٩١٩٠٠٤٣٥٠٠١'])
def test_geoid_validation_preserves_leading_zeros_and_exact_ascii_lengths(value):
    payload=json.loads(raw());payload['result']['addressMatches'][0]['geographies']['Census Block Groups'][0]['GEOID']=value
    with pytest.raises(GeocoderError,match='SCHEMA_ERROR'):
        parse_census(json.dumps(payload).encode())


@pytest.mark.parametrize('payload',[b'not json',b'null',b'[]',b'{"result":{}}',b'x'*(MAX_BYTES+1)])
def test_schema_failure_is_sanitized(payload):
    with pytest.raises(GeocoderError,match='SCHEMA_ERROR'):
        parse_census(payload)


def test_recorded_bytes_retain_verified_hashes():
    manifest=json.loads((FIXTURES/'manifest.json').read_text())
    for entry in manifest['captures']:
        content=(FIXTURES/entry['fixture']).read_bytes()
        assert hashlib.sha256(content).hexdigest()==entry['sha256']
        assert len(content)==entry['bytes']
        assert len(parse_census(content).candidates)==entry['matches']


class Opener:
    def __init__(self,body=None,error=None,content_type='application/json'):
        self.body=body if body is not None else raw();self.error=error;self.content_type=content_type;self.calls=[]
    def open(self,request,timeout):
        self.calls.append((request,timeout))
        if self.error:raise self.error
        stream=io.BytesIO(self.body);stream.status=200;stream.headers=Message();stream.headers['Content-Type']=self.content_type
        return stream


def test_transport_capture_and_fixed_endpoint():
    opener=Opener();capture=fetch_census('444 Westport Avenue, Norwalk, CT 06851',opener=opener)
    assert capture.raw==raw() and capture.sha256==hashlib.sha256(raw()).hexdigest()
    assert capture.retrieved_at.tzinfo
    request,timeout=opener.calls[0]
    assert request.full_url.startswith('https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?')
    assert timeout==10 and request.get_header('User-agent').startswith('ParagonRadar/')


@pytest.mark.parametrize('error,code',[(TimeoutError('secret-address'),'TIMEOUT'),(URLError('secret-address'),'SOURCE_ERROR'),(HTTPError('https://private-address',503,'secret-address',None,None),'HTTP_ERROR')])
def test_transport_errors_never_expose_addresses(error,code):
    with pytest.raises(GeocoderError) as exc:
        fetch_census('Private address',opener=Opener(error=error))
    assert str(exc.value)==code and 'address' not in str(exc.value)
    assert exc.value.__suppress_context__


def test_response_limits_content_type_and_request_echo():
    for opener in [Opener(body=b'x'*(MAX_BYTES+1)),Opener(content_type='text/html')]:
        with pytest.raises(GeocoderError,match='SCHEMA_ERROR'):
            fetch_census('Private address',opener=opener)
    with pytest.raises(GeocoderError,match='SCHEMA_ERROR'):
        fetch_census('A different address',opener=Opener())


@pytest.mark.parametrize('value',['', 'x'*501,'line\nbreak',None,True])
def test_bad_inputs_never_contact_provider(value):
    opener=Opener()
    with pytest.raises(ValueError):fetch_census(value,opener=opener)
    assert not opener.calls
