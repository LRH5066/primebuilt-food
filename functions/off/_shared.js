/**
 * PrimeBuilt → Open Food Facts relay (Cloudflare Pages Function).
 *
 * The app sends a product (or a pack photo) here; this adds the PrimeBuilt account's
 * login, which lives only in this site's Cloudflare settings (OFF_USER, OFF_PASSWORD,
 * OFF_MODE = "live" or "test"), and passes it on. Nothing else can be done through it:
 * no logins, no account changes, no deleting. Nothing is stored here.
 */

export const json = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });

export const refuse = (why, status = 400) => json(status, { status: 0, status_verbose: why });

/** Their real site, or their test site (which sits behind a published "off"/"off" password). */
export function target(env) {
  const live = String(env.OFF_MODE || '').toLowerCase() === 'live';
  return { base: live ? 'https://world.openfoodfacts.org' : 'https://world.openfoodfacts.net', auth: live ? {} : { Authorization: 'Basic b2ZmOm9mZg==' }, live };
}

export const goodCode = (c) => typeof c === 'string' && /^\d{8,14}$/.test(c);
export const goodUuid = (u) => typeof u === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(u);

// ---------------------------------------------------------------------------
// A limit per hour. Kept in memory: each Cloudflare server keeps its own count, so this
// slows a flood down rather than being exact (the app sends a handful a week at most).
// ---------------------------------------------------------------------------
const HOUR = 3600_000;
const seen = new Map(); // key -> times (ms)
export function overLimit(key, max) {
  const now = Date.now();
  const list = (seen.get(key) || []).filter((t) => now - t < HOUR);
  if (list.length >= max) {
    seen.set(key, list);
    return true;
  }
  list.push(now);
  seen.set(key, list);
  if (seen.size > 5000) for (const [k, v] of seen) if (!v.some((t) => now - t < HOUR)) seen.delete(k);
  return false;
}

export function ip(request) {
  return request.headers.get('CF-Connecting-IP') || 'unknown';
}

export function account(env) {
  return env.OFF_USER && env.OFF_PASSWORD ? { user_id: env.OFF_USER, password: env.OFF_PASSWORD } : null;
}
