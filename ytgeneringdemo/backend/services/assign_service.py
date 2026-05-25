from datetime import datetime

from backend.db import get_connection
from backend.config_cache import get_config
from backend.models.assignment import AssignmentResult
from backend.utils.pallet import parse_pall


def _find_contiguous_start(locs: list[str], used_set: set[str],
                           pall_cap_map: dict[str, float],
                           needed_pall: float) -> int:
    """Return index of the first contiguous free run that fits needed_pall.
    Falls back to the start of the largest run if none fits."""
    best_start = 0
    best_cap = -1.0
    run_start = None
    run_cap = 0.0
    for i, loc in enumerate(locs):
        if loc not in used_set:
            if run_start is None:
                run_start = i
            run_cap += pall_cap_map.get(loc, 1.0)
            if run_cap >= needed_pall:
                return run_start
        else:
            if run_start is not None and run_cap > best_cap:
                best_start = run_start
                best_cap = run_cap
            run_start = None
            run_cap = 0.0
    if run_start is not None and run_cap > best_cap:
        best_start = run_start
    return best_start


def run(day: int, orderstop: str, lock: bool = False) -> AssignmentResult:
    warnings: list[str] = []

    config = get_config()

    zones = config.get("zones", [])
    agency_gap = config.get("agency_gap", 0)
    zone_conditions = " OR ".join("(location_seq BETWEEN ? AND ?)" for _ in zones)
    zone_params = [v for z in zones for v in (z["seq_min"], z["seq_max"])]

    conn = get_connection()

    def zone_index(location_seq):
        for i, z in enumerate(zones):
            if z["seq_min"] <= location_seq <= z["seq_max"]:
                return i
        return len(zones)

    locations = sorted(
        conn.execute(
            "SELECT location, location_seq, snake_seq AS seq, pall_capacity"
            " FROM Locations"
            f" WHERE location IS NOT NULL AND ({zone_conditions})",
            zone_params,
        ).fetchall(),
        key=lambda r: (zone_index(r["location_seq"]), r["seq"]),
    )

    agencies = conn.execute(
        "SELECT agency_num, agency_alias, assignment_order, start_seq, end_seq, cluster_group"
        " FROM Agency"
        " ORDER BY assignment_order, agency_num",
    ).fetchall()

    orderstop_filter = ("12:00:00",) if orderstop == "12:00" else ("06:00:00", "12:00:00")
    placeholders = ",".join("?" * len(orderstop_filter))

    locked_locations: set[str] = set()
    locked_customers: set[int] = set()
    locked_by_alias: dict[str, list[str]] = {}
    if lock:
        existing = conn.execute(
            "SELECT a.location, a.custom_num, ag.agency_alias"
            " FROM Assignments a"
            " JOIN Agency ag ON a.agency_num = ag.agency_num"
            " WHERE a.dispatch_day = ? AND a.agency_num IS NOT NULL",
            (day,),
        ).fetchall()
        for row in existing:
            locked_locations.add(row["location"])
            if row["custom_num"] is not None:
                locked_customers.add(int(row["custom_num"]))
            locked_by_alias.setdefault(row["agency_alias"], []).append(row["location"])

    prebook = conn.execute(
        f"SELECT p.agency_num, p.custom_num, p.assign_pall, a.agency_alias"
        f" FROM Prebook p"
        f" JOIN Custom c ON p.custom_num = c.custom_num"
        f" JOIN Agency a ON p.agency_num = a.agency_num"
        f" WHERE p.day_num = ? AND c.orderstop IN ({placeholders})",
        (day, *orderstop_filter),
    ).fetchall()

    prebook = [r for r in prebook if r["custom_num"] not in locked_customers]

    used = set(locked_locations)
    pall_cap = {r["location"]: r["pall_capacity"] or 1.0 for r in locations}

    gap_locs_by_alias: dict[str, set[str]] = {}
    if locked_locations and agency_gap > 0:
        locked_alias_map: dict[str, str] = {}
        for al, locs in locked_by_alias.items():
            for loc in locs:
                locked_alias_map[loc] = al
        gap_remaining = 0
        current_zone = None
        last_alias: str | None = None
        for r in locations:
            loc = r["location"]
            zi = zone_index(r["location_seq"])
            if zi != current_zone:
                gap_remaining = 0
                current_zone = zi
            if loc in locked_locations:
                gap_remaining = agency_gap
                last_alias = locked_alias_map.get(loc)
            elif gap_remaining > 0 and last_alias:
                used.add(loc)
                gap_locs_by_alias.setdefault(last_alias, set()).add(loc)
                gap_remaining -= 1

    prebook_by_alias: dict[str, list] = {}
    for row in prebook:
        prebook_by_alias.setdefault(row["agency_alias"], []).append(row)
    for customers in prebook_by_alias.values():
        customers.sort(key=lambda r: (max(parse_pall(r["assign_pall"]), 1.0), r["custom_num"]))

    alias_config: dict[str, dict] = {}
    for agency in agencies:
        alias = agency["agency_alias"]
        if alias not in alias_config:
            alias_config[alias] = {"start_seq": agency["start_seq"], "end_seq": agency["end_seq"]}

    def alias_location_list(alias: str, total_pall_override: float | None = None,
                            anchor_locs: set[str] | None = None) -> list[str]:
        """Return all locations in the agency's range (used or not), in correct order.
        For spanning agencies, picks the zone with a contiguous run that fits.
        Pass total_pall_override when placing a cluster (so the combined cluster
        size — not just one member's — drives the zone choice).
        Pass anchor_locs (e.g. existing locked positions) to lock the zone choice
        to wherever those anchors live, so the unit can never split across zones."""
        cfg = alias_config.get(alias, {})
        s, e = cfg.get("start_seq"), cfg.get("end_seq")
        if s is None or e is None:
            return [r["location"] for r in locations]

        lo, hi = min(s, e), max(s, e)
        reversed_dir = s > e

        touched = [i for i, z in enumerate(zones) if lo <= z["seq_max"] and hi >= z["seq_min"]]

        if len(touched) <= 1:
            candidates = [r for r in locations if lo <= r["location_seq"] <= hi]
            if reversed_dir:
                candidates.sort(key=lambda r: r["seq"], reverse=True)
            return [r["location"] for r in candidates]

        if anchor_locs:
            anchor_seqs = [r["location_seq"] for r in locations if r["location"] in anchor_locs]
            anchor_zones = {zone_index(seq) for seq in anchor_seqs}
            anchor_zones.discard(len(zones))
            if anchor_zones:
                touched = [zi for zi in touched if zi in anchor_zones]

        if total_pall_override is not None:
            total_pall = total_pall_override
        else:
            total_pall = sum(max(parse_pall(c["assign_pall"]), 1.0)
                             for c in prebook_by_alias.get(alias, [])
                             if c["custom_num"] not in locked_customers)

        def contiguous_start(candidates) -> int:
            """Return the index where the first fitting contiguous block starts, or -1."""
            cap = 0.0
            start = None
            for i, r in enumerate(candidates):
                if r["location"] not in used:
                    if start is None:
                        start = i
                    cap += pall_cap[r["location"]]
                    if cap >= total_pall:
                        return start
                else:
                    cap = 0.0
                    start = None
            return -1

        best: list[str] = []
        best_cap = 0.0
        for zi in touched:
            z = zones[zi]
            zone_lo, zone_hi = max(lo, z["seq_min"]), min(hi, z["seq_max"])
            candidates = [r for r in locations if zone_lo <= r["location_seq"] <= zone_hi]
            idx = contiguous_start(candidates)
            if idx >= 0:
                return [r["location"] for r in candidates[idx:]]
            avail_cap = sum(pall_cap[r["location"]] for r in candidates if r["location"] not in used)
            if avail_cap > best_cap:
                best_cap = avail_cap
                best = [r["location"] for r in candidates]
        return best

    seen: set[str] = set()
    ordered_aliases: list[str] = []
    for agency in agencies:
        alias = agency["agency_alias"]
        if alias not in seen:
            seen.add(alias)
            ordered_aliases.append(alias)

    alias_to_cluster: dict[str, str] = {}
    cluster_members: dict[str, list[str]] = {}
    for agency in agencies:
        cluster = agency["cluster_group"]
        if not cluster:
            continue
        alias = agency["agency_alias"]
        if alias in alias_to_cluster:
            continue
        alias_to_cluster[alias] = cluster
        cluster_members.setdefault(cluster, []).append(alias)

    units: list[list[str]] = []
    seen_clusters: set[str] = set()
    for alias in ordered_aliases:
        cluster = alias_to_cluster.get(alias)
        if cluster:
            if cluster in seen_clusters:
                continue
            seen_clusters.add(cluster)
            units.append(cluster_members[cluster])
        else:
            units.append([alias])

    new_assignments: list[dict] = []

    for unit_aliases in units:
        customers = []
        for alias in unit_aliases:
            customers.extend(c for c in prebook_by_alias.get(alias, [])
                             if c["custom_num"] not in locked_customers)
        if not customers:
            continue

        total_pall = sum(max(parse_pall(c["assign_pall"]), 1.0) for c in customers)

        unit_locked: set[str] = set()
        for alias in unit_aliases:
            unit_locked.update(locked_by_alias.get(alias, []))

        alias_locs = alias_location_list(unit_aliases[0], total_pall, unit_locked)

        own_gaps: set[str] = set()
        for alias in unit_aliases:
            own_gaps |= gap_locs_by_alias.get(alias, set())
        used -= own_gaps

        if unit_locked:
            loc_cursor = 0
            for i, loc in enumerate(alias_locs):
                if loc in unit_locked:
                    loc_cursor = i
                    break
        else:
            loc_cursor = _find_contiguous_start(
                alias_locs, used, pall_cap, total_pall)

        assigned_any = False

        for customer in customers:
            remaining = max(parse_pall(customer["assign_pall"]), 1.0)
            while remaining > 0:
                while loc_cursor < len(alias_locs) and alias_locs[loc_cursor] in unit_locked:
                    loc_cursor += 1
                if loc_cursor >= len(alias_locs) or alias_locs[loc_cursor] in used:
                    warnings.append(f"No locations left for customer {customer['custom_num']}")
                    break
                loc = alias_locs[loc_cursor]
                new_assignments.append({"location": loc, "agency_num": customer["agency_num"], "custom_num": customer["custom_num"]})
                used.add(loc)
                remaining -= pall_cap[loc]
                loc_cursor += 1
                assigned_any = True

        if assigned_any and not any(loc in unit_locked for loc in alias_locs[loc_cursor:]):
            gap_added = 0
            while gap_added < agency_gap and loc_cursor < len(alias_locs):
                loc = alias_locs[loc_cursor]
                if loc not in used:
                    used.add(loc)
                    gap_added += 1
                loc_cursor += 1

        used |= own_gaps

    try:
        before_rows = conn.execute(
            "SELECT location, status_id, agency_num, custom_num FROM Assignments WHERE dispatch_day = ?",
            (day,),
        ).fetchall()
        before = {r["location"]: (r["status_id"], r["agency_num"], r["custom_num"]) for r in before_rows}

        if locked_locations:
            lp = ",".join("?" * len(locked_locations))
            conn.execute(
                f"UPDATE Assignments SET agency_num = NULL, custom_num = NULL, status_id = 1"
                f" WHERE dispatch_day = ? AND location NOT IN ({lp})",
                (day, *locked_locations),
            )
        else:
            conn.execute(
                "UPDATE Assignments SET agency_num = NULL, custom_num = NULL, status_id = 1"
                " WHERE dispatch_day = ?",
                (day,),
            )
        conn.executemany(
            "UPDATE Assignments SET agency_num = ?, custom_num = ?, status_id = 2"
            " WHERE location = ? AND dispatch_day = ?",
            [(a["agency_num"], a["custom_num"], a["location"], day) for a in new_assignments],
        )

        after_rows = conn.execute(
            "SELECT location, agency_num, custom_num FROM Assignments WHERE dispatch_day = ?",
            (day,),
        ).fetchall()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        changelog_rows = []
        for r in after_rows:
            loc = r["location"]
            old = before.get(loc, (1, None, None))
            old_status, old_agency, old_custom = old
            if (r["agency_num"], r["custom_num"]) != (old_agency, old_custom):
                changelog_rows.append((loc, old_status, old_custom, old_agency, ts, day))
        if changelog_rows:
            conn.executemany(
                "INSERT INTO LocChangelog (location, status_id, custom_num, agency_num, timestamp, dispatch_day)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                changelog_rows,
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return AssignmentResult(success=True, summaries=[], warnings=warnings)
