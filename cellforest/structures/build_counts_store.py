import os
import pickle
from pathlib import Path

from cellforest.structures.CountsStore import CountsStore


def build_counts_store(matrix, cell_ids, features, save_path=None):
    store = CountsStore()
    store.matrix = matrix
    store.cell_ids = cell_ids
    store.features = features
    if save_path:
        save_path = Path(save_path)
        os.makedirs(save_path.parent, exist_ok=True)
        with open(save_path, "wb") as f:
            pickle.dump(store, f, protocol=pickle.HIGHEST_PROTOCOL)
    return store
