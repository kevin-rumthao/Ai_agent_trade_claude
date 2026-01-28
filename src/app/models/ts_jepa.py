import torch
import torch.nn as nn
import copy

class TS_JEPA(nn.Module):
    """
    Time-Series Joint Embedding Predictive Architecture.
    
    Goal: Learn a robust 'Latent State' of the market that ignores noise.
    """
    def __init__(self, input_dim=12, embed_dim=64):
        """
        input_dim: Number of features (OHLCV + OFI + Technicals)
        embed_dim: Size of the output 'State Vector'
        """
        super().__init__()
        
        # 1. The Context Encoder (The "Eyes")
        # Reads the past (Context) and outputs a State Vector
        self.context_encoder = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(128, 128),
            nn.GELU(),
            nn.Linear(128, embed_dim),
            nn.Tanh()  # Tanh keeps state bounded between -1 and 1
        )
        
        # 2. The Target Encoder (The "Teacher")
        # Identical structure, but weights are updated via momentum (not gradient descent)
        self.target_encoder = copy.deepcopy(self.context_encoder)
        for param in self.target_encoder.parameters():
            param.requires_grad = False  # Freeze gradients
            
        # 3. The Predictor (The "Reasoning")
        # Tries to predict Future State from Current State
        self.predictor = nn.Sequential(
            nn.Linear(embed_dim, 32),
            nn.GELU(),
            nn.Linear(32, embed_dim)
        )

    def forward(self, x_context):
        """
        Forward pass for INFERENCE (Trading Mode).
        We only use the Context Encoder to get the state.
        """
        return self.context_encoder(x_context)

    def get_latent_state(self, x_input):
        """Helper to get the clean state vector."""
        with torch.no_grad():
            return self.context_encoder(x_input)    