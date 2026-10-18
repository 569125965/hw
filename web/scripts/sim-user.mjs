#!/usr/bin/env node
const API = process.env.BASE_API || "http://127.0.0.1:8000";
const WEB = process.env.BASE_WEB || "http://127.0.0.1:5173";

async function main() {
  const health = await fetch(`${API}/api/v1/health`).then((r) => r.json());
  if (health.status !== "ok") throw new Error("api unhealthy");
  const search = await fetch(`${API}/api/v1/stocks/search?q=宁德`).then((r) => r.json());
  const code = search.items[0].code;
  const research = await fetch(`${API}/api/v1/stocks/${code}/research`).then((r) => r.json());
  if (!research.forecast?.stance) throw new Error("missing forecast");
  const html = await fetch(WEB).then((r) => r.text());
  if (!html.includes("研盘")) throw new Error("web index missing brand");
  console.log("sim-user ok", research.name, research.forecast.stance);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
