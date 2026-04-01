(function () {
  const form = document.getElementById("search-form");
  const input = document.getElementById("query-input");
  const recipeForm = document.getElementById("recipe-form");
  const recipeInput = document.getElementById("recipe-query-input");
  const recipeServingsInput = document.getElementById("recipe-servings-input");
  const cartForm = document.getElementById("cart-form");
  const cartItemsInput = document.getElementById("cart-items-input");
  const resultsSection = document.getElementById("results-section");
  const resultsGrid = document.getElementById("results-grid");
  const recipeResultsSection = document.getElementById("recipe-results-section");
  const recipeResultsList = document.getElementById("recipe-results-list");
  const cartResultsSection = document.getElementById("cart-results-section");
  const cartResultsList = document.getElementById("cart-results-list");
  const dealsSection = document.getElementById("deals-section");
  const dealsList = document.getElementById("deals-list");
  const emptyState = document.getElementById("empty-state");
  const loading = document.getElementById("loading-skeleton");
  const debugPanel = document.getElementById("debug-panel");
  const debugQuery = document.getElementById("debug-query");
  const debugIntent = document.getElementById("debug-intent");
  const debugConstraints = document.getElementById("debug-constraints");
  const debugSecondaryIntents = document.getElementById("debug-secondary-intents");
  const debugExecutionMode = document.getElementById("debug-execution-mode");
  const debugCandidatePaths = document.getElementById("debug-candidate-paths");
  const debugSignals = document.getElementById("debug-signals");

  const PLATFORM_LOGOS = {
    blinkit: "🟢",
    zepto: "🟣",
    instamart: "🟠",
    bigbasket: "🛒",
    jiomart: "🔵",
    dmart: "🟡",
  };

  function formatCurrency(value) {
    return Number(value || 0).toLocaleString("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    });
  }

  function clearSections() {
    resultsGrid.innerHTML = "";
    recipeResultsList.innerHTML = "";
    cartResultsList.innerHTML = "";
    dealsList.innerHTML = "";
    emptyState.classList.add("hidden");
    resultsSection.classList.add("hidden");
    recipeResultsSection.classList.add("hidden");
    cartResultsSection.classList.add("hidden");
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
    debugSecondaryIntents.textContent = (parsed?.intent_result?.secondary_intents || []).join(", ") || "none";
    debugExecutionMode.textContent = parsed?.execution_plan?.mode || "-";
    debugCandidatePaths.textContent = String((parsed?.candidate_paths || []).length);
    const signalKeys = Object.keys(parsed?.platform_signals || {});
    debugSignals.textContent = signalKeys.length ? signalKeys.join(", ") : "none";
    debugPanel.classList.remove("hidden");
  }

  function renderDebugFromMetadata(metadata) {
    debugQuery.textContent = metadata?.normalized_query || "-";
    debugIntent.textContent = metadata?.intent || "-";
    debugConstraints.textContent = JSON.stringify(metadata?.constraints || {});
    debugSecondaryIntents.textContent = "n/a";
    debugExecutionMode.textContent = "direct endpoint";
    debugCandidatePaths.textContent = "n/a";
    debugSignals.textContent = "n/a";
    debugPanel.classList.remove("hidden");
  }

  function platformLabel(platform) {
    const key = String(platform || "").toLowerCase();
    return `${PLATFORM_LOGOS[key] || "🏬"} ${(platform || "unknown").toUpperCase()}`;
  }

  function getSafeUrl(url) {
    if (typeof url !== "string") return "";
    return /^https?:\/\//i.test(url) ? url : "";
  }

  function renderResults(searchData) {
    const items = Array.isArray(searchData.results) ? searchData.results : [];
    const best = searchData.best_option || {};

    if (!items.length) {
      emptyState.classList.remove("hidden");
      emptyState.querySelector("h2").textContent = "🧺 No products found";
      emptyState.querySelector("p").textContent = "Try widening your budget, keywords, or constraints.";
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

      const safeUrl = getSafeUrl(item.url);
      card.innerHTML = `
        ${isBest ? '<span class="best-label">Best Choice</span>' : ""}
        <h3 class="product-name">${item.name || "Unknown Product"}</h3>
        <div class="price-row">
          <span class="price">${formatCurrency(item.price)}</span>
          ${item.original_price ? `<span class="original-price">${formatCurrency(item.original_price)}</span>` : ""}
        </div>
        <p class="meta"><strong>${platformLabel(item.platform)}</strong> | Delivery ${item.delivery_time_minutes || "N/A"} min</p>
        <div class="badges">${discountBadge}${ratingBadge}</div>
      `;

      const button = document.createElement("button");
      button.className = "cta";
      button.type = "button";
      button.textContent = safeUrl ? "View on Store" : "Link not available";
      button.disabled = !safeUrl;
      button.addEventListener("click", () => {
        if (safeUrl) {
          window.open(safeUrl, "_blank", "noopener,noreferrer");
        }
      });

      card.appendChild(button);
      resultsGrid.appendChild(card);
    });

    resultsSection.classList.remove("hidden");
  }

  function renderDeals(searchData) {
    const deals = Array.isArray(searchData.deals) ? searchData.deals : [];
    if (!deals.length) {
      dealsSection.classList.add("hidden");
      return;
    }

    deals.forEach((deal) => {
      const div = document.createElement("div");
      div.className = "deal-item";
      div.innerHTML = `
        <div><strong>${deal.product_name || "Product"}</strong></div>
        <div class="meta">${platformLabel(deal.platform)}</div>
        <div class="badges"><span class="badge discount">${deal.discount_percent || 0}% off</span></div>
      `;
      dealsList.appendChild(div);
    });

    dealsSection.classList.remove("hidden");
  }

  function renderRecipe(data) {
    const items = Array.isArray(data.results) ? data.results : [];
    if (!items.length) {
      emptyState.classList.remove("hidden");
      emptyState.querySelector("h2").textContent = "🍲 No recipe ingredients mapped";
      emptyState.querySelector("p").textContent = "Try a different recipe query.";
      return;
    }

    items.forEach((row) => {
      const ingredient = row.ingredient || {};
      const cheapest = row.cheapest_option || {};
      const card = document.createElement("article");
      card.className = "card";
      card.innerHTML = `
        <h3 class="product-name">${ingredient.name || "Ingredient"}</h3>
        <p class="meta">Quantity: ${ingredient.quantity || "-"} ${ingredient.unit || ""}</p>
        <div class="price-row">
          <span class="price">${formatCurrency(cheapest.price)}</span>
        </div>
        <p class="meta">Cheapest on: ${platformLabel(cheapest.platform)}</p>
        <p class="meta">Available on: ${(row.available_on || []).map(platformLabel).join(", ") || "N/A"}</p>
      `;
      recipeResultsList.appendChild(card);
    });
    recipeResultsSection.classList.remove("hidden");
  }

  function renderCart(data) {
    const groups = Array.isArray(data.results) ? data.results : [];
    if (!groups.length) {
      emptyState.classList.remove("hidden");
      emptyState.querySelector("h2").textContent = "🛍️ Cart optimization returned no groups";
      emptyState.querySelector("p").textContent = "Try different cart items.";
      return;
    }
    groups.forEach((group) => {
      const card = document.createElement("article");
      card.className = "card";
      card.innerHTML = `
        <h3 class="product-name">${platformLabel(group.platform)}</h3>
        <p class="meta">Subtotal: ${formatCurrency(group.subtotal)}</p>
        <p class="meta">${(group.items || []).map((i) => `${i.name} (${formatCurrency(i.price)})`).join(" • ")}</p>
      `;
      cartResultsList.appendChild(card);
    });
    const summary = document.createElement("article");
    summary.className = "card best";
    summary.innerHTML = `
      <span class="best-label">Optimized Summary</span>
      <h3 class="product-name">Total optimized cost</h3>
      <div class="price-row"><span class="price">${formatCurrency(data.best_option?.total_optimized_cost)}</span></div>
      <p class="meta">Savings: ${formatCurrency(data.best_option?.savings)}</p>
    `;
    cartResultsList.appendChild(summary);
    cartResultsSection.classList.remove("hidden");
  }

  function parseCartItems(text) {
    return String(text || "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [nameRaw, qtyRaw] = line.split(",");
        const name = (nameRaw || "").trim();
        const quantity = Math.max(1, Number((qtyRaw || "1").trim()) || 1);
        return { name, quantity };
      })
      .filter((item) => item.name);
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
      emptyState.classList.remove("hidden");
      emptyState.querySelector("h2").textContent = "Unable to load results";
      emptyState.querySelector("p").textContent = "Please try again in a moment.";
    } finally {
      showLoading(false);
    }
  }

  async function runRecipe(query, servings) {
    clearSections();
    showLoading(true);
    try {
      const resp = await fetch("/recipe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, servings }),
      });
      if (!resp.ok) throw new Error("Unable to fetch recipe");
      const data = await resp.json();
      renderRecipe(data);
      renderDeals(data);
      renderDebugFromMetadata(data.metadata);
    } catch (err) {
      emptyState.classList.remove("hidden");
      emptyState.querySelector("h2").textContent = "Unable to load recipe flow";
      emptyState.querySelector("p").textContent = "Please try again in a moment.";
    } finally {
      showLoading(false);
    }
  }

  async function runCartOptimization(items) {
    clearSections();
    showLoading(true);
    try {
      const resp = await fetch("/cart-optimization", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
      });
      if (!resp.ok) throw new Error("Unable to optimize cart");
      const data = await resp.json();
      renderCart(data);
      renderDeals(data);
      renderDebugFromMetadata(data.metadata);
    } catch (err) {
      emptyState.classList.remove("hidden");
      emptyState.querySelector("h2").textContent = "Unable to optimize cart";
      emptyState.querySelector("p").textContent = "Please try again in a moment.";
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

  recipeForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = recipeInput.value.trim();
    const servings = Number(recipeServingsInput.value) || 2;
    if (!query) return;
    runRecipe(query, servings);
  });

  cartForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const items = parseCartItems(cartItemsInput.value);
    if (!items.length) return;
    runCartOptimization(items);
  });
})();
