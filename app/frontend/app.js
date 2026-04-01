(function () {
  const form = document.getElementById("search-form");
  const input = document.getElementById("query-input");
  const resultsSection = document.getElementById("results-section");
  const resultsGrid = document.getElementById("results-grid");
  const dealsSection = document.getElementById("deals-section");
  const dealsList = document.getElementById("deals-list");
  const noResults = document.getElementById("no-results");
  const loading = document.getElementById("loading-skeleton");
  const debugPanel = document.getElementById("debug-panel");
  const debugQuery = document.getElementById("debug-query");
  const debugIntent = document.getElementById("debug-intent");
  const debugConstraints = document.getElementById("debug-constraints");

  function formatCurrency(value) {
    return Number(value || 0).toLocaleString("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    });
  }

  function clearSections() {
    resultsGrid.innerHTML = "";
    dealsList.innerHTML = "";
    noResults.classList.add("hidden");
    resultsSection.classList.add("hidden");
    dealsSection.classList.add("hidden");
  }

  function showLoading(isLoading) {
    loading.classList.toggle("hidden", !isLoading);
  }

  function parseConstraints(structured) {
    const constraints = structured?.constraints || {};
    const list = [];
    if (constraints.budget && typeof constraints.budget.amount !== "undefined") {
      list.push(`budget ${constraints.budget.operator || "="} ${constraints.budget.amount}`);
    }
    if (Array.isArray(constraints.preferences) && constraints.preferences.length) {
      list.push(`preferences: ${constraints.preferences.join(", ")}`);
    }
    return list.length ? list.join(" | ") : "none";
  }

  function renderDebug(parsed) {
    debugQuery.textContent = parsed?.structured_query?.normalized_query || parsed?.clean_query?.normalized_text || "-";
    debugIntent.textContent = parsed?.intent_result?.intent || "-";
    debugConstraints.textContent = parseConstraints(parsed?.structured_query);
    debugPanel.classList.remove("hidden");
  }

  function renderResults(searchData) {
    const items = Array.isArray(searchData.results) ? searchData.results : [];
    const best = searchData.best_option || {};

    if (!items.length) {
      noResults.classList.remove("hidden");
      return;
    }

    items.forEach((item) => {
      const isBest = Boolean(
        item.name && best.name && item.platform && best.platform &&
          item.name === best.name &&
          String(item.platform).toLowerCase() === String(best.platform).toLowerCase()
      );

      const card = document.createElement("article");
      card.className = `card${isBest ? " best" : ""}`;

      const discountBadge = item.discount_percent ? `<span class="badge discount">${item.discount_percent}% off</span>` : "";
      const ratingBadge = item.rating ? `<span class="badge rating">⭐ ${item.rating}</span>` : "";

      card.innerHTML = `
        ${isBest ? '<span class="best-label">Best Choice</span>' : ""}
        <h3 class="product-name">${item.name || "Unknown Product"}</h3>
        <div class="price-row">
          <span class="price">${formatCurrency(item.price)}</span>
          ${item.original_price ? `<span class="original-price">${formatCurrency(item.original_price)}</span>` : ""}
        </div>
        <p class="meta"><strong>${(item.platform || "unknown").toUpperCase()}</strong> | Delivery ${item.delivery_time_minutes || "N/A"} min</p>
        <div class="badges">${discountBadge}${ratingBadge}</div>
      `;

      const button = document.createElement("button");
      button.className = "cta";
      button.type = "button";
      button.textContent = "View on Store";
      button.addEventListener("click", () => {
        if (typeof item.url === "string" && /^https?:\/\//i.test(item.url)) {
          window.open(item.url, "_blank", "noopener,noreferrer");
        }
      });

      card.appendChild(button);
      resultsGrid.appendChild(card);
    });

    resultsSection.classList.remove("hidden");
  }

  function renderDeals(searchData) {
    const deals = Array.isArray(searchData.deals) ? searchData.deals : [];
    if (!deals.length) return;

    deals.forEach((deal) => {
      const div = document.createElement("div");
      div.className = "deal-item";
      div.innerHTML = `
        <div><strong>${deal.product_name || "Product"}</strong></div>
        <div class="meta">${(deal.platform || "").toUpperCase()}</div>
        <div class="badges"><span class="badge discount">${deal.discount_percent || 0}% off</span></div>
      `;
      dealsList.appendChild(div);
    });

    dealsSection.classList.remove("hidden");
  }

  async function runSearch(query) {
    clearSections();
    showLoading(true);

    try {
      const parseResp = await fetch("/parse-query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!parseResp.ok) throw new Error("Unable to parse query");
      const parsed = await parseResp.json();
      renderDebug(parsed);

      const searchResp = await fetch("/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed),
      });

      if (!searchResp.ok) throw new Error("Unable to fetch search results");
      const data = await searchResp.json();

      renderResults(data);
      renderDeals(data);
    } catch (err) {
      noResults.classList.remove("hidden");
      noResults.querySelector("h2").textContent = "Unable to load results";
      noResults.querySelector("p").textContent = "Please try again in a moment.";
    } finally {
      showLoading(false);
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = input.value.trim();
    if (!query) return;
    runSearch(query);
  });
})();
