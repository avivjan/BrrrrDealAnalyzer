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

const API_BASE_URL = "https://brrrrdealanalyzer.onrender.com";

const cashflowForm = document.getElementById("cashflow-form");
const cashflowSubmitBtn = document.getElementById("cashflow-submit");
const cashflowStatus = document.getElementById("cashflow-status");
const cashflowResultsCard = document.getElementById("cashflow-results");
const cashflowEl = document.getElementById("result-cashflow");
const dscrEl = document.getElementById("result-dscr");
const cashOutEl = document.getElementById("result-cash-out");
const cashflowErrorEl = document.getElementById("cashflow-error");
const cashflowMessagesEl = document.getElementById("cashflow-messages");

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

function formatRatio(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
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

function showCashflowError(message) {
  if (!cashflowErrorEl) return;
  cashflowErrorEl.textContent = message;
  cashflowErrorEl.classList.add("visible");
}

function clearCashflowError() {
  if (!cashflowErrorEl) return;
  cashflowErrorEl.textContent = "";
  cashflowErrorEl.classList.remove("visible");
}

function showCashflowMessages(messages = []) {
  if (!cashflowMessagesEl) return;
  const content = messages
    .filter((msg) => typeof msg === "string" && msg.trim().length > 0)
    .map((msg) => `<li>${msg}</li>`)
    .join("");

  if (content) {
    cashflowMessagesEl.innerHTML = `<ul>${content}</ul>`;
    cashflowMessagesEl.classList.add("visible");
  } else {
    clearCashflowMessages();
  }
}

function clearCashflowMessages() {
  if (!cashflowMessagesEl) return;
  cashflowMessagesEl.textContent = "";
  cashflowMessagesEl.classList.remove("visible");
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
  const response = await fetch(`${API_BASE_URL}/CalcPrecentageOfARVRes`, {
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
    showError(err.message || "Unable to reach the backend service.");
  } finally {
    setLoading(arvSubmitBtn, formStatusEl, false);
  }
}

// ----- CASH FLOW CALCULATOR -----
function buildCashFlowPayload() {
  return {
    arv: getNumericValue(cashflowForm, "arv"),
    purchasePrice: getNumericValue(cashflowForm, "purchasePrice"),
    rehabCost: getNumericValue(cashflowForm, "rehabCost"),
    down_payment: getNumericValue(cashflowForm, "down_payment"),
    closingCostsBuy: getNumericValue(cashflowForm, "closingCostsBuy"),
    hmlPoints: getNumericValue(cashflowForm, "hmlPoints"),
    hmlInterestInCash: getNumericValue(cashflowForm, "hmlInterestInCash"),
    closingCostsRefi: getNumericValue(cashflowForm, "closingCostsRefi"),
    loanTermYears: getNumericValue(cashflowForm, "loanTermYears"),
    ltv: getNumericValue(cashflowForm, "ltv"),
    rent: getNumericValue(cashflowForm, "rent"),
    interestRate: getNumericValue(cashflowForm, "interestRate"),
    vacancyPercent: getNumericValue(cashflowForm, "vacancyPercent"),
    property_managment_fee_precentages_from_rent: getNumericValue(
      cashflowForm,
      "property_managment_fee_precentages_from_rent"
    ),
    maintenancePercent: getNumericValue(cashflowForm, "maintenancePercent"),
    capexPercent: getNumericValue(cashflowForm, "capexPercent"),
    taxes: getNumericValue(cashflowForm, "taxes"),
    insurance: getNumericValue(cashflowForm, "insurance"),
    hoa: getNumericValue(cashflowForm, "hoa"),
  };
}

function displayCashflowResults(data) {
  const { cash_flow, dscr, cash_out } = data;
  cashflowEl.textContent = formatCurrency(cash_flow);
  dscrEl.textContent = formatRatio(dscr);
  cashOutEl.textContent = formatCurrency(cash_out);

  cashflowResultsCard.hidden = false;
  cashflowResultsCard.classList.add("visible");
}

async function calculateCashFlow(payload) {
  const response = await fetch(`${API_BASE_URL}/calcCashFlow`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = "";
    let messages = [];
    try {
      const errorBody = await response.json();
      if (errorBody && (errorBody.detail || errorBody.message)) {
        detail = errorBody.detail || errorBody.message;
      }
      if (errorBody && Array.isArray(errorBody.messages)) {
        messages = errorBody.messages.filter(
          (msg) => typeof msg === "string" && msg.trim().length > 0
        );
      }
    } catch {
      // ignore
    }
    const message = detail || `Backend error (status ${response.status}).`;
    const error = new Error(message);
    error.messages = messages;
    throw error;
  }

  return await response.json();
}

function handleCashflowSubmit(event) {
  event.preventDefault();
  if (!cashflowForm) return;
  clearCashflowError();
  clearCashflowMessages();
  setLoading(cashflowSubmitBtn, cashflowStatus, true, "Crunching…");

  const payload = buildCashFlowPayload();

  calculateCashFlow(payload)
    .then(displayCashflowResults)
    .catch((err) => {
      console.error(err);
      showCashflowError(err.message || "Unable to reach the backend service.");
      if (err.messages && err.messages.length > 0) {
        showCashflowMessages(err.messages);
      }
    })
    .finally(() => {
      setLoading(cashflowSubmitBtn, cashflowStatus, false);
    });

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
