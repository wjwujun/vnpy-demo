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
"""
DualThrust交易策略
"""

class DualThrustStrategy(CtaTemplate):
    """"""

    author = "用Python的交易员"

    # 策略参数
    fixed_size = 1
    k1 = 0.4
    k2 = 0.6

    # 策略变量
    bars = []    # K线对象的列表

    day_open = 0
    day_high = 0
    day_low = 0

    range = 0
    long_entry = 0
    short_entry = 0
    exit_time = time(hour=14, minute=55)

    long_entered = False
    short_entered = False

    # 参数列表，保存了参数的名称
    parameters = ["k1", "k2", "fixed_size"]

    # 变量列表，保存了变量的名称
    variables = ["range", "long_entry", "short_entry", "exit_time"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(DualThrustStrategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager()
        self.bars = []

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        # 载入历史数据，并采用回放计算的方式初始化策略数值
        self.write_log("策略初始化")
        self.load_bar(10)

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        # 撤销之前发出的尚未成交的委托（包括限价单和停止单）
        self.cancel_all()

        # 计算指标数值
        self.bars.append(bar)
        if len(self.bars) <= 2:
            return
        else:
            self.bars.pop(0)
        last_bar = self.bars[-2]
        # 新的一天
        if last_bar.datetime.date() != bar.datetime.date():
            # 如果已经初始化
            if self.day_high:
                self.range = self.day_high - self.day_low
                self.long_entry = bar.open_price + self.k1 * self.range
                self.short_entry = bar.open_price - self.k2 * self.range

            self.day_open = bar.open_price
            self.day_high = bar.high_price
            self.day_low = bar.low_price

            self.long_entered = False
            self.short_entered = False
        else:
            self.day_high = max(self.day_high, bar.high_price)
            self.day_low = min(self.day_low, bar.low_price)
        # 尚未到收盘
        if not self.range:
            return

        if bar.datetime.time() < self.exit_time:
            if self.pos == 0:
                if bar.close_price > self.day_open:
                    if not self.long_entered:
                        self.buy(self.long_entry, self.fixed_size, stop=True)
                else:
                    if not self.short_entered:
                        self.short(self.short_entry,
                                   self.fixed_size, stop=True)
            # 持有多头仓位
            elif self.pos > 0:
                self.long_entered = True
                # 多头止损单
                self.sell(self.short_entry, self.fixed_size, stop=True)
                # 空头开仓单
                if not self.short_entered:
                    self.short(self.short_entry, self.fixed_size, stop=True)
            # 持有空头仓位
            elif self.pos < 0:
                self.short_entered = True
                # 空头止损单
                self.cover(self.long_entry, self.fixed_size, stop=True)
                # 多头开仓单
                if not self.long_entered:
                    self.buy(self.long_entry, self.fixed_size, stop=True)
        # 收盘平仓
        else:
            if self.pos > 0:
                self.sell(bar.close_price * 0.99, abs(self.pos))
            elif self.pos < 0:
                self.cover(bar.close_price * 1.01, abs(self.pos))
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
