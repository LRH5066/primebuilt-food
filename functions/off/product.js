/** POST /off/product: a product's details (form fields), checked, then passed on. */
import { account, goodCode, goodUuid, ip, json, overLimit, refuse, target } from './_shared.js';

// Only these fields may go through, each with its own check
const TEXT = { product_name: 150, brands: 100, quantity: 60, serving_size: 60 };
const FIXED = { lang: ['en'], add_countries: ['en:united-kingdom'], nutrition_data_per: ['100g'] };
const GRAMS = ['proteins', 'carbohydrates', 'sugars', 'fat', 'saturated-fat', 'fiber', 'salt']; // per 100 g, so 0–100
const MICROS = [
  'vitamin-a', 'vitamin-d', 'vitamin-e', 'vitamin-k', 'vitamin-c', 'vitamin-b1', 'vitamin-b2', 'vitamin-pp', 'pantothenic-acid', 'vitamin-b6',
  'vitamin-b9', 'vitamin-b12', 'biotin', 'potassium', 'calcium', 'phosphorus', 'magnesium', 'iron', 'zinc', 'copper',
  'manganese', 'selenium', 'chromium', 'molybdenum', 'iodine',
];
const UNITS = { kcal: ['kcal'], grams: ['g'], micro: ['mg', 'µg'] };

const num = (v) => (typeof v === 'string' && /^\d+(\.\d+)?$/.test(v.trim()) ? Number(v) : NaN);

/** The checked fields, or the reason they were turned away. */
export function checkFields(form) {
  const out = {};
  for (const [k, raw] of form.entries()) {
    const v = String(raw);
    if (['code', 'app_uuid', 'app_version'].includes(k)) continue;
    if (k in TEXT) {
      const t = v.trim();
      if (!t || t.length > TEXT[k] || /[<>{}]|https?:|www\./i.test(t)) return `“${k}” doesn’t look right`;
      out[k] = t;
    } else if (k in FIXED) {
      if (!FIXED[k].includes(v)) return `“${k}” isn’t allowed`;
      out[k] = v;
    } else if (k === 'nutriment_energy-kcal') {
      const n = num(v);
      if (!(n >= 0 && n <= 950)) return 'calories should be 0–950 per 100 g';
      out[k] = v;
    } else if (k === 'nutriment_energy-kcal_unit') {
      if (!UNITS.kcal.includes(v)) return 'calorie unit isn’t allowed';
      out[k] = v;
    } else if (k.startsWith('nutriment_')) {
      const unit = k.endsWith('_unit');
      const name = k.slice('nutriment_'.length, unit ? -'_unit'.length : undefined);
      if (GRAMS.includes(name)) {
        if (unit ? !UNITS.grams.includes(v) : !(num(v) >= 0 && num(v) <= 100)) return `${name} should be 0–100 g per 100 g`;
      } else if (MICROS.includes(name)) {
        if (unit ? !UNITS.micro.includes(v) : !(num(v) >= 0 && num(v) < 100000)) return `${name} doesn’t look right`;
      } else return `“${name}” isn’t allowed`;
      out[k] = v;
    } else return `“${k}” isn’t allowed`;
  }
  // Protein, carbs and fat can't add up to more than the whole 100 g
  const g = (n) => (out[`nutriment_${n}`] != null ? Number(out[`nutriment_${n}`]) : 0);
  if (g('proteins') + g('carbohydrates') + g('fat') > 105) return 'protein, carbs and fat add up to more than 100 g';
  if (g('sugars') > g('carbohydrates') + 1 && out.nutriment_carbohydrates != null) return 'sugars can’t be more than carbs';
  if (g('saturated-fat') > g('fat') + 1 && out.nutriment_fat != null) return 'saturated fat can’t be more than fat';
  // Calories can't be far below what protein, carbs and fat give (4 / 4 / 9 per gram).
  // Only that way round: alcohol adds calories the label doesn't split out, and sweeteners
  // like those in sugar-free gum count as carbs with fewer calories, so there's room for both.
  if (out['nutriment_energy-kcal'] != null && out.nutriment_proteins != null && out.nutriment_carbohydrates != null && out.nutriment_fat != null) {
    const est = g('proteins') * 4 + g('carbohydrates') * 4 + g('fat') * 9;
    const kcal = Number(out['nutriment_energy-kcal']);
    if (est > kcal * 1.8 + 60) return 'calories are too low for the protein, carbs and fat';
  }
  if (!Object.keys(out).length) return 'nothing to send';
  return out;
}

export async function onRequestPost({ request, env }) {
  const acc = account(env);
  if (!acc) return refuse('sharing is switched off', 503);
  let form;
  try {
    form = await request.formData();
  } catch {
    return refuse('not a form');
  }
  const code = form.get('code');
  const uuid = form.get('app_uuid');
  if (!goodCode(code)) return refuse('barcode should be 8–14 digits');
  if (!goodUuid(uuid)) return refuse('missing app code');
  if (overLimit(`p:${ip(request)}`, 20) || overLimit(`p:${uuid}`, 20)) return refuse('too many products this hour, try later', 429);
  const fields = checkFields(form);
  if (typeof fields === 'string') return refuse(fields, 422);

  const t = target(env);
  const version = String(form.get('app_version') || '1').slice(0, 12);
  const body = new URLSearchParams({ code, ...acc, app_name: 'PrimeBuilt', app_version: version, app_uuid: uuid, ...fields, comment: 'Added with the PrimeBuilt app' });
  const res = await fetch(`${t.base}/cgi/product_jqm2.pl`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': `PrimeBuilt/${version} (relay)`, ...t.auth }, body });
  const answer = await res.json().catch(() => null);
  if (!res.ok || !answer) return refuse(`Open Food Facts error (http ${res.status})`, 502);
  return json(200, { status: answer.status, status_verbose: answer.status_verbose });
}

