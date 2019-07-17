from vnpy.app.cta_strategy import (
    CtaTemplate,
    StopOrder,
    Direction,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)

"""
单标的海龟交易策略，实现了完整海龟策略中的信号部分。
"""
class TurtleSignalStrategy(CtaTemplate):
    """"""
    author = "用Python的交易员"

    # 策略参数
    entry_window = 20           # 入场通道窗口
    exit_window = 10            # 出场通道窗口
    atr_window = 20             # 计算ATR波动率的窗口
    fixed_size = 1              # 每次交易的数量
    # 策略变量
    entry_up = 0                # 入场通道上轨
    entry_down = 0              # 入场通道下轨
    exit_up = 0                 # 出场通道上轨
    exit_down = 0               # 出场通道下轨
    atr_value = 0               # ATR波动率

    long_entry = 0              # 多头入场价格
    short_entry = 0             # 空头入场价格
    long_stop = 0               # 多头止损价格
    short_stop = 0              # 空头止损价格

    # 参数列表，保存了参数的名称
    parameters = ["entry_window", "exit_window", "atr_window", "fixed_size"]
    # 变量列表，保存了变量的名称
    variables = ["entry_up", "entry_down", "exit_up", "exit_down", "atr_value"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(TurtleSignalStrategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager()

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(20)

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
           收到Bar推送的回调
        """
        self.cancel_all()

        # 保存K线数据
        self.am.update_bar(bar)
        if not self.am.inited:
            return

        # 计算指标数值
        self.entry_up, self.entry_down = self.am.donchian(self.entry_window)
        self.exit_up, self.exit_down = self.am.donchian(self.exit_window)

        # 判断是否要进行交易
        if not self.pos:
            self.atr_value = self.am.atr(self.atr_window)

            self.long_entry = 0
            self.short_entry = 0
            self.long_stop = 0
            self.short_stop = 0

            self.send_buy_orders(self.entry_up)
            self.send_short_orders(self.entry_down)
        elif self.pos > 0:
            # 加仓逻辑
            self.send_buy_orders(self.long_entry)

            # 止损逻辑
            sell_price = max(self.long_stop, self.exit_down)
            self.sell(sell_price, abs(self.pos), True)

        elif self.pos < 0:
            # 加仓逻辑
            self.send_short_orders(self.short_entry)
            # 止损逻辑
            cover_price = min(self.short_stop, self.exit_up)
            self.cover(cover_price, abs(self.pos), True)
        # 发出状态更新事件
        self.put_event()

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
                成交推送
        """
        if trade.direction == Direction.LONG:
            self.long_entry = trade.price
            self.long_stop = self.long_entry - 2 * self.atr_value
        else:
            self.short_entry = trade.price
            self.short_stop = self.short_entry + 2 * self.atr_value

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass

    def send_buy_orders(self, price):
        """发出一系列的买入停止单"""

        t = self.pos / self.fixed_size

        if t < 1:
            self.buy(price, self.fixed_size, True)

        if t < 2:
            self.buy(price + self.atr_value * 0.5, self.fixed_size, True)

        if t < 3:
            self.buy(price + self.atr_value, self.fixed_size, True)

        if t < 4:
            self.buy(price + self.atr_value * 1.5, self.fixed_size, True)

    def send_short_orders(self, price):
        """发出一系列的卖出停止单"""
        t = self.pos / self.fixed_size

        if t > -1:
            self.short(price, self.fixed_size, True)

        if t > -2:
            self.short(price - self.atr_value * 0.5, self.fixed_size, True)

        if t > -3:
            self.short(price - self.atr_value, self.fixed_size, True)

        if t > -4:
            self.short(price - self.atr_value * 1.5, self.fixed_size, True)
