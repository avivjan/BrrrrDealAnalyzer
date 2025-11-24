// ----- DOM SELECTION -----
const arvForm = document.getElementById("deal-form");
const arvSubmitBtn = document.getElementById("submit-btn");
const formStatusEl = document.getElementById("form-status");
const errorMessageEl = document.getElementById("error-message");
const resultsCard = document.getElementById("results-card");
const totalPurchaseCostsEl = document.getElementById("result-total-purchase-costs");
const allInPercentEl = document.getElementById("result-all-in-percent");
const rule70El = document.getElementById("result-70-rule");
const maxAllowedPurchasePriceEl = document.getElementById("result-max-allowed-purchase-price");
const diffPurchasePriceEl = document.getElementById("result-difference-purchase-price");

const cashflowForm = document.getElementById("cashflow-form");
const cashflowSubmitBtn = document.getElementById("cashflow-submit");
const cashflowStatus = document.getElementById("cashflow-status");
const cashflowResultsCard = document.getElementById("cashflow-results");
const grossIncomeEl = document.getElementById("result-gross-income");
const vacancyEl = document.getElementById("result-vacancy");
const operatingExpensesEl = document.getElementById("result-operating-expenses");
const noiEl = document.getElementById("result-noi");
const cashflowEl = document.getElementById("result-cashflow");
const cashflowAnnualEl = document.getElementById("result-cashflow-annual");

