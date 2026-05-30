# massing-generator

## What this does

Generates 3D building massings that fit a zoning envelope. Given the legal building envelope (max height, footprint polygon, setbacks, FSI, permitted uses), produces two or three viable building options as 3D models with photorealistic facade renders.

The pipeline:
1. Build a 3D box matching the envelope (deterministic geometry — `shapely` + `trimesh`).
2. Generate realistic facades for each face using **SDXL + ControlNet**, conditioned on a description derived from the envelope and use mix.
3. Wrap the generated facades onto the 3D mass.
4. Optionally apply a light **LoRA** fine-tuned on Toronto building photos for stylistic fidelity (red brick, victorian bases, glass tops, etc.).

If 3D fights us, the 2.5D extruded-mass fallback still demos well.

## Contract

```python
def generate(envelope: ZoningEnvelope) -> MassingOutput
```

Full type definitions in `src/massing_generator/schemas.py`. Source of truth in `docs/CONTRACTS.md`.

## Data sources

- **Toronto building photos** — collected from public sources (Street View, Wikimedia Commons, city archives). Owned and curated within this component.
- Local images in `./data/training_images/` (gitignored).

## How to run solo

```bash
# from repo root
uv sync

# mock generation (prints metadata, writes a placeholder .obj)
uv run python -m massing_generator.cli demo

# OR standalone service on :8003
uv run uvicorn massing_generator.service:app --port 8003 --reload
```

## Current state

- [x] Skeleton scaffolded, contract function returns mock 3D output paths
- [x] CLI runs end-to-end
- [x] Standalone FastAPI service runs
- [ ] Deterministic envelope-to-mesh in `controlnet.py` (use `shapely.Polygon` + `trimesh.creation.extrude_polygon`)
- [ ] SDXL + ControlNet facade generation (`controlnet.py`)
- [ ] Apply facade textures to mesh faces (`generate.py`)
- [ ] Optional Toronto-style LoRA training (`lora.py`)
- [ ] Building photo collection (`ingest.py`)

## Next tasks

1. Build the deterministic 3D mass from an envelope. Inputs: footprint polygon (WGS84 → local meters), max height, setbacks. Output: trimesh.Mesh.
2. Wire up SDXL + ControlNet via diffusers. Use the Canny ControlNet on the elevation outline to keep facade proportions matching the mass.
3. Glue: render facade per face, UV-map onto the mesh, export .glb (web-friendly).
4. Collect ~200 Toronto building photos for the LoRA. Train with `peft`. Optional but stylistically nice.
5. Wire `generate.py` to call the pipeline and return real `MassingOutput`.

## File map

| File | Purpose |
|---|---|
| `src/massing_generator/__init__.py` | Re-exports `generate()` |
| `src/massing_generator/schemas.py` | Pydantic types |
| `src/massing_generator/ingest.py` | Building photo collection |
| `src/massing_generator/controlnet.py` | SDXL + ControlNet facade pipeline + envelope-to-mesh geometry |
| `src/massing_generator/lora.py` | Optional Toronto-style LoRA training |
| `src/massing_generator/generate.py` | `generate()` — THE CONTRACT |
| `src/massing_generator/service.py` | Optional FastAPI on :8003 |
| `src/massing_generator/cli.py` | Solo demo CLI |
| `tests/test_smoke.py` | Smoke test |
