"""PyTorch/vLLM logits processor wrapper for the fused TAS CUDA kernel."""

from __future__ import annotations

import sys
from typing import Any

STATUS_OK = 0
STATUS_NULL_COLLAPSE = 1
STATUS_SENTIENT_LOCK = 2


class TASFusedLogitsProcessor:
    """Zero-copy CUDA logits processor for high-throughput TAS guardrails."""

    def __init__(self, entropy_threshold: float = 0.15, engine: Any | None = None):
        if entropy_threshold < 0:
            raise ValueError("entropy_threshold must be non-negative")
        self.entropy_threshold = entropy_threshold
        self._engine = engine

    @property
    def engine(self) -> Any:
        """Load the compiled CUDA extension lazily so CPU-only installs still import."""
        if self._engine is None:
            import tas_cuda_engine

            self._engine = tas_cuda_engine
        return self._engine

    def __call__(self, logits: Any, allowed_mask: Any) -> Any:
        """Apply in-place fused masking and invariant checks to CUDA logits."""
        import torch

        if logits.device != allowed_mask.device:
            raise ValueError("logits and allowed_mask must be on the same device")
        if logits.shape != allowed_mask.shape:
            raise ValueError("allowed_mask shape must match logits shape")
        if logits.dtype != torch.float32:
            raise TypeError("logits must be a torch.float32 tensor")
        if allowed_mask.dtype != torch.bool:
            raise TypeError("allowed_mask must be a torch.bool tensor")
        if not logits.is_cuda or not allowed_mask.is_cuda:
            raise ValueError("logits and allowed_mask must be CUDA tensors")
        if not logits.is_contiguous() or not allowed_mask.is_contiguous():
            raise ValueError("logits and allowed_mask must be contiguous")

        batch_size = logits.size(0)
        status_flags = torch.empty(batch_size, dtype=torch.int32, device=logits.device)
        entropy_out = torch.empty(batch_size, dtype=torch.float32, device=logits.device)

        self.engine.apply_guardrails(
            logits,
            allowed_mask,
            status_flags,
            entropy_out,
            self.entropy_threshold,
        )

        for idx, status in enumerate(status_flags.tolist()):
            if status == STATUS_NULL_COLLAPSE:
                sys.stderr.write(
                    f"[FATAL ⊥] Null Collapse on batch index {idx}. Hard kernel halt.\n"
                )
                sys.exit(1)
            if status == STATUS_SENTIENT_LOCK:
                raise RuntimeError(
                    f"[SENTIENT LOCK] Low-entropy degenerate state detected on batch {idx} "
                    f"(H = {entropy_out[idx].item():.4f} bits). Context frozen."
                )
            if status != STATUS_OK:
                raise RuntimeError(f"Unknown TAS CUDA guardrail status {status} on batch {idx}")

        return logits