// ----- UTILITY FUNCTIONS -----
function getNumericValue(form, name) {
  const value = form.elements[name]?.value ?? "";
  const parsed = parseFloat(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function formatCurrency(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatPercent(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  const percentage = value * 100;
  return `${percentage.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`;
}

function setLoading(button, statusEl, isLoading, message = "Calculating…") {
  if (!button || !statusEl) return;
  if (isLoading) {
    button.disabled = true;
    button.textContent = message;
    statusEl.textContent = "Working on it…";
  } else {
    button.disabled = false;
    button.textContent = button.dataset.defaultText || button.textContent;
    statusEl.textContent = "";
  }
}

function showError(message) {
  if (!errorMessageEl) return;
  errorMessageEl.textContent = message;
  errorMessageEl.classList.add("visible");
}

function clearError() {
  if (!errorMessageEl) return;
  errorMessageEl.textContent = "";
  errorMessageEl.classList.remove("visible");
}

// ----- ACQUISITION CALCULATOR -----
function displayAcquisitionResults(data) {
  const {
    total_purchase_costs,
    alllInPrecentFromARV,
    passes_70_rule,
    max_allowed_purchase_price_to_meet_70_rule,
    difference_in_purchase_price_to_meet_70_rule,
  } = data;

  totalPurchaseCostsEl.textContent = formatCurrency(total_purchase_costs);
  allInPercentEl.textContent = formatPercent(alllInPrecentFromARV / 100);
  maxAllowedPurchasePriceEl.textContent = formatCurrency(
    max_allowed_purchase_price_to_meet_70_rule
  );

  if (
    typeof difference_in_purchase_price_to_meet_70_rule === "number" &&
    difference_in_purchase_price_to_meet_70_rule >= 0
  ) {
    diffPurchasePriceEl.textContent = formatCurrency(
      difference_in_purchase_price_to_meet_70_rule
    );
  } else {
    diffPurchasePriceEl.textContent = "Already meets 70% rule";
  }

  rule70El.classList.remove("pass", "fail");
  if (passes_70_rule) {
    rule70El.textContent = "PASS";
    rule70El.classList.add("pass");
  } else {
    rule70El.textContent = "FAIL";
    rule70El.classList.add("fail");
  }

  resultsCard.hidden = false;
  resultsCard.classList.add("visible");
}

function buildAcquisitionPayload() {
  return {
    arv: getNumericValue(arvForm, "arv"),
    purchase_price: getNumericValue(arvForm, "purchase_price"),
    origination_points_percent: getNumericValue(
      arvForm,
      "origination_points_percent"
    ),
    title_fees: getNumericValue(arvForm, "title_fees"),
    attorney_fees: getNumericValue(arvForm, "attorney_fees"),
    recording_fees: getNumericValue(arvForm, "recording_fees"),
    transfer_taxes: getNumericValue(arvForm, "transfer_taxes"),
    lender_underwriting_fees: getNumericValue(
      arvForm,
      "lender_underwriting_fees"
    ),
    title_insurance: getNumericValue(arvForm, "title_insurance"),
    survey_cost: getNumericValue(arvForm, "survey_cost"),
    inspection_costs: getNumericValue(arvForm, "inspection_costs"),
    hml_underwriting_fee: getNumericValue(arvForm, "hml_underwriting_fee"),
    hml_processing_fee: getNumericValue(arvForm, "hml_processing_fee"),
    hml_appraisal_fee: getNumericValue(arvForm, "hml_appraisal_fee"),
    draw_setup_fee: getNumericValue(arvForm, "draw_setup_fee"),
    rehab_cost: getNumericValue(arvForm, "rehab_cost"),
    rehab_utilities_cost: getNumericValue(arvForm, "rehab_utilities_cost"),
  };
}

async function calculateAllInPercentage(payload) {
  const response = await fetch("http://localhost:8000/CalcPrecentageOfARVRes", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = "";
    try {
      const errorBody = await response.json();
      if (errorBody && (errorBody.detail || errorBody.message)) {
        detail = errorBody.detail || errorBody.message;
      }
    } catch {
      // ignore
    }
    const message = detail || `Backend error (status ${response.status}).`;
    throw new Error(message);
  }

  return await response.json();
}

async function handleArvSubmit(event) {
  event.preventDefault();
  clearError();
  setLoading(arvSubmitBtn, formStatusEl, true);

  const payload = buildAcquisitionPayload();

  try {
    const data = await calculateAllInPercentage(payload);
    displayAcquisitionResults(data);
  } catch (err) {
    console.error(err);
    showError(
      err.message ||
        "Something went wrong while contacting the backend. Please ensure the FastAPI server is running on localhost:8000."
    );
  } finally {
    setLoading(arvSubmitBtn, formStatusEl, false);
  }
}

// ----- CASH FLOW CALCULATOR -----
function calculateCashFlow(inputs) {
  const grossIncome = inputs.rent + inputs.otherIncome;
  const vacancyLoss = grossIncome * (inputs.vacancyPercent / 100);

  const managementFee = grossIncome * (inputs.managementPercent / 100);
  const otherVariable = grossIncome * (inputs.otherPercent / 100);

  const fixedExpenses =
    inputs.taxes + inputs.insurance + inputs.maintenance + inputs.capex + inputs.utilities + inputs.hoa;

  const operatingExpenses =
    vacancyLoss + managementFee + otherVariable + fixedExpenses;

  const netOperatingIncome = grossIncome - operatingExpenses;
  const cashFlow = netOperatingIncome - inputs.mortgage;

  return {
    grossIncome,
    vacancyLoss,
    operatingExpenses,
    netOperatingIncome,
    cashFlow,
    cashFlowAnnual: cashFlow * 12,
  };
}

function buildCashFlowInputs() {
  return {
    rent: getNumericValue(cashflowForm, "rent"),
    otherIncome: getNumericValue(cashflowForm, "other_income"),
    vacancyPercent: getNumericValue(cashflowForm, "vacancy_percent"),
    taxes: getNumericValue(cashflowForm, "taxes"),
    insurance: getNumericValue(cashflowForm, "insurance"),
    mortgage: getNumericValue(cashflowForm, "mortgage"),
    maintenance: getNumericValue(cashflowForm, "maintenance"),
    capex: getNumericValue(cashflowForm, "capex"),
    utilities: getNumericValue(cashflowForm, "utilities"),
    hoa: getNumericValue(cashflowForm, "hoa"),
    managementPercent: getNumericValue(cashflowForm, "management_percent"),
    otherPercent: getNumericValue(cashflowForm, "other_percent"),
  };
}

function displayCashflowResults(results) {
  grossIncomeEl.textContent = formatCurrency(results.grossIncome);
  vacancyEl.textContent = formatCurrency(results.vacancyLoss);
  operatingExpensesEl.textContent = formatCurrency(results.operatingExpenses);
  noiEl.textContent = formatCurrency(results.netOperatingIncome);
  cashflowEl.textContent = formatCurrency(results.cashFlow);
  cashflowAnnualEl.textContent = formatCurrency(results.cashFlowAnnual);

  cashflowResultsCard.hidden = false;
  cashflowResultsCard.classList.add("visible");
}

function handleCashflowSubmit(event) {
  event.preventDefault();
  if (!cashflowForm) return;
  setLoading(cashflowSubmitBtn, cashflowStatus, true, "Crunching…");

  const inputs = buildCashFlowInputs();
  const results = calculateCashFlow(inputs);
  displayCashflowResults(results);

  setLoading(cashflowSubmitBtn, cashflowStatus, false);
}

// ----- EVENT BINDING -----
if (arvForm) {
  arvSubmitBtn.dataset.defaultText = arvSubmitBtn.textContent;
  arvForm.addEventListener("submit", handleArvSubmit);
}

if (cashflowForm) {
  cashflowSubmitBtn.dataset.defaultText = cashflowSubmitBtn.textContent;
  cashflowForm.addEventListener("submit", handleCashflowSubmit);
}
