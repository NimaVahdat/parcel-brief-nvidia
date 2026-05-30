"""Index subpackage: embed, store, retrieve."""

from opposition_generator.index.embed import build_index, embed_batch, embed_text
from opposition_generator.index.retrieve import Retrieved, retrieve

__all__ = ["build_index", "embed_text", "embed_batch", "retrieve", "Retrieved"]
