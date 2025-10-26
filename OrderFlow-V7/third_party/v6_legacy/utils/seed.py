import json
import os
import random

import numpy as np

def set_seed(seed: int = None):
    if seed is None:
        seed = random.randint(0, 2**32 - 1)
    os.makedirs("output/results", exist_ok=True)
    with open("output/results/seed.json", "w") as f:
        json.dump({"seed": seed}, f)
    np.random.seed(seed)
    return seed

if __name__ == "__main__":
    print("Seed set:", set_seed())
