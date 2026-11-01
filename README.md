# PrimeBuilt food search

Builds small search files of UK branded foods from [Open Food Facts](https://world.openfoodfacts.org) once a week, so the PrimeBuilt app can search branded products quickly and reliably.

- `build.py` turns the Open Food Facts export into files: `index.json` and `s/<letters>.json`.
- `.github/workflows/build.yml` runs it every Monday and publishes the files to the `site` branch.
- Cloudflare Pages serves the `site` branch as plain files.

Nothing about app users is stored or sent here. The app only downloads files.

## Licence

Food data © Open Food Facts contributors, available under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1-0/). The extract published on the `site` branch is offered under the same licence.

## Sharing products with Open Food Facts (`functions/off/`)

When someone shares a missing product from the app, it comes here first (`/off/product`, `/off/photo`). This site adds the PrimeBuilt account's login and passes it on to Open Food Facts, so the password is never inside the app.

- The login lives only in Cloudflare: Pages project → Settings → Variables and Secrets: `OFF_USER`, `OFF_PASSWORD` (Encrypt), `OFF_MODE` (`live` or `test`). Change it there; the app doesn't need an update.
- Only adding a product's details and pack photos goes through. Fields are on an allow list with sensible limits (0–950 kcal, 0–100 g per 100 g, protein+carbs+fat ≤ 100 g, real JPEG/PNG photos up to 8 MB, no links in names).
- Up to 20 products and 40 photos an hour per phone and per internet address (counted in memory on each Cloudflare server, so it slows floods rather than being exact).
- Nothing is stored here. `/off/status` says whether sharing is on and whether it goes to the real or the test site.
- The daily build copies `functions/` into the published site.
