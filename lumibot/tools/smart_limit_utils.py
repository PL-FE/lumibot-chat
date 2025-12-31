from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from typing import List, Optional


def infer_tick_size(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
    if bid is None or ask is None:
        return None
    candidates = [0.01, 0.05, 0.1]
    for tick in candidates:
        if _is_multiple_of_tick(bid, tick) and _is_multiple_of_tick(ask, tick):
            return tick
    return 0.01


def _is_multiple_of_tick(value: float, tick: float) -> bool:
    try:
        scaled = Decimal(str(value)) / Decimal(str(tick))
    except (InvalidOperation, ZeroDivisionError):
        return False
    return abs(scaled - scaled.to_integral_value()) <= Decimal("0.000001")


def round_to_tick(price: float, tick_size: Optional[float], side: Optional[str] = None) -> float:
    if tick_size is None or tick_size <= 0:
        return price
    tick = Decimal(str(tick_size))
    value = Decimal(str(price))
    if side == "buy":
        rounded = (value / tick).to_integral_value(rounding=ROUND_CEILING) * tick
    elif side == "sell":
        rounded = (value / tick).to_integral_value(rounding=ROUND_FLOOR) * tick
    else:
        rounded = (value / tick).to_integral_value(rounding=ROUND_HALF_UP) * tick
    return float(rounded)


def compute_mid(bid: float, ask: float) -> float:
    return (bid + ask) / 2.0


def compute_final_price(bid: float, ask: float, side: str, final_price_pct: float) -> float:
    spread = ask - bid
    if side == "buy":
        return bid + spread * final_price_pct
    return ask - spread * final_price_pct


def build_price_ladder(mid: float, final_price: float, step_count: int) -> List[float]:
    if step_count <= 1:
        return [final_price]
    ladder = []
    step_delta = (final_price - mid) / float(step_count - 1)
    for idx in range(step_count):
        ladder.append(mid + step_delta * idx)
    return ladder


def expected_fill_price(mid: float, slippage: float, side: str) -> float:
    if side == "buy":
        return mid + slippage
    return mid - slippage
