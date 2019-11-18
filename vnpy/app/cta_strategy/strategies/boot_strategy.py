import random
from datetime import time

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
from vnpy.trader.database import database_manager
"""
"""

class DoubleMa22Strategy(CtaTemplate):
    author = "wj"

    # 策略变量
    fixed_size = 10      # 开仓数量
    open_count = 7      # 每次开次数
    ma_value = 0        #20min avgrage
    day_start_time = time(hour=8, minute=58)
    day_exit_time = time(hour=14, minute=55)
    time_arrs_open=[time(hour=9, minute=00),time(hour=13, minute=30)]
    time_arrs=[time(hour=10, minute=00),time(hour=11, minute=00),time(hour=14, minute=00)]



    close_price=[4,7,10,15,20,25,30,35,40,45,50,60,70,80,90,100,125,200,250,300,350,400,450,500]  #止盈等级，根据等级来确定止盈的价格
    close_price_two=[4,7,10]
    arr_long = []   # 确定止盈的范围
    arr_short = []  # 确定止盈的范围
    stop_long = 0   # 多头止损
    stop_short = 0  # 空头止损
    long_time = 0   # 多次数
    short_time = 0  # 空次数

    open_price = 0      #开盘价
    first_price = 0
    stop_price=0        #下单价和最新价格之差
    open_spread=0       #开仓价之差
    current_price = 0   #下单价
    direction = ""      #下单方向
    today_direction=""  #今日方向
    up = 0

    entered = True
    reverse = 0

    # 参数列表，保存了参数的名称
    #parameters = ['fixed_size','open_count']

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(DoubleMa22Strategy, self).__init__(cta_engine, strategy_name, vt_symbol, setting)

        #self.bg = BarGenerator(self.on_bar,5,self.on_5min_bar)
        # 时间序列容器：计算技术指标用
        self.am = ArrayManager()
        #bar生成
        self.bg = BarGenerator(self.on_bar)
        self.up = random.randint(0, 1)
        if self.up==1:
            self.today_direction="多"
        else:
            self.today_direction = "空"
        print("20191113************************************************444")

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        #self.load_bar(5)       #初始化加载3天的数据


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
        self.bg.update_tick(tick)
        if self.open_price!=tick.open_price:
            self.open_price=tick.open_price
            self.first_price=tick.last_price
        print("(%s),反(%s),balance:(%s),pnl：(%s),latest：(%s),first：(%s),open：(%s),"
              "order：(%s),direction：(%s),long_stop：(%s),short_stop：(%s),long(%s),short(%s),pos(%s)"%(
            self.today_direction,self.reverse,self.cta_engine.account,self.cta_engine.pnl,tick.last_price,self.first_price,
            tick.open_price,self.current_price,self.direction,self.stop_long,self.stop_short,self.long_time,self.short_time,
            self.pos))


        self.get_price(tick)      #获取止损价格

        if self.pos == 0 and self.long_time == self.short_time and self.long_time < self.open_count:
            if tick.datetime.time().replace(microsecond=0) in self.time_arrs:     #整点
                self.init_data()
                if self.up == 1:
                    self.buy(tick.last_price + 1, self.fixed_size)
                else:
                    self.short(tick.last_price - 1, self.fixed_size)
        else:
            self.cover_sell_pos(tick)

        #保存tick数据
        database_manager.save_tick_data([tick])

    def get_price(self,tick: TickData):
        if self.current_price != 0:
            self.stop_price = self.current_price - tick.last_price  # stop_price=下单价-最新价，负数buy,是张，
            if self.direction == Direction.LONG:
                if self.stop_price < 0:  # 盈利
                    for i in self.close_price:
                        if abs(self.stop_price) >= i and (i not in self.arr_long):
                            self.cancel_all()
                            if i in self.close_price_two:
                                self.stop_long = tick.last_price - 3
                            else:
                                self.stop_long = tick.last_price - 5
                            self.arr_long.append(i)
                else:  # 亏损
                    if self.stop_price >= 10:
                        self.sell(tick.last_price - 1, abs(self.pos))  # 亏损超过10点，立马平仓
                    else:
                        self.stop_long = max(self.current_price - 6, self.stop_long)  # 亏损止损价
            else:
                if self.stop_price < 0:  # 亏损
                    if self.stop_price <= -10:
                        self.cover(tick.last_price + 1, abs(self.pos))  # 亏损超过10点，立马平仓
                    else:
                        self.stop_short = min(self.current_price + 6, self.stop_short)  # 亏损止损价
                else:  # 盈利
                    for i in self.close_price:
                        if self.stop_price >= i and (i not in self.arr_short):
                            self.cancel_all()
                            if i in self.close_price_two:
                                self.stop_short = tick.last_price + 3
                            else:
                                self.stop_short = tick.last_price + 5
                            self.arr_short.append(i)

    def cover_sell_pos(self,tick: TickData):
        if tick.datetime.time().replace(microsecond=0) < self.day_exit_time:
            if self.pos > 0 and tick.last_price <= self.stop_long and self.stop_long != 0:  # 多头止
                self.sell(self.stop_long, abs(self.pos))
                if self.cta_engine.pnl < 0 and self.reverse == 0:  # 反转
                    self.reverse += 1
                    self.short(tick.last_price - 1, self.fixed_size)
            if self.pos < 0 and tick.last_price >= self.stop_short and self.stop_short != 0:  # 空头止
                self.cover(self.stop_short, abs(self.pos))
                if self.cta_engine.pnl < 0 and self.reverse == 0:  # 反转
                    self.reverse += 1
                    self.buy(tick.last_price + 1, self.fixed_size)
        else:
            # 白盘收仓
            self.end_trade(tick)

    def end_trade(self,tick: TickData):
        if self.pos > 0:
            self.sell(tick.last_price - 1, abs(self.pos))
        if self.pos < 0:
            self.cover(tick.last_price + 1, abs(self.pos))


    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.cancel_all()  # 取消所有未成交本地单
        #self.am.update_bar(bar)
        #保存bar数据
        database_manager.save_bar_data([bar])
        # if not self.am.inited:
        #     return
        #self.ma_value = self.am.sma(20)




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
        self.init_data()
        if trade.direction == Direction.LONG:
            self.stop_long=trade.price - 6
            self.long_time += 1
        else:
            self.stop_short = trade.price + 6
            self.short_time += 1
        self.current_price = trade.price
        self.direction = trade.direction

    def init_data(self):
        self.arr_long = []
        self.arr_short = []
        self.stop_long = 0
        self.stop_short = 0

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
