"""
System-1 Evaluation Pipeline
Complete testing with confidence intervals, McNemar test, per-class metrics,
confusion matrix, and latency benchmarking.
"""
import torch
from torch.utils.data import DataLoader
import numpy as np
import h5py
import os
import json
import time
from typing import Dict, List, Tuple
from collections import defaultdict
from scipy import stats
from model import System1_CNNLSTM


class Evaluator:
    """Complete evaluation suite for System-1."""

    FAULT_NAMES = [
        'Low-impedance', 'High-impedance', 'Freq-deviation',
        'Voltage-sag', 'Islanding', 'FDI-attack', 'Load-transient'
    ]

    def __init__(self, model: System1_CNNLSTM,
                 device: torch.device,
                 results_dir: str = "./results"):
        self.model = model.to(device)
        self.device = device
        self.results_dir = results_dir
        os.makedirs(results_dir, exist_ok=True)

    @torch.no_grad()
    def predict(self, test_loader: DataLoader) -> Tuple[np.ndarray, np.ndarray, List[float]]:
        """Run inference and collect predictions + latencies."""
        self.model.eval()
        all_preds, all_targets, all_latencies = [], [], []

        for X_batch, y_batch in test_loader:
            X_batch = X_batch.to(self.device)
            batch_size = X_batch.size(0)

            # Measure inference latency per batch
            if self.device.type == 'cuda':
                torch.cuda.synchronize()
                start = torch.cuda.Event(enable_timing=True)
                end = torch.cuda.Event(enable_timing=True)
                start.record()
                logits, _ = self.model(X_batch)
                end.record()
                torch.cuda.synchronize()
                latency = start.elapsed_time(end) / batch_size
            else:
                start = time.perf_counter()
                logits, _ = self.model(X_batch)
                latency = (time.perf_counter() - start) * 1000 / batch_size

            preds = logits.argmax(dim=1).cpu().numpy()
            targets = y_batch.numpy()

            all_preds.extend(preds)
            all_targets.extend(targets)
            all_latencies.extend([latency] * batch_size)

        return np.array(all_preds), np.array(all_targets), all_latencies

    def compute_per_class_metrics(self, preds: np.ndarray,
                                   targets: np.ndarray,
                                   n_classes: int = 7) -> Dict:
        """Precision, recall, F1 per class."""
        metrics = {}
        for c in range(n_classes):
            tp = np.sum((preds == c) & (targets == c))
            fp = np.sum((preds == c) & (targets != c))
            fn = np.sum((preds != c) & (targets == c))

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * precision * recall / (precision + recall)
                  if (precision + recall) > 0 else 0.0)

            metrics[self.FAULT_NAMES[c]] = {
                'accuracy': tp / max(1, np.sum(targets == c)),
                'precision': round(precision, 4),
                'recall': round(recall, 4),
                'f1': round(f1, 4),
            }
        return metrics

    def bootstrap_ci(self, accuracies: np.ndarray,
                     n_bootstrap: int = 1000,
                     alpha: float = 0.05) -> Tuple[float, float, float]:
        """Bootstrap 95% confidence interval."""
        means = []
        for _ in range(n_bootstrap):
            sample = np.random.choice(accuracies, size=len(accuracies),
                                      replace=True)
            means.append(np.mean(sample))
        means = np.array(means)
        lower = np.percentile(means, 100 * alpha / 2)
        upper = np.percentile(means, 100 * (1 - alpha / 2))
        return np.mean(means), lower, upper

    def mcnemar_test(self, preds_a: np.ndarray, preds_b: np.ndarray,
                     targets: np.ndarray, name: str = "baseline") -> Dict:
        """McNemar test for paired classifier comparison."""
        correct_a = (preds_a == targets)
        correct_b = (preds_b == targets)

        b01 = np.sum(~correct_a & correct_b)  # A wrong, B correct
        b10 = np.sum(correct_a & ~correct_b)  # A correct, B wrong

        if b01 + b10 == 0:
            return {'name': name, 'statistic': 0.0, 'p_value': 1.0}

        # McNemar with continuity correction
        stat = (abs(b01 - b10) - 1)**2 / (b01 + b10)
        p_value = 1 - stats.chi2.cdf(stat, 1)
        significant = p_value < 0.05

        return {
            'name': name,
            'b01_A_wrong_B_correct': int(b01),
            'b10_A_correct_B_wrong': int(b10),
            'statistic': round(float(stat), 4),
            'p_value': round(float(p_value), 6),
            'significant': bool(significant),
        }

    def evaluate(self, test_loader: DataLoader,
                 baseline_preds: Dict[str, np.ndarray] = None,
                 n_bootstrap: int = 1000) -> Dict:
        """Full evaluation pipeline."""
        print(f"\n{'='*60}")
        print(f"Evaluating System-1 on {self.device}")
        print(f"{'='*60}")

        preds, targets, latencies = self.predict(test_loader)
        accuracy = np.mean(preds == targets)
        n_samples = len(targets)

        # Bootstrap CI
        acc_samples = (preds == targets).astype(float)
        mean_acc, ci_lower, ci_upper = self.bootstrap_ci(
            acc_samples, n_bootstrap
        )

        # Per-class metrics
        per_class = self.compute_per_class_metrics(preds, targets)

        # Latency percentiles
        latencies = np.array(latencies)
        latency_stats = {
            'mean_ms': round(float(np.mean(latencies)), 2),
            'std_ms': round(float(np.std(latencies)), 2),
            'min_ms': round(float(np.min(latencies)), 2),
            'max_ms': round(float(np.max(latencies)), 2),
            'p10_ms': round(float(np.percentile(latencies, 10)), 2),
            'p50_ms': round(float(np.percentile(latencies, 50)), 2),
            'p95_ms': round(float(np.percentile(latencies, 95)), 2),
            'p99_ms': round(float(np.percentile(latencies, 99)), 2),
        }

        # Confusion matrix
        confusion = np.zeros((7, 7), dtype=int)
        for t, p in zip(targets, preds):
            confusion[t, p] += 1

        results = {
            'n_samples': int(n_samples),
            'accuracy': round(float(accuracy * 100), 2),
            'accuracy_ci_95': [
                round(float(ci_lower * 100), 2),
                round(float(ci_upper * 100), 2),
            ],
            'per_class': per_class,
            'latency_ms': latency_stats,
            'confusion_matrix': confusion.tolist(),
            'fault_names': self.FAULT_NAMES,
        }

        # McNemar tests
        if baseline_preds:
            results['mcnemar_tests'] = {}
            for name, base_preds in baseline_preds.items():
                results['mcnemar_tests'][name] = self.mcnemar_test(
                    preds, base_preds, targets, name
                )

        # Print summary
        self._print_summary(results)

        # Save
        with open(os.path.join(self.results_dir, 'evaluation.json'), 'w') as f:
            json.dump(results, f, indent=2)

        return results

    def _print_summary(self, results: Dict):
        print(f"\n--- RESULTS SUMMARY ---")
        print(f"Samples: {results['n_samples']}")
        print(f"Accuracy: {results['accuracy']}% "
              f"(95% CI: {results['accuracy_ci_95']})")
        print(f"\nLatency (ms):")
        lat = results['latency_ms']
        print(f"  Mean: {lat['mean_ms']}, Std: {lat['std_ms']}")
        print(f"  P50: {lat['p50_ms']}, P95: {lat['p95_ms']}, "
              f"P99: {lat['p99_ms']}")
        print(f"\nPer-class accuracy:")
        for name, m in results['per_class'].items():
            print(f"  {name:20s}: {m['accuracy']*100:6.2f}%  "
                  f"F1={m['f1']:.3f}")

        if 'mcnemar_tests' in results:
            print(f"\nMcNemar tests (vs System-1):")
            for name, test in results['mcnemar_tests'].items():
                sig = "***" if test['significant'] else "ns"
                print(f"  {name:20s}: p={test['p_value']:.6f} {sig}")

    def benchmark_latency(self, input_shape: Tuple,
                          n_warmup: int = 100,
                          n_measure: int = 1000) -> Dict:
        """Detailed latency benchmarking."""
        self.model.eval()
        dummy = torch.randn(1, *input_shape).to(self.device)

        # Warmup
        for _ in range(n_warmup):
            self.model(dummy)

        latencies = []
        for _ in range(n_measure):
            if self.device.type == 'cuda':
                torch.cuda.synchronize()
                start = torch.cuda.Event(enable_timing=True)
                end = torch.cuda.Event(enable_timing=True)
                start.record()
                self.model(dummy)
                end.record()
                torch.cuda.synchronize()
                latencies.append(start.elapsed_time(end))
            else:
                start = time.perf_counter()
                self.model(dummy)
                latencies.append(
                    (time.perf_counter() - start) * 1000
                )

        latencies = np.array(latencies)
        return {
            'mean_ms': round(float(np.mean(latencies)), 2),
            'std_ms': round(float(np.std(latencies)), 2),
            'p50_ms': round(float(np.percentile(latencies, 50)), 2),
            'p95_ms': round(float(np.percentile(latencies, 95)), 2),
            'p99_ms': round(float(np.percentile(latencies, 99)), 2),
            'min_ms': round(float(np.min(latencies)), 2),
            'max_ms': round(float(np.max(latencies)), 2),
        }


