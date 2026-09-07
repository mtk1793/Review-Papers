import torch
import torch.nn as nn
from config import TrainingConfig


class System1CNNLSTM(nn.Module):
    def __init__(self, num_buses=39, num_channels=3,
                 num_fault_types=7, lstm_hidden=256):
        super().__init__()
        input_channels = num_buses * num_channels

        self.conv1 = nn.Conv1d(input_channels, 64, kernel_size=3, padding=1)
        self.pool1 = nn.MaxPool1d(2)
        self.conv2 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
        self.pool2 = nn.MaxPool1d(2)

        self.lstm = nn.LSTM(128, lstm_hidden, num_layers=2,
                            batch_first=True, dropout=0.2)

        self.fc_fault = nn.Sequential(
            nn.Linear(lstm_hidden, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, num_fault_types),
        )
        self.fc_action = nn.Sequential(
            nn.Linear(lstm_hidden, 128),
            nn.ReLU(),
            nn.Linear(128, num_buses * 2),
        )

    def forward(self, x):
        x = x.transpose(1, 2)
        x = torch.relu(self.conv1(x))
        x = self.pool1(x)
        x = torch.relu(self.conv2(x))
        x = self.pool2(x)
        x = x.transpose(1, 2)
        x, _ = self.lstm(x)
        x = x[:, -1, :]
        fault_logits = self.fc_fault(x)
        action = self.fc_action(x)
        return fault_logits, action


def build_model(config: TrainingConfig, num_buses: int) -> System1CNNLSTM:
    model = System1CNNLSTM(
        num_buses=num_buses,
        num_channels=config.num_channels,
        num_fault_types=config.num_fault_types,
        lstm_hidden=config.lstm_hidden,
    )
    return model.to(config.device)


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def get_model_size_mb(model: nn.Module, dtype=torch.float32) -> float:
    param_size = sum(p.numel() * torch.tensor([], dtype=dtype).element_size()
                     for p in model.parameters())
    return param_size / (1024 * 1024)
