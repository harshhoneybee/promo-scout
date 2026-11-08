# Build status — 8 November 2026

## Verified

- Dependency-free Python 3.10+ CLI and local browser server implemented.
- 31 unit tests passed: 12 parser and 19 engine/provider-contract tests.
- All 50 supplied episodes parsed: 3,727 timed events; no scene-bound warnings.
- Offline baseline processed all 50 episodes without errors: 174 valid candidates, 10 selected after overlap suppression; 22 episodes had no baseline candidate. These are mechanical results, not editorial accuracy or recall measurements.
- HTTP smoke test returned 200 for homepage, configuration, and synthetic-demo analysis (4 candidates, 1 distinct selected clip).
- Frontend JavaScript passed a syntax check.
- Source content and full-pack outputs excluded from the repository.

## Not yet verified

- No live AI inference run: provider/model credentials or a local model must be configured. AI behavior was tested using explicit mock responses, including malformed output and failures.
- Visual browser testing could not run in the build environment: Chromium was blocked by its socket restrictions. Review layout and export buttons in your local browser.
- No measured audience results; no claim of CTR uplift or comprehensive promo recall.
- Final human editorial shortlist, two-page solution PDF and narrated walkthrough remain to be completed.

## Honest failure examples

The offline baseline can select a reassuring or resolved statement as its ending because it contains cue words. The candidate is timestamp-valid but does not establish a meaningful cliffhanger. This is a rule-based baseline failure, not evidence of a live model error.

During AI-assisted implementation, code review found duration validation rounded before checking limits. That could accept 19.996s or 60.004s as valid. The fix compares raw durations, and regression tests cover both edges. This is a real example to describe in the AI-tool-use disclosure.

## Next steps

1. Run the synthetic demo locally and inspect its evidence.
2. Configure a model; run a synthetic AI smoke test and inspect raw responses.
3. Run all 50 episodes in AI mode, retaining unedited output and any episode errors.
4. Review top 10, a sample of lower-ranked candidates, and some abstained episodes using QUALITY_REVIEW.md. Record actual judgments and changes separately from raw outputs.
5. Write the maximum-two-page solution document using only verified claims and your own decisions. Record a short walkthrough in your own voice.
