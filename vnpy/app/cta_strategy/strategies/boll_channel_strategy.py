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
策略逻辑：
1. 布林通道（信号）
2. CCI指标（过滤）
3. ATR指标（止损）

适合品种：螺纹钢
适合周期：15分钟

这里的策略是作者根据原文结合vn.py实现，对策略实现上做了一些修改，仅供参考。

"""

class BollChannelStrategy(CtaTemplate):
    """"""

    author = "用Python的交易员"
    # 策略参数
    boll_window = 18        # 布林通道窗口数
    boll_dev = 3.4          # 布林通道的偏差
    cci_window = 10         # CCI窗口数
    atr_window = 30         # ATR窗口数
    sl_multiplier = 5.2     # 计算止损距离的乘数
    fixed_size = 1          # 初始化数据所用的天数

    # 策略变量
    boll_up = 0             # 布林通道上轨
    boll_down = 0           # 布林通道下轨
    cci_value = 0           # CCI指标数值
    atr_value = 0           # ATR指标数值

    intra_trade_high = 0    # 持仓期内的最高点
    intra_trade_low = 0     # 持仓期内的最低点
    long_stop = 0           # 多头止损
    short_stop = 0          # 空头止损
    # 参数列表，保存了参数的名称
    parameters = ["boll_window", "boll_dev", "cci_window",
                  "atr_window", "sl_multiplier", "fixed_size"]
    # 变量列表，保存了变量的名称
    variables = ["boll_up", "boll_down", "cci_value", "atr_value",
                 "intra_trade_high", "intra_trade_low", "long_stop", "short_stop"]

    # ----------------------------------------------------------------------
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(BollChannelStrategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        # 创建K线合成器对象
        self.bg = BarGenerator(self.on_bar, 15, self.on_15min_bar)
        self.am = ArrayManager()

    # ----------------------------------------------------------------------
    def on_init(self):
        """
        Callback when strategy is inited.
        初始化策略 回调函数
        """
        self.write_log("策略初始化")

        # 载入历史数据，并采用回放计算的方式初始化策略数值，初始化10天的数据
        self.load_bar(10)

    # ----------------------------------------------------------------------
    def on_start(self):
        """
        Callback when strategy is started.
        启动策略的回调
        """
        self.write_log("策略启动")

    # ----------------------------------------------------------------------
    def on_stop(self):
        """
        Callback when strategy is stopped.

        """
        self.write_log("策略停止")

    # ----------------------------------------------------------------------
    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    # ----------------------------------------------------------------------
    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        收到Bar推送
        """
        self.bg.update_bar(bar)
    #----------------------------------------------------------------------
    def on_15min_bar(self, bar: BarData):
        """收到X分钟K线"""
        self.cancel_all()

        # 保存K线数据
        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return
        # 计算指标数值
        self.boll_up, self.boll_down = am.boll(self.boll_window, self.boll_dev)
        self.cci_value = am.cci(self.cci_window)
        self.atr_value = am.atr(self.atr_window)

        # 判断是否要进行交易

        # 当前无仓位，发送开仓委托
        if self.pos == 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price

            if self.cci_value > 0:
                self.buy(self.boll_up, self.fixed_size, True)
            elif self.cci_value < 0:
                self.short(self.boll_down, self.fixed_size, True)
        # 持有多头仓位
        elif self.pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = bar.low_price

            self.long_stop = self.intra_trade_high - self.atr_value * self.sl_multiplier
            self.sell(self.long_stop, abs(self.pos), True)
        # 持有空头仓位
        elif self.pos < 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)

            self.short_stop = self.intra_trade_low + self.atr_value * self.sl_multiplier
            self.cover(self.short_stop, abs(self.pos), True)

        # 发出状态更新事件
        self.put_event()
    #----------------------------------------------------------------------
    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        收到委托变化推送
        """
        pass
    #----------------------------------------------------------------------
    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        # 发出状态更新事件
        """
        self.put_event()
    #----------------------------------------------------------------------
    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
