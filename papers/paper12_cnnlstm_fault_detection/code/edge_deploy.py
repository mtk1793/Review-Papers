import torch
import torch.nn as nn
import numpy as np
import time

from config import TrainingConfig
from model import System1CNNLSTM, count_parameters, get_model_size_mb


def quantize_int8(model_fp32):
    model_fp32.eval()
    model_int8 = torch.quantization.quantize_dynamic(
        model_fp32,
        {nn.Linear, nn.LSTM, nn.Conv1d},
        dtype=torch.qint8,
    )
    return model_int8


def fuse_model_ops(model):
    model.eval()
    modules_to_fuse = []
    for name, module in model.named_children():
        if isinstance(module, nn.Sequential):
            children = list(module.named_children())
            for i in range(len(children) - 1):
                if (isinstance(children[i][1], nn.Conv1d) and
                        isinstance(children[i+1][1], nn.ReLU)):
                    modules_to_fuse.append(
                        [f"{name}.{children[i][0]}", f"{name}.{children[i+1][0]}"]
                    )
    if modules_to_fuse:
        torch.quantization.fuse_modules(model, modules_to_fuse, inplace=True)
    return model


def export_to_onnx(model, input_shape, filepath):
    model.eval()
    dummy_input = torch.randn(input_shape)
    torch.onnx.export(
        model,
        dummy_input,
        filepath,
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=['pmu_waveform'],
        output_names=['fault_logits', 'action_predictions'],
        dynamic_axes={
            'pmu_waveform': {0: 'batch_size'},
            'fault_logits': {0: 'batch_size'},
            'action_predictions': {0: 'batch_size'},
        },
    )
    return filepath


def project_edge_latency(gpu_latency_ms, model_params_m, quantization_factor=0.57,
                          arm_factor=4.5):
    edge_unoptimized = gpu_latency_ms * arm_factor
    edge_int8 = edge_unoptimized * quantization_factor
    bn_folding_speedup = 0.85
    edge_bn_folded = edge_int8 * bn_folding_speedup
    op_fusion_speedup = 0.94
    edge_fused = edge_bn_folded * op_fusion_speedup
    overhead_ms = 0.8
    return {
        'edge_unoptimized_ms': edge_unoptimized,
        'edge_int8_ms': edge_int8,
        'edge_bn_folded_ms': edge_bn_folded,
        'edge_fused_ms': edge_fused,
        'edge_total_ms': edge_fused + overhead_ms,
        'overhead_ms': overhead_ms,
    }


def print_edge_deployment_report(model, gpu_latency_stats, config):
    params_m = count_parameters(model) / 1e6
    model_size_fp32 = get_model_size_mb(model, torch.float32)

    print("\n" + "=" * 60)
    print("  EDGE DEPLOYMENT PROJECTION (Raspberry Pi 5)")
    print("=" * 60)
    print(f"  Model parameters: {params_m:.2f}M")
    print(f"  Model size (FP32): {model_size_fp32:.1f} MB")
    print(f"  GPU latency (mean): {gpu_latency_stats['mean_ms']:.1f} ms")

    projection = project_edge_latency(gpu_latency_stats['mean_ms'], params_m)
    print(f"\n  Projected Pi 5 latencies:")
    print(f"    Unoptimized FP32:  {projection['edge_unoptimized_ms']:.1f} ms")
    print(f"    INT8 quantized:    {projection['edge_int8_ms']:.1f} ms")
    print(f"    + BN folding:      {projection['edge_bn_folded_ms']:.1f} ms")
    print(f"    + Operator fusion: {projection['edge_fused_ms']:.1f} ms")
    print(f"    + Data overhead:   {projection['overhead_ms']:.1f} ms")
    print(f"    Total projected:   {projection['edge_total_ms']:.1f} ms")

    pmu_interval = 33.3
    total_edge = projection['edge_total_ms'] + pmu_interval
    print(f"\n  End-to-end (Pi 5 + PMU frame): {total_edge:.1f} ms")
    target = 50.0
    print(f"  IEEE C37.90 target (50 ms):    {'MEETS' if total_edge < target else 'EXCEEDS'}")

    return projection
