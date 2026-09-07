import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support,
    confusion_matrix
)
import time
from tqdm import tqdm

from config import TrainingConfig, FAULT_NAMES
from model import build_model, count_parameters, get_model_size_mb


def compute_metrics(y_true, y_pred, num_classes=7):
    acc = accuracy_score(y_true, y_pred)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=range(num_classes), average=None, zero_division=0
    )
    precision_macro = precision.mean()
    recall_macro = recall.mean()
    f1_macro = f1.mean()
    cm = confusion_matrix(y_true, y_pred, labels=range(num_classes))
    return {
        'accuracy': acc,
        'precision_per_class': precision,
        'recall_per_class': recall,
        'f1_per_class': f1,
        'support_per_class': support,
        'precision_macro': precision_macro,
        'recall_macro': recall_macro,
        'f1_macro': f1_macro,
        'confusion_matrix': cm,
    }


class MultiObjectiveLoss(nn.Module):
    def __init__(self, lambda_action=0.5, lambda_l2=1e-5):
        super().__init__()
        self.lambda_action = lambda_action
        self.lambda_l2 = lambda_l2
        self.ce_loss = nn.CrossEntropyLoss()
        self.mse_loss = nn.MSELoss()

    def forward(self, fault_logits, fault_targets, action_preds, action_targets,
                model_params):
        loss_fault = self.ce_loss(fault_logits, fault_targets)
        loss_action = self.mse_loss(action_preds, action_targets.view(
            action_preds.shape[0], -1))
        l2_reg = sum(torch.sum(p ** 2) for p in model_params)
        return loss_fault + self.lambda_action * loss_action + self.lambda_l2 * l2_reg


def train_epoch(model, dataloader, optimizer, criterion, device):
    model.train()
    total_loss = 0.0
    all_preds, all_targets = [], []

    for batch_X, batch_y, batch_action in dataloader:
        batch_X = batch_X.to(device)
        batch_y = batch_y.to(device)
        batch_action = batch_action.to(device)

        optimizer.zero_grad()
        fault_logits, action_preds = model(batch_X)
        loss = criterion(fault_logits, batch_y, action_preds, batch_action,
                         model.parameters())
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * batch_X.size(0)
        all_preds.append(fault_logits.argmax(dim=1).cpu().numpy())
        all_targets.append(batch_y.cpu().numpy())

    all_preds = np.concatenate(all_preds)
    all_targets = np.concatenate(all_targets)
    metrics = compute_metrics(all_targets, all_preds)

    return total_loss / len(dataloader.dataset), metrics


@torch.no_grad()
def evaluate(model, dataloader, criterion, device):
    model.eval()
    total_loss = 0.0
    all_preds, all_targets = [], []

    for batch_X, batch_y, batch_action in dataloader:
        batch_X = batch_X.to(device)
        batch_y = batch_y.to(device)
        batch_action = batch_action.to(device)

        fault_logits, action_preds = model(batch_X)
        loss = criterion(fault_logits, batch_y, action_preds, batch_action,
                         model.parameters())

        total_loss += loss.item() * batch_X.size(0)
        all_preds.append(fault_logits.argmax(dim=1).cpu().numpy())
        all_targets.append(batch_y.cpu().numpy())

    all_preds = np.concatenate(all_preds)
    all_targets = np.concatenate(all_targets)
    metrics = compute_metrics(all_targets, all_preds)

    return total_loss / len(dataloader.dataset), metrics, all_preds, all_targets


@torch.no_grad()
def measure_inference_latency(model, input_shape, device, num_warmup=1000,
                               num_measure=1000):
    model.eval()
    dummy_input = torch.randn(input_shape, device=device)
    if device == "cuda":
        torch.cuda.synchronize()
        starter = torch.cuda.Event(enable_timing=True)
        ender = torch.cuda.Event(enable_timing=True)

    for _ in range(num_warmup):
        _ = model(dummy_input)

    latencies = []
    for _ in range(num_measure):
        if device == "cuda":
            starter.record()
            _ = model(dummy_input)
            ender.record()
            torch.cuda.synchronize()
            latencies.append(starter.elapsed_time(ender))
        else:
            start = time.perf_counter()
            _ = model(dummy_input)
            latencies.append((time.perf_counter() - start) * 1000.0)

    latencies = np.array(latencies)
    return {
        'mean_ms': float(np.mean(latencies)),
        'std_ms': float(np.std(latencies)),
        'p10_ms': float(np.percentile(latencies, 10)),
        'p50_ms': float(np.percentile(latencies, 50)),
        'p95_ms': float(np.percentile(latencies, 95)),
        'p99_ms': float(np.percentile(latencies, 99)),
        'min_ms': float(np.min(latencies)),
        'max_ms': float(np.max(latencies)),
    }


