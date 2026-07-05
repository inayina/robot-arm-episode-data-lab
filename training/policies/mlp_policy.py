"""PyTorch Multi-Layer Perceptron (MLP) Policy for state-based Behavioral Cloning."""

import numpy as np

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    # Define dummy base class to avoid crash when importing without torch
    class nn_Module:
        pass
    class torch_nn:
        Module = nn_Module
    nn = torch_nn()


if HAS_TORCH:
    class MLPPolicy(nn.Module):
        """A simple MLP policy that predicts actions from state observations."""

        def __init__(
            self,
            state_dim: int,
            action_dim: int,
            hidden_dims: list[int] = [128, 128],
            dropout: float = 0.0,
        ) -> None:
            super().__init__()
            self.state_dim = state_dim
            self.action_dim = action_dim

            layers = []
            in_dim = state_dim
            for h_dim in hidden_dims:
                layers.append(nn.Linear(in_dim, h_dim))
                layers.append(nn.LayerNorm(h_dim))
                layers.append(nn.ReLU())
                if dropout > 0.0:
                    layers.append(nn.Dropout(dropout))
                in_dim = h_dim
            layers.append(nn.Linear(in_dim, action_dim))

            self.network = nn.Sequential(*layers)

            # Store normalization statistics
            self.state_mean = np.zeros(state_dim, dtype=np.float32)
            self.state_std = np.ones(state_dim, dtype=np.float32)
            self.action_mean = np.zeros(action_dim, dtype=np.float32)
            self.action_std = np.ones(action_dim, dtype=np.float32)

        def forward(self, state: torch.Tensor) -> torch.Tensor:
            """Predict action from normalized state."""
            return self.network(state)

        def set_normalization(
            self,
            state_mean: np.ndarray,
            state_std: np.ndarray,
            action_mean: np.ndarray,
            action_std: np.ndarray,
        ) -> None:
            """Set numpy statistics and keep them for serialization/adaptation."""
            self.state_mean = state_mean.copy()
            self.state_std = state_std.copy()
            self.action_mean = action_mean.copy()
            self.action_std = action_std.copy()
else:
    class MLPPolicy:
        """Dummy placeholder class when torch is not installed."""
        def __init__(self, *args, **kwargs) -> None:
            raise ImportError("PyTorch is required for MLPPolicy. Please run: pip install torch")
