import time

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
"""
    上开
"""


class DoubleMa22Strategy(CtaTemplate):
    author = "wj"

    # 策略变量
    fixed_size = 1      # 开仓数量
    current_price=0     # 下单价格
    max_open=5          #每天最大开仓次数
    open_count=0        #今日开仓次数
    today=0             #当天时间

    stop_long_price=0   #多单止损价格
    stop_short_price=0  #空单止损价格
    vt_orderids = []        # 保存委托代码的列表
    # 参数列表，保存了参数的名称
    parameters = ["current_price", "max_open", "open_count",
                  "today", "fixed_size"]


    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(DoubleMa22Strategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.bg = BarGenerator(self.on_bar,5,self.on_5min_bar)
        self.am = ArrayManager()
        self.today=time.strftime("%Y-%m-%d", time.localtime())

        # 注意策略类中的可变对象属性（通常是list和dict等），在策略初始化时需要重新创建，
        # 否则会出现多个策略实例之间数据共享的情况，有可能导致潜在的策略逻辑错误风险，
        # 策略类中的这些可变对象属性可以选择不写，全都放在__init__下面，写主要是为了阅读
        # 策略时方便（更多是个编程习惯的选择）

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(10)       #初始化加载数据

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

    # ----------------------------------------------------------------------
    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)




    def on_5min_bar(self, bar: BarData):
        """5分钟K线"""

        # 撤销之前发出的尚未成交的委托（包括限价单和停止单）
        self.cancel_all()
        self.vt_orderids.clear()
        # 保存K线数据
        self.am.update_bar(bar)
        if not self.am.inited:
            return

        # Determine whether positions can also be opened on the day
        now = time.strftime("%Y-%m-%d", time.localtime())
        if (self.open_count > self.max_open):
            if (self.today == now):
                return
        else:
            self.today = time.strftime("%Y-%m-%d", time.localtime())
            self.open_count = 0

        # Calculator the 5min moving average
        self.ma_value = self.am.sma(5)

        # 当前无仓位
        if self.pos == 0:
            if bar.close_price > self.ma_value:  # The current price is above the 5min moving average，Long positions
                self.stop_long_price = bar.close_price - 20  # long stop  price
                vt_orderids = self.buy(bar.close_price + 2, self.fixed_size)
                self.current_price = bar.close_price + 2
                self.vt_orderids.extend(vt_orderids)        #save orderids
            elif bar.close_price < self.ma_value:  # The current price is above the 5min moving average，Short positions
                self.stop_long_price = bar.close_price + 20  # short stop  price
                vt_orderids = self.short(bar.close_price - 2, self.fixed_size)
                self.current_price = bar.close_price + 2
                self.vt_orderids.extend(vt_orderids)        #save orderids
        # Holding a long position
        elif self.pos > 0:
            if bar.close_price <= self.stop_long_price or bar.close_price <= self.ma_value:  # long stop loss,current price <= Stop-Loss Price，trigger stop price
                self.sell(bar.close_price - 2, abs(self.pos))

        # Hold short positions
        elif self.pos < 0:
            if bar.close_price >= self.stop_short_price or bar.close_price <= self.ma_value:  # short stop loss,current price>=Stop-Loss Price，trigger stop price
                self.cover(bar.close_price + 2, abs(self.pos))

        # 发出状态更新事件
        self.put_event()






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
