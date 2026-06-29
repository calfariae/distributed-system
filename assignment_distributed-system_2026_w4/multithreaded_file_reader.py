import threading
import time
import os

class FileChunkReader(threading.Thread):
    def __init__(self, filename, start_byte, end_byte, chunk_id, result_dict):
        threading.Thread.__init__(self)
        self.filename = filename
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.chunk_id = chunk_id
        self.result_dict = result_dict
    
    def run(self):
        with open(self.filename, 'r') as file:
            file.seek(self.start_byte)
            # Read the chunk (approximate - adjust for exact line boundaries if needed)
            chunk_size = self.end_byte - self.start_byte
            data = file.read(chunk_size)
            self.result_dict[self.chunk_id] = data
        # print(f"[Thread {self.chunk_id}] Read bytes {self.start_byte}-{self.end_byte}")

def get_file_chunks(filename, num_chunks):
    """Divide file into chunks for parallel reading"""
    file_size = os.path.getsize(filename)
    chunk_size = file_size // num_chunks
    chunks = []
    
    for i in range(num_chunks):
        start = i * chunk_size
        end = start + chunk_size if i < num_chunks - 1 else file_size
        chunks.append((start, end))
    return chunks

def read_file_parallel(filename, num_threads):
    """Read file using multiple threads in parallel"""
    chunks = get_file_chunks(filename, num_threads)
    results = {}
    threads = []
    
    start_time = time.time()
    
    # Create and start threads
    for i, (start, end) in enumerate(chunks):
        thread = FileChunkReader(filename, start, end, i, results)
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    end_time = time.time()
    
    # Combine results
    full_content = ''.join(results[i] for i in sorted(results.keys()))
    
    return full_content, end_time - start_time

def read_file_singlethread(filename):
    """Read file using single thread (baseline)"""
    start_time = time.time()
    with open(filename, 'r') as file:
        content = file.read()
    end_time = time.time()
    return content, end_time - start_time

if __name__ == "__main__":
    # Create a large test file (e.g., 10 MB)
    print("Creating test file...")
    test_filename = "large_test.txt"
    with open(test_filename, "w") as f:
        for i in range(200000):  # ~10-15 MB depending on line length
            f.write(f"Line {i}: This is sample data for multithreading performance testing.\n")
    
    file_size_mb = os.path.getsize(test_filename) / (1024 * 1024)
    print(f"Test file created. Size: {file_size_mb:.2f} MB")
    
    # Single-threaded read
    print("\n" + "="*50)
    print("SINGLE-THREAD READ (Baseline)")
    print("="*50)
    content_single, time_single = read_file_singlethread(test_filename)
    print(f"Time taken: {time_single:.4f} seconds")
    
    # Multi-threaded read with different thread counts
    thread_counts = [2, 4, 8]
    
    print("\n" + "="*50)
    print("MULTI-THREAD READ (Parallel Chunks)")
    print("="*50)
    
    for num_threads in thread_counts:
        content_multi, time_multi = read_file_parallel(test_filename, num_threads)
        speedup = time_single / time_multi if time_multi > 0 else 0
        efficiency = (speedup / num_threads) * 100
        
        print(f"\nThreads: {num_threads}")
        print(f"  Time taken: {time_multi:.4f} seconds")
        print(f"  Speedup: {speedup:.2f}x")
        print(f"  Efficiency: {efficiency:.1f}%")
    
    # Verify content matches
    print("\n" + "="*50)
    print("VERIFICATION")
    print("="*50)
    content_4threads, _ = read_file_parallel(test_filename, 4)
    if content_single == content_4threads:
        print("✓ Content matches between single-thread and multi-thread reads")
    else:
        print("✗ Content mismatch - check chunk boundary handling")