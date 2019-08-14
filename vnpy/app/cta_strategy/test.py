import datetime
import time



print(datetime.datetime.now().minute)
print(datetime.datetime.now().strftime("%H:%M:%S"))
print(type(datetime.datetime.now().strftime("%H:%M:%S")))
print (time.strftime("%H:%M:%S"))

if datetime.datetime.now().strftime("%H:%M:%S")>='16:25:20':
    print("111")
else:
    print("22222")




