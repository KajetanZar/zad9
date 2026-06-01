"""
Manager class for handling apartment management operations.
"""

from datetime import datetime

from src.models import (
    Apartment,
    ApartmentEvent,
    ApartmentSettlement,
    Bill,
    Parameters,
    Tenant,
    TenantBlacklistEntry,
    TenantSettlement,
    Transfer,
)

MONTHS_PER_YEAR = 12
INVALID_MONTH_MESSAGE = "Month must be between 1 and 12"
INVALID_APARTMENT_MESSAGE = "Apartment key does not exist"


class Manager:
    """
    Manager class responsible for loading data and providing methods
    to manage apartments, tenants, transfers, bills, and apartment events.
    """

    def __init__(self, parameters: Parameters):
        self.parameters = parameters

        self.apartments = {}
        self.tenants = {}
        self.transfers = []
        self.bills = []
        self.tenants_blacklist = []
        self.apartment_events = []

        self.load_data()

    def load_data(self):
        """Load data from JSON files specified in the parameters."""
        self.apartments = Apartment.from_json_file(self.parameters.apartments_json_path)
        self.tenants = Tenant.from_json_file(self.parameters.tenants_json_path)
        self.transfers = Transfer.from_json_file(self.parameters.transfers_json_path)
        self.bills = Bill.from_json_file(self.parameters.bills_json_path)
        self.tenants_blacklist = TenantBlacklistEntry.from_json_file(
            self.parameters.tenants_blacklist_json_path,
        )

    def load_additional_data(self):
        """Load additional data such as apartment events from JSON files."""
        self.apartment_events = ApartmentEvent.from_json_file(
            self.parameters.apartment_events_json_path,
        )

    def generate_apartment_events_report(
        self,
        apartment_key: str,
        only_unsolved: bool = True,
    ) -> list[ApartmentEvent]:
        """Generate a report of apartment events for a given apartment key."""
        if apartment_key not in self.apartments:
            error_message = INVALID_APARTMENT_MESSAGE
            raise ValueError(error_message)
        return [
            event
            for event in self.apartment_events
            if event.apartment == apartment_key and (not event.solved or not only_unsolved)
        ]

    def check_tenants_apartment_keys(self) -> bool:
        """Check if all tenants have valid apartment keys that exist in the apartments data."""
        return all(tenant.apartment in self.apartments for tenant in self.tenants.values())

    def get_apartment(self, apartment_key: str) -> Apartment | None:
        """Get an apartment by its key."""
        return self.apartments.get(apartment_key, None)

    def get_apartment_costs(
        self,
        apartment_key: str,
        year: int | None = None,
        month: int | None = None,
    ) -> float | None:
        """Calculate the total costs for a given apartment, optionally filtered by year/month."""
        if month is not None and (month < 1 or month > MONTHS_PER_YEAR):
            error_message = INVALID_MONTH_MESSAGE
            raise ValueError(error_message)
        if apartment_key not in self.apartments:
            return None

        total_cost = 0.0
        for bill in self.bills:
            if (
                bill.apartment == apartment_key
                and (year is None or bill.settlement_year == year)
                and (month is None or bill.settlement_month == month)
            ):
                total_cost += bill.amount_pln
        return total_cost

    def get_settlement(
        self,
        apartment_key: str,
        year: int,
        month: int,
    ) -> ApartmentSettlement | None:
        """Get the apartment settlement for a given apartment key, year, and month."""
        if month < 1 or month > MONTHS_PER_YEAR:
            error_message = INVALID_MONTH_MESSAGE
            raise ValueError(error_message)
        if apartment_key not in self.apartments:
            return None

        total_cost = self.get_apartment_costs(apartment_key, year, month)
        if total_cost is None:
            return None

        return ApartmentSettlement(
            key=f"{apartment_key}-{year}-{month}",
            apartment=apartment_key,
            year=year,
            month=month,
            total_due_pln=total_cost,
        )

    def create_tenants_settlements(
        self,
        apartment_settlement: ApartmentSettlement,
    ) -> list[TenantSettlement] | None:
        """Create tenant settlements based on the apartment settlement."""
        if apartment_settlement.month < 1 or apartment_settlement.month > MONTHS_PER_YEAR:
            error_message = INVALID_MONTH_MESSAGE
            raise ValueError(error_message)
        if apartment_settlement.apartment not in self.apartments:
            return None

        tenants_in_apartment = [
            tenant for tenant in self.tenants.values() if tenant.apartment == apartment_settlement.apartment
        ]
        if not tenants_in_apartment:
            return []

        return [
            TenantSettlement(
                tenant=tenant.name,
                apartment_settlement=apartment_settlement.key,
                month=apartment_settlement.month,
                year=apartment_settlement.year,
                total_due_pln=apartment_settlement.total_due_pln / len(tenants_in_apartment),
            )
            for tenant in tenants_in_apartment
        ]

    def get_debtors(
        self,
        apartment_key: str,
        year: int,
        month: int,
    ) -> list[str]:
        """Get a list of tenant names (debtors) for a given apartment key, year, and month."""
        if month < 1 or month > MONTHS_PER_YEAR:
            error_message = INVALID_MONTH_MESSAGE
            raise ValueError(error_message)
        if apartment_key not in self.apartments:
            error_message = INVALID_APARTMENT_MESSAGE
            raise ValueError(error_message)

        settlement = self.get_settlement(apartment_key, year, month)
        if settlement is None:
            return []

        tenant_settlements = self.create_tenants_settlements(settlement)
        if tenant_settlements is None:
            return []

        output: list[str] = []
        for tenant_settlement in tenant_settlements:
            tenant_transfers = [
                transfer
                for transfer in self.transfers
                if self.tenants[transfer.tenant].name == tenant_settlement.tenant
                and transfer.settlement_year == year
                and transfer.settlement_month == month
            ]
            total_paid = sum(
                transfer.amount_pln
                for transfer in tenant_transfers
                if transfer.settlement_year == year and transfer.settlement_month == month
            )
            if total_paid < tenant_settlement.total_due_pln:
                output.append(tenant_settlement.tenant)
        return output

    def calculate_tax(self, year: int, month: int, tax_rate: float) -> float:
        """Calculate the tax amount based on the total income from transfers."""
        total_income = sum(
            transfer.amount_pln
            for transfer in self.transfers
            if transfer.settlement_year == year and transfer.settlement_month == month
        )
        return round(total_income * tax_rate, 0)

    def check_deposits(self) -> float:
        """Check if the total deposits from tenants cover the total due amounts."""
        total_deposits = 0.0
        total_due = 0.0
        for tenant in self.tenants.values():
            total_deposits += sum(
                transfer.amount_pln
                for transfer in self.transfers
                if self.tenants[transfer.tenant].name == tenant.name and transfer.type == "deposit"
            )
            total_due += tenant.deposit_pln

        return total_deposits - total_due

    def get_annual_balance(self, year: int) -> float:
        """Calculate the annual balance for a given year based on transfers and bills."""
        total_income = sum(transfer.amount_pln for transfer in self.transfers if transfer.settlement_year == year)
        total_due = sum(bill.amount_pln for bill in self.bills if bill.settlement_year == year)
        return total_income - total_due

    def has_any_bills(self, apartment_key: str, year: int, month: int) -> bool:
        """Check if there are any bills for a given apartment key, year, and month."""
        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12")
        if apartment_key not in self.apartments:
            raise ValueError("Apartment key does not exist")
        return any(
            bill
            for bill in self.bills
            if bill.apartment == apartment_key and bill.settlement_year == year and bill.settlement_month == month
        )

    def check_transfers_amount_range(self) -> bool:
        """Check if all transfers have amounts within the specified range in parameters."""
        for transfer in self.transfers:
            if (
                transfer.amount_pln > self.parameters.max_transfer_pln
                or transfer.amount_pln < -self.parameters.max_refund_pln
            ):
                return False
        return True

    def check_tenant_blacklist(self, tenant_name: str) -> bool:
        """Check if a tenant is in the blacklist."""
        return any(entry.tenant == tenant_name for entry in self.tenants_blacklist)

    def check_transfers_tenant(self) -> bool:
        """Check if all transfers are associated with valid tenants and their agreement dates."""
        for transfer in self.transfers:
            if transfer.tenant not in self.tenants:
                return False
            if transfer.settlement_year is not None and transfer.settlement_month is not None:
                agreement_from = self.tenants[transfer.tenant].date_agreement_from
                agreement_from = datetime.strptime(agreement_from, "%Y-%m-%d").date()
                agreement_to = self.tenants[transfer.tenant].date_agreement_to
                agreement_to = datetime.strptime(agreement_to, "%Y-%m-%d").date()
                if (transfer.settlement_year < agreement_from.year) or (transfer.settlement_year > agreement_to.year):
                    return False

        return True
