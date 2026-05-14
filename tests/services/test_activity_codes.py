from app.backend.models import Area
from app.backend.routers.activities import _activity_code_base, _code_part


def test_code_part_normalizes_swedish_label_to_safe_code():
    assert _code_part("GG Påfyllning / kväll") == "GG_PAFYLLNING_KVALL"


def test_activity_code_base_prefixes_area_when_label_lacks_it():
    area = Area(code="GG", name="Granngården")

    assert _activity_code_base("Påfyllning", area) == "GG_PAFYLLNING"


def test_activity_code_base_does_not_double_prefix_area():
    area = Area(code="GG", name="Granngården")

    assert _activity_code_base("GG Påfyllning", area) == "GG_PAFYLLNING"
