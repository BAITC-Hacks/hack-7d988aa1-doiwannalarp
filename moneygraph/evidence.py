"""Short, cautious Russian evidence statements for a single node."""

import math

from moneygraph.schemas import EVIDENCE_MAX

BANNED = ("виновен", "виновна", "преступник", "является организатором",
          "установлено", "доказано", "остаток")


def _get(row, key, default=0):
    value = row.get(key, default)
    return default if value is None else value


def _number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _kzt(value):
    value = _number(value)
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}".replace(".", ",") + " млн KZT"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.0f} тыс. KZT"
    return f"{value:.0f} KZT"


def build_evidence(row, thresholds=None) -> str:
    """Return a bounded, non-accusatory evidence statement."""
    role = _get(row, "role", "peripheral")
    in_deg = int(_number(_get(row, "in_deg")))
    out_deg = int(_number(_get(row, "out_deg")))
    seed_payers = int(_number(_get(row, "seed_payers")))
    in_sum = _kzt(_get(row, "in_sum"))
    out_sum = _kzt(_get(row, "out_sum"))
    ratio = _number(_get(row, "pass_ratio"))
    pass_pct = round(100 * ratio)
    fast_pct = round(100 * _number(_get(row, "fast_through_share")))
    censored = bool(_get(row, "censored", False))

    isolated_seed = bool(_get(row, "is_seed", False)) and in_deg == out_deg == 0
    if isolated_seed:
        result = "Seed без наблюдаемых переводов >=5 000 KZT в июле."
    elif role == "coordinator":
        result = (f"Кандидат в координаторы: сходятся средства {int(_number(_get(row, 'seed_reach')))} seed "
                  f"через {int(_number(_get(row, 'feeder_branches')))} ветки; получено {in_sum}.")
    elif role == "consolidator":
        result = (f"Признаки консолидации: {in_deg} плательщиков ({seed_payers} seed), получено {in_sum}; "
                  f"дальше ушло {pass_pct}%; до {int(_number(_get(row, 'max_payers_3d')))} платеж. за 3 дня.")
    elif role == "distributor":
        result = f"Признаки веерного распределения: {out_deg} получателей, отправлено {out_sum}."
    elif role == "transit":
        result = f"Признаки транзита: пропущено {pass_pct}% полученного ({in_sum}); {fast_pct}% ушло в течение 2 дней."
    elif role == "terminal":
        result = ("Кандидат в конечные получатели (в наблюдаемом окне): "
                  f"получено {in_sum} от {in_deg} плательщиков, дальше ушло {pass_pct}%.")
    elif role == "boundary":
        result = ("Граница выгрузки (4-е колено): исходящие не выгружались, роль не определима; "
                  f"получено {in_sum} от {in_deg}.")
    else:
        turnover = _kzt(_number(_get(row, "in_sum")) + _number(_get(row, "out_sum")))
        result = f"Выраженных признаков роли нет: {in_deg} вх. / {out_deg} исх., оборот {turnover}."

    if censored:
        result = result.replace(f"дальше ушло {pass_pct}%", "исходящие не наблюдаются (граница выгрузки)")
    if bool(_get(row, "inflow_incomplete", False)) and not isolated_seed:
        suffix = "; есть входящие вне выборки"
        if len(result) + len(suffix) <= EVIDENCE_MAX:
            result += suffix
    if len(result) > EVIDENCE_MAX:
        result = result[:EVIDENCE_MAX - 1] + "…"
    if any(word in result.lower() for word in BANNED):
        raise ValueError("Evidence contains a prohibited term")
    return result
