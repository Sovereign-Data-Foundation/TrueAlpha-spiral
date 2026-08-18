from pathlib import Path

from setuptools import setup
from torch.utils.cpp_extension import BuildExtension, CUDAExtension

ROOT = Path(__file__).parent

setup(
    name="tas_cuda_engine",
    ext_modules=[
        CUDAExtension(
            "tas_cuda_engine",
            [str(ROOT / "tas_kernel.cu")],
            extra_compile_args={"nvcc": ["-O3", "--use_fast_math"]},
        )
    ],
    cmdclass={"build_ext": BuildExtension},
)
