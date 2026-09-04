import subprocess
import time

cmd = [
    "rfi", "pull",
    "--state", "/Users/tim-macbook/Documents/rfi/1/",
    "--firm", "seagate",
    "--selection", "first_in_date_range",
    "--start-date", "2024-08-07",
    "--end-date", "2026-08-07",
]

for i in range(20):  # comfortably above ~8 quarterly calls
    print(f"\n=== Pull {i + 1} ===")

    result = subprocess.run(cmd, text=True)

    if result.returncode != 0:
        print(f"Stopping: rfi pull exited {result.returncode}")
        break

    time.sleep(1)
else:
    print("Stopped at safety limit.")

