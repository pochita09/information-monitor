const ALLOWED_ORIGINS = new Set(["https://pochita09.github.io", "http://localhost:8787", "http://localhost:3000", "http://127.0.0.1:8787"]);
const REASONS = new Set(["既知", "浅い", "自分に無関係", "ソースが弱い"]);
const INDEX_KEY = "feedback:index", CONFIG_KEY = "config:global", INDEX_LIMIT = 500, MAX_BODY_BYTES = 16_384;
const DEFAULT_CONFIG = { topics: { "ai-models": { display_name: "AIモデル系", criteria: "あなたはAI情報のキュレーターです。重要なAIモデル、新機能、API変更、価格改定、研究成果、業界に大きな影響を与えるニュースを優先してください。", threshold: 6, sources: { "openai-news": true, "deepmind-blog": true, "anthropic-news": true, "anthropic-research": true } } }, run: { times: ["07:13", "13:17", "21:23"], keep_below_threshold: true, telegram_enabled: false } };
const KNOWN_TOPICS = new Set(Object.keys(DEFAULT_CONFIG.topics));
const KNOWN_SOURCES = new Map(Object.entries(DEFAULT_CONFIG.topics).map(([id, topic]) => [id, new Set(Object.keys(topic.sources))]));

function corsHeaders(origin) { return { "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "GET, POST, PUT, OPTIONS", "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "86400", Vary: "Origin" }; }
function json(data, status = 200, origin = null) { const headers = { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" }; if (origin && ALLOWED_ORIGINS.has(origin)) Object.assign(headers, corsHeaders(origin)); return new Response(JSON.stringify(data), { status, headers }); }
function allowedOrigin(request) { const origin = request.headers.get("Origin"); return origin && ALLOWED_ORIGINS.has(origin) ? origin : null; }
function requiredString(value, name, maxLength, errors) { if (typeof value !== "string" || !value.trim()) { errors.push(`${name} is required`); return ""; } const trimmed = value.trim(); if (trimmed.length > maxLength) errors.push(`${name} is too long`); return trimmed; }
function cloneDefaultConfig() { return structuredClone(DEFAULT_CONFIG); }
function validTime(value) { return typeof value === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(value); }

function validateConfig(input) {
  const errors = [];
  if (!input || typeof input !== "object" || Array.isArray(input)) return { errors: ["JSON object is required"] };
  const topics = input.topics, run = input.run;
  if (!topics || typeof topics !== "object" || Array.isArray(topics)) errors.push("topics is required");
  if (!run || typeof run !== "object" || Array.isArray(run)) errors.push("run is required");
  const normalized = cloneDefaultConfig();
  if (topics && typeof topics === "object" && !Array.isArray(topics)) {
    for (const [topicId, value] of Object.entries(topics)) {
      if (!KNOWN_TOPICS.has(topicId)) { errors.push(`unknown topic_id: ${topicId}`); continue; }
      if (!value || typeof value !== "object" || Array.isArray(value)) { errors.push(`topic ${topicId} must be an object`); continue; }
      const displayName = requiredString(value.display_name, `topics.${topicId}.display_name`, 80, errors);
      const criteria = requiredString(value.criteria, `topics.${topicId}.criteria`, 4_000, errors);
      const threshold = value.threshold;
      if (!Number.isInteger(threshold) || threshold < 1 || threshold > 10) errors.push(`topics.${topicId}.threshold must be 1..10`);
      if (!value.sources || typeof value.sources !== "object" || Array.isArray(value.sources)) errors.push(`topics.${topicId}.sources is required`);
      const sources = {};
      for (const [sourceId, enabled] of Object.entries(value.sources || {})) {
        if (!KNOWN_SOURCES.get(topicId).has(sourceId)) { errors.push(`unknown source_id: ${sourceId}`); continue; }
        if (typeof enabled !== "boolean") errors.push(`topics.${topicId}.sources.${sourceId} must be boolean`);
        else sources[sourceId] = enabled;
      }
      for (const sourceId of KNOWN_SOURCES.get(topicId)) if (!(sourceId in sources)) errors.push(`topics.${topicId}.sources.${sourceId} is required`);
      normalized.topics[topicId] = { display_name: displayName, criteria, threshold, sources };
    }
    for (const topicId of KNOWN_TOPICS) if (!(topicId in topics)) errors.push(`topics.${topicId} is required`);
  }
  if (run && typeof run === "object" && !Array.isArray(run)) {
    if (!Array.isArray(run.times) || run.times.length < 1 || run.times.length > 12 || !run.times.every(validTime)) errors.push("run.times must contain 1..12 HH:MM values");
    else normalized.run.times = [...new Set(run.times)].sort();
    for (const key of ["keep_below_threshold", "telegram_enabled"]) {
      if (typeof run[key] !== "boolean") errors.push(`run.${key} must be boolean`); else normalized.run[key] = run[key];
    }
  }
  return errors.length ? { errors } : { config: normalized };
}

function validateFeedback(input) {
  const errors = [];
  if (!input || typeof input !== "object" || Array.isArray(input)) return { errors: ["JSON object is required"] };
  const item_id = requiredString(input.item_id, "item_id", 64, errors); if (item_id && !/^[a-f0-9]{64}$/i.test(item_id)) errors.push("item_id is invalid");
  const topic_id = requiredString(input.topic_id, "topic_id", 80, errors); if (topic_id && !/^[a-z0-9][a-z0-9-]*$/i.test(topic_id)) errors.push("topic_id is invalid");
  const vote = input.vote; if (vote !== "up" && vote !== "down") errors.push("vote must be up or down");
  if (vote === "down" && (typeof input.reason !== "string" || !REASONS.has(input.reason))) errors.push("reason is required and must be allowed for down vote"); if (vote === "up" && input.reason != null) errors.push("reason must be null for up vote");
  const score = input.score; if (!Number.isInteger(score) || score < 1 || score > 10) errors.push("score must be an integer from 1 to 10");
  const title = requiredString(input.title, "title", 300, errors), summary = requiredString(input.summary, "summary", 2_000, errors), source = requiredString(input.source, "source", 120, errors), url = requiredString(input.url, "url", 2_048, errors); try { if (url) new URL(url); } catch { errors.push("url is invalid"); }
  return errors.length ? { errors } : { feedback: { item_id, topic_id, vote, reason: vote === "down" ? input.reason : null, score, title, summary, source, url } };
}
async function readJson(request) { const text = await request.text(); if (new TextEncoder().encode(text).length > MAX_BODY_BYTES) return { error: "request body is too large", status: 413 }; try { return { value: JSON.parse(text) }; } catch { return { error: "invalid JSON", status: 400 }; } }
async function getIndex(kv) { const value = await kv.get(INDEX_KEY, "json"); return Array.isArray(value) ? value.filter((item) => typeof item === "string") : []; }
async function saveFeedback(kv, feedback) { const record = { ...feedback, created_at: new Date().toISOString() }; await kv.put(`feedback:${record.item_id}`, JSON.stringify(record)); const index = await getIndex(kv); await kv.put(INDEX_KEY, JSON.stringify([record.item_id, ...index.filter((id) => id !== record.item_id)].slice(0, INDEX_LIMIT))); return record; }
async function listFeedback(kv) { return (await Promise.all((await getIndex(kv)).map((id) => kv.get(`feedback:${id}`, "json")))).filter((value) => value && typeof value === "object"); }

async function handle(request, env) {
  const url = new URL(request.url), origin = allowedOrigin(request), isConfigGet = url.pathname === "/config" && request.method === "GET";
  if (request.method === "OPTIONS") return origin ? new Response(null, { status: 204, headers: corsHeaders(origin) }) : json({ error: "origin is not allowed" }, 403);
  if (!origin && !isConfigGet) return json({ error: "origin is not allowed" }, 403);
  if (!env.FEEDBACK) return json({ error: "storage is not configured" }, 500, origin);
  if (isConfigGet) return json({ config: (await env.FEEDBACK.get(CONFIG_KEY, "json")) || cloneDefaultConfig() }, 200, origin);
  if (url.pathname === "/config" && request.method === "PUT") { if (!origin) return json({ error: "origin is not allowed" }, 403); const parsed = await readJson(request); if (parsed.error) return json({ error: parsed.error }, parsed.status, origin); const result = validateConfig(parsed.value); if (result.errors) return json({ error: "validation failed", details: result.errors }, 400, origin); await env.FEEDBACK.put(CONFIG_KEY, JSON.stringify(result.config)); return json({ config: result.config }, 200, origin); }
  if (url.pathname === "/feedback" && request.method === "GET") return json({ feedback: await listFeedback(env.FEEDBACK) }, 200, origin);
  if (url.pathname.startsWith("/feedback/") && request.method === "GET") { const id = decodeURIComponent(url.pathname.slice(10)); if (!/^[a-f0-9]{64}$/i.test(id)) return json({ error: "item_id is invalid" }, 400, origin); const feedback = await env.FEEDBACK.get(`feedback:${id}`, "json"); return feedback ? json({ feedback }, 200, origin) : json({ error: "feedback not found" }, 404, origin); }
  if (url.pathname === "/feedback" && request.method === "POST") { const parsed = await readJson(request); if (parsed.error) return json({ error: parsed.error }, parsed.status, origin); const result = validateFeedback(parsed.value); return result.errors ? json({ error: "validation failed", details: result.errors }, 400, origin) : json({ feedback: await saveFeedback(env.FEEDBACK, result.feedback) }, 200, origin); }
  return json({ error: "method or path is not allowed" }, 405, origin);
}
export default { fetch: (request, env) => handle(request, env) };
export { handle, validateFeedback, validateConfig, DEFAULT_CONFIG };
