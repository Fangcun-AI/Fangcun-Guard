"""
Train MLP classifier for Guard Router and export weights as JSON.

Reads training_data.jsonl, computes embeddings via bge-m3 (OpenAI-compatible API),
trains a 2-layer MLP (1024→256→15), and exports weights to classifier_weights.json.

Usage:
    python train_classifier.py \
        --embedding-url http://localhost:58004/v1 \
        --embedding-key EMPTY \
        --embedding-model bge-m3 \
        --epochs 50 \
        --lr 0.001

Requirements (training only, not needed at runtime):
    pip install torch numpy
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).parent
TRAINING_DATA_PATH = DATA_DIR / "training_data.jsonl"
DIMENSIONS_PATH = DATA_DIR / "dimensions.json"
WEIGHTS_OUTPUT_PATH = DATA_DIR / "classifier_weights.json"


def load_training_data():
    """Load training data from JSONL file."""
    samples = []
    with open(TRAINING_DATA_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def load_dimensions():
    """Load dimension definitions."""
    with open(DIMENSIONS_PATH) as f:
        data = json.load(f)
    return {d["id"]: d["index"] for d in data["dimensions"]}


def get_embeddings_batch(client, texts, model_name, batch_size=32):
    """Get embeddings for texts using OpenAI-compatible embedding API."""
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.embeddings.create(input=batch, model=model_name)
        batch_embeddings = [d.embedding for d in response.data]
        all_embeddings.extend(batch_embeddings)
        if (i + batch_size) % 100 == 0 or i + batch_size >= len(texts):
            print(f"  Embedded {min(i + batch_size, len(texts))}/{len(texts)}")
    return np.array(all_embeddings, dtype=np.float32)


def train_mlp(X, y, n_classes, hidden_dim=256, epochs=50, lr=0.001, batch_size=64):
    """Train 2-layer MLP using PyTorch, return numpy weights."""
    try:
        import torch
        import torch.nn as nn
        import torch.optim as optim
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError:
        print("ERROR: PyTorch is required for training. Install with: pip install torch")
        sys.exit(1)

    input_dim = X.shape[1]

    # Define model
    model = nn.Sequential(
        nn.Linear(input_dim, hidden_dim),
        nn.ReLU(),
        nn.Dropout(0.2),
        nn.Linear(hidden_dim, n_classes),
    )

    X_tensor = torch.from_numpy(X)
    y_tensor = torch.from_numpy(y).long()

    # Train/val split (90/10)
    n = len(X_tensor)
    indices = torch.randperm(n)
    split = int(0.9 * n)
    train_idx, val_idx = indices[:split], indices[split:]

    train_dataset = TensorDataset(X_tensor[train_idx], y_tensor[train_idx])
    val_dataset = TensorDataset(X_tensor[val_idx], y_tensor[val_idx])
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_acc = 0.0
    best_state = None

    for epoch in range(epochs):
        # Train
        model.train()
        total_loss = 0
        for xb, yb in train_loader:
            optimizer.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        scheduler.step()

        # Validate
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                preds = model(xb).argmax(dim=1)
                correct += (preds == yb).sum().item()
                total += len(yb)

        val_acc = correct / total if total > 0 else 0
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1}/{epochs}: loss={total_loss/len(train_loader):.4f}, val_acc={val_acc:.4f}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.cpu().numpy().tolist() for k, v in model.state_dict().items()}

    print(f"\n  Best validation accuracy: {best_val_acc:.4f}")
    return best_state


def export_weights(state_dict, dim_map, output_path):
    """Export MLP weights as JSON for NumPy inference at runtime."""
    weights = {
        "architecture": "mlp_2layer",
        "input_dim": len(state_dict["0.weight"][0]),
        "hidden_dim": len(state_dict["0.weight"]),
        "output_dim": len(state_dict["3.weight"]),
        "dimensions": {v: k for k, v in dim_map.items()},  # index → dimension_id
        "layers": {
            "fc1_weight": state_dict["0.weight"],    # (hidden, input)
            "fc1_bias": state_dict["0.bias"],         # (hidden,)
            "fc2_weight": state_dict["3.weight"],    # (output, hidden)
            "fc2_bias": state_dict["3.bias"],         # (output,)
        },
    }

    with open(output_path, "w") as f:
        json.dump(weights, f)

    file_size = output_path.stat().st_size / 1024
    print(f"  Weights exported to {output_path} ({file_size:.0f} KB)")


def main():
    parser = argparse.ArgumentParser(description="Train Guard Router MLP classifier")
    parser.add_argument("--embedding-url", default=os.environ.get("EMBEDDING_API_BASE_URL", "http://localhost:58004/v1"))
    parser.add_argument("--embedding-key", default=os.environ.get("EMBEDDING_API_KEY", "EMPTY"))
    parser.add_argument("--embedding-model", default=os.environ.get("EMBEDDING_MODEL_NAME", "bge-m3"))
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    # Load data
    print("Loading training data...")
    samples = load_training_data()
    dim_map = load_dimensions()
    print(f"  {len(samples)} samples, {len(dim_map)} dimensions")

    # Prepare labels
    texts = [s["text"] for s in samples]
    labels = np.array([dim_map[s["dimension"]] for s in samples], dtype=np.int64)

    # Get embeddings
    print("\nComputing embeddings via bge-m3...")
    from openai import OpenAI
    client = OpenAI(api_key=args.embedding_key, base_url=args.embedding_url)
    X = get_embeddings_batch(client, texts, args.embedding_model)
    print(f"  Embedding shape: {X.shape}")

    # Train MLP
    print(f"\nTraining MLP ({X.shape[1]}→{args.hidden_dim}→{len(dim_map)})...")
    state_dict = train_mlp(
        X, labels,
        n_classes=len(dim_map),
        hidden_dim=args.hidden_dim,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
    )

    # Export weights
    print("\nExporting weights...")
    export_weights(state_dict, dim_map, WEIGHTS_OUTPUT_PATH)

    print("\nDone! Classifier is ready.")
    print(f"  Copy {WEIGHTS_OUTPUT_PATH} to your deployment.")


if __name__ == "__main__":
    main()
