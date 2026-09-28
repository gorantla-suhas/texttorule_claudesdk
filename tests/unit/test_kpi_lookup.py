"""KPI catalog loader tests."""

from pathlib import Path

from app.services.csv_loader import load_kpi_catalog
from app.tools.kpi_lookup import known_columns


def test_load_kpi_catalog(tmp_path: Path):
    csv = tmp_path / "kpi.csv"
    csv.write_text(
        "id,feature_name,group_id,group_name,kpi_type,description,data_type,time_window_value,search_text,aliases\n"
        "1,foo,10,G1,Normal KPI,desc,numeric,7d,foo search text,foo_alias\n",
        encoding="utf-8",
    )
    catalog = load_kpi_catalog(csv)
    assert len(catalog) == 1
    assert catalog[0].feature_name == "foo"
    assert catalog[0].group_name == "G1"


def test_known_columns():
    from app.tools.kpi_lookup import KpiMeta

    catalog = [
        KpiMeta(
            id="1", feature_name="a", group_id="1", group_name="G", kpi_type="",
            description="", kpi_type_name="", time_window_value="", activity="",
            network_scope="", direction_value="", data_type="", value_references="",
            value_type="", aliases="", search_text="",
        )
    ]
    assert known_columns(catalog) == {"a"}
