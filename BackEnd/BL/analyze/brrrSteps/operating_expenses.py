"""BRRRR step: monthly operating expenses of a regular year after the refi, with their components.

Taxes and insurance are the steady monthly figures (bill x 0.96 / 12, and the regular-year insurance),
never a closing lump: those belong to the purchase-to-refi outputs."""

from decimal import Decimal

from BL.analyze.common.deal_math import OperatingExpenses


def operating_expenses_step(payload, monthly_property_tax_after_refi, monthly_insurance_after_refi) -> OperatingExpenses:
    vacancy = payload.rent * (payload.vacancy_percent / Decimal("100.0"))
    management = payload.rent * (payload.property_managment_fee_precentages_from_rent / Decimal("100.0"))
    maintenance = payload.rent * (payload.maintenance_percent / Decimal("100.0"))
    capex = payload.rent * (payload.capex_percent_of_rent / Decimal("100.0"))
    total = vacancy + management + maintenance + capex + monthly_property_tax_after_refi + monthly_insurance_after_refi + payload.montly_hoa
    return OperatingExpenses(total, vacancy, management, maintenance, capex, monthly_property_tax_after_refi, monthly_insurance_after_refi)
