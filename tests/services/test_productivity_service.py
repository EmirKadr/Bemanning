from pathlib import Path

from app.backend.productivity_service import build_productivity_report


def write(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def test_productivity_report_groups_pick_trans_and_pallet_logs(tmp_path):
    write(
        tmp_path / "v_ask_pick_log_full-20260518075529.csv",
        """
Zon\tPlockat\tAnvändare\tÄndrad\tVikt\tBolag
A\t3\tUSER1\t2026-05-18 08:10:00\t1,5\tGG
B\t4\tUSER1\t2026-05-18 08:40:00\t2,5\tGG
S\t5\tUSER1\t2026-05-18 09:05:00\t3,0\tGG
R\t7\tAUTO1\t2026-05-18 10:15:00\t1,0\tMG
Q\t2\tECOM1\t2026-05-18 11:00:00\t1,0\tMG
O\t1\tMGUSER\t2026-05-18 12:00:00\t1,0\tMG
""",
    )
    write(
        tmp_path / "v_ask_trans_log-20260518075534.csv",
        """
Till\tAntal\tAnvändare\tTimestamp\tBolag
AS100\t9\tDEC1\t2026-05-18 10:30:00\tGG
LC100\t4\tDEC1\t2026-05-18 10:45:00\tGG
AS200\t6\tDEC2\t2026-05-18 11:00:00\tMG
""",
    )
    write(
        tmp_path / "v_ask_palletloading_log-20260518075605.csv",
        """
Typ\tAnvändare\tÄndrad\tBolag
220\tPACK1\t2026-05-18 13:00:00\tGG
220\tPACK2\t2026-05-18 14:00:00\tMG
200\tPACK2\t2026-05-18 15:00:00\tMG
""",
    )
    write(
        tmp_path / "v_ask_kpi_target-20260518080915.csv",
        """
Bolag\tLager\tFlödesnamn\tProcessnamn\tBeskrivning\tRader\tKollin\tPallar
GG\t404\tOUTBOUND\tManual_Pick\tManuellt plock\t10\t0\t0
GG\t404\tOUTBOUND\tBulky_Pick\tSkrymmande Plock\t5\t0\t0
GG\t404\tOUTBOUND\tAutostore\tAutostore\t20\t0\t0
GG\t404\tINBOUND\tDecanting\tDekantering\t9\t0\t0
GG\t404\tOUTBOUND\tEcom_pack\tE - Handel pack\t0\t0\t2
MG\tJKP\tOUTBOUND\tManual_Pick\tManuellt plock\t10\t0\t0
MG\tJKP\tOUTBOUND\tBulky_Pick\tSkrymmande Plock\t4\t0\t0
MG\tJKP\tOUTBOUND\tE_Commerce\tE - Handel\t8\t0\t0
MG\tJKP\tINBOUND\tDecanting\tDekantering\t6\t0\t0
MG\tJKP\tOUTBOUND\tEcom_pack\tE - Handel pack\t0\t0\t2
""",
    )

    report = build_productivity_report(tmp_path)
    sections = {
        section["id"]: section
        for group in report["groups"]
        for section in group["sections"]
    }

    gg_pick = sections["gg_pick_ab"]
    assert gg_pick["total_rows"] == 2
    assert gg_pick["rows"][0]["user"] == "USER1"
    assert gg_pick["rows"][0]["hourly"] == {"8": 2}
    assert gg_pick["rows"][0]["worked_hours"] == 1
    assert gg_pick["rows"][0]["rows_per_hour"] == 2
    assert gg_pick["rows"][0]["productivity_pct"] == 0.2
    assert gg_pick["rows"][0]["total_kolli"] == 12

    assert sections["gg_decanting"]["rows"][0]["user"] == "DEC1"
    assert sections["gg_decanting"]["rows"][0]["total_rows"] == 1
    assert sections["gg_decanting"]["rows"][0]["total_kolli"] == 13

    assert sections["gg_ecom_pack"]["rows"][0]["user"] == "PACK1"
    assert sections["gg_ecom_pack"]["rows"][0]["target_per_hour"] == 2
    assert sections["mg_ecom_pack"]["rows"][0]["user"] == "PACK2"
    assert sections["mg_ecom_pick"]["rows"][0]["user"] == "ECOM1"
