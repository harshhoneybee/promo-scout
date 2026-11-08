# Build status - 8 November 2026

## Completed full-pack AI run

The final user export confirms these results with Groq `openai/gpt-oss-120b` and prompt version 1.0:

| Measure | Verified result |
|---|---:|
| Episodes successfully analysed | 50 / 50 |
| Timed source events | 3,727 |
| Candidates proposed | 100 |
| Candidates passing mechanical checks | 54 |
| Candidates rejected | 46 |
| Distinct promos shortlisted | 10 |
| Responses reused in final resume | 41 |
| Episodes not attempted / remaining errors | 0 / 0 |

Replaying validation and ranking on all 100 recorded proposals against the original input reproduced the 54 valid candidates, 46 rejections and top 10. All 10 CSV rows matched the JSON shortlist. The confidential input and unedited outputs are excluded from this repository.

The rejection reasons were 37 duration violations, 10 cuts through spoken dialogue and one ending-evidence violation. These are 48 reason occurrences across 46 candidates, because two candidates had multiple reasons. Of the 37 duration violations, 35 were shorter than 20 seconds and two were longer than 60 seconds. One episode explicitly returned no candidates; ten episodes had no mechanically valid candidate. Neither result measures promo recall.

## Implementation and verification

- Dependency-free Python 3.10+ CLI and local browser server.
- 62 passing unit tests: 12 parser, 19 engine/provider-contract, six HTTP diagnostic, nine model-output and 16 retry/checkpoint tests.
- All 50 supplied episodes parsed without scene-bound warnings.
- Offline baseline also processed all 50 episodes: 174 valid candidates, ten selected after overlap suppression and 22 episodes without a baseline candidate. These are mechanical results, not a controlled quality comparison.
- HTTP smoke checks passed for the homepage, configuration and synthetic-demo analysis. Frontend JavaScript passed a syntax check.
- A local mocked HTTP integration test ran the demo twice with one provider call, confirming browser API checkpoint reuse.
- User screenshots show the completed live browser workflow. The final downloaded JSON and CSV were inspected. Automated visual browser tests were unavailable in the build environment.
- Final response envelopes and checkpoint timestamps are preserved in the full-run JSON; checkpoint reuse is explicitly labelled.

## Reliability failures observed and addressed

The early synthetic response exhausted a 1,800-token completion budget: its final content was empty and 1,798 tokens were used for reasoning. The Groq GPT-OSS adapter now requests low reasoning effort, strict JSON schema output and a 4,096-token completion budget. Truncation is diagnosed before JSON parsing; the original response is retained.

The initial full-pack run encountered HTTP 413 for one episode and HTTP 429 later in the pack. Compact serialization reduced the measured affected user-message length from 19,491 to 18,069 characters without changing source values or cache identity; a later export confirmed that episode succeeded. Persistent rate limits stop new requests visibly. Bounded retries honor `Retry-After`, with an adjustable cumulative wait budget. Saved completed responses are reused when the same input and settings are run again.

Later connection failures left nine episodes unfinished. The final resumed export reused 41 responses and completed the remaining nine without errors. Its elapsed 8,278.501 seconds includes quota waiting and is not a fresh-run inference-time benchmark. The successful run verifies recovery through resume, not guaranteed provider availability or throughput.

## Token accounting

Across the 50 preserved successful response envelopes:

- Input: 228,503 tokens.
- Output: 35,168 tokens.
- Total: 263,671 tokens.

These totals count each saved response once. They exclude failed attempts and separate demo runs; reused usage is not a new charge. Actual cost depends on current provider rates, caching and billing. At input/output prices per million tokens, the successful-response estimate is `0.228503 * input_price + 0.035168 * output_price` before cache discounts.

## Editorial audit and remaining limits

An AI-assisted source audit reviewed all ten shortlisted cuts, five non-shortlisted valid candidates sampled across their score ranking, and two episodes with no valid output. It found missing-context and weak-opening problems despite perfect model scores. Nine of the ten shortlisted cuts scored 100/100; their order partly reflects the shorter-duration tie-break. This sample is not a human acceptance study, a recall benchmark or evidence of advertising performance.

A separately documented review may change the editorial order, but original model outputs must remain unchanged. The submitter reviewed the two-page solution brief, which has been finalized separately with the private raw-output archive. Actual-footage validation remains pending. Confidential source-derived recommendations are not published here.

## Concrete AI error examples

In the public synthetic demo, a selected 00:00.00-00:56.00 clip scored 80/100 and described the lawyer reaching for an envelope as unresolved. The source action at 00:53.00-00:56.00 says Evelyn snatches it away before he can reach it. The claimed local struggle is resolved inside the clip. This source comparison was AI-assisted and is not a recorded human-review result.

During implementation review, duration validation was found to round before checking limits. That could accept 19.996-second or 60.004-second clips. The implementation now checks raw durations, and regression tests cover both edges.

## Remaining submission steps

1. Review the proposed editorial choices against the actual footage when available and record personal judgments separately.
2. Use the finalized two-page solution document and its AI-assistance disclosure.
3. Supply the prototype link and unedited full-input outputs through the authorized assignment route; keep confidential content out of the public repository.
4. Optionally record a short walkthrough in the submitter's own voice. Do not claim measured audience results or time savings without a controlled evaluation.
