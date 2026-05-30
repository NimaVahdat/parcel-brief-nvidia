"""Optional: Toronto-style LoRA for SDXL.

Train on collected Toronto building photos so generated facades look local.
"""

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def train_lora() -> None:
    """Fine-tune an SDXL LoRA on data/training_images/ via peft + diffusers.

    TODO:
    1. Collect ~200 images of Toronto buildings (Street View, Wikimedia).
    2. Caption each with a short Toronto-style descriptor.
    3. Train a LoRA with rank 16, ~2000 steps.
    4. Save to data/lora_toronto.safetensors.
    """
    raise NotImplementedError("LoRA training not implemented yet — nice-to-have.")
