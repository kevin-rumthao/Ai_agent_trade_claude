
import os

filename = 'data/BTCUSDT_5Y_1m.csv'
with open(filename, 'rb') as f:
    try:  # Handle empty file case
        f.seek(-2, os.SEEK_END)
        while f.read(1) != b'\n':
            f.seek(-2, os.SEEK_CUR)
    except OSError:
        f.seek(0)
    last_line = f.readline().decode()
    print(last_line)
