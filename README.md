# PrimeBuilt food search

Builds small search files of UK branded foods from [Open Food Facts](https://world.openfoodfacts.org) once a week, so the PrimeBuilt app can search branded products quickly and reliably.

- `build.py` turns the Open Food Facts export into files: `index.json` and `s/<letters>.json`.
- `.github/workflows/build.yml` runs it every Monday and publishes the files to the `site` branch.
- Cloudflare Pages serves the `site` branch as plain files.

Nothing about app users is stored or sent here. The app only downloads files.

## Licence

Food data © Open Food Facts contributors, available under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1-0/). The extract published on the `site` branch is offered under the same licence.
