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

# close_price = [10, 20, 30]
# arr = []
# for bb in close_price:
#     print(bb)
#     str='{}{}'.format('sell_', bb)
#     print(str)
#     if bb / 10 > 0:
#         if str not in  arr:
#             profit_price = bb - 5
#             arr.append(str)
#
#
# print(arr)
# long_entered=False
# short_entered=True
# price_diff=3
# if long_entered and price_diff in [-4, -3]:
#     print("---1111111111111")
# if short_entered and price_diff in [4, 3]:
#     print("22222222222222")



a=0
file = open('word2.txt','a',encoding='utf-8')
arr=["a","a",]
with open("word.txt","r+", encoding='utf-8') as f:
    for line in f:
        if len(line)!=1:
            print(line.split(" ")[0][0:1])
            file.write(line.split(" ")[0]+"       "+line.split(" ")[1])


