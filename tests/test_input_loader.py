import pytest
from banyan_screen.input_loader import load_seed, parse_money, _canon_columns


def test_parse_money_variants():
    assert parse_money("$5M") == 5_000_000
    assert parse_money("5,000,000") == 5_000_000
    assert parse_money("3.4m") == 3_400_000
    assert parse_money("2bn") == 2_000_000_000
    assert parse_money("") is None
    assert parse_money(None) is None


def test_canon_columns_maps_aliases():
    canon = _canon_columns(["Company Name", "Website", "Industry", "Annual Revenue", "Investors"])
    assert canon["name"] == "Company Name"
    assert canon["domain"] == "Website"
    assert canon["revenue"] == "Annual Revenue"
    assert canon["ownership"] == "Investors"


def test_load_seed_maps_firmographics(tmp_path):
    p = tmp_path / "seed.csv"
    p.write_text("Company,Website,Country,Industry,Revenue,Employees,Ownership\n"
                 "Acme Health,acme.example,UK,Healthcare SaaS,$8M,45,Founder-owned\n"
                 'GrowthCo,growth.example,US,AI,$250M,900,Series C VC\n')
    recs = load_seed(str(p))
    assert len(recs) == 2
    a = recs[0]
    assert a["name"] == "Acme Health" and a["domain"] == "acme.example"
    assert a["revenue_est_usd"]["value"] == 8_000_000 and a["revenue_est_usd"]["confidence"] >= 0.7
    assert a["revenue_est_usd"]["below_2M"] is False and a["revenue_est_usd"]["above_100M"] is False
    assert a["ownership_fit"]["score"] >= 0.8       # founder-owned
    assert "employees=45" in a["notes"]
    g = recs[1]
    assert g["revenue_est_usd"]["above_100M"] is True   # $250M
    assert g["ownership_fit"]["score"] <= 0.4           # VC
    assert "recurring_revenue" in g["_needs_enrichment"]


def test_missing_name_column_raises(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("Foo,Bar\n1,2\n")
    with pytest.raises(ValueError):
        load_seed(str(p))


def test_seed_records_score_through_pipeline(tmp_path):
    from banyan_screen.config import RubricConfig
    from banyan_screen.ingest import company_from_record, banyan_scores
    from banyan_screen.rubric_engine import score_company
    p = tmp_path / "seed.csv"
    p.write_text("Company,Revenue,Ownership\nAcme,$8M,Founder-owned\n")
    recs = load_seed(str(p))
    cfg = RubricConfig.from_yaml("config.yaml")
    r = score_company(company_from_record(recs[0]), banyan_scores(recs[0]), cfg)
    assert r.tier is not None
