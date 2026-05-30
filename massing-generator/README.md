# massing-generator

## What this does

Generates 3D building massings that fit a zoning envelope. Given the legal
building envelope (max height, footprint polygon, setbacks, FSI, permitted
uses), produces one or more viable building options as interactive 3D models.

The pipeline (vendored from the `nvidia-hack` prototype, now in
`src/massing_generator/builder/`):

1. **Preprocess** (deterministic, no LLM): WGS84 footprint → metric lot dims,
   compass setbacks → front/rear/side, `max_fsi`/`max_height` → hard caps.
2. **Design** (LLM): an Anthropic model turns the brief + caps into a complete,
   buildable building spec — storeys, materials, facades, massing, unit mix —
   strictly within the caps. Picks a house or a mixed-use tower schema.
3. **Validate** (`builder/validate_building.py`): a geometric/structural gate
   (lot fit, coverage/FSI consistency, storey-height sums, tower
   stepback/penthouse nesting, opening/balcony storey refs). Errors are fed back
   to the model for a repair turn.
4. **Render**: textured **PyVista/VTK** scene → interactive HTML + PNG +
   best-effort glTF. Falls back to the dependency-light **Plotly** renderer, so
   a model is still produced on a headless box without VTK.

## Contract

```python
def generate(envelope: ZoningEnvelope) -> MassingOutput
```

Type definitions in `src/massing_generator/schemas.py`; source of truth in
`docs/CONTRACTS.md`. `generate()` runs the real engine when `ANTHROPIC_API_KEY`
is set and returns deterministic **mock** options otherwise (so the end-to-end
brief pipeline and tests run offline). Force the mock with `MASSING_USE_MOCK=1`.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | required for the real (LLM) path |
| `MASSING_USE_MOCK` | `0` | `1` forces the mock path |
| `MASSING_NUM_OPTIONS` | `1` | real design variants (each = one LLM call) |
| `MASSING_RENDER_MODE` | `hq` | `hq` \| `normal` \| `blueprint` \| `plotly` |
| `MASSING_DATA_DIR` | `massing-generator/data` | textures + renders output root |
| `MASSING_TEXTURES_DIR` / `MASSING_OUTPUT_DIR` | under `MASSING_DATA_DIR` | overrides |

Generated textures and renders land in `./data/` (gitignored). Bundled few-shot
and demo specs ship in `src/massing_generator/builder/specs/`.

## How to run solo

```bash
# from repo root
uv sync

# mock generation (no LLM, no render) — prints MassingOutput JSON
uv run python -m massing_generator.cli demo

# real engine for the demo envelope (needs ANTHROPIC_API_KEY)
uv run python -m massing_generator.cli build --num-options 1
uv run python -m massing_generator.cli build path/to/brief.json

# render an existing spec offline (no LLM)
uv run python -m massing_generator.cli render \
    src/massing_generator/builder/specs/discription_building.json --mode hq

# validate a spec
uv run python -m massing_generator.cli validate \
    src/massing_generator/builder/specs/discription_building.json

# standalone service on :8003
uv run uvicorn massing_generator.service:app --port 8003 --reload
```

The engine modules are also runnable directly, e.g.
`uv run python -m massing_generator.builder.generate_spec` and
`uv run python -m massing_generator.builder.render_pyvista <spec> --mode hq`.

## Current state

- [x] Contract `generate()` returns a real `MassingOutput`
- [x] Deterministic preprocess: envelope → metric lot + hard caps
- [x] LLM building-spec generation with validator-driven repair loop
- [x] Geometric/structural validator (house + mixed-use tower schemas)
- [x] PyVista HQ/normal/blueprint render (HTML + PNG + glTF), Plotly fallback
- [x] Mock fallback keeps the e2e pipeline working with no API key
- [ ] Toronto-style fidelity tuning (LoRA / reference-image conditioning)

## File map

| File | Purpose |
|---|---|
| `src/massing_generator/__init__.py` | Re-exports `generate()` and the contract types |
| `src/massing_generator/schemas.py` | Pydantic types |
| `src/massing_generator/generate.py` | `generate()` — THE CONTRACT (real engine + mock) |
| `src/massing_generator/service.py` | Optional FastAPI on :8003 |
| `src/massing_generator/cli.py` | Solo CLI: `demo` / `build` / `render` / `validate` |
| `src/massing_generator/builder/pipeline.py` | Glue: envelope → raw → spec → render → Massing |
| `src/massing_generator/builder/generate_spec.py` | Brief → LLM building spec (repair loop) |
| `src/massing_generator/builder/llm_client.py` | Pluggable LLM client (Anthropic; NIM/vLLM stub) |
| `src/massing_generator/builder/validate_building.py` | Geometric/structural validator |
| `src/massing_generator/builder/render_pyvista.py` | Textured PyVista renderer (HTML/PNG/glTF) |
| `src/massing_generator/builder/build_3d.py` | Plotly renderer (headless fallback) |
| `src/massing_generator/builder/textures.py` | Procedural seamless PBR textures |
| `src/massing_generator/builder/paths.py` | Resolves specs/textures/output dirs |
| `src/massing_generator/builder/specs/` | Bundled few-shot + demo specs |
| `tests/test_smoke.py` | Smoke + mapping + offline-render tests |
