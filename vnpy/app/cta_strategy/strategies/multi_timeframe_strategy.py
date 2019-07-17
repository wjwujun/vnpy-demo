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
一个跨时间周期的策略，基于15分钟K线判断趋势方向，并使用5分钟RSI指标作为入场
"""
class MultiTimeframeStrategy(CtaTemplate):
    """"""
    author = "用Python的交易员"

    # 策略参数
    rsi_signal = 20     # RSI信号阈值
    rsi_window = 14     # RSI窗口
    fast_window = 5     # 快速均线窗口
    slow_window = 20    # 慢速均线窗口
    fixed_size = 1       # 每次交易的数量

    # 策略变量
    rsi_value = 0       # RSI指标的数值
    rsi_long = 0        # RSI买开阈值
    rsi_short = 0       # RSI卖开阈值
    fast_ma = 0         # 5分钟快速均线
    slow_ma = 0         # 5分钟慢速均线
    ma_trend = 0        # 均线趋势，多头1，空头-1
    # 参数列表，保存了参数的名称
    parameters = ["rsi_signal", "rsi_window",
                  "fast_window", "slow_window",
                  "fixed_size"]
    # 变量列表，保存了变量的名称
    variables = ["rsi_value", "rsi_long", "rsi_short",
                 "fast_ma", "slow_ma", "ma_trend"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(MultiTimeframeStrategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.rsi_long = 50 + self.rsi_signal
        self.rsi_short = 50 - self.rsi_signal
        # 创建K线合成器对象
        self.bg5 = BarGenerator(self.on_bar, 5, self.on_5min_bar)
        self.am5 = ArrayManager()

        self.bg15 = BarGenerator(self.on_bar, 15, self.on_15min_bar)
        self.am15 = ArrayManager()

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        # 载入历史数据，并采用回放计算的方式初始化策略数值,初始化数据所用的天数10
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
        self.bg5.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg5.update_bar(bar)
        self.bg15.update_bar(bar)

    def on_5min_bar(self, bar: BarData):
        """5分钟K线"""


        self.cancel_all()
        # 保存K线数据
        self.am5.update_bar(bar)
        if not self.am5.inited:
            return
        # 如果15分钟数据尚未初始化完毕，则直接返回
        if not self.ma_trend:
            return
        # 计算指标数值
        self.rsi_value = self.am5.rsi(self.rsi_window)
        # 判断是否要进行交易

        # 当前无仓位
        if self.pos == 0:
            if self.ma_trend > 0 and self.rsi_value >= self.rsi_long:
                self.buy(bar.close_price + 5, self.fixed_size)
            elif self.ma_trend < 0 and self.rsi_value <= self.rsi_short:
                self.short(bar.close_price - 5, self.fixed_size)
        # 持有多头仓位
        elif self.pos > 0:
            if self.ma_trend < 0 or self.rsi_value < 50:
                self.sell(bar.close_price - 5, abs(self.pos))
        # 持有空头仓位
        elif self.pos < 0:
            if self.ma_trend > 0 or self.rsi_value > 50:
                self.cover(bar.close_price + 5, abs(self.pos))
        # 发出状态更新事件
        self.put_event()

    def on_15min_bar(self, bar: BarData):
        """15分钟K线推送"""

        self.am15.update_bar(bar)
        if not self.am15.inited:
            return

        # 计算均线并判断趋势
        self.fast_ma = self.am15.sma(self.fast_window)
        self.slow_ma = self.am15.sma(self.slow_window)

        if self.fast_ma > self.slow_ma:
            self.ma_trend = 1
        else:
            self.ma_trend = -1

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
