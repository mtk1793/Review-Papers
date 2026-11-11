import torch
import numpy as np
from torch.utils.data import DataLoader, TensorDataset
import time

from config import (
    TrainingConfig, IEEE_9_BUS, IEEE_39_BUS, IEEE_118_BUS,
    FAULT_NAMES,
)
from model import build_model, count_parameters
from data_pipeline import (
    generate_realistic_pmu_data, augment_dataset, normalize_data,
)
from train import (
    evaluate, compute_metrics, MultiObjectiveLoss,
    bootstrap_confidence_interval,
)


def zero_shot_evaluate(model, system, config, train_stats):
    print(f"\n  Generating {system.name} test data...")
    X, y, y_action = generate_realistic_pmu_data(
        system, num_samples=1000, waveform_length=config.waveform_samples,
        sampling_rate_hz=config.sampling_rate_hz, random_seed=99,
    )

    X_norm = (X - train_stats['mean']) / (train_stats['std'])

    dataset = TensorDataset(
        torch.FloatTensor(X_norm), torch.LongTensor(y),
        torch.FloatTensor(y_action),
    )
    loader = DataLoader(dataset, batch_size=config.batch_size, shuffle=False)
    criterion = MultiObjectiveLoss()

    _, metrics, preds, targets = evaluate(model, loader, criterion, config.device)
    return metrics


def transfer_learning_evaluate(model, system, config, train_stats,
                                train_fraction=0.10, seed=42):
    import torch.optim as optim
    from train import train_epoch

    print(f"\n  Generating {system.name} fine-tuning data ({train_fraction*100:.0f}%)...")
    n_train = max(100, int(5000 * train_fraction))
    X, y, y_action = generate_realistic_pmu_data(
        system, num_samples=n_train + 1000, waveform_length=config.waveform_samples,
        sampling_rate_hz=config.sampling_rate_hz, random_seed=seed,
    )

    X_norm = (X - train_stats['mean']) / (train_stats['std'])

    X_ft, y_ft, y_action_ft = X_norm[:n_train], y[:n_train], y_action[:n_train]
    X_test, y_test, y_action_test = X_norm[n_train:], y[n_train:], y_action[n_train:]

    ft_dataset = TensorDataset(
        torch.FloatTensor(X_ft), torch.LongTensor(y_ft),
        torch.FloatTensor(y_action_ft),
    )
    ft_loader = DataLoader(ft_dataset, batch_size=config.batch_size, shuffle=True)

    optimizer = optim.Adam(model.parameters(), lr=config.learning_rate_initial * 0.1)
    criterion = MultiObjectiveLoss(config.lambda_action, config.lambda_l2)

    for epoch in range(10):
        train_epoch(model, ft_loader, optimizer, criterion, config.device)

    test_dataset = TensorDataset(
        torch.FloatTensor(X_test), torch.LongTensor(y_test),
        torch.FloatTensor(y_action_test),
    )
    test_loader = DataLoader(test_dataset, batch_size=config.batch_size, shuffle=False)
    _, metrics, preds, targets = evaluate(model, test_loader, criterion, config.device)

    return metrics


def run_cross_system_evaluation(config, model_9bus, train_stats):
    print("\n" + "=" * 60)
    print("  CROSS-SYSTEM GENERALIZATION EVALUATION")
    print("=" * 60)

    results = {}
    print(f"\n  {'System':<15} {'Accuracy':>10} {'Macro F1':>10}")
    print(f"  {'-'*35}")

    for system in [IEEE_9_BUS, IEEE_39_BUS, IEEE_118_BUS]:
        sys_model = build_model(config, system.num_buses)

        if system.name == "IEEE_9":
            sys_model.load_state_dict(model_9bus.state_dict())
            metrics = zero_shot_evaluate(sys_model, system, config, train_stats)
        else:
            sys_model.load_state_dict(model_9bus.state_dict(), strict=False)
            metrics = zero_shot_evaluate(sys_model, system, config, train_stats)

        results[system.name] = metrics
        print(f"  {system.name:<15} {metrics['accuracy']*100:>9.2f}% "
              f"{metrics['f1_macro']:>10.4f}")

        for i, name in enumerate(FAULT_NAMES):
            print(f"    {name:<26} P={metrics['precision_per_class'][i]:.3f} "
                  f"R={metrics['recall_per_class'][i]:.3f} "
                  f"F1={metrics['f1_per_class'][i]:.3f}")

    print(f"\n  TRANSFER LEARNING (118-bus)")
    print(f"  {'Fraction':>12} {'Accuracy':>10} {'Macro F1':>10}")
    print(f"  {'-'*35}")

    fractions = [0.05, 0.10, 0.20]
    tl_results = {}

    for frac in fractions:
        tl_model = build_model(config, IEEE_118_BUS.num_buses)
        tl_model.load_state_dict(model_9bus.state_dict(), strict=False)

        metrics = transfer_learning_evaluate(
            tl_model, IEEE_118_BUS, config, train_stats,
            train_fraction=frac, seed=42 + int(frac * 100),
        )
        tl_results[frac] = metrics
        print(f"  {frac*100:>10.0f}%      {metrics['accuracy']*100:>9.2f}% "
              f"{metrics['f1_macro']:>10.4f}")

    return results, tl_results


if __name__ == "__main__":
    config = TrainingConfig()
    print("Loading base 9-bus model training data...")

    X_base, y_base, y_action_base = generate_realistic_pmu_data(
        IEEE_9_BUS, num_samples=5000, waveform_length=config.waveform_samples,
        sampling_rate_hz=config.sampling_rate_hz, random_seed=42,
    )

    X_aug, y_aug, y_action_aug = augment_dataset(X_base, y_base, y_action_base)
    X_norm, _, _ = normalize_data(X_aug, y_aug, y_action_aug)

    train_stats = {
        'mean': X_base.mean(axis=(0, 1), keepdims=True),
        'std': X_base.std(axis=(0, 1), keepdims=True) + 1e-8,
    }

    model_9bus = build_model(config, IEEE_9_BUS.num_buses)
    print("Note: Use main.py to train the model first, then run cross-system eval.")
    print("Using untrained model for demonstration only.")

    results, tl_results = run_cross_system_evaluation(config, model_9bus, train_stats)
