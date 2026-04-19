# Pilot fixtures

Place a single **non-PHI** sample OPG here before running the Step 8 smoke test:

    sample-opg.jpg

Source options (must be re-usable for commercial evaluation — check the license):
- A synthetic panoramic radiograph rendered from a published teaching phantom
- An image from a public dental imaging dataset with a permissive license (e.g., Kaggle's "Dental Panoramic Images" — verify license before use)
- A radiograph captured from a typodont (anatomical tooth model) in Dr. Basher's office

**Do not place a real patient image in this directory.** This folder is checked into the repo and therefore the image is persisted in git history — which would be a reportable PHI exposure.

If you need to smoke-test with real PHI, do it through the hosted `/analyze` endpoint at runtime, not via a committed fixture.
