import datetime
import time



# print(datetime.datetime.now().minute)
# print(datetime.datetime.now().strftime("%H:%M:%S"))
# print(type(datetime.datetime.now().strftime("%H:%M:%S")))
# print (time.strftime("%H:%M:%S"))

# if datetime.datetime.now().strftime("%H:%M:%S")>='16:25:20':
#     print("111")
# else:
#     print("22222")

# print(11/10>1)
# print(1/10>1)
# print(20/10>1)

close_price = [10, 20, 30]
arr = []
for bb in close_price:
    print(bb)
    str='{}{}'.format('sell_', bb)
    print(str)
    if bb / 10 > 0:
        if str not in  arr:
            profit_price = bb - 5
            arr.append(str)


print(arr)
