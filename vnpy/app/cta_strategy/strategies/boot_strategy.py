from datetime import time
from time import sleep

from vnpy.app.cta_strategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)
from vnpy.trader.constant import Direction
from vnpy.trader.utility import load_json, save_json

"""
"""

class DoubleMa22Strategy(CtaTemplate):
    author = "wj"

    # 策略变量
    fixed_size = 1      # 开仓数量
    ma_value = 0         #5min avgrage
    exit_time = time(hour=14, minute=55)
    start_time = time(hour=8, minute=59)
    close_price=[4,7,10,15,20,25,30,35,40,45,50,60,70,80,90,100,125,200,250,300,350,400,450,500]  #止盈等级，根据等级来确定止盈的价格
    close_price_two=[4,7,10]
    arr_long = []  # 确定止盈的范围
    arr_short = []  # 确定止盈的范围
    stop_long = 0  # 多头止损
    stop_short = 0  # 空头止损

    open_count = 2
    long_time = 0
    short_time = 0
    long_entered = False
    short_entered = False
    last_price = 0
    num=0
    stop_price=0
    open_spread=0       #开仓价之差
    action_status=True #点差
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(DoubleMa22Strategy, self).__init__(cta_engine, strategy_name, vt_symbol, setting)

        #self.bg = BarGenerator(self.on_bar,5,self.on_5min_bar)
        self.bg = BarGenerator(self.on_bar)
        # 时间序列容器：计算技术指标用
        #self.am = ArrayManager()
        print("2019114************************************************444")

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        #self.load_bar(3)       #初始化加载3天的数据

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")
        #self.put_event()

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")

        #self.put_event()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        if self.last_price == 0:
            self.last_price = tick.last_price
            self.open_spread = abs(self.last_price - tick.open_price)
            if self.last_price > tick.open_price and self.open_spread < 18:
                self.long_entered = True
            elif self.last_price > tick.open_price and self.open_spread >= 18:
                self.short_entered = True
            elif self.last_price < tick.open_price and self.open_spread < 18:
                self.short_entered = True
            elif self.last_price < tick.open_price and self.open_spread >= 18:
                self.long_entered = True

        #获取最新价格和开盘第一次价格的差异
        price_diff = self.last_price - tick.last_price
        print("余额:(%s),盈亏：(%s),1次价：(%s),当前价：(%s),开盘价：(%s),下单价：(%s),"
              "多空: (%s,%s),方向：(%s),多止损价：(%s),空止损：(%s),多次数(%s),空次数(%s),仓位(%s)"%(
            self.cta_engine.account,self.cta_engine.pnl,self.last_price,tick.last_price,tick.open_price,
            self.current_price,self.long_entered,self.short_entered,self.direction,self.stop_long,self.stop_short,
            self.long_time,self.short_time,self.pos))
        # 确定止平仓的价格范围
        if self.current_price != 0:
            self.stop_price = self.current_price - tick.last_price  #stop_price=下单价-最新价，负数buy,是张，
            if  self.direction == Direction.LONG:
                if self.stop_price < 0:          #盈利
                    for i in self.close_price:
                        if abs(self.stop_price) >= i and (i not in self.arr_long):
                            self.cancel_all()
                            if i in self.close_price_two:
                                self.stop_long = tick.last_price - 3
                            else:
                                self.stop_long = tick.last_price - 5
                            self.arr_long.append(i)
                else:                       #亏损
                    if self.stop_price >= 10:
                        self.sell(tick.last_price - 1, abs(self.pos))                #亏损超过10点，立马平仓
                    else:
                        self.stop_long=max(self.current_price - 5,self.stop_long)     #亏损止损价
            else:
                if self.stop_price < 0:      #亏损
                    if  self.stop_price <= -10:
                        self.cover(tick.last_price + 1, abs(self.pos))                    #亏损超过10点，立马平仓
                    else:
                        self.stop_short=min(self.current_price + 5,self.stop_short)       #亏损止损价
                else:                   #盈利
                    for i in self.close_price:
                        if self.stop_price >= i and (i not in self.arr_short):
                            self.cancel_all()
                            if i in self.close_price_two:
                                self.stop_short = tick.last_price + 3
                            else:
                                self.stop_short = tick.last_price + 5
                            self.arr_short.append(i)


        if self.start_time< tick.datetime.time() < self.exit_time:
            # 当前无仓位
            if self.pos == 0 and self.pos < self.fixed_size and (self.long_time < self.open_count or self.short_time < self.open_count):
                #清空停止数据
                self.arr_long=[]
                self.arr_short=[]
                self.stop_short=0
                self.stop_long=0
                self.current_price=0
                self.direction=""

                if self.long_entered:    #如果最新价格和 开盘第一次价格的差异3<=price_diff <=8 就开单
                    if  price_diff in [5,6]:
                        self.buy(tick.last_price+1, self.fixed_size)
                    elif price_diff in [-5,-6]:
                        self.buy(tick.last_price + 1, self.fixed_size)
                    self.stop_long = tick.last_price - 5
                elif self.short_entered :
                    if  price_diff in [-5,-6]:
                        self.short(tick.last_price-1, self.fixed_size)
                    elif price_diff in [5,6]:
                        self.short(tick.last_price - 1, self.fixed_size)

                    self.stop_short = tick.last_price + 5

            elif self.pos > 0 :  # 多头止损单
                if tick.last_price <= self.stop_long :
                    self.sell(self.stop_long, abs(self.pos))
            elif self.pos < 0:   # 空头止损单
                if tick.last_price >= self.stop_short :
                    self.cover(self.stop_short, abs(self.pos))
        else:   # 收盘平仓
            if self.pos > 0:
                self.sell(tick.last_price - 1, abs(self.pos))
            elif self.pos < 0:
                self.cover(tick.last_price + 1, abs(self.pos))



    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)
        self.cancel_all()


    def on_5min_bar(self, bar: BarData):
        """5分钟bar线"""

        # 保存bar数据
        #self.am.update_bar(bar)
        #if not self.am.inited:
        #    return
        #print("当前5min的bar的数据量：(%s)"%(self.am.count))

        # Calculator the 5min moving average
        #self.ma_value = self.am.sma(5)





    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_trade(self, trade: TradeData):
        """
            成交后初始止损价格
        """
        if trade.direction == Direction.LONG:
            self.stop_long=trade.price - 5
            self.long_time += 1
        else:
            self.stop_short = trade.price + 5
            self.short_time += 1
        self.current_price = trade.price
        self.direction = trade.direction



    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
