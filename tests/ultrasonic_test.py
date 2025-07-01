from findee import Findee
import time

car = Findee()

while True:
    distance = car.ultrasonic.get_distance()
    print(f"{distance:.3f} cm")
    time.sleep(0.1)

