import torch
import numpy as np
from dataclasses import dataclass
from typing import Tuple

@dataclass
class SystemConfig:
    name: str
    num_buses: int
    num_generators: int
    num_loads: int
    num_lines: int

IEEE_9_BUS = SystemConfig("IEEE_9", 9, 3, 3, 6)
IEEE_39_BUS = SystemConfig("IEEE_39", 39, 10, 19, 46)
IEEE_118_BUS = SystemConfig("IEEE_118", 118, 54, 91, 186)

@dataclass
class TrainingConfig:
    num_channels: int = 3
    waveform_samples: int = 256
    sampling_rate_hz: int = 30000
    lstm_hidden: int = 256
    num_fault_types: int = 7
    batch_size: int = 64
    max_epochs: int = 50
    early_stopping_patience: int = 5
    learning_rate_initial: float = 0.001
    learning_rate_decay_epochs: Tuple[int, int] = (10, 25)
    learning_rate_decay_factors: Tuple[float, float] = (0.5, 0.2)
    lambda_action: float = 0.5
    lambda_l2: float = 1e-5
    dropout_lstm: float = 0.2
    dropout_fc: float = 0.3
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    random_seeds: Tuple[int, ...] = (42, 123, 456, 789, 1011)
    num_augmented_examples: int = 60000
    test_set_size: int = 1000
    val_split: float = 0.15

FAULT_NAMES = [
    "low_impedance_fault",
    "high_impedance_fault",
    "frequency_deviation",
    "voltage_sag",
    "islanding_event",
    "fdi_cyber_attack",
    "load_transient",
]

FAULT_SHORT_NAMES = ["LIF", "HIF", "FD", "VS", "IS", "FDI", "LT"]

@dataclass
class AttackConfig:
    fgsm_epsilons: Tuple[float, ...] = (0.01, 0.05, 0.10, 0.20)
    fdi_voltage_perturbation: float = 0.10
    fdi_frequency_perturbation_hz: float = 1.0
    fdi_coordinated_v_pert: float = 0.05
    fdi_coordinated_f_pert: float = 0.50
    fdi_sample_duration: Tuple[int, int] = (5, 50)
