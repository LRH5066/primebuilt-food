"""
PrimeBuilt food search: builds small static search files from Open Food Facts.

Runs daily on GitHub Actions (see .github/workflows/build.yml):
  python3 build.py en.openfoodfacts.org.products.csv.gz site

Output (served as plain files by Cloudflare Pages):
  site/index.json          manifest: version date, columns, which file holds each word prefix
  site/s/<prefix>.json     products with a word starting with <prefix> (most scanned first)
  site/_headers            cache rules
  site/ATTRIBUTION.txt     licence + credit

The app downloads index.json (twice a day) and then only the one small file
for what you type, and searches it on the phone.

Data: Open Food Facts (https://world.openfoodfacts.org), Open Database License (ODbL).
This extract (UK products with nutrition) is offered under the same licence.
"""
import csv, gzip, json, os, re, sys, unicodedata, datetime, collections

SRC, OUT = sys.argv[1], sys.argv[2]
MAX_PER_FILE = 3000        # most-scanned products kept per prefix file
MAX_FILES = 19500          # Cloudflare Pages allows 20,000 files
# Words too common to be useful in a two-word file
STOP = {'and', 'with', 'the', 'in', 'of', 'for', 'a', 'to', 'on', 'or', 'no', 'de', 'en', 'et', 'la', 'le', 'per', 'from', 'free', 'pack', 'x'}
SPLIT_AT = 1200            # a 2-letter group bigger than this is split into 3-letter files
csv.field_size_limit(1 << 30)

COLS = ['code', 'name', 'brand', 'kcal', 'protein', 'carbs', 'fat', 'fibre', 'sugars', 'satFat', 'salt', 'alcohol', 'servingG', 'servingText', 'packG', 'packText', 'liquid', 'scans', 'img', 'shops']

def num(v):
    try:
        x = float(v)
        return x if x == x and x >= 0 else None
    except (TypeError, ValueError):
        return None

def r(v, dp=1):
    return None if v is None else round(v, dp)

def ascii_fold(s):
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()

def folder_of(code):
    # Open Food Facts stores photos in folders made from the barcode: 5060360507736 -> 506/036/050/7736
    if len(code) <= 8:
        return code
    c = code.zfill(13)
    return f'{c[0:3]}/{c[3:6]}/{c[6:9]}/{c[9:]}'

def image_key(code, url):
    # Keep only a few characters per product ("front_en.12"); the app rebuilds the web address
    m = re.search(r'/images/products/(.+)/([^/]+?)\.\d+\.jpg$', url or '')
    if not m:
        return None
    folder, key = m.group(1), m.group(2)
    return key if folder == folder_of(code) else f'/{folder}/{key}'

# Supermarkets the product is listed as sold in (for the app's "Shop" filter)
SHOP_TAGS = {
    'tesco': 'tesco', 'sainsbury-s': 'sainsburys', 'sainsburys': 'sainsburys', 'asda': 'asda', 'morrisons': 'morrisons',
    'aldi': 'aldi', 'lidl': 'lidl', 'co-op': 'coop', 'coop': 'coop', 'the-co-operative': 'coop', 'co-operative': 'coop',
    'marks-spencer': 'ms', 'marks-and-spencer': 'ms', 'm-s': 'ms', 'waitrose': 'waitrose', 'iceland': 'iceland', 'ocado': 'ocado',
}

def shops_of(tags):
    out = []
    for t in tags.split(','):
        t = t.strip().split(':')[-1]
        s = SHOP_TAGS.get(t)
        if s and s not in out:
            out.append(s)
    return ','.join(out) or None

def words_of(text):
    return [w for w in re.split(r'[^a-z0-9]+', ascii_fold(text)) if w]

