"""
System-1: Complete Pipeline Orchestrator
Generates data -> Trains model -> Evaluates -> Produces results.

Usage:
    python run_all.py --device cpu    # CPU-only (safe, default)
    python run_all.py --device cuda   # GPU-accelerated
    python run_all.py --quick         # Fast test run (small dataset)
"""
import os
import sys
import time
import json
import argparse
import torch
import numpy as np

# Add current dir to path
sys.path.insert(0, os.path.dirname(__file__))

from generate_data import generate_all_systems, FaultConfig, PMUFaultGenerator
from train import train_system1
from evaluate import evaluate_system1
from model import System1_CNNLSTM


def main():
    parser = argparse.ArgumentParser(
        description='System-1: CNN-LSTM Fault Detection Pipeline'
    )
    parser.add_argument('--device', default='cpu',
                        choices=['cpu', 'cuda'],
                        help='Device for training/inference')
    parser.add_argument('--quick', action='store_true',
                        help='Quick test with small dataset')
    parser.add_argument('--data_dir', default='./data')
    parser.add_argument('--model_dir', default='./models')
    parser.add_argument('--results_dir', default='./results')
    args = parser.parse_args()

    if args.quick:
        n_events = 50  # Very small for testing
        print(f"\n{'='*60}")
        print("QUICK TEST MODE (small dataset)")
        print(f"{'='*60}")
    else:
        n_events = 5000  # Full dataset
        print(f"\n{'='*60}")
        print("FULL TRAINING MODE")
        print(f"{'='*60}")

    device_str = args.device
    if device_str == 'cuda' and not torch.cuda.is_available():
        print("CUDA not available, falling back to CPU")
        device_str = 'cpu'

    overall_start = time.time()
    results_summary = {}

    # ================================================================
    # STEP 1: Generate datasets
    # ================================================================
    print(f"\n{'#'*60}")
    print("# STEP 1: DATA GENERATION")
    print(f"{'#'*60}")

    systems = [
        ('IEEE9', 9),
        ('IEEE39', 39),
        ('IEEE118', 118),
    ]

    for name, n_buses in systems:
        print(f"\n  Generating {name} ({n_buses} buses)...")
        config = FaultConfig(
            num_buses=n_buses,
            n_events_per_type=n_events,
        )
        gen = PMUFaultGenerator(config)
        gen.generate_dataset(name, args.data_dir)

    data_time = time.time()

    # ================================================================
    # STEP 2: Train System-1 on IEEE 9-bus
    # ================================================================
    print(f"\n{'#'*60}")
    print("# STEP 2: TRAINING System-1")
    print(f"{'#'*60}")

    print("\n  Training on IEEE 9-bus (primary training system)...")
    trainer = train_system1(
        data_dir=args.data_dir,
        system='IEEE9',
        output_dir=args.model_dir,
        device_str=device_str,
    )
    train_time = time.time()

    # ================================================================
    # STEP 3: Evaluate on all three systems
    # ================================================================
    print(f"\n{'#'*60}")
    print("# STEP 3: EVALUATION (Zero-Shot Transfer)")
    print(f"{'#'*60}")

    for name, n_buses in systems:
        print(f"\n  Evaluating on {name} ({n_buses} buses)...")

        # Load trained model
        checkpoint = torch.load(
            os.path.join(args.model_dir, 'IEEE9', 'best_model.pt'),
            map_location=device_str
        )

        model = System1_CNNLSTM(
            num_buses=n_buses,
            num_channels=3,
            num_fault_types=7,
        )
        # Note: For different bus counts, we adapt by
        # training separate models or using the 9-bus weights
        # and fine-tuning. Here we evaluate the 9-bus-trained
        # model zero-shot on all systems.
        if n_buses == 9:
            model.load_state_dict(checkpoint['model_state_dict'])

        results = evaluate_system1(
            model_dir=os.path.join(args.model_dir, 'IEEE9'),
            data_dir=args.data_dir,
            system=name,
            results_dir=os.path.join(args.results_dir, name),
            device_str=device_str,
        )
        results_summary[name] = {
            'accuracy': results['accuracy'],
            'accuracy_ci': results['accuracy_ci_95'],
            'latency_mean': results['latency_ms']['mean_ms'],
        }

    eval_time = time.time()

    # ================================================================
    # SUMMARY
    # ================================================================
    print(f"\n{'='*60}")
    print("PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"\n  Timing:")
    print(f"    Data generation: {(data_time-overall_start)/60:.1f} min")
    print(f"    Training:        {(train_time-data_time)/60:.1f} min")
    print(f"    Evaluation:      {(eval_time-train_time)/60:.1f} min")
    print(f"    Total:           {(eval_time-overall_start)/60:.1f} min")

    print(f"\n  Results Summary:")
    print(f"  {'System':<12s} {'Accuracy':<12s} {'95% CI':<20s} {'Latency(ms)'}")
    print(f"  {'-'*60}")
    for name, r in results_summary.items():
        print(f"  {name:<12s} {r['accuracy']}%{'':8s}"
              f"[{r['accuracy_ci'][0]}-{r['accuracy_ci'][1]}]%{'':4s}"
              f"{r['latency_mean']}ms")

    # Save summary
    with open(os.path.join(args.results_dir, 'summary.json'), 'w') as f:
        json.dump({
            'timing': {
                'data_gen_min': round((data_time-overall_start)/60, 1),
                'training_min': round((train_time-data_time)/60, 1),
                'evaluation_min': round((eval_time-train_time)/60, 1),
                'total_min': round((eval_time-overall_start)/60, 1),
            },
            'results': results_summary,
            'device': device_str,
            'model_params': 1870000,
        }, f, indent=2)

    print(f"\n  All results saved to: {args.results_dir}/")
    print(f"  Models saved to:     {args.model_dir}/")
    print(f"  Data saved to:       {args.data_dir}/")
    print(f"\n{'='*60}")


if __name__ == '__main__':
    main()
