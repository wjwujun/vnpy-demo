import time

import datetime

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
    tick 止损
"""

class DoubleMa22Strategy(CtaTemplate):
    author = "wj"
    position_filename = "posotion_data.json"

    # 策略变量
    fixed_size = 1      # 开仓数量
    max_open=5          #每天最大开仓次数

    stop_price=0        #止损价格
    profit_price=0      #止盈价格
    ma_value = 0        #5min avgrage
    open_count = 1      # 今日开仓次数
    open_price=0        #今日开盘价
    active=True         #开仓开关
    close_position=False #平仓开关
    close_profit=0      #盈利平仓条件
    # 参数列表，保存了参数的名称
    parameters = ["max_open","fixed_size"]


    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(DoubleMa22Strategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.bg = BarGenerator(self.on_bar,5,self.on_5min_bar)
        # 时间序列容器：计算技术指标用
        self.am = ArrayManager()


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
        #self.open_price=tick.open_price
        print("查看当前盈亏：(%s),当前价：(%s),下单价：(%s),方向：(%s),止损价：(%s),止盈价格：(%s)"%(
            self.pnl,tick.last_price,self.current_price,self.direction,self.stop_price,self.profit_price))


        if self.open_count == self.max_open:
            self.active = False


        if tick.datetime.strftime("%H:%M:%S") >="14:55:00":
            if self.pos > 0:
                self.sell(tick.last_price - 1, abs(self.pos))
            elif self.pos < 0:
                self.cover(tick.last_price + 1, abs(self.pos))
            return

        #停止
        if self.current_price!=0:
            if self.direction==Direction.LONG:
                self.stop_price = tick.current_price - 10
                self.close_profit = tick.last_price-self.current_price
                if self.close_profit/10>0:
                    self.profit_price=tick.last_price-5

            if self.direction==Direction.SHORT:
                self.stop_price = tick.current_price + 10
                self.close_profit = self.current_price-tick.last_price
                if self.close_profit/10 > 0:
                    self.profit_price = tick.last_price + 5


        # 当前无仓位
        if self.pos == 0 and self.active:
            self.close_position = True
            if tick.last_price > self.open_price and tick.last_price > self.ma_value:
                print("buy 下单价：(%s),当前均值：(%s),当前最新价：(%s)" % (tick.last_price + 1, self.ma_value,tick.last_price))
                num = self.buy(tick.last_price + 1, self.fixed_size)
                if num:
                    self.open_count += 1
                return
            elif tick.last_price < self.open_price and tick.last_price < self.ma_value:
                print("short 下单价：(%s),当前均值：(%s),当前最新价：(%s)" % (tick.last_price - 1, self.ma_value,tick.last_price))
                num = self.short(tick.last_price - 1, self.fixed_size)
                if num:
                    self.open_count += 1
                return


        if self.pos > 0 and self.close_position:
            if tick.last_price - 2 <= self.stop_price:            #止损
                self.sell(tick.stop_price, abs(self.pos))
                self.close_position = False
            if tick.last_price == self.profit_price:             #止盈
                self.sell(tick.profit_price - 1, abs(self.pos))
                self.close_position = False
        elif self.pos < 0 and self.close_position:
            if  tick.last_price + 2 >= self.stop_price:          #止损
                self.cover(tick.stop_price, abs(self.pos))
                self.close_position = False
            if tick.last_price == self.profit_price:             #止盈
                self.cover(tick.profit_price + 1, abs(self.pos))
                self.close_position = False

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)
        # 撤销之前发出的尚未成交的委托（包括限价单和停止单）
        self.cancel_all()

        # if self.open_count == self.max_open:
        #     self.active=False
        #
        # # 当前无仓位
        # if self.pos == 0 and self.active:
        #     if bar.close_price > self.open_price and bar.close_price > self.ma_value:
        #         self.stop_long_price = bar.close_price - 20
        #         self.current_price = bar.close_price + 2
        #         print("buy 价格：(%s),当前均值：(%s)" % (bar.close_price + 2,self.ma_value))
        #         num=self.buy(bar.close_price + 2, self.fixed_size)
        #         if num:
        #             self.open_count += 1
        #
        #     elif bar.close_price < self.open_price  and bar.close_price < self.ma_value:
        #         self.stop_short_price = bar.close_price + 20
        #         self.current_price = bar.close_price + 2
        #         print("short 价格：(%s),当前均值：(%s)" % (bar.close_price - 2,self.ma_value))
        #         num=self.short(bar.close_price - 2, self.fixed_size)
        #         if num:
        #             self.open_count+=1

        # elif self.pos > 0:
        #     print("buy------:", self.stop_long_price)
        #     print("hc2001.SHFE------:", bar.close_price)
        #     if self.stop_long_price != 0 and bar.close_price <= self.stop_long_price:
        #         self.sell(self.stop_long_price, abs(self.pos))
        #         print("buy------:", self.stop_long_price)
        #     elif self.ma_value != 0 and bar.close_price >= self.ma_value:
        #         self.sell(bar.close_price - 2, abs(self.pos))
        # elif self.pos < 0:
        #     if self.stop_short_price != 0 and bar.close_price >= self.stop_short_price:
        #         print("short------:",self.stop_short_price)
        #         self.cover(self.stop_short_price, abs(self.pos))
        #     elif self.ma_value != 0 and bar.close_price >= self.ma_value:
        #         self.cover(bar.close_price + 2, abs(self.pos))


    def on_5min_bar(self, bar: BarData):
        """5分钟bar线"""

        # 保存K线数据
        self.am.update_bar(bar)
        if not self.am.inited:
            return
        print("当前5min的bar的数据量：(%s)"%(self.am.count))

        # Calculator the 5min moving average
        self.ma_value = self.am.sma(5)

        #if abs(self.pos)< abs(self.fixed_size):
            # # 当前无仓位
            # if self.pos == 0:
            #     if bar.close_price > self.ma_value:  # The current price is above the 5min moving average，Long positions
            #         self.stop_long_price = bar.close_price - 20  # long stop  price
            #         self.current_price = bar.close_price + 2
            #         print("当前开仓次数：(%s)" %(self.open_count))
            #         orderId=self.buy(bar.close_price + 2, self.fixed_size)
            #         if orderId:
            #             self.open_count  += 1
            #
            #     elif bar.close_price < self.ma_value:  # The current price is above the 5min moving average，Short positions
            #         self.stop_short_price = bar.close_price + 20  # short stop  price
            #         self.current_price = bar.close_price + 2
            #         orderId=self.short(bar.close_price - 2, self.fixed_size)
            #         print("当前开仓次数：(%s)" % (self.open_count))
            #         if orderId:
            #             self.open_count  += 1

        # 发出状态更新事件
        #self.put_event()



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
