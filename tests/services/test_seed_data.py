from app.backend.seed import ACTIVITIES, AREAS


def test_seed_contains_ehandel_area_and_default_activities():
    areas_by_code = {area["code"]: area for area in AREAS}
    activity_codes = {activity["code"] for activity in ACTIVITIES}

    assert areas_by_code["EH"]["name"] == "E-Handel"
    assert {"EH_PLOCK", "EH_PACK", "EH_STOD", "EH_VAS"} <= activity_codes
