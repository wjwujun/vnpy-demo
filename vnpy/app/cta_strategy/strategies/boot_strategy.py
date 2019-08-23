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
    position_filename = "posotion_data.json"

    # 策略变量
    fixed_size = 1      # 开仓数量
    ma_value = 0         #5min avgrage
    exit_time = time(hour=14, minute=55)
    start_time = time(hour=8, minute=59)
    close_price=[5,10,20,30,40,50,60,70,80,90]  #止盈等级，根据等级来确定止盈的价格
    arr_long = []  # 确定止盈的范围
    arr_short = []  # 确定止盈的范围
    stop_long = 0  # 多头止损
    stop_short = 0  # 空头止损

    open_count=2
    long_time = 0
    short_time = 0
    long_entered = False
    short_entered = False
    last_price= 0
    parameters = ["fixed_size"]


    open_spread=0       #开仓价之差
    action_status=False #点差
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(DoubleMa22Strategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.bg = BarGenerator(self.on_bar,5,self.on_5min_bar)
        # 时间序列容器：计算技术指标用
        self.am = ArrayManager()
        print("************************************************4444")

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(3)       #初始化加载3天的数据

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")
        self.put_event()

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")

        self.put_event()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)
        if self.last_price == 0:
            self.last_price=tick.last_price
            self.open_spread = abs(self.last_price - tick.open_price)
            if abs(self.open_spread) <= 10:
                self.action_status=True
                if self.last_price > tick.open_price :
                    self.long_entered = True
                elif self.last_price < tick.open_price :
                    self.short_entered = True
            else:
                if self.last_price > tick.open_price :
                    self.short_entered = True
                elif self.last_price < tick.open_price :
                    self.long_entered = True




        print("查看当前盈亏：(%s),当前价：(%s),开盘价：(%s),下单价：(%s),方向：(%s),"
              "多止损价：(%s),空止损价：(%s),多单次数(%s),空单次数(%s),当前仓位(%s)"%(
            self.pnl,tick.last_price,tick.open_price,self.current_price,self.direction,
            self.stop_long,self.stop_short,self.long_time,self.short_time,self.pos))
        # 确定止平仓的价格范围
        if self.current_price != 0:
            stop_price = abs(self.current_price - tick.last_price)
            for i in self.close_price:
                if self.direction == Direction.LONG:
                    if stop_price > i and (i not in self.arr_long):
                        self.stop_long = tick.last_price - 5
                        self.arr_long.append(i)
                else:
                    if stop_price > i and (i not in self.arr_short):
                        self.stop_short = tick.last_price + 5
                        self.arr_short.append(i)
            self.stop_long = max(self.current_price - 5, self.stop_long)
            self.stop_short = min(self.current_price + 5, self.stop_short)

        if self.start_time< tick.datetime.time() < self.exit_time:
            # 当前无仓位
            if self.pos == 0 and self.pos < self.fixed_size:
                self.arr_long=[]         #无仓位清空数据
                self.arr_short=[]         #无仓位清空数据
                aa=self.last_price - tick.last_price
                if  self.action_status:
                    if self.long_entered and aa == 5 and self.long_time <= self.open_count :
                        self.long_time += 1
                        self.buy(tick.last_price + 1, self.fixed_size)
                    elif self.short_entered and aa == -5  and self.short_time <= self.open_count :
                        self.short_time += 1
                        self.short(tick.last_price - 1, self.fixed_size)
                    sleep(1)
                else:
                    if self.long_entered and aa == 5 and self.long_time <= self.open_count :
                        self.long_time += 1
                        self.buy(tick.last_price + 1, self.fixed_size)
                    elif self.short_entered and aa == -5 and self.short_time <= self.open_count :
                        self.short_time += 1
                        self.short(tick.last_price - 1, self.fixed_size)
                    sleep(1)
            elif self.pos > 0 :
                # 多头止损单
                self.sell(self.stop_long, abs(self.pos),True)
            elif self.pos < 0:
                # 空头止损单
                self.cover(self.stop_short, abs(self.pos),True)
        # 收盘平仓
        else:
            if self.pos > 0:
                self.sell(tick.last_price + 1, abs(self.pos))
            elif self.pos < 0:
                self.cover(tick.last_price - 1, abs(self.pos))

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)
        self.cancel_all()


    def on_5min_bar(self, bar: BarData):
        """5分钟bar线"""

        # 保存bar数据
        self.am.update_bar(bar)
        if not self.am.inited:
            return
        #print("当前5min的bar的数据量：(%s)"%(self.am.count))

        # Calculator the 5min moving average
        self.ma_value = self.am.sma(5)




    def clearData(self):
        self.position = {}
        save_json(self.position_filename, {})


    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
