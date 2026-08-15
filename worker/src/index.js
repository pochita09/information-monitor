const ALLOWED_ORIGINS = new Set(["https://pochita09.github.io", "http://localhost:8787", "http://localhost:3000", "http://127.0.0.1:8787"]);
const REASONS = new Set(["既知", "浅い", "自分に無関係", "ソースが弱い"]);
const INDEX_KEY = "feedback:index";
const INDEX_LIMIT = 500;
const MAX_BODY_BYTES = 8_192;

function corsHeaders(origin) { return { "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "86400", Vary: "Origin" }; }
function json(data, status = 200, origin = null) { const headers = { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" }; if (origin && ALLOWED_ORIGINS.has(origin)) Object.assign(headers, corsHeaders(origin)); return new Response(JSON.stringify(data), { status, headers }); }
function requestOrigin(request) { const origin = request.headers.get("Origin"); return origin && ALLOWED_ORIGINS.has(origin) ? origin : null; }
function stringField(value, name, maxLength, errors) { if (typeof value !== "string" || !value.trim()) { errors.push(`${name} is required`); return ""; } const trimmed = value.trim(); if (trimmed.length > maxLength) errors.push(`${name} is too long`); return trimmed; }

function validateFeedback(input) {
  const errors = [];
  if (!input || typeof input !== "object" || Array.isArray(input)) return { errors: ["JSON object is required"] };
  const item_id = stringField(input.item_id, "item_id", 64, errors);
  if (item_id && !/^[a-f0-9]{64}$/i.test(item_id)) errors.push("item_id is invalid");
  const topic_id = stringField(input.topic_id, "topic_id", 80, errors);
  if (topic_id && !/^[a-z0-9][a-z0-9-]*$/i.test(topic_id)) errors.push("topic_id is invalid");
  const vote = input.vote;
  if (vote !== "up" && vote !== "down") errors.push("vote must be up or down");
  if (vote === "down" && (typeof input.reason !== "string" || !REASONS.has(input.reason))) errors.push("reason is required and must be allowed for down vote");
  if (vote === "up" && input.reason != null) errors.push("reason must be null for up vote");
  const score = input.score;
  if (!Number.isInteger(score) || score < 1 || score > 10) errors.push("score must be an integer from 1 to 10");
  const title = stringField(input.title, "title", 300, errors);
  const summary = stringField(input.summary, "summary", 2_000, errors);
  const source = stringField(input.source, "source", 120, errors);
  const url = stringField(input.url, "url", 2_048, errors);
  try { if (url) new URL(url); } catch { errors.push("url is invalid"); }
  return errors.length ? { errors } : { feedback: { item_id, topic_id, vote, reason: vote === "down" ? input.reason : null, score, title, summary, source, url } };
}
async function getIndex(kv) { const value = await kv.get(INDEX_KEY, "json"); return Array.isArray(value) ? value.filter((item) => typeof item === "string") : []; }
async function saveFeedback(kv, feedback) { const record = { ...feedback, created_at: new Date().toISOString() }; await kv.put(`feedback:${record.item_id}`, JSON.stringify(record)); const index = await getIndex(kv); await kv.put(INDEX_KEY, JSON.stringify([record.item_id, ...index.filter((id) => id !== record.item_id)].slice(0, INDEX_LIMIT))); return record; }
async function listFeedback(kv) { return (await Promise.all((await getIndex(kv)).map((id) => kv.get(`feedback:${id}`, "json")))).filter((value) => value && typeof value === "object"); }

async function handle(request, env) {
  const origin = requestOrigin(request);
  if (request.method === "OPTIONS") return origin ? new Response(null, { status: 204, headers: corsHeaders(origin) }) : json({ error: "origin is not allowed" }, 403);
  if (!origin) return json({ error: "origin is not allowed" }, 403);
  const url = new URL(request.url);
  if (!env.FEEDBACK) return json({ error: "feedback storage is not configured" }, 500, origin);
  if (url.pathname === "/feedback" && request.method === "GET") return json({ feedback: await listFeedback(env.FEEDBACK) }, 200, origin);
  if (url.pathname.startsWith("/feedback/") && request.method === "GET") { const id = decodeURIComponent(url.pathname.slice(10)); if (!/^[a-f0-9]{64}$/i.test(id)) return json({ error: "item_id is invalid" }, 400, origin); const feedback = await env.FEEDBACK.get(`feedback:${id}`, "json"); return feedback ? json({ feedback }, 200, origin) : json({ error: "feedback not found" }, 404, origin); }
  if (url.pathname === "/feedback" && request.method === "POST") { const length = Number(request.headers.get("Content-Length") || "0"); if (length > MAX_BODY_BYTES) return json({ error: "request body is too large" }, 413, origin); const text = await request.text(); if (new TextEncoder().encode(text).length > MAX_BODY_BYTES) return json({ error: "request body is too large" }, 413, origin); let body; try { body = JSON.parse(text); } catch { return json({ error: "invalid JSON" }, 400, origin); } const result = validateFeedback(body); return result.errors ? json({ error: "validation failed", details: result.errors }, 400, origin) : json({ feedback: await saveFeedback(env.FEEDBACK, result.feedback) }, 200, origin); }
  return json({ error: "method or path is not allowed" }, 405, origin);
}
export default { fetch: (request, env) => handle(request, env) };
export { handle, validateFeedback };