def main():
    keep = []
    extra_words = {}  # code -> all brands (searchable, not shown)
    with gzip.open(SRC, 'rt', encoding='utf-8', errors='replace', newline='') as f:
        rd = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
        head = next(rd)
        ix = {h: i for i, h in enumerate(head)}
        def g(row, k):
            i = ix.get(k)
            return row[i] if i is not None and i < len(row) else ''
        n = 0
        for row in rd:
            n += 1
            if 'en:united-kingdom' not in g(row, 'countries_tags'):
                continue
            code = g(row, 'code').strip()
            name = (g(row, 'product_name_en') or g(row, 'product_name') or g(row, 'generic_name_en') or g(row, 'generic_name')).strip()
            # Some products are just called "GetPRO": add the description so you can tell them apart
            desc = (g(row, 'generic_name_en') or g(row, 'generic_name')).strip()
            if desc and len(name) < 16 and desc.lower() not in name.lower():
                name = f'{name} {desc}'
            if not code.isdigit() or not name:
                continue
            kcal = num(g(row, 'energy-kcal_100g'))
            if kcal is None and num(g(row, 'energy_100g')) is not None:
                kcal = num(g(row, 'energy_100g')) / 4.184
            if kcal is None or kcal > 950:
                continue
            salt = num(g(row, 'salt_100g'))
            if salt is None and num(g(row, 'sodium_100g')) is not None:
                salt = num(g(row, 'sodium_100g')) * 2.5
            qty = g(row, 'quantity').strip()
            unit = g(row, 'product_quantity_unit').strip().lower()
            liquid = 1 if unit == 'ml' or re.search(r'\d\s*(ml|cl|l)\b', qty, re.I) else 0
            sq = num(g(row, 'serving_quantity'))
            pq = num(g(row, 'product_quantity'))
            brands_all = g(row, 'brands')
            brand = brands_all.split(',')[0].strip()
            keep.append([
                code, name[:90], brand[:40], round(kcal), r(num(g(row, 'proteins_100g'))), r(num(g(row, 'carbohydrates_100g'))),
                r(num(g(row, 'fat_100g'))), r(num(g(row, 'fiber_100g'))), r(num(g(row, 'sugars_100g'))), r(num(g(row, 'saturated-fat_100g'))),
                r(salt, 2), r(num(g(row, 'alcohol_100g'))),
                r(sq) if sq and sq < 5000 else None, g(row, 'serving_size').strip()[:24] or None,
                r(pq) if pq and pq <= 3000 else None, qty[:24] or None, liquid, int(num(g(row, 'unique_scans_n')) or 0),
                image_key(code, g(row, 'image_front_small_url') or g(row, 'image_small_url')),
                shops_of(g(row, 'stores_tags')),
            ])
            extra_words[code] = brands_all
    print(f'read {n} rows, kept {len(keep)} UK products with nutrition')
    missing = [c for c in ('code', 'product_name', 'brands', 'countries_tags', 'energy-kcal_100g', 'proteins_100g', 'carbohydrates_100g', 'fat_100g') if c not in ix]
    if missing:
        print('WARNING: columns not found in the export:', missing)
    if len(keep) < 1000:
        sys.exit('Too few products: the export format may have changed. Not publishing.')

    # Same barcode twice: keep the most scanned
    best = {}
    for p in keep:
        if p[0] not in best or p[17] > best[p[0]][17]:
            best[p[0]] = p
    prods = sorted(best.values(), key=lambda p: -p[17])

    # Every word of name + brand, plus brand and name with spaces removed ("get pro" -> getpro)
    by2 = collections.defaultdict(list)
    pwords = []  # each product's words (for the two-word files)
    for i, p in enumerate(prods):
        ws = set(words_of(f'{p[1]} {p[2]} {extra_words.get(p[0], "")}'))
        pwords.append({w for w in ws if len(w) >= 2 and w not in STOP})
        for extra in [p[2], p[1], *extra_words.get(p[0], '').split(',')]:
            j = ''.join(words_of(extra))
            if j:
                ws.add(j)
        for w in ws:
            if len(w) >= 2:
                by2[w[:2]].append((w, i))

    os.makedirs(os.path.join(OUT, 's'), exist_ok=True)
    files = {}
    overflow = {}  # prefix -> products that didn't fit in its file
    name_len = [max(1, len(words_of(p[1]))) for p in prods]
    def write(prefix, idxs):
        allx = sorted(set(idxs))  # product order = most scanned first
        if len(allx) > MAX_PER_FILE:
            # Busy file: two thirds most scanned, one third the closest names ("Chopped onions"
            # rather than another flavour of "Cheese and onion crisps")
            top = allx[:MAX_PER_FILE * 2 // 3]
            chosen = set(top)
            close = sorted((i for i in allx if i not in chosen), key=lambda i: (name_len[i], i))
            uniq = sorted(chosen | set(close[:MAX_PER_FILE - len(top)]))
            rest = [i for i in allx if i not in set(uniq)]
        else:
            uniq, rest = allx, []
        with open(os.path.join(OUT, 's', f'{prefix}.json'), 'w', encoding='utf-8') as fh:
            json.dump([prods[i] for i in uniq], fh, ensure_ascii=False, separators=(',', ':'))
        files[prefix] = len(uniq)
        if rest:
            overflow[prefix] = rest

    # Cloudflare Pages allows 20,000 files: split less if we'd go over
    split_at = SPLIT_AT
    while True:
        n_files = sum(1 if len({i for _, i in e}) <= split_at else len({(w[:3] if len(w) >= 3 else w) for w, _ in e}) for e in by2.values())
        if n_files <= 18000:
            break
        split_at *= 2
    for p2, entries in by2.items():
        idxs = {i for _, i in entries}
        if len(idxs) <= split_at:
            write(p2, idxs)
        else:
            by3 = collections.defaultdict(set)
            for w, i in entries:
                by3[w[:3] if len(w) >= 3 else w].add(i)
            for p3, s in by3.items():
                write(p3, s)

    # Two-word files for the products that didn't fit: "frozen chopped onions" is cut from
    # the busy "oni" file (crisps are scanned far more), so it also goes in x/oni-fr.json
    # (products with an "oni…" word AND an "fr…" word). The app asks for these when you
    # type two or more words.
    pairs = collections.defaultdict(set)
    for prefix, idxs in overflow.items():
        for i in idxs:
            for v in pwords[i]:
                if not v.startswith(prefix):
                    pairs[f'{prefix}-{v[:2]}'].add(i)
    budget = MAX_FILES - len(files) - 10
    keep_pairs = sorted(pairs, key=lambda k: -len(pairs[k]))[:max(0, budget)]
    os.makedirs(os.path.join(OUT, 'x'), exist_ok=True)
    for k in keep_pairs:
        rows = sorted(pairs[k])[:MAX_PER_FILE]
        with open(os.path.join(OUT, 'x', f'{k}.json'), 'w', encoding='utf-8') as fh:
            json.dump([prods[i] for i in rows], fh, ensure_ascii=False, separators=(',', ':'))
    print(f'{len(overflow)} busy files; wrote {len(keep_pairs)} two-word files (of {len(pairs)} possible)')

    manifest = {
        'version': datetime.date.today().isoformat(),
        'cols': COLS,
        'over': sorted(overflow),  # busy files that have two-word files in x/
        'files': files,  # prefix -> number of products in that file
        'products': len(prods),
        'licence': 'Open Food Facts data, ODbL. See ATTRIBUTION.txt',
    }
    with open(os.path.join(OUT, 'index.json'), 'w') as fh:
        json.dump(manifest, fh, separators=(',', ':'))
    with open(os.path.join(OUT, '_headers'), 'w') as fh:
        fh.write('/*\n  Cache-Control: public, max-age=86400\n  Access-Control-Allow-Origin: *\n')
    with open(os.path.join(OUT, 'ATTRIBUTION.txt'), 'w') as fh:
        fh.write('Food data from Open Food Facts (https://world.openfoodfacts.org), made available under the Open Database License (ODbL) https://opendatacommons.org/licenses/odbl/1-0/.\n'
                 'This file set is a UK extract (products with nutrition information) used by the PrimeBuilt app, offered under the same licence.\n'
                 'Product photos are hosted by Open Food Facts and licensed CC BY-SA 3.0 by their contributors.\n')
    with open(os.path.join(OUT, 'index.html'), 'w') as fh:
        fh.write('<!doctype html><meta charset="utf-8"><title>PrimeBuilt food search data</title><p>Data files for the PrimeBuilt app. Food data from Open Food Facts (ODbL). See ATTRIBUTION.txt.</p>')
    sizes = sorted(files.values())
    print(f'wrote {len(files)} files; products per file: median {sizes[len(sizes)//2]}, max {sizes[-1]}')

main()
