// if the page does not start (e.g. an old cache or a lost connection), offer a reload instead of a black screen.
// A file of its own (not inline): the Content-Security-Policy of the pages allows only scripts from the app (main.py).
setTimeout(() => {
  const a = document.getElementById("app");
  if (!a || a.children.length) return;
  const btn = document.createElement("button");
  btn.textContent = "⟳ Reload";
  btn.style.cssText = "font:inherit;padding:10px 18px;border-radius:10px;border:0;background:#5b5bd6;color:#fff";
  btn.addEventListener("click", () => location.reload());
  const p = document.createElement("p");
  p.textContent = "Family Quest";
  const inner = document.createElement("div");
  inner.append(p, btn);
  const box = document.createElement("div");
  box.style.cssText = "min-height:80vh;display:grid;place-items:center;font:16px system-ui;color:#888;text-align:center";
  box.append(inner);
  a.replaceChildren(box);
}, 10000);
