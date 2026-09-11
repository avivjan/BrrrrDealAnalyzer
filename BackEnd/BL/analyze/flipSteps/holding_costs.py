"""Flip step: operating costs during holding, and total holding costs."""

from decimal import Decimal


def operating_and_holding_costs_step(payload, total_hml_interest):
    monthly_taxes = payload.annual_property_taxes / Decimal("12.0")
    monthly_insurance = payload.annual_insurance / Decimal("12.0")
    monthly_operating = monthly_taxes + monthly_insurance + payload.montly_hoa + payload.monthly_utilities
    total_operating = monthly_operating * payload.holding_time_months
    total_holding_costs = total_hml_interest + total_operating
    return monthly_taxes, monthly_insurance, monthly_operating, total_operating, total_holding_costs
