async function post(url, body) {
  const res = await fetch(url, { method: "POST", body });
  const data = await res.json().catch(() => ({ error: "Unexpected response from the server." }));
  if (!res.ok) throw new Error(data.error || "Request failed.");
  return data.text;
}

async function run(button, out, task) {
  button.disabled = true;
  out.hidden = false;
  out.className = "ai-out";
  out.textContent = "Thinking...";
  try {
    out.textContent = await task();
  } catch (err) {
    out.className = "ai-out error";
    out.textContent = err.message;
  } finally {
    button.disabled = false;
  }
}

const panel = document.getElementById("ai-panel");

document.getElementById("insights-btn").addEventListener("click", (e) => {
  const body = new FormData();
  body.append("month", panel.dataset.month);
  run(e.target, document.getElementById("insights-out"), () => post("/ai/insights", body));
});

document.getElementById("ask-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const form = e.target;
  run(form.querySelector("button"), document.getElementById("ask-out"), () => post("/ai/ask", new FormData(form)));
});
