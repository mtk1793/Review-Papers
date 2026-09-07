import torch
import numpy as np
import time
import sys

from config import (
    TrainingConfig, AttackConfig, IEEE_9_BUS, IEEE_39_BUS, IEEE_118_BUS,
    FAULT_NAMES, FAULT_SHORT_NAMES,
)
from model import build_model, count_parameters, get_model_size_mb, System1CNNLSTM
from data_pipeline import (
    generate_realistic_pmu_data, augment_dataset, normalize_data,
)
from train import (
    train_full, evaluate, compute_metrics, MultiObjectiveLoss,
    measure_inference_latency, bootstrap_confidence_interval,
    print_detailed_results,
)
from adversarial import evaluate_adversarial
from edge_deploy import print_edge_deployment_report, quantize_int8, fuse_model_ops
from torch.utils.data import DataLoader, TensorDataset


def main():
    print("=" * 60)
    print("  System-1: CNN-LSTM Dual-Stream Fault Detection")
    print("  Sub-10ms Reflexive Layer for CAPSM")
    print("=" * 60)

    config = TrainingConfig()
    print(f"\n  Device: {config.device}")
    print(f"  PyTorch: {torch.__version__}")

    primary_system = IEEE_39_BUS
    print(f"\n  Primary test system: {primary_system.name}")
    print(f"  Buses: {primary_system.num_buses}")

    print("\n" + "-" * 40)
    print("  [1/5] Generating realistic PMU data")
    print("  Using IEEE test system parameters (real grid topology)")
    print("-" * 40)

    base_examples = 5000
    print(f"  Generating {base_examples} base fault scenarios...")

    t_start = time.time()
    X, y, y_action = generate_realistic_pmu_data(
        primary_system,
        num_samples=base_examples,
        waveform_length=config.waveform_samples,
        sampling_rate_hz=config.sampling_rate_hz,
        random_seed=42,
    )
    print(f"  Generated in {time.time() - t_start:.1f}s")
    print(f"  Shape: {X.shape} (samples x timesteps x features)")

    print(f"\n  Augmenting to {config.num_augmented_examples} examples...")
    t_start = time.time()
    X, y, y_action = augment_dataset(X, y, y_action, rng_seed=42)
    actual_samples = X.shape[0]
    print(f"  Augmented in {time.time() - t_start:.1f}s")
    print(f"  Final dataset: {actual_samples} examples")

    fault_counts = np.bincount(y, minlength=7)
    print(f"\n  Class distribution:")
    for i, name in enumerate(FAULT_NAMES):
        print(f"    {name}: {fault_counts[i]} ({100*fault_counts[i]/actual_samples:.1f}%)")

    n_total = X.shape[0]
    n_test = config.test_set_size
    n_val = int(n_total * config.val_split)
    n_train = n_total - n_test - n_val

    indices = np.random.RandomState(42).permutation(n_total)
    train_idx = indices[:n_train]
    val_idx = indices[n_train:n_train + n_val]
    test_idx = indices[n_train + n_val:]

    X_train, y_train, y_action_train = X[train_idx], y[train_idx], y_action[train_idx]
    X_val, y_val, y_action_val = X[val_idx], y[val_idx], y_action[val_idx]
    X_test, y_test, y_action_test = X[test_idx], y[test_idx], y_action[test_idx]

    print(f"\n  Train: {len(train_idx)} | Val: {len(val_idx)} | Test: {len(test_idx)}")

    X_train, X_val, X_test = normalize_data(X_train, X_val, X_test)

    print("\n" + "-" * 40)
    print("  [2/5] Building and training model")
    print("-" * 40)

    model, history, best_val_acc, best_epoch = train_full(
        config, X_train, y_train, y_action_train,
        X_val, y_val, y_action_val,
        num_buses=primary_system.num_buses,
        seed=123,
    )

    n_params = count_parameters(model)
    model_size = get_model_size_mb(model)
    print(f"\n  Model parameters: {n_params:,} ({n_params/1e6:.2f}M)")
    print(f"  Model size (FP32): {model_size:.1f} MB")
    print(f"  Best val accuracy: {best_val_acc*100:.2f}% at epoch {best_epoch}")

    print("\n" + "-" * 40)
    print("  [3/5] Evaluating on test set")
    print("-" * 40)

    test_dataset = TensorDataset(
        torch.FloatTensor(X_test), torch.LongTensor(y_test),
        torch.FloatTensor(y_action_test),
    )
    test_loader = DataLoader(test_dataset, batch_size=config.batch_size,
                              shuffle=False)

    criterion = MultiObjectiveLoss(config.lambda_action, config.lambda_l2)
    test_loss, test_metrics, test_preds, test_targets = evaluate(
        model, test_loader, criterion, config.device)

    print_detailed_results(test_metrics, "FINAL TEST RESULTS")

    print(f"\n  Confusion Matrix (counts):")
    cm = test_metrics['confusion_matrix']
    header = "        " + "".join(f"{n:>8}" for n in FAULT_SHORT_NAMES)
    print(header)
    for i, name in enumerate(FAULT_SHORT_NAMES):
        row = "".join(f"{cm[i][j]:>8}" for j in range(7))
        print(f"  {name:>4}  {row}")

    print(f"\n  Normalized Confusion Matrix (row %):")
    cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True) * 100
    print(header)
    for i, name in enumerate(FAULT_SHORT_NAMES):
        row = "".join(f"{cm_norm[i][j]:>7.1f}" for j in range(7))
        print(f"  {name:>4}  {row}")

    acc_ci = bootstrap_confidence_interval(
        (test_preds == test_targets).astype(float),
        lambda x: x.mean()
    )
    print(f"\n  Bootstrap 95% CI for accuracy:")
    print(f"  Mean: {acc_ci[0]*100:.2f}% [{acc_ci[1]*100:.2f}% - {acc_ci[2]*100:.2f}%]")

    print("\n" + "-" * 40)
    print("  [4/5] Measuring inference latency")
    print("-" * 40)

    input_shape = (1, config.waveform_samples, primary_system.num_buses * 3)
    latency_stats = measure_inference_latency(model, input_shape, config.device)

    print(f"  GPU inference latency (N=1000):")
    print(f"    Mean:     {latency_stats['mean_ms']:.1f} ms")
    print(f"    Std:      {latency_stats['std_ms']:.1f} ms")
    print(f"    P50:      {latency_stats['p50_ms']:.1f} ms")
    print(f"    P95:      {latency_stats['p95_ms']:.1f} ms")
    print(f"    P99:      {latency_stats['p99_ms']:.1f} ms")
    print(f"    Min/Max:  {latency_stats['min_ms']:.1f}/{latency_stats['max_ms']:.1f} ms")

    pmu_interval = 33.3
    end_to_end = latency_stats['mean_ms'] + pmu_interval
    print(f"\n  End-to-end (GPU inf. + PMU frame): {end_to_end:.1f} ms")

    print("\n" + "-" * 40)
    print("  [5/5] Adversarial robustness & edge deployment")
    print("-" * 40)

    baseline_metrics, fgsm_results = evaluate_adversarial(
        model, X_test, y_test, y_action_test, config.batch_size, config.device)

    edge_projection = print_edge_deployment_report(model, latency_stats, config)

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Test Accuracy:     {test_metrics['accuracy']*100:.2f}%")
    print(f"  GPU Latency:       {latency_stats['mean_ms']:.1f} ± {latency_stats['std_ms']:.1f} ms")
    print(f"  End-to-End (GPU):  {end_to_end:.1f} ms")
    print(f"  Pi 5 Projected:    {edge_projection['edge_total_ms']:.1f} ms")
    print(f"  Parameters:        {n_params/1e6:.2f}M")
    print(f"  Model Size:        {model_size:.1f} MB (FP32)")
    print("=" * 60)

    print("\n  Saving model...")
    torch.save({
        'model_state_dict': model.state_dict(),
        'config': {
            'num_buses': primary_system.num_buses,
            'num_channels': config.num_channels,
            'num_fault_types': config.num_fault_types,
            'lstm_hidden': config.lstm_hidden,
        },
        'metrics': {
            'test_accuracy': float(test_metrics['accuracy']),
            'test_f1_macro': float(test_metrics['f1_macro']),
            'gpu_latency_ms': float(latency_stats['mean_ms']),
            'pi5_projected_ms': float(edge_projection['edge_total_ms']),
        },
        'history': history,
    }, "system1_cnn_lstm_checkpoint.pt")
    print("  Saved: system1_cnn_lstm_checkpoint.pt")

    return model, test_metrics, latency_stats


if __name__ == "__main__":
    model, metrics, latency = main()
