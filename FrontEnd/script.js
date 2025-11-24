// ----- DOM SELECTION -----

/**
 * Cache DOM elements used throughout the script.
 */
const form = document.getElementById("deal-form");
const submitBtn = document.getElementById("submit-btn");
const formStatusEl = document.getElementById("form-status");
const errorMessageEl = document.getElementById("error-message");

const resultsCard = document.getElementById("results-card");
const totalPurchaseCostsEl = document.getElementById(
  "result-total-purchase-costs"
);
const allInPercentEl = document.getElementById("result-all-in-percent");
const rule70El = document.getElementById("result-70-rule");
const maxAllowedPurchasePriceEl = document.getElementById(
  "result-max-allowed-purchase-price"
);
const diffPurchasePriceEl = document.getElementById(
  "result-difference-purchase-price"
);

// ----- UTILITY FUNCTIONS -----

/**
 * Safely parse a numeric input value.
 * Treats empty / invalid values as 0 to keep the request payload numeric.
 * @param {string} name - The field name / input name.
 * @returns {number}
 */
function getNumericValue(name) {
  const value = form.elements[name]?.value ?? "";
  const parsed = parseFloat(value);
  if (Number.isNaN(parsed)) {
    return 0;
  }
  return parsed;
}

/**
 * Format a number as currency with thousands separators and 2 decimals.
 * @param {number} value
 * @returns {string}
 */
function formatCurrency(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * Format a decimal as percentage with 2 decimals.
 * Example: 0.72 -> "72.00%"
 * @param {number} value
 * @returns {string}
 */
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

/**
 * Show loading state on the submit button and status text.
 */
function setLoading(isLoading) {
  if (isLoading) {
    submitBtn.disabled = true;
    submitBtn.textContent = "Calculating…";
    formStatusEl.textContent = "Contacting backend on localhost:8000…";
  } else {
    submitBtn.disabled = false;
    submitBtn.textContent = "Calculate";
    formStatusEl.textContent = "";
  }
}

/**
 * Show an error message in the UI.
 * @param {string} message
 */
function showError(message) {
  errorMessageEl.textContent = message;
  errorMessageEl.classList.add("visible");
}

/**
 * Clear any visible error message.
 */
function clearError() {
  errorMessageEl.textContent = "";
  errorMessageEl.classList.remove("visible");
}

/**
 * Populate results section with the response from the backend.
 * @param {object} data - Response JSON from backend.
 */
function displayResults(data) {
  const {
    total_purchase_costs,
    alllInPrecentFromARV,
    passes_70_rule,
    max_allowed_purchase_price_to_meet_70_rule,
    difference_in_purchase_price_to_meet_70_rule,
  } = data;

  totalPurchaseCostsEl.textContent = formatCurrency(total_purchase_costs);
  allInPercentEl.textContent = alllInPrecentFromARV;
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
    // If backend returns -1 or a negative number, show a friendly message.
    diffPurchasePriceEl.textContent = "Already meets 70% rule";
  }

  // 70% rule pill
  rule70El.classList.remove("pass", "fail");
  if (passes_70_rule) {
    rule70El.textContent = "PASS";
    rule70El.classList.add("pass");
  } else {
    rule70El.textContent = "FAIL";
    rule70El.classList.add("fail");
  }

  // Reveal results card
  resultsCard.hidden = false;
  resultsCard.classList.add("visible");
}

// ----- API LOGIC -----

/**
 * Build request payload from form data.
 * @returns {object}
 */
function buildPayload() {
  return {
    arv: getNumericValue("arv"),
    purchase_price: getNumericValue("purchase_price"),
    origination_points_percent: getNumericValue("origination_points_percent"),
    title_fees: getNumericValue("title_fees"),
    attorney_fees: getNumericValue("attorney_fees"),
    recording_fees: getNumericValue("recording_fees"),
    transfer_taxes: getNumericValue("transfer_taxes"),
    lender_underwriting_fees: getNumericValue("lender_underwriting_fees"),
    title_insurance: getNumericValue("title_insurance"),
    survey_cost: getNumericValue("survey_cost"),
    inspection_costs: getNumericValue("inspection_costs"),
    hml_underwriting_fee: getNumericValue("hml_underwriting_fee"),
    hml_processing_fee: getNumericValue("hml_processing_fee"),
    hml_appraisal_fee: getNumericValue("hml_appraisal_fee"),
    draw_setup_fee: getNumericValue("draw_setup_fee"),
    rehab_cost: getNumericValue("rehab_cost"),
    rehab_utilities_cost: getNumericValue("rehab_utilities_cost"),
  };
}

/**
 * Call the FastAPI backend to calculate all-in % of ARV.
 * @param {object} payload
 * @returns {Promise<object>}
 */
async function calculateAllInPercentage(payload) {
  const response = await fetch("http://localhost:8000/CalcPrecentageOfARVRes", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    // Try to surface error details if available
    let detail = "";
    try {
      const errorBody = await response.json();
      if (errorBody && (errorBody.detail || errorBody.message)) {
        detail = errorBody.detail || errorBody.message;
      }
    } catch {
      // ignore JSON parse errors
    }
    const message = detail || `Backend error (status ${response.status}).`;
    throw new Error(message);
  }

  return await response.json();
}

// ----- EVENT BINDING -----

/**
 * Handle form submission:
 *  - prevent default behavior
 *  - build payload
 *  - call backend
 *  - update UI with results or error
 */
async function handleFormSubmit(event) {
  event.preventDefault();

  clearError();
  setLoading(true);

  const payload = buildPayload();

  try {
    const data = await calculateAllInPercentage(payload);
    displayResults(data);
  } catch (err) {
    console.error(err);
    showError(
      err.message ||
        "Something went wrong while contacting the backend. Please ensure the FastAPI server is running on localhost:8000."
    );
  } finally {
    setLoading(false);
  }
}

// Attach submit handler once DOM is ready.
if (form) {
  form.addEventListener("submit", handleFormSubmit);
}


