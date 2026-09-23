import pandas as pd


def gaps(enriched_df: pd.DataFrame) -> pd.DataFrame:
    mask = enriched_df["censored"] | enriched_df["inflow_incomplete"]
    subset = enriched_df.loc[mask].copy()

    def reason(row):
        parts = []
        if row["censored"]:
            parts.append("boundary")
        if row["inflow_incomplete"]:
            parts.append("inflow_incomplete")
        return "+".join(parts)

    def request(row):
        parts = []
        if row["censored"]:
            parts.append("исходящие переводы за пределами 4-го колена")
        if row["inflow_incomplete"]:
            parts.append("входящие переводы из-за пределов выборки")
        return "Запросить " + "; ".join(parts) + "."

    records = subset.to_dict("records")
    subset["reason"] = [reason(row) for row in records]
    subset["request"] = [request(row) for row in records]
    subset = subset.sort_values(["seed_flow_in", "gid"], ascending=[False, True])
    return subset[["gid", "reason", "seed_flow_in", "in_sum", "in_deg", "request"]].reset_index(drop=True)


def run(G, enriched_df, raw=None) -> pd.DataFrame:
    return gaps(enriched_df)
