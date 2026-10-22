"""Every input the user typed into the deal form, grouped the way the form groups them, ready to display.

The interactive report's optional "Deal Inputs" section reads this. The sub-stages are the form's tabs
(`frontend/src/config/dealInputPhaseTabs.ts`: Buy · Rehab · Rent & Holding · Refinance for BRRRR,
Buy & Rehab · Flip Strategy · Expenses for FLIP) and the groups, labels and order are the section
components' (`frontend/src/components/deal/brrr/*Section.vue`, the FLIP blocks of `DealInputsForm.vue`).
`tests/test_report_deal_inputs.py` pins the field keys per tab to the frontend file.

Only calculator inputs are listed: no notes, contact, task, links or comps, so the file is safe to share.
A field left blank on a formula default shows the value the calculator actually used (the result's
`*_effective` fields) with an "auto" chip, as the form shows it in grey with its "auto" tag. The form's
deprecated or hidden BRRRR keys (`closingCostsBuy`, `closingCostsRefi`, `cashReserve`,
`use_HM_for_rehab`) are never listed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional

from BL.reports.common.deal_pdf import format_value_like_calculation_popup

# -- the declarative map ---------------------------------------------------------------------------

DealInputs = dict[str, Any]
CalculatorResult = dict[str, Any]


@dataclass(frozen=True)
class DealInputField:
    payload_key: str
    label: str
    # money · money_in_thousands · percent · points · days · months · years · date · yes_no · choice · text
    display_kind: str
    # "/mo" or "/yr" after a money value, as the form's per-month / per-year fields read.
    value_suffix: str = ""
    # A formula-default field: the result field holding the value used when the input is left blank.
    effective_result_key: Optional[str] = None
    # A blank field with a constant default (the $250 notary fee).
    constant_default_when_blank: Optional[Any] = None
    formula_hint: Optional[str] = None
    # A day count with a date the calculator derives from it ("Refi closing Jul 09, 2026").
    linked_date_result_key: Optional[str] = None
    linked_date_label: Optional[str] = None
    choice_labels: Optional[dict[str, str]] = None
    # The form hides some fields (a notary fee with the notary off, an empty note, ...).
    shown_when: Optional[Callable[[DealInputs], bool]] = None


@dataclass(frozen=True)
class DealInputGroup:
    title: Optional[str]
    fields: tuple[DealInputField, ...]


@dataclass(frozen=True)
class DealInputSection:
    tab_key: str
    title: str
    icon: str
    groups: tuple[DealInputGroup, ...]


def _has_text(payload_key: str) -> Callable[[DealInputs], bool]:
    return lambda inputs: bool(str(inputs.get(payload_key) or "").strip())


def _is_on(payload_key: str) -> Callable[[DealInputs], bool]:
    return lambda inputs: bool(inputs.get(payload_key))


def _has_buy_closing_date(inputs: DealInputs) -> bool:
    return bool(inputs.get("buyClosingDate"))


TITLE_MODE_BUY_LABELS = {"standard": "Standard (lender's policy)", "we_pay_all": "We pay all closing costs"}

BRRRR_DEAL_INPUT_SECTIONS: tuple[DealInputSection, ...] = (
    DealInputSection("buy", "Buy", "home", (
        DealInputGroup(None, (
            DealInputField("buyClosingDate", "Closing Date (Buy)", "date"),
            DealInputField("sellerPaidCurrentYearTaxes", "Seller already paid this year's taxes", "yes_no",
                           formula_hint="Auto: yes only for a December closing", shown_when=_has_buy_closing_date),
            DealInputField("purchasePrice", "Purchase Price", "money_in_thousands"),
            DealInputField("earnestMoneyDeposit", "Earnest Money Deposit", "money"),
        )),
        DealInputGroup("Hard Money", (
            DealInputField("down_payment", "Down Payment", "percent"),
            DealInputField("hmlPoints", "Points", "points"),
            DealInputField("HMLInterestRate", "Interest Rate", "percent"),
        )),
        DealInputGroup("Closing Costs (Buy)", (
            DealInputField("loanChargesBuy", "Loan Charges", "money"),
            DealInputField("recordingTransferBuy", "Recording & Transfer", "money",
                           effective_result_key="recording_transfer_buy_effective",
                           formula_hint="Formula: $250 + 0.55% of the hard money loan + the deed transfer tax"),
            DealInputField("titleModeBuy", "Title Charges", "choice", choice_labels=TITLE_MODE_BUY_LABELS),
            DealInputField("titleEscrowBuy", "Title & Escrow / Settlement", "money",
                           effective_result_key="title_escrow_buy_effective",
                           formula_hint="Formula: by the title charges and the purchase price tier"),
            DealInputField("onlineNotaryBuy", "Online notary", "yes_no"),
            DealInputField("onlineNotaryFeeBuy", "Notary fee", "money", constant_default_when_blank=250,
                           formula_hint="Default: $250", shown_when=_is_on("onlineNotaryBuy")),
            DealInputField("otherClosingCostsBuy", "Other Closing Costs", "money"),
            DealInputField("otherClosingCostsBuyNote", "What the other closing costs are for", "text",
                           shown_when=_has_text("otherClosingCostsBuyNote")),
        )),
    )),
    DealInputSection("rehab", "Rehab", "wrench", (
        DealInputGroup(None, (
            DealInputField("rehabCost", "Actual Rehab Cost", "money_in_thousands"),
            DealInputField("constructionLoanBudget", "Construction Loan Budget", "money_in_thousands"),
            DealInputField("rehabContingency", "Contingency", "percent"),
            DealInputField("rehabCushion", "Rehab Cushion", "money"),
        )),
    )),
    DealInputSection("rentHolding", "Rent & Holding", "key", (
        DealInputGroup(None, (
            DealInputField("rent", "Monthly Rent", "money", value_suffix="/mo"),
            DealInputField("daysUntilRented", "Until Tenant Occupied", "days",
                           linked_date_result_key="tenant_occupied_date", linked_date_label="Tenant occupied"),
            DealInputField("monthlyUtilitiesUntilRented", "Utilities until Rented (per month)", "money", value_suffix="/mo"),
            DealInputField("maintenanceBeforeRefi", "Maintenance before Refi", "money"),
            DealInputField("appliances", "Appliances", "money"),
        )),
        DealInputGroup("Holding Costs", (
            DealInputField("annual_property_taxes", "Annual Taxes", "money", value_suffix="/yr"),
            DealInputField("annual_insurance", "Annual Insurance", "money", value_suffix="/yr"),
            DealInputField("montly_hoa", "Monthly HOA", "money", value_suffix="/mo"),
        )),
        DealInputGroup("Operating Expenses (% of rent)", (
            DealInputField("vacancyPercent", "Vacancy", "percent"),
            DealInputField("maintenancePercent", "Maint.", "percent"),
            DealInputField("capexPercent", "CapEx", "percent"),
            DealInputField("property_managment_fee_precentages_from_rent", "Prop. Mgmt", "percent"),
        )),
    )),
    DealInputSection("refinance", "Refinance", "refresh", (
        DealInputGroup(None, (
            DealInputField("daysUntilRefi", "Days to Refi", "days",
                           linked_date_result_key="refi_closing_date", linked_date_label="Refi closing"),
            DealInputField("arv_in_thousands", "ARV", "money_in_thousands"),
            DealInputField("lowestArv", "Lowest ARV Possible (stress test)", "money_in_thousands",
                           effective_result_key="lowest_arv_effective", formula_hint="Formula: 90% of ARV"),
            DealInputField("ltv_as_precent", "LTV", "percent"),
            DealInputField("interestRate", "Long Term Interest Rate", "percent"),
            DealInputField("loanTermYears", "Loan Term", "years"),
        )),
        DealInputGroup("Closing Costs (Refi)", (
            DealInputField("loanChargesRefi", "Loan Charges (Refi)", "money"),
            DealInputField("recordingTransferRefi", "Recording & Transfer (Refi)", "money",
                           effective_result_key="recording_transfer_refi_effective",
                           formula_hint="Formula: 0.55% of the refi loan + $250"),
            DealInputField("titleEscrowRefi", "Title & Escrow / Settlement (Refi)", "money",
                           effective_result_key="title_escrow_refi_effective",
                           formula_hint="Formula: $800 + 0.45% of the refi loan"),
            DealInputField("onlineNotaryRefi", "Online notary", "yes_no"),
            DealInputField("onlineNotaryFeeRefi", "Notary fee", "money", constant_default_when_blank=250,
                           formula_hint="Default: $250", shown_when=_is_on("onlineNotaryRefi")),
            DealInputField("appraisalFee", "Appraisal", "money"),
            DealInputField("surveyFee", "Survey", "money"),
            DealInputField("refiUnderwritingFee", "Underwriting Fee", "money"),
            DealInputField("refiPoints", "Broker Points", "points"),
            DealInputField("brokerProcessingFeeRefi", "Broker Processing Fee", "money"),
            DealInputField("otherClosingCostsRefi", "Other Closing Costs (Refi)", "money"),
            DealInputField("otherClosingCostsRefiNote", "What the other refi closing costs are for", "text",
                           shown_when=_has_text("otherClosingCostsRefiNote")),
        )),
        DealInputGroup("Reserves escrowed at refi", (
            DealInputField("maintenanceReserve", "Maintenance Reserve", "money"),
            DealInputField("vacancyReserve", "Vacancy Reserve (1 month rent)", "money",
                           effective_result_key="vacancy_reserve_effective", formula_hint="Formula: one month of rent"),
            DealInputField("capexReserve", "CapEx Reserve", "money"),
        )),
    )),
)

FLIP_DEAL_INPUT_SECTIONS: tuple[DealInputSection, ...] = (
    DealInputSection("buyRehab", "Buy & Rehab", "home", (
        DealInputGroup(None, (
            DealInputField("purchasePrice", "Purchase Price", "money_in_thousands"),
            DealInputField("rehabCost", "Rehab Cost", "money_in_thousands"),
            DealInputField("rehabContingency", "Contingency", "percent"),
            DealInputField("closingCostsBuy", "Closing Costs (Buy)", "money_in_thousands"),
        )),
        DealInputGroup("Hard Money Details", (
            DealInputField("down_payment", "Down Payment", "percent"),
            DealInputField("hmlPoints", "Points", "points"),
            DealInputField("HMLInterestRate", "Interest Rate", "percent"),
            DealInputField("use_HM_for_rehab", "Use HM for Rehab", "yes_no"),
        )),
    )),
    DealInputSection("flipStrategy", "Flip Strategy", "dollar", (
        DealInputGroup(None, (
            DealInputField("salePrice", "Projected Sale Price", "money_in_thousands"),
            DealInputField("holdingTime", "Holding Time", "months"),
        )),
        DealInputGroup("Selling Costs", (
            DealInputField("buyerAgentSellingFee", "Buyer Agent Fee", "percent"),
            DealInputField("sellerAgentSellingFee", "Seller Agent Fee", "percent"),
            DealInputField("sellingClosingCosts", "Closing Costs", "money_in_thousands"),
        )),
        DealInputGroup("Taxes", (
            DealInputField("capitalGainsTax", "Capital Gains Tax Rate", "percent"),
        )),
    )),
    DealInputSection("expenses", "Expenses", "wallet", (
        DealInputGroup(None, (
            DealInputField("annual_property_taxes", "Annual Taxes", "money", value_suffix="/yr"),
            DealInputField("annual_insurance", "Annual Insurance", "money", value_suffix="/yr"),
            DealInputField("montly_hoa", "Monthly HOA", "money", value_suffix="/mo"),
            DealInputField("monthly_utilities", "Monthly Utilities", "money", value_suffix="/mo"),
        )),
    )),
)


def deal_input_sections_for_deal_type(deal_type: str) -> tuple[DealInputSection, ...]:
    return FLIP_DEAL_INPUT_SECTIONS if (deal_type or "").upper() == "FLIP" else BRRRR_DEAL_INPUT_SECTIONS


# -- resolving the user's values -------------------------------------------------------------------

@dataclass(frozen=True)
class ResolvedDealInputRow:
    label: str
    value_text: str
    display_kind: str
    # "auto" for a formula or constant default the user left blank; "yes" / "no" for a toggle.
    chips: tuple[str, ...] = ()
    hint: Optional[str] = None


@dataclass(frozen=True)
class ResolvedDealInputGroup:
    title: Optional[str]
    rows: tuple[ResolvedDealInputRow, ...]


@dataclass(frozen=True)
class ResolvedDealInputSection:
    tab_key: str
    title: str
    icon: str
    groups: tuple[ResolvedDealInputGroup, ...] = field(default_factory=tuple)

    @property
    def row_count(self) -> int:
        return sum(len(group.rows) for group in self.groups)


def _decimal(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _trimmed_number(number: Decimal) -> str:
    """12.50 → "12.5", 75.000 → "75", 1234 → "1,234"."""
    text = f"{number:,.4f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def format_deal_date(value: Any) -> str:
    parsed = _as_date(value)
    return parsed.strftime("%b %d, %Y") if parsed else "—"


def format_deal_input_value(display_kind: str, value: Any, value_suffix: str = "", choice_labels: Optional[dict[str, str]] = None) -> str:
    """One input as the report shows it. A missing value reads "—"."""
    if display_kind == "date":
        return format_deal_date(value)
    if display_kind == "yes_no":
        return "Yes" if value else "No"
    if display_kind == "choice":
        return (choice_labels or {}).get(str(value), str(value)) if value is not None else "—"
    if display_kind == "text":
        return str(value or "").strip() or "—"
    number = _decimal(value)
    if number is None:
        return "—"
    if display_kind == "money_in_thousands":
        return format_value_like_calculation_popup("money", float(number * 1000)) + value_suffix
    if display_kind == "money":
        return format_value_like_calculation_popup("money", float(number)) + value_suffix
    if display_kind == "percent":
        return f"{_trimmed_number(number)}%"
    if display_kind == "points":
        return f"{_trimmed_number(number)} pts"
    if display_kind in ("days", "months", "years"):
        singular = display_kind[:-1]
        return f"{_trimmed_number(number)} {singular if number == 1 else display_kind}"
    return _trimmed_number(number)


def _resolve_row(input_field: DealInputField, inputs: DealInputs, result: CalculatorResult) -> ResolvedDealInputRow:
    raw_value = inputs.get(input_field.payload_key)
    chips: list[str] = []
    hint: Optional[str] = None

    if raw_value is None and input_field.effective_result_key is not None:
        # Left blank: the form shows the formula's value in grey with "auto"; so does the report.
        effective_value = result.get(input_field.effective_result_key)
        value_text = (format_value_like_calculation_popup("money", effective_value)
                      if effective_value is not None else "—")
        chips.append("auto")
        hint = input_field.formula_hint
    elif raw_value is None and input_field.constant_default_when_blank is not None:
        value_text = format_deal_input_value(input_field.display_kind, input_field.constant_default_when_blank, input_field.value_suffix)
        chips.append("auto")
        hint = input_field.formula_hint
    elif input_field.payload_key == "sellerPaidCurrentYearTaxes" and raw_value is None:
        closing_date = _as_date(inputs.get("buyClosingDate"))
        automatic_value = bool(closing_date and closing_date.month == 12)
        value_text = format_deal_input_value("yes_no", automatic_value)
        chips.extend(["auto", "yes" if automatic_value else "no"])
        hint = input_field.formula_hint
    else:
        value_text = format_deal_input_value(input_field.display_kind, raw_value, input_field.value_suffix, input_field.choice_labels)
        if input_field.display_kind == "yes_no":
            chips.append("yes" if raw_value else "no")

    if input_field.linked_date_result_key and result.get(input_field.linked_date_result_key):
        hint = f"{input_field.linked_date_label} {format_deal_date(result[input_field.linked_date_result_key])}"
    return ResolvedDealInputRow(input_field.label, value_text, input_field.display_kind, tuple(chips), hint)


def resolve_deal_input_sections(deal_type: str, inputs: DealInputs, result: CalculatorResult) -> list[ResolvedDealInputSection]:
    """The form's sub-stages with the user's values, formatted; hidden fields left out as the form leaves them."""
    resolved_sections = []
    for section in deal_input_sections_for_deal_type(deal_type):
        resolved_groups = []
        for group in section.groups:
            rows = tuple(
                _resolve_row(input_field, inputs, result)
                for input_field in group.fields
                if input_field.shown_when is None or input_field.shown_when(inputs)
            )
            if rows:
                resolved_groups.append(ResolvedDealInputGroup(group.title, rows))
        resolved_sections.append(ResolvedDealInputSection(section.tab_key, section.title, section.icon, tuple(resolved_groups)))
    return resolved_sections
