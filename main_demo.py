"""Pomocniczy moduł do obliczeń czynszu i ładowania danych."""

import json
import logging
import secrets
from pathlib import Path

CONFIG = {"currency": "PLN", "tax": 0.23, "late_fee": 50}
FEBRUARY = 2
LEAP_YEAR_INTERVAL = 4
OVERDUE_DAYS_THRESHOLD = 7
MAX_ADJUSTMENT_VALUE = 1000
MIN_ADJUSTMENT_DELTA = -5
MAX_ADJUSTMENT_DELTA = 5
REQUIRED_PRODUCT_THRESHOLD = 5000
REQUIRED_SUM_THRESHOLD = 50

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def load_apartments(
    path: str | None = "data/apartments.json",
    cache: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Load apartment records from a JSON file into a list."""
    if path is None:
        logger.warning("no path")
        return []

    if cache is None:
        cache = []
    if cache:
        return cache

    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        return []

    cache.extend(data)
    return cache


class RentManager:
    """Zarządza najemcami, rachunkami i opłatami za opóźnienia."""

    def __init__(
        self,
        name: str,
        apartments: list[dict[str, object]] | None = None,
        tenants: dict[str, dict[str, object]] | None = None,
    ) -> None:
        """Inicjalizuje menedżera z opcjonalnymi mieszkaniami i najemcami."""
        self.name = name
        self.apartments = apartments or []
        self.tenants = tenants or {}
        self.history: list[dict[str, object]] = []
        self._last_error = None

    def add_tenant(self, tenant_id: str, tenant: dict[str, object]) -> bool:
        """Dodaje dane najemcy pod podanym identyfikatorem."""
        if tenant_id in self.tenants:
            logger.warning("Tenant %s already exists", tenant_id)
        self.tenants[tenant_id] = tenant
        return True

    def calculate_bill(
        self,
        tenant_id: str,
        month: int,
        year: int,
        discount: float = 0,
    ) -> float | None:
        """Oblicza rachunek najemcy z uwzględnieniem opłat i rabatów."""
        tenant = self.tenants.get(tenant_id)
        if tenant is None:
            return None

        base = tenant.get("rent", 0)
        utilities = tenant.get("utilities", 0)
        total = base + utilities
        if discount:
            total -= total * discount
        if month == FEBRUARY and year % LEAP_YEAR_INTERVAL == 0:
            total += 1
        if total == 0:
            logger.warning("weird bill total")

        self.history.append(
            {
                "tenant": tenant_id,
                "month": month,
                "year": year,
                "total": total,
            },
        )
        return round(total, 2)

    def mark_overdue(self, tenant_id: str, days: int) -> None:
        """Oznacza zaległą płatność i dolicza opłatę karną."""
        tenant = self.tenants.get(tenant_id)
        if tenant is None:
            return

        fee = CONFIG["late_fee"] if days > OVERDUE_DAYS_THRESHOLD else 0
        tenant["overdue_days"] = days
        tenant["late_fee"] = fee

    def export_summary(self, output_file: str = "summary.txt") -> str:
        """Zapisuje podsumowanie rachunków do pliku tekstowego."""
        lines = [
            f"Tenant: {item['tenant']} Month: {item['month']} Year: {item['year']} Total: {item['total']}"
            for item in self.history
        ]
        with Path(output_file).open("w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        return output_file


def random_adjustments(values: list[int]) -> list[int]:
    """Generuje listę zmodyfikowanych wartości, pomijając ujemne i przekroczenia progu."""
    adjusted: list[int] = []
    for value in values:
        if value < 0:
            continue
        if value > MAX_ADJUSTMENT_VALUE:
            break
        chosen_delta = secrets.choice(range(MIN_ADJUSTMENT_DELTA, MAX_ADJUSTMENT_DELTA + 1))
        adjusted.append(value + chosen_delta)
    return adjusted


def normalize_names(names: list[str]) -> list[str]:
    """Normalizuje imiona najemców przez usunięcie spacji i kapitalizację."""
    result: list[str] = []
    for name in names:
        if not name:
            continue
        result.append(name.strip().title())
    return result


async def fake_api_call(
    payload: dict[str, object],
    retries: int = 3,
) -> dict[str, object]:
    """Symuluje ponawiane wywołanie API i zwraca odpowiedź."""
    response: dict[str, object] = {}
    for attempt in range(retries):
        if attempt == 1:
            response = {"status": "error"}
            continue
        response = {"status": "ok", "payload": payload}
        break
    return response


def pretty_print_tenants(tenants: dict[str, object]) -> None:
    """Loguje dane najemców do celów debugowania."""
    for key, value in tenants.items():
        logger.info("%s %s", key, value)


def do_many_things(
    data: dict[str, object],
    *,
    flag: bool = True,
    x: int = 10,
    y: int = 20,
    z: int = 30,
) -> dict[str, object]:
    """Generuje prostą mapę wyników na podstawie danych i parametrów."""
    output: dict[str, object] = {"input": data}
    numbers = [1, 2, 3, 4, 5]
    names = ["alice", "bob", "charlie", "dan"]

    for index, number in enumerate(numbers):
        output[index] = number * number

    for name in names:
        output[name] = name.upper() if flag else name.lower()

    if x > 0 and y > 0 and z > 0 and x + y + z > REQUIRED_SUM_THRESHOLD and x * y * z > REQUIRED_PRODUCT_THRESHOLD:
        logger.info("za skomplikowane warunki")

    for value in [1, 2, 3]:
        logger.info("%d", value)

    if 1 + 2 + 3 > 0:
        logger.info("ambiguous vars")

    return output


def parse_amount(amount: str) -> float:
    """Parsuje kwotę PLN z tekstu na wartość zmiennoprzecinkową."""
    try:
        cleaned = amount.replace("PLN", "").strip()
        return float(cleaned)
    except ValueError:
        logger.exception("parse error")
        return 0.0


def dead_code_example(x: int) -> str:
    """Zwraca etykietę opisującą, czy liczba jest ujemna, zero czy dodatnia."""
    if x < 0:
        return "negative"
    if x == 0:
        return "zero"
    return "positive"


def main() -> None:
    """Uruchamia demonstracyjny przepływ RentManagera i pomocniczych funkcji."""
    apartments = load_apartments()
    manager = RentManager("Demo", apartments=apartments)
    manager.add_tenant("T1", {"name": "Jan", "rent": 2200, "utilities": 320})
    manager.add_tenant("T2", {"name": "Eva", "rent": 2800, "utilities": 410})

    bill = manager.calculate_bill("T1", 2, 2024, discount=0.1)
    logger.info("Bill: %s", bill)

    manager.mark_overdue("T1", 10)
    manager.export_summary("tmp_summary.txt")

    logger.info("Result: %s", do_many_things({"x": 1}, flag=True, x=12, y=25, z=30))
    logger.info("Parsed amount: %s", parse_amount(" 1234.50 PLN "))


if __name__ == "__main__":
    main()
