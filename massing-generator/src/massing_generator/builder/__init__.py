"""Building-spec engine: zoning brief -> LLM building spec -> 3D render.

Vendored from the `nvidia-hack` prototype and adapted to run as a package.
Light to import (no heavy deps at module load); renderers and the LLM client
are imported lazily by ``pipeline``.
"""