def evaluate_system1(model_dir: str = "./models/IEEE39",
                     data_dir: str = "./data",
                     system: str = "IEEE39",
                     results_dir: str = "./results",
                     device_str: str = "cuda") -> Dict:
    """Load trained model and run evaluation."""
    device = torch.device(device_str if torch.cuda.is_available() else "cpu")

    # Load model
    checkpoint = torch.load(
        os.path.join(model_dir, 'best_model.pt'),
        map_location=device
    )

    # Get model config from data
    test_path = os.path.join(data_dir, f"{system}_test.h5")
    with h5py.File(test_path, 'r') as f:
        n_buses = f.attrs['n_buses']
        n_channels = f.attrs['n_channels']
        n_fault_types = f.attrs['n_fault_types']

    model = System1_CNNLSTM(
        num_buses=n_buses,
        num_channels=n_channels,
        num_fault_types=n_fault_types,
    )
    model.load_state_dict(checkpoint['model_state_dict'])

    # Load test data
    test_dataset = PMUDataset(test_path, augment=False)
    test_loader = DataLoader(test_dataset, batch_size=64,
                             shuffle=False)

    # Evaluate
    evaluator = Evaluator(model, device, results_dir)
    results = evaluator.evaluate(test_loader, n_bootstrap=1000)

    # Benchmark
    bench = evaluator.benchmark_latency(
        (256, n_buses * n_channels)
    )
    print(f"\nBenchmark latency: {bench}")

    with open(os.path.join(results_dir, 'benchmark.json'), 'w') as f:
        json.dump(bench, f, indent=2)

    return results


class PMUDataset(torch.utils.data.Dataset):
    """Simple HDF5-backed dataset (no augmentation)."""
    def __init__(self, h5_path, augment=False):
        with h5py.File(h5_path, 'r') as f:
            self.X = torch.from_numpy(f['X'][:].astype(np.float32))
            self.y = torch.from_numpy(f['y'][:].astype(np.int64))

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--system', default='IEEE39')
    parser.add_argument('--model_dir', default='./models/IEEE39')
    parser.add_argument('--data_dir', default='./data')
    parser.add_argument('--results_dir', default='./results')
    parser.add_argument('--device', default='cuda')
    args = parser.parse_args()

    evaluate_system1(args.model_dir, args.data_dir,
                     args.system, args.results_dir, args.device)
