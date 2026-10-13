import winsound
import time

freq = int(input("Enter frequency (800-1500): "))
duration = int(input("Enter duration per beep (ms): "))

print("Playing for 5 seconds...")

start = time.time()

while time.time() - start < 5:
    winsound.Beep(freq, duration)

print("Done!")