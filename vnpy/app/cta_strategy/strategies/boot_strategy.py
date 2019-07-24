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
    fast_ma = 0         # 5分钟快速均线
    slow_ma = 0         # 5分钟慢速均线
    ma_trend = 0        # 判断多空方向
    current_price=0.0   #当前价格


    # ----------------------------------------------------------------------
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(DoubleMa22Strategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.bg = BarGenerator(self.on_bar,5, self.on_5min_bar)
        self.am = ArrayManager()

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

        self.cancel_all()
        # 保存K线数据
        self.am.update_bar(bar)
        if not self.am.inited:
            return

        # 计算5m均线
        self.ma_value = self.am.sma(5)

        # 当前无仓位
        if self.pos == 0:
            if self.ma_value >= self.rsi_long:
                self.buy(bar.close_price + 2, self.fixed_size)
            elif self.rsi_value <= self.rsi_short:
                self.short(bar.close_price - 2, self.fixed_size)
        # 持有多头
        elif self.pos > 0:
            if self.rsi_value < 50:
                self.sell(bar.close_price - 2, abs(self.pos))
        # 持有空头
        elif self.pos < 0:
            if self.rsi_value > 50:
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
