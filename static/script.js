const form = document.getElementById("eval-form");
const submitBtn = document.getElementById("submit-btn");
const exampleBtn = document.getElementById("example-btn");
const resultsEl = document.getElementById("results");
const errorEl = document.getElementById("error");
const judgeBadges = document.getElementById("judge-badges");

const EXAMPLE = {
  customer_request: "Return damaged chocolate box and get refund",
  transcript:
    "Customer: Hi, my chocolate box arrived crushed and partially melted.\n" +
    "Agent: I'm sorry to hear that. Could you share your order number?\n" +
    "Customer: It's ORD-48213.\n" +
    "Agent: Thanks, I can see the order. I've authorized a return and a full refund of $45.99 will be issued to your original payment method within 3-5 business days.\n" +
    "Customer: Great, thank you!",
  system_state: "Return authorized, refund $45.99 initiated",
};

async function loadJudgeModes() {
  try {
    const res = await fetch("/api/judges");
    const data = await res.json();
    judgeBadges.innerHTML = Object.entries(data.modes)
      .map(([name, mode]) => `<span class="badge ${mode}">${name} · ${mode}</span>`)
      .join("");
  } catch (e) {
    // Non-fatal: badges are a nice-to-have.
  }
}

function renderResults(data) {
  errorEl.classList.add("hidden");
  resultsEl.classList.remove("hidden");

  document.getElementById("consensus-score").textContent = data.consensus_score.toFixed(1);
  document.getElementById("score-spread").textContent = data.score_spread.toFixed(1);

  const reviewEl = document.getElementById("review-flag");
  if (data.needs_human_review) {
    reviewEl.className = "review-flag warn";
    reviewEl.textContent = `⚠️ High disagreement (spread > ${data.review_threshold}) — flagged for human review`;
  } else {
    reviewEl.className = "review-flag ok";
    reviewEl.textContent = "✅ Judges agree — no human review needed";
  }

  const grid = document.getElementById("judge-results");
  grid.innerHTML = data.individual_results
    .map((r) => {
      const isError = r.mode === "error";
      const scoreText = r.score === null || r.score === undefined ? "—" : r.score.toFixed(1);
      return `
        <div class="judge-card ${isError ? "error" : ""}">
          <div class="name">${r.judge_name} <span class="mode-tag">${r.mode}</span></div>
          <div class="score">${scoreText}</div>
          <div class="reasoning">${r.reasoning}</div>
        </div>`;
    })
    .join("");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  submitBtn.textContent = "Running judges...";
  errorEl.classList.add("hidden");

  const payload = {
    customer_request: document.getElementById("customer_request").value,
    transcript: document.getElementById("transcript").value,
    system_state: document.getElementById("system_state").value,
  };

  try {
    const res = await fetch("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail ? JSON.stringify(detail.detail) : `Request failed (${res.status})`);
    }
    const data = await res.json();
    renderResults(data);
  } catch (err) {
    errorEl.textContent = `Error: ${err.message}`;
    errorEl.classList.remove("hidden");
    resultsEl.classList.add("hidden");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Run judges";
  }
});

exampleBtn.addEventListener("click", () => {
  document.getElementById("customer_request").value = EXAMPLE.customer_request;
  document.getElementById("transcript").value = EXAMPLE.transcript;
  document.getElementById("system_state").value = EXAMPLE.system_state;
});

loadJudgeModes();
