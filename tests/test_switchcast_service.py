"""Tests for SWITCHcast / Kaltura link extraction and download service."""

from app.services.switchcast_service import extract_switchcast_ids

def test_extract_switchcast_ids():
    sample_url = (
        "https://api.cast.switch.ch/p/106/sp/10600/playManifest/entryId/0_f7vr9lic/protocol/https/"
        "format/applehttp/flavorIds/0_yn9reccu,0_r2yfqz6i,0_o6bpo0bf/ks/djJ8MTA2fCyqYrf5kjCb1_77r_X/a.m3u8"
    )
    entry_id, flavor_id, ks = extract_switchcast_ids(sample_url)
    assert entry_id == "0_f7vr9lic"
    assert flavor_id == "0_yn9reccu"
    assert ks == "djJ8MTA2fCyqYrf5kjCb1_77r_X"

def test_extract_switchcast_ids_missing():
    entry_id, flavor_id, ks = extract_switchcast_ids("https://example.com/invalid")
    assert entry_id is None
    assert flavor_id is None
    assert ks is None
