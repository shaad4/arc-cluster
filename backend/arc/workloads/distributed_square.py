"""Approved demonstration; never executed automatically by ARC."""

import argparse
import json

import ray

parser = argparse.ArgumentParser()
parser.add_argument("--count", type=int, default=8, choices=range(1, 101))
args = parser.parse_args()
ray.init(address="auto")


@ray.remote(num_cpus=0.25)
def square(value):
    return {
        "input": value,
        "square": value * value,
        "node_id": ray.get_runtime_context().get_node_id(),
    }


print(json.dumps(ray.get([square.remote(i) for i in range(args.count)])))
ray.shutdown()