def train_full(config: TrainingConfig, X_train, y_train, y_action_train,
               X_val, y_val, y_action_val, num_buses: int, seed: int):
    torch.manual_seed(seed)
    np.random.seed(seed)

    train_dataset = TensorDataset(
        torch.FloatTensor(X_train),
        torch.LongTensor(y_train),
        torch.FloatTensor(y_action_train),
    )
    val_dataset = TensorDataset(
        torch.FloatTensor(X_val),
        torch.LongTensor(y_val),
        torch.FloatTensor(y_action_val),
    )

    train_loader = DataLoader(train_dataset, batch_size=config.batch_size,
                               shuffle=True, drop_last=False)
    val_loader = DataLoader(val_dataset, batch_size=config.batch_size,
                             shuffle=False, drop_last=False)

    model = build_model(config, num_buses)
    criterion = MultiObjectiveLoss(config.lambda_action, config.lambda_l2)
    optimizer = optim.Adam(model.parameters(), lr=config.learning_rate_initial)

    scheduler = optim.lr_scheduler.MultiStepLR(
        optimizer,
        milestones=list(config.learning_rate_decay_epochs),
        gamma=config.learning_rate_decay_factors[0],
    )

    best_val_acc = 0.0
    best_epoch = 0
    patience_counter = 0
    history = {'train_loss': [], 'val_loss': [], 'val_acc': []}

    for epoch in range(1, config.max_epochs + 1):
        train_loss, train_metrics = train_epoch(
            model, train_loader, optimizer, criterion, config.device)
        val_loss, val_metrics, _, _ = evaluate(
            model, val_loader, criterion, config.device)

        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['val_acc'].append(val_metrics['accuracy'])

        scheduler.step()

        if val_metrics['accuracy'] > best_val_acc:
            best_val_acc = val_metrics['accuracy']
            best_epoch = epoch
            patience_counter = 0
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        else:
            patience_counter += 1

        if epoch % 5 == 0:
            tqdm.write(
                f"Epoch {epoch:3d} | Train Loss: {train_loss:.4f} | "
                f"Val Loss: {val_loss:.4f} | Val Acc: {val_metrics['accuracy']:.4f} | "
                f"LR: {scheduler.get_last_lr()[0]:.6f}"
            )

        if patience_counter >= config.early_stopping_patience:
            tqdm.write(f"Early stopping at epoch {epoch}")
            break

    model.load_state_dict(best_state)
    return model, history, best_val_acc, best_epoch


def bootstrap_confidence_interval(data, statistic_fn, n_iterations=1000,
                                   alpha=0.05):
    rng = np.random.RandomState(42)
    estimates = []
    for _ in range(n_iterations):
        sample = rng.choice(data, size=len(data), replace=True)
        estimates.append(statistic_fn(sample))
    estimates = np.array(estimates)
    ci_low = np.percentile(estimates, 100 * alpha / 2)
    ci_high = np.percentile(estimates, 100 * (1 - alpha / 2))
    return np.mean(estimates), ci_low, ci_high


def print_detailed_results(metrics, title="Results"):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(f"  Accuracy: {metrics['accuracy']*100:.2f}%")
    print(f"  Macro Precision: {metrics['precision_macro']:.4f}")
    print(f"  Macro Recall:    {metrics['recall_macro']:.4f}")
    print(f"  Macro F1:        {metrics['f1_macro']:.4f}")
    print(f"\n  Per-Class Metrics:")
    print(f"  {'Class':<28} {'Prec':>8} {'Recall':>8} {'F1':>8} {'Support':>8}")
    print(f"  {'-'*60}")
    for i, name in enumerate(FAULT_NAMES):
        print(f"  {name:<28} {metrics['precision_per_class'][i]:>8.4f} "
              f"{metrics['recall_per_class'][i]:>8.4f} "
              f"{metrics['f1_per_class'][i]:>8.4f} "
              f"{metrics['support_per_class'][i]:>8d}")
