from pathlib import Path

from tas_pythonetics import (
    STATUS_NULL_COLLAPSE,
    STATUS_OK,
    STATUS_SENTIENT_LOCK,
    TASFusedLogitsProcessor,
)

ROOT = Path(__file__).resolve().parents[1]
KERNEL = ROOT / "tas_cuda_engine" / "tas_kernel.cu"
SETUP = ROOT / "tas_cuda_engine" / "setup.py"


def test_status_codes_are_stable_for_cuda_processor():
    assert STATUS_OK == 0
    assert STATUS_NULL_COLLAPSE == 1
    assert STATUS_SENTIENT_LOCK == 2


def test_processor_imports_without_loading_cuda_extension():
    processor = TASFusedLogitsProcessor(entropy_threshold=0.15)

    assert processor.entropy_threshold == 0.15


def test_cuda_kernel_contains_fused_guardrail_operations():
    source = KERNEL.read_text()

    assert "tas_fused_guardrails_kernel" in source
    assert "row_logits[i] = -INFINITY" in source
    assert "STATUS_NULL_COLLAPSE" in source
    assert "final_allowed == 1" in source
    assert "STATUS_SENTIENT_LOCK" in source
    assert "local_entropy -= p * (log_p * log2_e)" in source


def test_cuda_setup_uses_pytorch_cuda_extension():
    source = SETUP.read_text()

    assert "CUDAExtension" in source
    assert "tas_kernel.cu" in source
    assert "--use_fast_math" in source
