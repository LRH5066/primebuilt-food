/** POST /off/photo: one pack photo (front or nutrition label), checked, then passed on. */
import { account, goodCode, goodUuid, ip, json, overLimit, refuse, target } from './_shared.js';

const MAX_BYTES = 8 * 1024 * 1024;

/** A real JPEG or PNG (checked from the file's first bytes, not its name). */
export function isImage(bytes) {
  const b = new Uint8Array(bytes.slice(0, 8));
  const jpeg = b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff;
  const png = b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47;
  return jpeg ? 'image/jpeg' : png ? 'image/png' : null;
}

export async function onRequestPost({ request, env }) {
  const acc = account(env);
  if (!acc) return refuse('sharing is switched off', 503);
  if (Number(request.headers.get('Content-Length') || 0) > MAX_BYTES + 100_000) return refuse('photo too big', 413);
  let form;
  try {
    form = await request.formData();
  } catch {
    return refuse('not a form');
  }
  const code = form.get('code');
  const uuid = form.get('app_uuid');
  const kind = form.get('kind');
  const file = form.get('photo');
  if (!goodCode(code)) return refuse('barcode should be 8–14 digits');
  if (!goodUuid(uuid)) return refuse('missing app code');
  if (kind !== 'front' && kind !== 'nutrition') return refuse('photo should be the front or the label');
  if (!file || typeof file === 'string') return refuse('no photo');
  if (overLimit(`i:${ip(request)}`, 40) || overLimit(`i:${uuid}`, 40)) return refuse('too many photos this hour, try later', 429);
  const bytes = await file.arrayBuffer();
  if (bytes.byteLength > MAX_BYTES || bytes.byteLength < 5000) return refuse('photo size doesn’t look right', 413);
  const type = isImage(bytes);
  if (!type) return refuse('that isn’t a photo', 415);

  const t = target(env);
  const version = String(form.get('app_version') || '1').slice(0, 12);
  const field = `${kind}_en`;
  const out = new FormData();
  for (const [k, v] of Object.entries({ code, ...acc, app_name: 'PrimeBuilt', app_version: version, app_uuid: uuid, imagefield: field })) out.append(k, v);
  out.append(`imgupload_${field}`, new Blob([bytes], { type }), `${field}.${type === 'image/png' ? 'png' : 'jpg'}`);
  const res = await fetch(`${t.base}/cgi/product_image_upload.pl`, { method: 'POST', headers: { 'User-Agent': `PrimeBuilt/${version} (relay)`, ...t.auth }, body: out });
  const answer = await res.json().catch(() => null);
  if (!res.ok || !answer) return refuse(`Open Food Facts error (http ${res.status})`, 502);
  return json(200, { status: answer.status, error: answer.error });
}

