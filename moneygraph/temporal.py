import datetime as dt

import pandas as pd


def add_temporal(features_df: pd.DataFrame, tx_df: pd.DataFrame) -> pd.DataFrame:
    tx = tx_df.copy()
    tx["date"] = pd.to_datetime(tx["date"]).dt.normalize()
    max_date = tx["date"].max()

    inflow = tx.groupby(["dst", "date"])["src"].agg(lambda s: frozenset(s)).reset_index()
    inflow_by_node: dict[int, dict] = {}
    for row in inflow.itertuples(index=False):
        inflow_by_node.setdefault(row.dst, {})[row.date] = row.src

    outflow_sum = tx.groupby(["src", "date"])["sum_kzt"].sum().reset_index()
    outflow_by_node: dict[int, dict] = {}
    for row in outflow_sum.itertuples(index=False):
        outflow_by_node.setdefault(row.src, {})[row.date] = row.sum_kzt

    first_last = tx.groupby(tx["src"]).apply(lambda g: (g["date"].min(), g["date"].max()))
    in_first_last = tx.groupby(tx["dst"]).apply(lambda g: (g["date"].min(), g["date"].max()))

    results = []
    for gid in features_df["gid"]:
        day_payers = inflow_by_node.get(gid, {})
        if day_payers:
            same_day_counts = {d: len(p) for d, p in day_payers.items()}
            max_payers_same_day = max(same_day_counts.values())
            max_payers_date = max(same_day_counts, key=lambda d: (same_day_counts[d], -d.toordinal()))
            max_payers_date_str = max_payers_date.strftime("%Y-%m-%d")

            dates_sorted = sorted(day_payers)
            best_3d = 0
            for start in dates_sorted:
                window_end = start + dt.timedelta(days=2)
                payers = set()
                for d in dates_sorted:
                    if start <= d <= window_end:
                        payers |= day_payers[d]
                best_3d = max(best_3d, len(payers))
            max_payers_3d = best_3d
        else:
            max_payers_same_day = 0
            max_payers_date_str = ""
            max_payers_3d = 0

        out_days = outflow_by_node.get(gid, {})
        total_out = sum(out_days.values())
        if total_out > 0 and day_payers:
            in_dates = sorted(day_payers)
            fast_sum = 0.0
            for d_out, amount in out_days.items():
                if any(0 <= (d_out - d_in).days <= 2 for d_in in in_dates):
                    fast_sum += amount
            fast_through_share = fast_sum / total_out
        else:
            fast_through_share = 0.0

        in_days = tx[tx["dst"] == gid]
        total_in = in_days["sum_kzt"].sum()
        if total_in > 0:
            late_cutoff = max_date - dt.timedelta(days=1)
            late_sum = in_days.loc[in_days["date"] >= late_cutoff, "sum_kzt"].sum()
            late_inflow_share = late_sum / total_in
        else:
            late_inflow_share = 0.0

        fl = first_last.get(gid)
        ifl = in_first_last.get(gid)
        dates = [d for pair in (fl, ifl) if pair for d in pair]
        first_date = min(dates).strftime("%Y-%m-%d") if dates else ""
        last_date = max(dates).strftime("%Y-%m-%d") if dates else ""

        results.append({
            "gid": gid,
            "max_payers_same_day": max_payers_same_day,
            "max_payers_date": max_payers_date_str,
            "max_payers_3d": max_payers_3d,
            "fast_through_share": round(float(fast_through_share), 4),
            "late_inflow_share": round(float(late_inflow_share), 4),
            "first_date": first_date,
            "last_date": last_date,
        })

    temporal_df = pd.DataFrame(results)
    out = features_df.drop(columns=list(temporal_df.columns[1:])).merge(temporal_df, on="gid", how="left")
    return out[features_df.columns]
