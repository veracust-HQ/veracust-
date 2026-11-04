from __future__ import annotations
import torch
from torch import nn

class GraphAttention(nn.Module):
    """Dense multi-head self-attention used as a learnable graph message operator."""
    def __init__(self, dim: int, heads: int = 4, dropout: float = 0.1):
        super().__init__()
        if dim % heads:
            raise ValueError("hidden_dim must be divisible by graph_heads.")
        self.heads, self.head_dim = heads, dim // heads
        self.qkv = nn.Linear(dim, dim * 3)
        self.proj = nn.Linear(dim, dim)
        self.dropout = nn.Dropout(dropout)
        self.norm = nn.LayerNorm(dim)

    def forward(self, x: torch.Tensor):
        b, n, d = x.shape
        q, k, v = self.qkv(x).chunk(3, dim=-1)
        def split(t):
            return t.view(b, n, self.heads, self.head_dim).transpose(1, 2)
        q, k, v = split(q), split(k), split(v)
        attn = torch.softmax((q @ k.transpose(-2, -1)) / (self.head_dim ** 0.5), dim=-1)
        out = (self.dropout(attn) @ v).transpose(1, 2).contiguous().view(b, n, d)
        return self.norm(x + self.proj(out)), attn.mean(dim=1)

class AASISTL(nn.Module):
    """Compact AASIST-inspired dual-graph classifier; not a canonical AASIST-L reproduction."""
    def __init__(self, input_dim: int, hidden_dim: int = 128, heads: int = 4,
                 dropout: float = 0.15):
        super().__init__()
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        self.spectral = GraphAttention(hidden_dim, heads, dropout)
        self.temporal = GraphAttention(hidden_dim, heads, dropout)
        self.stack_node = nn.Parameter(torch.randn(1, 1, hidden_dim) * 0.02)
        self.hs_gal = GraphAttention(hidden_dim, heads, dropout)
        self.classifier = nn.Sequential(nn.LayerNorm(hidden_dim), nn.Dropout(dropout),
                                        nn.Linear(hidden_dim, 1))

    def forward(self, features: torch.Tensor, return_attention: bool = False):
        if features.ndim != 3:
            raise ValueError("Expected SSL features [batch, frames, channels].")
        h = self.input_proj(features)
        s, att_s = self.spectral(h)
        delta = torch.cat([h[:, :1], h[:, 1:] - h[:, :-1]], dim=1)
        t, att_t = self.temporal(h + delta)
        mgo = torch.maximum(s, t)
        stack = self.stack_node.expand(mgo.shape[0], -1, -1)
        fused, att_stack = self.hs_gal(torch.cat([stack, mgo], dim=1))
        logits = self.classifier(fused[:, 0]).squeeze(-1)
        if return_attention:
            return logits, {"spectral": att_s, "temporal": att_t,
                "stack": att_stack, "graph_attn_peak": torch.maximum(att_s.max(), att_t.max())}
        return logits
