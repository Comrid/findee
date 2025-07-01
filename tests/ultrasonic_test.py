from findee import Findee
import time

car = Findee()

while True:
    distance = car.ultrasonic.get_distance()
    print(distance)
    time.sleep(0.1)

