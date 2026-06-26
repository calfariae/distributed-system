#!/usr/bin/env python3
"""
Performance Benchmarking for Distributed Sync System
Auto-starts nodes if not running
"""
import asyncio
import aiohttp
import time
import statistics
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nodes.lock_manager import DistributedLockManager
from src.nodes.queue_node import DistributedQueueNode
from src.nodes.cache_node import DistributedCacheNode

class BenchmarkRunner:
    def __init__(self, lock_ports, queue_ports, cache_ports):
        self.lock_ports = lock_ports
        self.queue_ports = queue_ports
        self.cache_ports = cache_ports
        self.results = []
        self.nodes = []  # Store node instances
    
    async def start_nodes(self):
        """Start all nodes for benchmarking"""
        base_ports = [8000, 8001, 8002]
        
        for i, base_port in enumerate(base_ports):
            node_id = f"bench_node{i+1}"
            peers = [f"localhost:{p}" for j, p in enumerate(base_ports) if j != i]
            
            # Lock Manager
            lock = DistributedLockManager(f"{node_id}_lock", "localhost", base_port, peers)
            await lock.start()
            
            # Queue Node
            queue = DistributedQueueNode(
                f"{node_id}_queue", "localhost", base_port + 1000,
                [f"localhost:{p+1000}" for p in base_ports if p != base_port]
            )
            await queue.start()
            
            # Cache Node
            cache = DistributedCacheNode(
                f"{node_id}_cache", "localhost", base_port + 2000,
                [f"localhost:{p+2000}" for p in base_ports if p != base_port]
            )
            await cache.start()
            
            self.nodes.append({"lock": lock, "queue": queue, "cache": cache})
            print(f"  Started node {node_id}")
        
        # Wait for leader election
        print("  Waiting for leader election...")
        await asyncio.sleep(3)
    
    async def stop_nodes(self):
        """Stop all nodes"""
        for node_group in self.nodes:
            for component in node_group.values():
                await component.stop()
        print("  All nodes stopped")
    
    async def run_all(self):
        """Run all benchmarks"""
        print("=" * 60)
        print("DISTRIBUTED SYSTEM BENCHMARKS")
        print("=" * 60)
        
        print("\nStarting nodes...")
        await self.start_nodes()
        
        try:
            await self.benchmark_lock_acquisition()
            await self.benchmark_lock_contention()
            await self.benchmark_queue_throughput()
            await self.benchmark_cache_performance()
            await self.benchmark_single_vs_distributed()
        finally:
            await self.stop_nodes()
        
        self.print_summary()
        self.save_results()
    
    async def find_leader(self):
        """Find the lock manager leader port"""
        for port in self.lock_ports:
            try:
                async with aiohttp.ClientSession() as session:
                    resp = await session.get(
                        f"http://localhost:{port}/lock/status",
                        timeout=aiohttp.ClientTimeout(total=2)
                    )
                    data = await resp.json()
                    if data.get("state") == "leader":
                        return port
            except Exception:
                pass
        return None
    
    async def benchmark_lock_acquisition(self, iterations=50):
        """Benchmark lock acquire/release cycle"""
        print("\n[1] Lock Acquisition Benchmark")
        
        leader = await self.find_leader()
        if not leader:
            print("  SKIP: No leader found")
            return
        
        latencies = []
        async with aiohttp.ClientSession() as session:
            for i in range(iterations):
                resource = f"bench_{i % 10}"
                start = time.time()
                
                resp = await session.post(
                    f"http://localhost:{leader}/lock/acquire",
                    json={"resource_id": resource, "mode": "exclusive", "owner_id": "bench"}
                )
                await resp.json()
                
                resp = await session.post(
                    f"http://localhost:{leader}/lock/release",
                    json={"resource_id": resource, "owner_id": "bench"}
                )
                await resp.json()
                
                latencies.append(time.time() - start)
        
        result = {
            "name": "Lock Acquire/Release",
            "iterations": iterations,
            "avg_ms": round(statistics.mean(latencies) * 1000, 2),
            "p50_ms": round(statistics.median(latencies) * 1000, 2),
            "p99_ms": round(sorted(latencies)[int(len(latencies) * 0.99)] * 1000, 2),
            "throughput_ops": round(iterations / sum(latencies), 1)
        }
        self.results.append(result)
        print(f"  Avg: {result['avg_ms']}ms | P50: {result['p50_ms']}ms | Throughput: {result['throughput_ops']} ops/s")
    
    async def benchmark_lock_contention(self, iterations=20):
        """Benchmark lock under contention"""
        print("\n[2] Lock Contention Benchmark")
        
        leader = await self.find_leader()
        if not leader:
            print("  SKIP: No leader found")
            return
        
        async def contender(client_id):
            latencies = []
            async with aiohttp.ClientSession() as session:
                for _ in range(iterations):
                    start = time.time()
                    resp = await session.post(
                        f"http://localhost:{leader}/lock/acquire",
                        json={"resource_id": "contended", "mode": "exclusive", "owner_id": f"client{client_id}"}
                    )
                    data = await resp.json()
                    
                    if data.get("granted"):
                        await asyncio.sleep(0.01)
                        await session.post(
                            f"http://localhost:{leader}/lock/release",
                            json={"resource_id": "contended", "owner_id": f"client{client_id}"}
                        )
                    
                    latencies.append(time.time() - start)
            return latencies
        
        all_latencies = []
        for batch in await asyncio.gather(contender(1), contender(2), contender(3)):
            all_latencies.extend(batch)
        
        result = {
            "name": "Lock Contention (3 clients)",
            "iterations": len(all_latencies),
            "avg_ms": round(statistics.mean(all_latencies) * 1000, 2),
            "p50_ms": round(statistics.median(all_latencies) * 1000, 2),
            "p99_ms": round(sorted(all_latencies)[int(len(all_latencies) * 0.99)] * 1000, 2),
        }
        self.results.append(result)
        print(f"  Avg: {result['avg_ms']}ms | P50: {result['p50_ms']}ms | P99: {result['p99_ms']}ms")
    
    async def benchmark_queue_throughput(self, iterations=100):
        """Benchmark queue push/pull throughput"""
        print("\n[3] Queue Throughput Benchmark")
        
        port = self.queue_ports[0]
        latencies = []
        
        async with aiohttp.ClientSession() as session:
            for i in range(iterations):
                start = time.time()
                
                resp = await session.post(
                    f"http://localhost:{port}/queue/push",
                    json={"queue_name": "bench_q", "data": {"i": i}}
                )
                push_data = await resp.json()
                
                # Handle forwarding
                if push_data.get("forwarded"):
                    target = push_data["target_node"]
                    host, p = target.split(":")
                    await session.post(
                        f"http://{host}:{p}/queue/push",
                        json={"queue_name": "bench_q", "data": {"i": i}}
                    )
                
                resp = await session.post(
                    f"http://localhost:{port}/queue/pull",
                    json={"queue_name": "bench_q", "consumer_id": "bench"}
                )
                pull_data = await resp.json()
                
                if pull_data.get("forwarded"):
                    target = pull_data["target_node"]
                    host, p = target.split(":")
                    await session.post(
                        f"http://{host}:{p}/queue/pull",
                        json={"queue_name": "bench_q", "consumer_id": "bench"}
                    )
                
                latencies.append(time.time() - start)
        
        result = {
            "name": "Queue Push/Pull",
            "iterations": iterations,
            "avg_ms": round(statistics.mean(latencies) * 1000, 2),
            "p50_ms": round(statistics.median(latencies) * 1000, 2),
            "throughput_ops": round(iterations / sum(latencies), 1)
        }
        self.results.append(result)
        print(f"  Avg: {result['avg_ms']}ms | Throughput: {result['throughput_ops']} ops/s")
    
    async def benchmark_cache_performance(self, iterations=100):
        """Benchmark cache hit/miss performance"""
        print("\n[4] Cache Performance Benchmark")
        
        port = self.cache_ports[0]
        
        async with aiohttp.ClientSession() as session:
            # Pre-populate
            for i in range(20):
                await session.post(
                    f"http://localhost:{port}/cache/put",
                    json={"key": f"key{i}", "value": f"value{i}"}
                )
            
            # Cache hits
            hit_latencies = []
            for i in range(iterations):
                start = time.time()
                await session.post(
                    f"http://localhost:{port}/cache/get",
                    json={"key": f"key{i % 20}"}
                )
                hit_latencies.append(time.time() - start)
            
            # Cache misses
            miss_latencies = []
            for i in range(iterations // 2):
                start = time.time()
                await session.post(
                    f"http://localhost:{port}/cache/get",
                    json={"key": f"nonexistent{i}"}
                )
                miss_latencies.append(time.time() - start)
        
        result = {
            "name": "Cache Performance",
            "hit_avg_ms": round(statistics.mean(hit_latencies) * 1000, 2),
            "miss_avg_ms": round(statistics.mean(miss_latencies) * 1000, 2),
            "hit_rate": f"{iterations}/{iterations + iterations//2}"
        }
        self.results.append(result)
        print(f"  Hit Avg: {result['hit_avg_ms']}ms | Miss Avg: {result['miss_avg_ms']}ms")
    
    async def benchmark_single_vs_distributed(self, iterations=30):
        """Compare single node vs distributed"""
        print("\n[5] Single vs Distributed Comparison")
        
        # Single node
        port = self.cache_ports[0]
        single_latencies = []
        
        async with aiohttp.ClientSession() as session:
            for i in range(iterations):
                start = time.time()
                await session.post(
                    f"http://localhost:{port}/cache/put",
                    json={"key": f"single_{i}", "value": f"v{i}"}
                )
                await session.post(
                    f"http://localhost:{port}/cache/get",
                    json={"key": f"single_{i}"}
                )
                single_latencies.append(time.time() - start)
        
        # Distributed
        dist_latencies = []
        async with aiohttp.ClientSession() as session:
            for i in range(iterations):
                cache_port = self.cache_ports[i % len(self.cache_ports)]
                start = time.time()
                await session.post(
                    f"http://localhost:{cache_port}/cache/put",
                    json={"key": f"dist_{i}", "value": f"v{i}"}
                )
                await session.post(
                    f"http://localhost:{cache_port}/cache/get",
                    json={"key": f"dist_{i}"}
                )
                dist_latencies.append(time.time() - start)
        
        single_avg = statistics.mean(single_latencies) * 1000
        dist_avg = statistics.mean(dist_latencies) * 1000
        
        result = {
            "name": "Single vs Distributed",
            "single_avg_ms": round(single_avg, 2),
            "distributed_avg_ms": round(dist_avg, 2),
            "overhead_percent": round(((dist_avg - single_avg) / single_avg) * 100, 1)
        }
        self.results.append(result)
        print(f"  Single Node: {result['single_avg_ms']}ms")
        print(f"  Distributed: {result['distributed_avg_ms']}ms")
        print(f"  Overhead: {result['overhead_percent']}%")
    
    def print_summary(self):
        """Print benchmark summary"""
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)
        for r in self.results:
            print(f"\n{r['name']}:")
            for k, v in r.items():
                if k != "name":
                    print(f"  {k}: {v}")
    
    def save_results(self):
        """Save results to JSON"""
        os.makedirs("benchmarks/results", exist_ok=True)
        filename = f"benchmarks/results/benchmark_{int(time.time())}.json"
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\nResults saved to {filename}")

async def main():
    lock_ports = [8000, 8001, 8002]
    queue_ports = [9000, 9001, 9002]
    cache_ports = [10000, 10001, 10002]
    
    runner = BenchmarkRunner(lock_ports, queue_ports, cache_ports)
    await runner.run_all()

if __name__ == "__main__":
    asyncio.run(main())