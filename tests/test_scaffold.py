import pytest
import yaml

from carina import scaffold


def test_scaffold_creates_valid_product(tmp_root):
    pdir = scaffold.create_data_product("energy-nl", name="Energy (NL)",
                                        source_table="00000TEST")
    praw = yaml.safe_load((pdir / "product.yaml").read_text())
    assert praw["id"] == "energy-nl"
    assert praw["status"] == "draft"
    assert praw["created"]  # the golden-path clock
    craw = yaml.safe_load((pdir / "contracts" / "energy-nl-source.yaml").read_text())
    assert craw["silver"]["table"] == "silver_energy_nl"
    assert craw["source"]["table"] == "00000TEST"
    assert (pdir / "transforms" / "10_gold.sql").exists()
    assert yaml.safe_load((pdir / "semantic" / "metrics.yaml").read_text())["metrics"]


def test_scaffold_rejects_bad_ids(tmp_root):
    with pytest.raises(ValueError):
        scaffold.create_data_product("Bad_Name")


def test_scaffold_refuses_overwrite(tmp_root):
    scaffold.create_data_product("dupe")
    with pytest.raises(FileExistsError):
        scaffold.create_data_product("dupe")


def test_minutes_since_created():
    assert scaffold.minutes_since_created({}) is None
    m = scaffold.minutes_since_created({"created": "2020-01-01T00:00:00+00:00"})
    assert m > 0
