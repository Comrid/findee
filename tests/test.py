import time

def no_exception():
    try:
        x = 10 + 20
    except:
        pass

def with_exception():
    try:
        x = 10 / 0
    except:
        pass

start = time.time()
for _ in range(10_000):
    no_exception()
print("🚀 No Exception:", time.time() - start)

start = time.time()
for _ in range(10_000):
    with_exception()
print("⚠️ With Exception:", time.time() - start)
