# Promo quality review

This is a review worksheet, not a claim of measured performance. Fill it using actual outputs from a recorded run. Automated timing validity and editorial quality are different checks.

## Before reviewing

Record the input identifier, run identifier, selection mode, model/provider (if used), prompt version, and review date. Preserve the original outputs; put review labels in a separate file. Do not publish confidential scripts, excerpts, or assignment outputs in a public repository.

Review the top 10 ranked clips and at least five clips sampled from the remaining candidates. Also inspect several rejected candidates or episodes with no selected clip. Record the sample method; reviewing only top-ranked results can hide missed opportunities. For a small run, review every candidate.

Read only the selected segment first, as a new viewer would experience it. Then consult surrounding material to check misleading omissions. A narrative question must remain unresolved inside the selected clip; a question mark alone is not evidence of a cliffhanger.

## Editorial rubric

Use a 0–2 score for each criterion. These scores are human judgments, not click-through predictions.

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| Hook in first 3 seconds | No identifiable hook | Interesting but needs setup | Immediately clear conflict, surprise, or urgent action |
| Unresolved ending | Main question resolved or arbitrary stop | Some uncertainty but weak urge to continue | Specific, consequential question remains open |
| Standalone clarity | Requires missing context | Basic action is clear; relationships or stakes need work | A new viewer can identify the situation and stakes |
| Cut completeness | Dialogue or essential action is cut unintentionally | Technically complete but awkward boundary | Coherent entry and deliberate exit at an available boundary |
| Faithful selection | Omissions materially misrepresent the story | Possible ambiguity requiring editor review | Supported by the selected script and surrounding context |

Suggested decision: **accept for editor review** only if every criterion scores at least 1 and hook, ending, and clarity each score 2. This is a project assumption, not a benchmark established by the assignment. A scripted interrupted sentence can be intentional; distinguish it from a tool cutting a sentence mid-line.

## Mechanical checks

- Each continuous segment has `end > start` and falls within the episode's available timing.
- The total selected duration is 20–60 seconds.
- Every source episode and referenced event exists.
- Boundaries do not cut through spoken dialogue, unless an explicitly documented, source-supported editorial choice is being reviewed.
- Dialogue, camera, and action records may overlap. Calculate a continuous clip's duration as `end - start`, never as the sum of record durations.
- The opening hook occurs in the actual first 3 seconds of the selected interval.
- Very similar overlapping suggestions are filtered so the shortlist contains distinct choices.
- Parse failures and episodes with no output are visible, not silently omitted.

## Review log template

| Run / candidate | Hook | Ending | Clarity | Cuts | Faithfulness | Decision | Evidence and failure reason |
|---|---:|---:|---:|---:|---:|---|---|
| Fill from actual run | — | — | — | — | — | Pending | Pending |

Report accepted/top-10, accepted/reviewed, timing-invalid/generated, and no-candidate episodes/processed. Always show denominators and mode. If comparing AI and baseline, use the same input set and rubric. Do not call acceptance rate “accuracy” without a defined ground-truth set. An empty failure count does not prove there are no failures.

## Failures to actively look for

1. A dramatic argument that resolves before the clip ends.
2. A mysterious ending that makes no sense without earlier episodes.
3. A hook visible only in a logline or later event, not the first 3 seconds.
4. A source-grounded time range that nevertheless cuts poorly on screen.
5. Repetitive recommendations from the same confrontation.
6. A quiet but powerful scene missed by keyword-based selection.
7. A model inventing a timestamp, event identifier, quote, or relationship.
8. A scene ending selected merely because the script says “cliffhanger.”

Record at least one actual AI error when AI is used. If the only executed mode is the deterministic baseline, say so; do not invent an AI failure or imply that an untested adapter produced the outputs.

## Limits and next validation

Screenplay timestamps are not verified edit points in a rendered video. Delivery, acting, framing, pacing, and visual legibility can change whether a hook works. An editor must confirm the proposed cuts against footage. The initial version selects single continuous segments; stitched promos are outside its scope.

Human review establishes shortlist usefulness, not advertising effectiveness. With a real team, measure editor acceptance and time saved against their current workflow. With distribution access, compare approved variants using a controlled test with defined audience, spend, and duration; report view retention and downstream viewing without claiming causation from uncontrolled results.

## Recorded synthetic-demo failure (8 November 2026)

Evidence: user screenshots of the successful Groq GPT-OSS 120B demo, checked against `examples/demo_episode.txt`. The selected 00:00.00–00:56.00 clip received an 80/100 model score and described the lawyer reaching for the envelope as an unresolved struggle. The 00:53.00–00:56.00 source action states that Evelyn snatches it away before he can reach it.

Human finding: the claimed cliffhanger is resolved inside the clip. Reject this rationale/cut for the proposed ending; keep the original output unchanged in the exported run. Timing validation does not establish narrative correctness. The remaining demo candidates and full-pack AI results still require review.
