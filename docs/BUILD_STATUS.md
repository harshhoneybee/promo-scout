# Build status — 8 November 2026

## Verified

- Dependency-free Python 3.10+ CLI and local browser server implemented.
- 59 unit tests passed: 12 parser, 19 engine/provider-contract, 6 HTTP diagnostic, 9 model-output and 13 retry/checkpoint tests.
- All 50 supplied episodes parsed: 3,727 timed events; no scene-bound warnings.
- Offline baseline processed all 50 episodes without errors: 174 valid candidates, 10 selected after overlap suppression; 22 episodes had no baseline candidate. These are mechanical results, not editorial accuracy or recall measurements.
- HTTP smoke test returned 200 for homepage, configuration, and synthetic-demo analysis (4 candidates, 1 distinct selected clip).
- Frontend JavaScript passed a syntax check.
- Source content and full-pack outputs excluded from the repository.
- User screenshots confirm a live synthetic Groq GPT-OSS 120B run: 3 candidates proposed, 0 mechanically rejected and 2 shortlisted in 2.3 seconds. Layout and candidate rendering are visible; download contents have not yet been inspected.
- Bounded HTTP 429 retry and checkpoint resume tested with simulated provider responses. A local HTTP integration test ran the demo twice with one mocked provider call, confirming reuse through the browser API. Browser JavaScript syntax passed. Live full-pack quota handling is not yet verified.

## Not yet verified

- Completion of the 15 missing episodes and full-pack editorial evaluation remain pending.
- Visual browser testing could not run in the build environment: Chromium was blocked by its socket restrictions. Review layout and export buttons in your local browser.
- No measured audience results; no claim of CTR uplift or comprehensive promo recall.
- Final human editorial shortlist, two-page solution PDF and narrated walkthrough remain to be completed.

## Honest failure examples

The offline baseline can select a reassuring or resolved statement as its ending because it contains cue words. The candidate is timestamp-valid but does not establish a meaningful cliffhanger. This is a rule-based baseline failure, not evidence of a live model error.

During AI-assisted implementation, code review found duration validation rounded before checking limits. That could accept 19.996s or 60.004s as valid. The fix compares raw durations, and regression tests cover both edges. This is a real example to describe in the AI-tool-use disclosure.

## Next steps

1. Preserve the successful synthetic demo export and the observed editorial error.
2. Update locally to include rate-limit retries and checkpoint resume.
3. Run all 50 episodes in AI mode, retaining unedited output and any episode errors.
4. Review top 10, a sample of lower-ranked candidates, and some abstained episodes using QUALITY_REVIEW.md. Record actual judgments and changes separately from raw outputs.
5. Write the maximum-two-page solution document using only verified claims and your own decisions. Record a short walkthrough in your own voice.

## HTTP diagnostics update

The API client now identifies itself as PromoScout and exposes only predefined, safe error categories for permission denials, gateway 1010, authentication and rate limits. Provider error text and secrets are not echoed. Failed episodes are highlighted at the top of the UI rather than looking like a successful empty shortlist. These changes are regression-tested; the subsequent user-run synthetic demo confirms the live connection works.

## Verified token-budget failure and fix

The user-supplied demo export recorded `finish_reason: length`, empty final content, 1,800 completion tokens and 1,798 reasoning tokens. The default was too small for this reasoning model. The Groq GPT-OSS adapter now requests low reasoning effort, a 4,096-token completion budget and strict structured JSON. It recognizes truncation before attempting JSON parsing and preserves the original response. No reasoning text or private run file was copied into this repository. The actual captured response was replayed locally to verify the clearer error. The subsequent user screenshots confirm a successful live synthetic rerun.

## Observed live model error

The user screenshots show a selected synthetic clip at 00:00.00–00:56.00 with an 80/100 model score. Its explanation asks whether the lawyer will seize the envelope and claims the struggle is unresolved. The supplied synthetic action at 00:53.00–00:56.00 explicitly says Evelyn snatches it away before he can reach it. That local action is resolved inside the selected clip. Human review rejects this stated cliffhanger even though automated timing checks pass. The 100/100 score on the other clip is also a model judgment, not measured audience performance. No confidential source text is needed to demonstrate this failure.

## Partial full-pack AI run and size diagnostics

User screenshots show 35 successful episodes out of 50, 76 proposed candidates, 37 mechanically rejected and 10 shortlisted. Episode 3 received HTTP 413; Episode 37 received persistent HTTP 429; Episodes 38–50 were not attempted after that rate limit. The 35 successful episodes should have local checkpoints with the default configuration; their presence and raw content still need confirmation from the user export.

Request serialization now removes JSON formatting whitespace without changing source values, event IDs, timestamps, generation settings or the logical checkpoint identity. For the Episode 3 input, the user-message size decreases from 19,491 to 18,069 characters. This is a measured size reduction, not a live confirmation that the provider will accept the request. HTTP 413 now explains the size problem, and persistent HTTP 429 reports the numeric Retry-After delay when supplied. Tests verify lossless serialization, retained checkpoint compatibility and safe diagnostics.
