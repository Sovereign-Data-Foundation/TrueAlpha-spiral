#include <torch/extension.h>
#include <cuda_runtime.h>
#include <cmath>

#define BLOCK_SIZE 512

#define STATUS_OK 0
#define STATUS_NULL_COLLAPSE 1
#define STATUS_SENTIENT_LOCK 2

__device__ inline float warpReduceMax(float val) {
    for (int offset = 16; offset > 0; offset /= 2) {
        val = fmaxf(val, __shfl_down_sync(0xffffffff, val, offset));
    }
    return val;
}

__device__ inline float warpReduceSum(float val) {
    for (int offset = 16; offset > 0; offset /= 2) {
        val += __shfl_down_sync(0xffffffff, val, offset);
    }
    return val;
}

__device__ inline int warpReduceSumInt(int val) {
    for (int offset = 16; offset > 0; offset /= 2) {
        val += __shfl_down_sync(0xffffffff, val, offset);
    }
    return val;
}

__global__ void tas_fused_guardrails_kernel(
    float* __restrict__ logits,
    const bool* __restrict__ mask,
    int* __restrict__ status_flags,
    float* __restrict__ entropy_out,
    const int vocab_size,
    const float entropy_threshold
) {
    const int batch_idx = blockIdx.x;
    const int tid = threadIdx.x;

    float* row_logits = logits + batch_idx * vocab_size;
    const bool* row_mask = mask + batch_idx * vocab_size;

    int local_allowed_count = 0;
    float local_max = -INFINITY;

    for (int i = tid; i < vocab_size; i += BLOCK_SIZE) {
        if (!row_mask[i]) {
            row_logits[i] = -INFINITY;
        } else {
            local_allowed_count++;
            local_max = fmaxf(local_max, row_logits[i]);
        }
    }

    __shared__ int shared_count[BLOCK_SIZE / 32];
    __shared__ float shared_scratch[BLOCK_SIZE / 32];

    const int lane = tid % 32;
    const int warp_id = tid / 32;

    int warp_count = warpReduceSumInt(local_allowed_count);
    float warp_max = warpReduceMax(local_max);

    if (lane == 0) {
        shared_count[warp_id] = warp_count;
        shared_scratch[warp_id] = warp_max;
    }
    __syncthreads();

    int total_allowed = 0;
    float global_max = -INFINITY;
    if (tid < 32) {
        int c = (tid < (BLOCK_SIZE / 32)) ? shared_count[tid] : 0;
        float m = (tid < (BLOCK_SIZE / 32)) ? shared_scratch[tid] : -INFINITY;
        total_allowed = warpReduceSumInt(c);
        global_max = warpReduceMax(m);
    }

    __shared__ int final_allowed;
    __shared__ float final_max;
    if (tid == 0) {
        final_allowed = total_allowed;
        final_max = global_max;
    }
    __syncthreads();

    if (final_allowed == 0) {
        if (tid == 0) {
            status_flags[batch_idx] = STATUS_NULL_COLLAPSE;
            entropy_out[batch_idx] = 0.0f;
        }
        return;
    }

    if (final_allowed == 1) {
        if (tid == 0) {
            status_flags[batch_idx] = STATUS_OK;
            entropy_out[batch_idx] = 0.0f;
        }
        return;
    }

    float local_sum_exp = 0.0f;
    for (int i = tid; i < vocab_size; i += BLOCK_SIZE) {
        if (row_mask[i]) {
            local_sum_exp += __expf(row_logits[i] - final_max);
        }
    }

    float warp_sum_exp = warpReduceSum(local_sum_exp);
    if (lane == 0) {
        shared_scratch[warp_id] = warp_sum_exp;
    }
    __syncthreads();

    float global_sum_exp = 0.0f;
    if (tid < 32) {
        float s = (tid < (BLOCK_SIZE / 32)) ? shared_scratch[tid] : 0.0f;
        global_sum_exp = warpReduceSum(s);
    }

    __shared__ float final_sum_exp;
    if (tid == 0) {
        final_sum_exp = global_sum_exp;
    }
    __syncthreads();

    float local_entropy = 0.0f;
    const float log2_e = 1.4426950408889634f;
    const float log_sum_exp = __logf(final_sum_exp);

    for (int i = tid; i < vocab_size; i += BLOCK_SIZE) {
        if (row_mask[i]) {
            float logit_diff = row_logits[i] - final_max;
            float p = __expf(logit_diff) / final_sum_exp;
            float log_p = logit_diff - log_sum_exp;
            local_entropy -= p * (log_p * log2_e);
        }
    }

    float warp_entropy = warpReduceSum(local_entropy);
    if (lane == 0) {
        shared_scratch[warp_id] = warp_entropy;
    }
    __syncthreads();

    float global_entropy = 0.0f;
    if (tid < 32) {
        float e = (tid < (BLOCK_SIZE / 32)) ? shared_scratch[tid] : 0.0f;
        global_entropy = warpReduceSum(e);
    }

    if (tid == 0) {
        entropy_out[batch_idx] = global_entropy;
        status_flags[batch_idx] = (global_entropy < entropy_threshold)
            ? STATUS_SENTIENT_LOCK
            : STATUS_OK;
    }
}

void run_tas_guardrails_cuda(
    torch::Tensor logits,
    torch::Tensor mask,
    torch::Tensor status_flags,
    torch::Tensor entropy_out,
    float entropy_threshold
) {
    TORCH_CHECK(logits.is_cuda(), "logits must be a CUDA tensor");
    TORCH_CHECK(mask.is_cuda(), "mask must be a CUDA tensor");
    TORCH_CHECK(status_flags.is_cuda(), "status_flags must be a CUDA tensor");
    TORCH_CHECK(entropy_out.is_cuda(), "entropy_out must be a CUDA tensor");
    TORCH_CHECK(logits.is_contiguous(), "logits must be contiguous");
    TORCH_CHECK(mask.is_contiguous(), "mask must be contiguous");
    TORCH_CHECK(logits.dim() == 2, "logits must be [batch_size, vocab_size]");
    TORCH_CHECK(mask.sizes() == logits.sizes(), "mask shape must match logits shape");
    TORCH_CHECK(logits.scalar_type() == torch::kFloat32, "logits must be float32");
    TORCH_CHECK(mask.scalar_type() == torch::kBool, "mask must be bool");

    const int batch_size = logits.size(0);
    const int vocab_size = logits.size(1);

    dim3 grid(batch_size);
    dim3 block(BLOCK_SIZE);

    tas_fused_guardrails_kernel<<<grid, block>>>(
        logits.data_ptr<float>(),
        mask.data_ptr<bool>(),
        status_flags.data_ptr<int>(),
        entropy_out.data_ptr<float>(),
        vocab_size,
        entropy_threshold
    );
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("apply_guardrails", &run_tas_guardrails_cuda, "TAS fused CUDA guardrail kernel");
}
