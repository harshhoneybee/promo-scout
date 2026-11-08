# Promo Scout

A runnable screenplay-to-promo prototype for **Problem 1: Find the Promos**.
Upload timestamped scripts, inspect ranked 20–60 second continuous clips, and export exact episode cuts with their source evidence.

**Status:** offline baseline tested on the full 50-episode assignment pack. AI integration is implemented and contract-tested with mock responses, but no live model run has been completed. Baseline outputs are not AI outputs or a submission-ready editorial shortlist.

## Start here (Windows)

Install Python 3.10 or newer, download this repository and extract it. Open PowerShell in the folder containing this README:

```powershell
py -m promo_finder serve
```

Open **http://localhost:8765** in your browser. Select **Use synthetic demo** and analyze in **Offline baseline** mode. Then upload your assignment ZIP. No Python packages, API key or payment are needed for baseline mode.

On macOS/Linux use `python3` instead of `py`. Stop the server with Ctrl+C.

## Command line

```bash
python -m promo_finder analyze examples/demo_episode.txt --mode baseline --out outputs/demo-001
python -m promo_finder analyze "path/to/assignment.zip" --mode baseline --top 10 --out outputs/full-baseline-001
python -m unittest discover -s tests -v
```

Each output directory must be new. It contains:

- `results.json`: metadata, episode coverage, all valid candidates, rejected candidates, ranked selection and exact model responses where available.
- `promos.csv`: editor-friendly ranked cut list, with formula-escaped text.
- `raw_responses.json`: unedited candidate-generator responses; baseline and AI runs are explicitly identified.

The browser keeps results in memory; download the JSON before closing the page. The command line writes them to disk.

## Connect a model

The model is replaceable; the parser, validator and ranking code stay the same.
Configure environment variables in the same terminal used to start the tool. `.env.example` documents settings but is **not loaded automatically**.

For a provider offering a compatible chat-completions endpoint (PowerShell):

```powershell
$env:PROMO_API_URL = "https://router.huggingface.co/v1/chat/completions"
$env:PROMO_MODEL = "YOUR_AVAILABLE_MODEL_ID"
$env:PROMO_API_KEY = "YOUR_KEY"
py -m promo_finder serve
```

Use a model currently available in your provider account; quota, model access and price are provider-dependent. Do not commit API keys or paste them into the browser. AI mode sends scripts to your configured provider, as permitted by the assignment. There is no silent baseline fallback on model errors.

Alternatively, run a local model with Ollama and use:

```powershell
$env:PROMO_API_URL = "http://localhost:11434/api/chat"
$env:PROMO_API_STYLE = "ollama"
$env:PROMO_MODEL = "YOUR_INSTALLED_MODEL_NAME"
py -m promo_finder serve
```

Local model inference does not require a paid API, but it requires installing Ollama, downloading a model and suitable hardware. This repository does not bundle a model. On macOS/Linux use `export NAME="value"` for environment settings.

After configuration, run a synthetic AI smoke test first, inspect raw JSON, then run the full pack:

```bash
python -m promo_finder analyze examples/demo_episode.txt --mode ai --out outputs/demo-ai-001
python -m promo_finder analyze "path/to/assignment.zip" --mode ai --out outputs/full-ai-001
```

The provider sends one sequential request per episode with a 120-second request timeout. A 50-episode AI run can take several minutes. Providers returning Markdown rather than strict JSON produce an explicit episode error; outputs remain available for diagnosis. CLI exit code 2 means partial episode failure, 1 means input/configuration/output failure.

Provider protocol references: [Hugging Face chat completion](https://huggingface.co/docs/inference-providers/tasks/chat-completion), [Ollama chat API](https://docs.ollama.com/api/chat).

## How it works

1. **Parse with Python.** Read episode metadata and every timed event. Preserve overlapping camera, action and dialogue entries; never sum their durations.
2. **Propose candidates.** Baseline uses transparent keyword cues. AI receives one episode with stable event IDs and can propose up to three candidates or abstain. The prompt is in `engine.py`.
3. **Validate with Python.** Resolve event IDs to source timestamps; enforce 20–60 seconds, episode bounds, complete spoken lines, hook evidence in the first 3 seconds, and cliffhanger evidence ending within the last 5 seconds. Invalid candidates are recorded, not silently repaired.
4. **Rank and deduplicate.** Weighted score = 40% hook + 35% cliffhanger + 25% clarity, mapped from 0–5 to 0–100. Remove clips overlapping at least 65% of the shorter selected clip in the same episode. Ties prefer shorter duration, then episode/start order. Weights are assumptions, not fitted predictors of ad performance.
5. **Review.** An editor checks standalone coherence, whether the ending is actually unresolved, and the corresponding footage. Use [the review worksheet](docs/QUALITY_REVIEW.md).

The source timeline grounds **timestamps and evidence**, not every claim in an AI-written explanation. A model can still misinterpret a scene. Numeric timing checks do not establish that a hook is compelling, fully understood within three seconds, or that a cliffhanger is genuine.

## Scope and limits

- Continuous, single-episode cuts only. Stitched/cross-episode promos and video editing are out of scope.
- Scripts are the source of truth for proposed timing. No footage, audio, frame alignment or measured ad results are supplied.
- Baseline clarity is a fixed 2/5 placeholder and explicitly unverified; keyword cues can mistake reassurance or rhetorical questions for cliffhangers.
- No forced promo per episode. All input episodes appear in the coverage report even if the generator abstains or an AI call fails.
- Input ZIP/TXT must follow the supplied timestamped format. Invalid scripts fail parsing rather than silently disappearing. The UI accepts ZIPs up to 10 MB and TXT up to 1 MB; CLI supports ZIP up to 50 MiB, individual text up to 2 MiB, expanded archive up to 100 MiB, and at most 500 episodes.
- The browser server binds to loopback and is intended for your laptop. It is not a hardened public multi-user deployment. GitHub Pages cannot execute this Python backend. A repository with these run instructions satisfies the brief's prototype format.
- AI calls are sequential; resume, caching and retries are not implemented. Larger rollouts should cache per-episode inputs by hash, bound concurrency/rate limits, log token usage and use human-review queues. Estimate cost from actual input/output tokens and the selected model's current price; do not invent a per-show cost.

## Confidentiality

The supplied Kuku scripts and outputs containing their text must **not be published**. This repository includes only synthetic sample content. `.gitignore` excludes `input/`, `private/`, `outputs/`, ZIPs and local secrets. Keep assignment files outside the repo or in those ignored folders. Review `git diff --cached` before pushing. Submit confidential raw outputs only through the authorized assignment route.

## Project map

| File | Responsibility |
|---|---|
| `promo_finder/parser.py` | Parse scripts and ZIPs into timed events |
| `promo_finder/engine.py` | Prompt, baseline, validation, ranking and audit trail |
| `promo_finder/providers.py` | Compatible API / Ollama adapter |
| `promo_finder/server.py` | Local browser API |
| `web/index.html` | Upload, review and export interface |
| `promo_finder/__main__.py` | CLI entry point |
| `tests/` | Parser, validation, model-failure regression checks |
| `docs/BUILD_STATUS.md` | Verified work, known gaps and next steps |

## AI assistance disclosure

ChatGPT/Codex assisted with scope, implementation, synthetic examples, tests and documentation. A code review caught a concrete AI-generated implementation error: rounding duration before validation could accept 19.996-second or 60.004-second clips. Validation now checks the raw duration before rounding for display, with regression tests. Review and understand every component before presenting this as your assignment work; personalize the decisions and disclosure honestly.
