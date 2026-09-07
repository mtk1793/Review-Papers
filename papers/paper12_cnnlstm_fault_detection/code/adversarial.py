import torch
import numpy as np
from torch.utils.data import DataLoader, TensorDataset

from config import TrainingConfig, AttackConfig, FAULT_NAMES
from model import build_model
from train import evaluate, compute_metrics, MultiObjectiveLoss


def fgsm_attack(model, X, y, y_action, epsilon, device):
    model.eval()
    X_adv = X.clone().detach().requires_grad_(True).to(device)

    fault_logits, action_preds = model(X_adv)
    loss_fn = torch.nn.CrossEntropyLoss()
    loss = loss_fn(fault_logits, y.to(device))
    loss.backward()

    grad_sign = X_adv.grad.data.sign()
    X_perturbed = X.to(device) + epsilon * grad_sign
    X_perturbed = torch.clamp(X_perturbed, X.min(), X.max())

    with torch.no_grad():
        fault_logits_adv, _ = model(X_perturbed)
        preds = fault_logits_adv.argmax(dim=1).cpu().numpy()

    return preds, X_perturbed.cpu()


def evaluate_fgsm(model, dataloader, epsilons, y_action_ref, device):
    results = {}
    for eps in epsilons:
        all_preds, all_targets = [], []
        for batch_X, batch_y, _ in dataloader:
            preds, _ = fgsm_attack(model, batch_X, batch_y, None, eps, device)
            all_preds.append(preds)
            all_targets.append(batch_y.numpy())
        all_preds = np.concatenate(all_preds)
        all_targets = np.concatenate(all_targets)
        results[eps] = compute_metrics(all_targets, all_preds)
    return results


def fdi_voltage_attack(X, perturbation_ratio=0.10, num_buses_attacked=1,
                        random_seed=None):
    rng = np.random.RandomState(random_seed)
    X_attacked = X.clone()
    N, T, C = X_attacked.shape
    num_buses = C // 3

    for i in range(N):
        attack_buses = rng.choice(num_buses, size=min(num_buses_attacked, num_buses),
                                   replace=False)
        for bus in attack_buses:
            ch_v = bus * 3
            perturbation = 1.0 + perturbation_ratio * rng.choice([-1, 1])
            X_attacked[i, :, ch_v] *= perturbation
    return X_attacked


def fdi_frequency_attack(X, perturbation_hz=1.0, num_buses_attacked=1,
                          random_seed=None):
    rng = np.random.RandomState(random_seed)
    X_attacked = X.clone()
    N, T, C = X_attacked.shape
    num_buses = C // 3

    for i in range(N):
        attack_buses = rng.choice(num_buses, size=min(num_buses_attacked, num_buses),
                                   replace=False)
        for bus in attack_buses:
            ch_f = bus * 3 + 2
            perturbation = 1.0 + (perturbation_hz / 60.0) * rng.choice([-1, 1])
            X_attacked[i, :, ch_f] *= perturbation
    return X_attacked


def fdi_coordinated_attack(X, v_pert=0.05, f_pert=0.50, num_buses_attacked=3,
                            random_seed=None):
    rng = np.random.RandomState(random_seed)
    X_attacked = X.clone()
    N, T, C = X_attacked.shape
    num_buses = C // 3

    for i in range(N):
        attack_buses = rng.choice(num_buses, size=min(num_buses_attacked, num_buses),
                                   replace=False)
        for bus in attack_buses:
            ch_v = bus * 3
            ch_f = bus * 3 + 2
            X_attacked[i, :, ch_v] *= (1.0 + v_pert * rng.choice([-1, 1]))
            X_attacked[i, :, ch_f] *= (1.0 + (f_pert / 60.0) * rng.choice([-1, 1]))
    return X_attacked


def evaluate_adversarial(model, X_test, y_test, y_action_test, batch_size, device):
    dataset = TensorDataset(torch.FloatTensor(X_test), torch.LongTensor(y_test),
                            torch.FloatTensor(y_action_test))
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
    criterion = MultiObjectiveLoss()

    print("\n" + "=" * 60)
    print("  ADVERSARIAL ROBUSTNESS EVALUATION")
    print("=" * 60)

    _, baseline_metrics, _, _ = evaluate(model, loader, criterion, device)
    print(f"\n  Baseline (clean): {baseline_metrics['accuracy']*100:.2f}%")

    epsilons = [0.01, 0.05, 0.10, 0.20]
    fgsm_results = evaluate_fgsm(model, loader, epsilons, y_action_test, device)
    for eps, metrics in fgsm_results.items():
        print(f"  FGSM eps={eps:.2f}: {metrics['accuracy']*100:.2f}%")

    dataset_clean = TensorDataset(torch.FloatTensor(X_test),
                                   torch.LongTensor(y_test),
                                   torch.FloatTensor(y_action_test))
    loader_clean = DataLoader(dataset_clean, batch_size=batch_size, shuffle=False)

    attack_configs = [
        ("FDI Voltage +-10%", lambda X: fdi_voltage_attack(X, 0.10, 1, 42)),
        ("FDI Frequency +-1.0Hz", lambda X: fdi_frequency_attack(X, 1.0, 1, 42)),
        ("FDI Coordinated", lambda X: fdi_coordinated_attack(X, 0.05, 0.50, 3, 42)),
    ]

    for name, attack_fn in attack_configs:
        all_preds, all_targets = [], []
        for batch_X, batch_y, _ in loader_clean:
            X_adv = attack_fn(batch_X)
            with torch.no_grad():
                fault_logits, _ = model(X_adv.to(device))
                preds = fault_logits.argmax(dim=1).cpu().numpy()
            all_preds.append(preds)
            all_targets.append(batch_y.numpy())
        all_preds = np.concatenate(all_preds)
        all_targets = np.concatenate(all_targets)
        metrics = compute_metrics(all_targets, all_preds)
        print(f"  {name}: {metrics['accuracy']*100:.2f}%")
        for i, fname in enumerate(FAULT_NAMES):
            print(f"    {fname}: P={metrics['precision_per_class'][i]:.3f} "
                  f"R={metrics['recall_per_class'][i]:.3f} "
                  f"F1={metrics['f1_per_class'][i]:.3f}")

    return baseline_metrics, fgsm_results
