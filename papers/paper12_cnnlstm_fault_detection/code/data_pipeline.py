import numpy as np
from scipy import signal
from typing import Dict, Tuple, List
import h5py

from config import (
    IEEE_9_BUS, IEEE_39_BUS, IEEE_118_BUS, SystemConfig,
    TrainingConfig, FAULT_NAMES,
)


IEEE_BUS_DATA = {
    "IEEE_9": {
        "base_MVA": 100.0,
        "bus_voltages": [
            1.040, 1.025, 1.025, 1.026, 0.996, 1.013, 1.026, 1.016, 1.032
        ],
        "bus_angles_deg": [
            0.00, 9.30, 4.70, -2.20, -4.00, -3.70, 0.70, 0.70, 1.97
        ],
        "gen_buses": [1, 2, 3],
        "gen_inertia_H": [47.28, 12.80, 6.02],
        "line_impedances": [
            (4, 5, 0.010, 0.085, 0.088),
            (4, 6, 0.017, 0.092, 0.079),
            (5, 7, 0.032, 0.161, 0.153),
            (6, 8, 0.039, 0.170, 0.179),
            (7, 8, 0.0085, 0.072, 0.0745),
            (8, 9, 0.0119, 0.1008, 0.1045),
        ],
    },
    "IEEE_39": {
        "base_MVA": 100.0,
        "bus_voltages": [
            1.048, 1.045, 1.030, 1.012, 1.008, 1.010, 1.000, 0.998,
            1.035, 1.018, 1.015, 1.001, 1.015, 1.012, 1.016, 1.032,
            1.034, 1.033, 1.050, 0.993, 1.032, 1.050, 1.050, 1.038,
            1.058, 1.053, 1.038, 1.038, 1.050, 1.047, 1.050, 1.050,
            1.050, 1.050, 1.050, 1.050, 1.050, 1.050, 1.050,
        ],
        "bus_angles_deg": [
            -6.58, -8.29, -9.92, -10.67, -9.29, -8.70, -10.97, -11.45,
            -9.33, -6.41, -7.24, -7.22, -7.10, -8.77, -9.25, -7.84,
            -8.90, -9.75, -2.51, -4.69, -5.41, -1.67, -1.55, -7.85,
            -5.64, -6.99, -9.18, -3.43, -0.60, -4.59, 0.00, -1.25,
            -0.86, -2.80, -3.56, -4.10, -10.00, -4.80, -11.30,
        ],
        "gen_buses": list(range(30, 40)),
        "gen_inertia_H": [500, 30.3, 35.8, 28.6, 26.0, 34.8, 26.4, 24.3, 34.5, 42.0],
    },
    "IEEE_118": {
        "base_MVA": 100.0,
    },
}


