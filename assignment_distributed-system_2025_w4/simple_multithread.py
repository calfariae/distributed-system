import threading
import time

class FileReaderThread(threading.Thread):
    def __init__(self, filename, data_container):
        threading.Thread.__init__(self)
        self.filename = filename
        self.data_container = data_container
    
    def run(self):
        print(f"[Reader Thread] Reading from {self.filename}...")
        time.sleep(0.5)  # Simulate I/O delay
        with open(self.filename, 'r') as file:
            self.data_container['content'] = file.read()
        print("[Reader Thread] Finished reading.")

class DisplayThread(threading.Thread):
    def __init__(self, data_container):
        threading.Thread.__init__(self)
        self.data_container = data_container
    
    def run(self):
        print("[Display Thread] Waiting for data...")
        while 'content' not in self.data_container:
            time.sleep(0.1)
        print("[Display Thread] Displaying content:")
        print("-" * 40)
        print(self.data_container['content'])
        print("-" * 40)

if __name__ == "__main__":
    # Create a sample file if it doesn't exist
    with open("sample.txt", "w") as f:
        f.write("Hello from multithreading!\n" * 100)
    
    shared_data = {}
    
    reader = FileReaderThread("sample.txt", shared_data)
    display = DisplayThread(shared_data)
    
    start = time.time()
    reader.start()
    display.start()
    
    reader.join()
    display.join()
    end = time.time()
    
    print(f"Total execution time: {end - start:.4f} seconds")