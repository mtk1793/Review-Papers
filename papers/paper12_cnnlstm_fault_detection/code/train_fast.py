import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
import h5py, json
import numpy as np
from model import System1_CNNLSTM, FaultDetectionLoss

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models', 'IEEE39')
os.makedirs(MODEL_DIR, exist_ok=True)

print('Loading IEEE39 data...')
with h5py.File(os.path.join(DATA_DIR, 'IEEE39_train.h5'), 'r') as f:
    X_train = f['X'][:].astype(np.float32)
    y_train = f['y'][:].astype(np.int64)

with h5py.File(os.path.join(DATA_DIR, 'IEEE39_val.h5'), 'r') as f:
    X_val = f['X'][:].astype(np.float32)
    y_val = f['y'][:].astype(np.int64)

with h5py.File(os.path.join(DATA_DIR, 'IEEE39_test.h5'), 'r') as f:
    X_test = f['X'][:].astype(np.float32)
    y_test = f['y'][:].astype(np.int64)

print(f'Train: {X_train.shape} {np.unique(y_train, return_counts=True)}')
print(f'Val:   {X_val.shape}')
print(f'Test:  {X_test.shape}')

# Per-feature normalization (z-score on training set)
mean = X_train.mean(axis=(0, 1), keepdims=True)
std = X_train.std(axis=(0, 1), keepdims=True) + 1e-8
X_train = (X_train - mean) / std
X_val = (X_val - mean) / std
X_test = (X_test - mean) / std
print(f'Normalized: train mean={X_train.mean():.4f}, std={X_train.std():.4f}')

np.random.seed(42)
noise = np.random.normal(0, 0.01, X_train.shape).astype(np.float32)
X_train_aug = np.concatenate([X_train, X_train + noise], axis=0)
y_train_aug = np.concatenate([y_train, y_train], axis=0)
idx = np.random.permutation(len(X_train_aug))
X_train_aug, y_train_aug = X_train_aug[idx], y_train_aug[idx]

print(f'Augmented train: {X_train_aug.shape}')

train_loader = DataLoader(
    TensorDataset(torch.tensor(X_train_aug), torch.tensor(y_train_aug)),
    batch_size=64, shuffle=True)
val_loader = DataLoader(
    TensorDataset(torch.tensor(X_val), torch.tensor(y_val)),
    batch_size=64, shuffle=False)
test_loader = DataLoader(
    TensorDataset(torch.tensor(X_test), torch.tensor(y_test)),
    batch_size=64, shuffle=False)

model = System1_CNNLSTM(num_buses=39, num_channels=3, num_fault_types=7)
n_params = model.count_parameters()
print(f'Model: {n_params:,} parameters ({n_params*4/1024/1024:.1f} MB FP32)')

criterion = nn.CrossEntropyLoss()
optimizer = AdamW(model.parameters(), lr=3e-3, weight_decay=1e-4)
scheduler = CosineAnnealingLR(optimizer, T_max=30, eta_min=1e-5)

best_val_acc = 0.0
best_epoch = 0
patience = 8
patience_counter = 0
history = {'train_loss': [], 'train_acc': [], 'val_loss': [], 'val_acc': []}

ckpt_path = os.path.join(MODEL_DIR, 'best_model.pt')
if os.path.exists(ckpt_path):
    ckpt = torch.load(ckpt_path, map_location='cpu', weights_only=False)
    try:
        model.load_state_dict(ckpt['model_state_dict'])
        best_val_acc = ckpt.get('best_val_acc', 0)
        best_epoch = ckpt.get('best_epoch', 0)
        print(f'Resumed from checkpoint: val_acc={best_val_acc*100:.2f}% at epoch {best_epoch}')
    except RuntimeError as e:
        print(f'Checkpoint mismatch (different arch), starting fresh')
        best_val_acc = 0.0
        best_epoch = 0

print(f'\nTraining System-1 on IEEE39 (117ch, {len(X_train_aug)} train events)')
print('='*70)

start = time.time()
MAX_EPOCHS = 50

for epoch in range(1, MAX_EPOCHS + 1):
    model.train()
    t_loss, t_correct, t_total = 0, 0, 0
    for X_batch, y_batch in train_loader:
        logits, _ = model(X_batch)
        loss = criterion(logits, y_batch)
        optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        t_loss += loss.item() * len(y_batch)
        t_correct += (logits.argmax(1) == y_batch).sum().item()
        t_total += len(y_batch)
    train_loss = t_loss / t_total
    train_acc = t_correct / t_total

    model.eval()
    v_loss, v_correct, v_total = 0, 0, 0
    with torch.no_grad():
        for X_batch, y_batch in val_loader:
            logits, _ = model(X_batch)
            loss = criterion(logits, y_batch)
            v_loss += loss.item() * len(y_batch)
            v_correct += (logits.argmax(1) == y_batch).sum().item()
            v_total += len(y_batch)
    val_loss = v_loss / v_total
    val_acc = v_correct / v_total
    scheduler.step()

    history['train_loss'].append(train_loss)
    history['train_acc'].append(train_acc)
    history['val_loss'].append(val_loss)
    history['val_acc'].append(val_acc)

    lr = optimizer.param_groups[0]['lr']
    marker = ''
    if val_acc > best_val_acc + 1e-4:
        best_val_acc = val_acc
        best_epoch = epoch
        patience_counter = 0
        torch.save({
            'model_state_dict': model.state_dict(),
            'best_val_acc': best_val_acc,
            'best_epoch': best_epoch,
            'history': history,
        }, os.path.join(MODEL_DIR, 'best_model.pt'))
        marker = ' *'
    else:
        patience_counter += 1

    elapsed = (time.time() - start) / 60
    print(f'Epoch {epoch:2d}/{MAX_EPOCHS} | LR {lr:.1e} | '
          f'T.Loss {train_loss:.4f} T.Acc {train_acc*100:5.1f}% | '
          f'V.Loss {val_loss:.4f} V.Acc {val_acc*100:5.1f}% '
          f'[{elapsed:.1f}m]{marker}')

    if patience_counter >= patience:
        print(f'\nEarly stopping at epoch {epoch}')
        break

elapsed = (time.time() - start) / 60
print(f'\nTraining complete: {elapsed:.1f} min')
print(f'Best val accuracy: {best_val_acc*100:.2f}% at epoch {best_epoch}')

torch.save({
    'model_state_dict': model.state_dict(),
    'best_val_acc': best_val_acc,
    'best_epoch': best_epoch,
    'history': history,
}, os.path.join(MODEL_DIR, 'final_model.pt'))
with open(os.path.join(MODEL_DIR, 'history.json'), 'w') as f:
    json.dump(history, f, indent=2)

print('\n' + '='*70)
print('Evaluating on test set...')
model.load_state_dict(torch.load(ckpt_path, map_location='cpu', weights_only=False)['model_state_dict'])
model.eval()

all_preds, all_labels = [], []
with torch.no_grad():
    for X_batch, y_batch in test_loader:
        logits, _ = model(X_batch)
        all_preds.append(logits.argmax(1).numpy())
        all_labels.append(y_batch.numpy())

all_preds = np.concatenate(all_preds)
all_labels = np.concatenate(all_labels)
test_acc = (all_preds == all_labels).mean()
print(f'Test accuracy: {test_acc*100:.2f}%')

from sklearn.metrics import classification_report
print('\nClassification Report:')
print(classification_report(all_labels, all_preds,
      target_names=['Low-imp', 'High-imp', 'Freq-dev', 'Volt-sag', 'Island', 'FDI', 'Load-trans']))