def generate_realistic_pmu_data(
    system: SystemConfig,
    num_samples: int,
    waveform_length: int = 256,
    sampling_rate_hz: int = 30000,
    base_frequency_hz: float = 60.0,
    random_seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.RandomState(random_seed)

    X = np.zeros((num_samples, waveform_length, system.num_buses * 3), dtype=np.float32)
    y = np.zeros(num_samples, dtype=np.int64)
    y_action_p = np.zeros((num_samples, system.num_buses), dtype=np.float32)
    y_action_q = np.zeros((num_samples, system.num_buses), dtype=np.float32)

    samples_per_fault = num_samples // 7
    t = np.arange(waveform_length) / sampling_rate_hz

    system_key = system.name
    if system_key not in IEEE_BUS_DATA:
        system_key = "IEEE_9"

    bus_data = IEEE_BUS_DATA[system_key]
    base_voltages = np.array(bus_data.get("bus_voltages", np.ones(system.num_buses)))
    if len(base_voltages) < system.num_buses:
        base_voltages = np.pad(base_voltages, (0, system.num_buses - len(base_voltages)),
                               mode='edge')

    pmu_noise_std_v = 0.001
    pmu_noise_std_i = 0.002
    pmu_noise_std_f = 0.0005

    pmu_total_vector_error = 0.01
    pmu_frequency_error_hz = 0.005

    def _apply_pmu_noise(signal_arr, noise_std):
        noise = rng.randn(*signal_arr.shape).astype(np.float32) * noise_std
        return signal_arr + noise

    def _generate_normal_waveform(bus_idx):
        v_mag = base_voltages[bus_idx] * (1.0 + pmu_total_vector_error * rng.randn())
        v = v_mag * np.sin(2 * np.pi * base_frequency_hz * t)
        i_mag = 0.5 + 0.1 * rng.randn()
        i = i_mag * np.sin(2 * np.pi * base_frequency_hz * t - 0.3)
        f = base_frequency_hz + pmu_frequency_error_hz * rng.randn(waveform_length)
        return v.astype(np.float32), i.astype(np.float32), f.astype(np.float32)

    fault_onset_min = 20
    fault_onset_max = 80

    for f_idx in range(7):
        start = f_idx * samples_per_fault
        end = start + samples_per_fault if f_idx < 6 else num_samples

        for sample_i in range(start, end):
            fault_bus = rng.randint(0, system.num_buses)
            fault_onset = rng.randint(fault_onset_min, fault_onset_max)

            if f_idx == 0:
                _make_low_impedance_fault(X, sample_i, t, fault_bus, fault_onset,
                                           system, rng, base_voltages, base_frequency_hz)
            elif f_idx == 1:
                _make_high_impedance_fault(X, sample_i, t, fault_bus, fault_onset,
                                            system, rng, base_voltages, base_frequency_hz)
            elif f_idx == 2:
                _make_frequency_deviation(X, sample_i, t, fault_bus, fault_onset,
                                          system, rng, base_voltages, base_frequency_hz)
            elif f_idx == 3:
                _make_voltage_sag(X, sample_i, t, fault_bus, fault_onset,
                                  system, rng, base_voltages, base_frequency_hz)
            elif f_idx == 4:
                _make_islanding(X, sample_i, t, fault_bus, fault_onset,
                                system, rng, base_voltages, base_frequency_hz)
            elif f_idx == 5:
                _make_fdi_attack(X, sample_i, t, fault_bus, fault_onset,
                                 system, rng, base_voltages, base_frequency_hz)
            elif f_idx == 6:
                _make_load_transient(X, sample_i, t, fault_bus, fault_onset,
                                     system, rng, base_voltages, base_frequency_hz)

            y[sample_i] = f_idx
            y_action_p[sample_i, fault_bus] = np.float32(rng.uniform(-0.1, 0.1))
            y_action_q[sample_i, fault_bus] = np.float32(rng.uniform(-0.05, 0.05))

    for bus in range(system.num_buses):
        ch_v = bus * 3
        ch_i = bus * 3 + 1
        ch_f = bus * 3 + 2
        X[:, :, ch_v] = _apply_pmu_noise(X[:, :, ch_v], pmu_noise_std_v)
        X[:, :, ch_i] = _apply_pmu_noise(X[:, :, ch_i], pmu_noise_std_i)
        X[:, :, ch_f] = _apply_pmu_noise(X[:, :, ch_f], pmu_noise_std_f)

    return X, y, np.stack([y_action_p, y_action_q], axis=-1)


def _make_low_impedance_fault(X, idx, t, fault_bus, fault_onset, system, rng,
                               base_voltages, base_freq):
    ch_v = fault_bus * 3
    ch_i = fault_bus * 3 + 1
    ch_f = fault_bus * 3 + 2

    v_mag = base_voltages[fault_bus]
    i_fault = 5.0 + rng.uniform(0, 10)

    for s in range(X.shape[1]):
        if s < fault_onset:
            X[idx, s, ch_v] = v_mag * np.sin(2 * np.pi * base_freq * t[s])
            X[idx, s, ch_i] = 0.5 * np.sin(2 * np.pi * base_freq * t[s] - 0.3)
        else:
            v_depressed = v_mag * 0.30 * (1 + 0.1 * rng.randn())
            X[idx, s, ch_v] = v_depressed * np.sin(2 * np.pi * base_freq * t[s])
            X[idx, s, ch_i] = i_fault * np.sin(2 * np.pi * base_freq * t[s] - 0.3)
        X[idx, s, ch_f] = base_freq + 0.01 * rng.randn()

    for other_bus in range(system.num_buses):
        if other_bus != fault_bus:
            ch_v_o = other_bus * 3
            ch_i_o = other_bus * 3 + 1
            ch_f_o = other_bus * 3 + 2
            sag = 1.0 - 0.3 * np.exp(-abs(other_bus - fault_bus) / system.num_buses)
            for s in range(X.shape[1]):
                if s < fault_onset:
                    X[idx, s, ch_v_o] = base_voltages[other_bus] * np.sin(
                        2 * np.pi * base_freq * t[s])
                else:
                    v_prop = base_voltages[other_bus] * sag * (
                        1 + 0.02 * rng.randn())
                    X[idx, s, ch_v_o] = v_prop * np.sin(
                        2 * np.pi * base_freq * t[s])
                X[idx, s, ch_i_o] = 0.5 * np.sin(2 * np.pi * base_freq * t[s] - 0.3)
                X[idx, s, ch_f_o] = base_freq + 0.01 * rng.randn()


def _make_high_impedance_fault(X, idx, t, fault_bus, fault_onset, system, rng,
                                base_voltages, base_freq):
    ch_v = fault_bus * 3
    sag_duration = 150
    for s in range(X.shape[1]):
        if s < fault_onset:
            X[idx, s, ch_v] = base_voltages[fault_bus] * np.sin(
                2 * np.pi * base_freq * t[s])
        elif s < fault_onset + sag_duration:
            progress = (s - fault_onset) / sag_duration
            v_mag = base_voltages[fault_bus] * (1.0 - 0.08 * progress)
            X[idx, s, ch_v] = v_mag * np.sin(2 * np.pi * base_freq * t[s])
        else:
            X[idx, s, ch_v] = base_voltages[fault_bus] * 0.92 * np.sin(
                2 * np.pi * base_freq * t[s])
        X[idx, s, ch_v + 1] = 0.5 * np.sin(2 * np.pi * base_freq * t[s] - 0.3)
        X[idx, s, ch_v + 2] = base_freq + 0.01 * rng.randn()
    for other_bus in range(system.num_buses):
        if other_bus != fault_bus:
            ch_v_o = other_bus * 3
            ch_i_o = other_bus * 3 + 1
            ch_f_o = other_bus * 3 + 2
            for s in range(X.shape[1]):
                X[idx, s, ch_v_o] = base_voltages[other_bus] * np.sin(
                    2 * np.pi * base_freq * t[s])
                X[idx, s, ch_i_o] = 0.5 * np.sin(2 * np.pi * base_freq * t[s] - 0.3)
                X[idx, s, ch_f_o] = base_freq + 0.01 * rng.randn()


def _make_frequency_deviation(X, idx, t, fault_bus, fault_onset, system, rng,
                               base_voltages, base_freq):
    H = 5.0
    freq_nadir = base_freq - 2.0 * rng.uniform(0.8, 1.2)
    tau = 2 * H / 60.0

    for bus in range(system.num_buses):
        ch_v = bus * 3
        ch_i = bus * 3 + 1
        ch_f = bus * 3 + 2
        for s in range(X.shape[1]):
            if s < fault_onset:
                f_inst = base_freq
            else:
                dt = (s - fault_onset) / 30000
                f_inst = freq_nadir + (base_freq - freq_nadir) * np.exp(-dt / tau)
                f_inst += 0.05 * rng.randn()
            X[idx, s, ch_f] = f_inst
            X[idx, s, ch_v] = base_voltages[bus] * np.sin(2 * np.pi * base_freq * t[s])
            X[idx, s, ch_i] = 0.5 * np.sin(2 * np.pi * base_freq * t[s] - 0.3)


def _make_voltage_sag(X, idx, t, fault_bus, fault_onset, system, rng,
                       base_voltages, base_freq):
    sag_depth = 0.40 + rng.uniform(0, 0.30)
    sag_duration = 80

    for bus in range(system.num_buses):
        ch_v = bus * 3
        ch_i = bus * 3 + 1
        ch_f = bus * 3 + 2
        distance = abs(bus - fault_bus)
        bus_sag = sag_depth * np.exp(-distance / (system.num_buses * 0.1))

        for s in range(X.shape[1]):
            if s < fault_onset:
                v_mag_b = base_voltages[bus]
            elif s < fault_onset + sag_duration:
                v_mag_b = base_voltages[bus] * (1.0 - bus_sag)
            else:
                recovery = min(1.0, (s - fault_onset - sag_duration) / 40)
                v_mag_b = base_voltages[bus] * (1.0 - bus_sag * (1.0 - recovery))

            X[idx, s, ch_v] = v_mag_b * np.sin(2 * np.pi * base_freq * t[s])
            X[idx, s, ch_i] = 0.5 * np.sin(2 * np.pi * base_freq * t[s] - 0.3)
            X[idx, s, ch_f] = base_freq + 0.01 * rng.randn()


def _make_islanding(X, idx, t, fault_bus, fault_onset, system, rng,
                     base_voltages, base_freq):
    freq_drift = base_freq * (1.0 + rng.uniform(-0.03, 0.03))
    v_oscillation = 0.05

    for bus in range(system.num_buses):
        ch_v = bus * 3
        ch_i = bus * 3 + 1
        ch_f = bus * 3 + 2
        for s in range(X.shape[1]):
            if s < fault_onset:
                f_inst = base_freq
                v_mag = base_voltages[bus]
            else:
                dt_s = (s - fault_onset) / 30000
                f_inst = base_freq + (freq_drift - base_freq) * (1 - np.exp(-dt_s / 0.5))
                v_mag = base_voltages[bus] * (1.0 + v_oscillation * np.sin(2 * np.pi * 5.0 * dt_s))
            X[idx, s, ch_v] = v_mag * np.sin(2 * np.pi * base_freq * t[s])
            X[idx, s, ch_i] = 0.5 * np.sin(2 * np.pi * base_freq * t[s] - 0.3)
            X[idx, s, ch_f] = f_inst


def _make_fdi_attack(X, idx, t, fault_bus, fault_onset, system, rng,
                      base_voltages, base_freq):
    attack_buses = rng.choice(system.num_buses, size=min(3, system.num_buses),
                               replace=False)
    v_pert = 0.05 + rng.uniform(0, 0.05)
    f_pert = 0.5 + rng.uniform(0, 0.5)

    for bus in range(system.num_buses):
        ch_v = bus * 3
        ch_i = bus * 3 + 1
        ch_f = bus * 3 + 2
        is_attacked = bus in attack_buses

        for s in range(X.shape[1]):
            if s < fault_onset or not is_attacked:
                v_mag = base_voltages[bus]
                f_inst = base_freq
            else:
                v_mag = base_voltages[bus] * (1.0 + v_pert * rng.choice([-1, 1]))
                f_inst = base_freq + f_pert * rng.choice([-1, 1])

            X[idx, s, ch_v] = v_mag * np.sin(2 * np.pi * base_freq * t[s])
            X[idx, s, ch_i] = 0.5 * np.sin(2 * np.pi * base_freq * t[s] - 0.3)
            X[idx, s, ch_f] = f_inst


def _make_load_transient(X, idx, t, fault_bus, fault_onset, system, rng,
                          base_voltages, base_freq):
    load_change = 0.20 * rng.choice([-1, 1])
    v_change = -0.02 * load_change

    for bus in range(system.num_buses):
        ch_v = bus * 3
        ch_i = bus * 3 + 1
        ch_f = bus * 3 + 2

        for s in range(X.shape[1]):
            if s < fault_onset:
                v_mag = base_voltages[bus]
                i_mag = 0.5
            else:
                v_mag = base_voltages[bus] * (1.0 + v_change *
                                              np.exp(-abs(bus - fault_bus) / 5))
                i_mag = 0.5 * (1.0 + load_change * np.exp(-abs(bus - fault_bus) / 5))

            X[idx, s, ch_v] = v_mag * np.sin(2 * np.pi * base_freq * t[s])
            X[idx, s, ch_i] = i_mag * np.sin(2 * np.pi * base_freq * t[s] - 0.3)
            X[idx, s, ch_f] = base_freq + 0.01 * rng.randn()


def augment_dataset(X, y, y_action, rng_seed=42):
    rng = np.random.RandomState(rng_seed)
    N, T, C = X.shape

    X_aug, y_aug, y_action_aug = [X], [y], [y_action]

    for i in range(N):
        shift = rng.randint(-10, 11)
        if shift > 0:
            X_pad = np.pad(X[i], ((shift, 0), (0, 0)), mode='edge')[:T]
        elif shift < 0:
            X_pad = np.pad(X[i], ((0, -shift), (0, 0)), mode='edge')[-T:]
        else:
            X_pad = X[i].copy()
        X_aug.append(X_pad[np.newaxis])
        y_aug.append(np.array([y[i]]))
        y_action_aug.append(y_action[i][np.newaxis])

    for i in range(N):
        noise = rng.randn(T, C).astype(np.float32) * 0.01
        X_aug.append((X[i] + noise)[np.newaxis])
        y_aug.append(np.array([y[i]]))
        y_action_aug.append(y_action[i][np.newaxis])

    for i in range(N):
        scale = 1.0 + rng.uniform(-0.05, 0.05)
        X_aug.append((X[i] * scale)[np.newaxis])
        y_aug.append(np.array([y[i]]))
        y_action_aug.append(y_action[i][np.newaxis])

    X_out = np.concatenate(X_aug, axis=0)
    y_out = np.concatenate(y_aug, axis=0)
    y_action_out = np.concatenate(y_action_aug, axis=0)
    return X_out, y_out, y_action_out


def normalize_data(X_train, X_val, X_test):
    train_mean = X_train.mean(axis=(0, 1), keepdims=True)
    train_std = X_train.std(axis=(0, 1), keepdims=True) + 1e-8
    return ((X_train - train_mean) / train_std,
            (X_val - train_mean) / train_std,
            (X_test - train_mean) / train_std)


def save_dataset_hdf5(filepath, X, y, y_action, metadata=None):
    with h5py.File(filepath, 'w') as f:
        f.create_dataset('X', data=X, compression='gzip')
        f.create_dataset('y', data=y, compression='gzip')
        f.create_dataset('y_action', data=y_action, compression='gzip')
        if metadata:
            for k, v in metadata.items():
                f.attrs[k] = v


def load_dataset_hdf5(filepath):
    with h5py.File(filepath, 'r') as f:
        X = f['X'][:]
        y = f['y'][:]
        y_action = f['y_action'][:] if 'y_action' in f else None
        metadata = dict(f.attrs)
    return X, y, y_action, metadata
