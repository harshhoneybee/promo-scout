# Build status — 8 November 2026

## Verified

- Dependency-free Python 3.10+ CLI and local browser server implemented.
- 44 unit tests passed: 12 parser, 19 engine/provider-contract, 5 HTTP diagnostic and 8 model-output tests.
- All 50 supplied episodes parsed: 3,727 timed events; no scene-bound warnings.
- Offline baseline processed all 50 episodes without errors: 174 valid candidates, 10 selected after overlap suppression; 22 episodes had no baseline candidate. These are mechanical results, not editorial accuracy or recall measurements.
- HTTP smoke test returned 200 for homepage, configuration, and synthetic-demo analysis (4 candidates, 1 distinct selected clip).
- Frontend JavaScript passed a syntax check.
- Source content and full-pack outputs excluded from the repository.

## Not yet verified

- A user-run synthetic Groq GPT-OSS 120B call authenticated successfully, but its original 1,800-token budget was exhausted before a final answer. The corrected request settings have automated coverage; a successful live rerun is still pending.
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

## HTTP diagnostics update

The API client now identifies itself as PromoScout and exposes only predefined, safe error categories for permission denials, gateway 1010, authentication and rate limits. Provider error text and secrets are not echoed. Failed episodes are highlighted at the top of the UI rather than looking like a successful empty shortlist. These changes are regression-tested; the user must rerun the synthetic demo to verify the live connection.

## Verified token-budget failure and fix

The user-supplied demo export recorded `finish_reason: length`, empty final content, 1,800 completion tokens and 1,798 reasoning tokens. The default was too small for this reasoning model. The Groq GPT-OSS adapter now requests low reasoning effort, a 4,096-token completion budget and strict structured JSON. It recognizes truncation before attempting JSON parsing and preserves the original response. No reasoning text or private run file was copied into this repository. The actual captured response was replayed locally to verify the clearer error. A live success cannot be claimed until the user reruns the demo.
