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
基于King Keltner通道的交易策略，适合用在股指上，
展示了OCO委托和5分钟K线聚合的方法。
"""

class KingKeltnerStrategy(CtaTemplate):
    """"""

    author = '用Python的交易员'
    # 策略参数
    kk_length = 11            # 计算通道中值的窗口数
    kk_dev = 1.6              # 计算通道宽度的偏差
    trailing_percent = 0.8    # 移动止损
    fixed_size = 1            # 每次交易的数量

    # 策略变量
    kk_up = 0               # KK通道上轨
    kk_down = 0             # KK通道下轨
    intra_trade_high = 0    # 持仓期内的最高点
    intra_trade_low = 0     # 持仓期内的最低点

    long_vt_orderids = []   # OCO委托买入开仓的委托号
    short_vt_orderids = []  # OCO委托卖出开仓的委托号
    vt_orderids = []        # 保存委托代码的列表

    # 参数列表，保存了参数的名称
    parameters = ['kk_length', 'kk_dev', 'fixed_size']

    # 变量列表，保存了变量的名称
    variables = ['kk_up', 'kk_down']

    # ----------------------------------------------------------------------
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(KingKeltnerStrategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        # 创建K线合成器对象
        self.bg = BarGenerator(self.on_bar, 5, self.on_5min_bar)
        self.am = ArrayManager()

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(10)  # 载入历史数据，并采用回放计算的方式初始化策略数值,10天

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
        self.bg.update_bar(bar)

    def on_5min_bar(self, bar: BarData):
        """收到5分钟K线"""

        # 撤销之前发出的尚未成交的委托（包括限价单和停止单）
        for orderid in self.vt_orderids:
            self.cancel_order(orderid)
        self.vt_orderids.clear()
        # 保存K线数据
        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return
        # 计算指标数值
        self.kk_up, self.kk_down = am.keltner(self.kk_length, self.kk_dev)
        # 判断是否要进行交易

        # 当前无仓位，发送OCO开仓委托
        if self.pos == 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price
            self.send_oco_order(self.kk_up, self.kk_down, self.fixed_size)
        # 持有多头仓位
        elif self.pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = bar.low_price

            vt_orderids = self.sell(self.intra_trade_high * (1 - self.trailing_percent / 100),
                                    abs(self.pos), True)
            self.vt_orderids.extend(vt_orderids)
        # 持有空头仓位
        elif self.pos < 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)

            vt_orderids = self.cover(self.intra_trade_low * (1 + self.trailing_percent / 100),
                                     abs(self.pos), True)
            self.vt_orderids.extend(vt_orderids)
        # 发出状态更新事件
        self.put_event()

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    # ----------------------------------------------------------------------
    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        if self.pos != 0:
            # 多头开仓成交后，撤消空头委托
            if self.pos > 0:
                for short_orderid in self.short_vt_orderids:
                    self.cancel_order(short_orderid)
            # 反之同样
            elif self.pos < 0:
                for buy_orderid in self.long_vt_orderids:
                    self.cancel_order(buy_orderid)
            # 移除委托号
            for orderid in (self.long_vt_orderids + self.short_vt_orderids):
                if orderid in self.vt_orderids:
                    self.vt_orderids.remove(orderid)
        # 发出状态更新事件
        self.put_event()

    # ----------------------------------------------------------------------
    def send_oco_order(self, buy_price, short_price, volume):
        """
            发送OCO委托

            OCO(One Cancel Other)委托：
            1. 主要用于实现区间突破入场
            2. 包含两个方向相反的停止单
            3. 一个方向的停止单成交后会立即撤消另一个方向的
        """

        # 发送双边的停止单委托，并记录委托号
        self.long_vt_orderids = self.buy(buy_price, volume, True)
        self.short_vt_orderids = self.short(short_price, volume, True)

        # 将委托号记录到列表中
        self.vt_orderids.extend(self.long_vt_orderids)
        self.vt_orderids.extend(self.short_vt_orderids)

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
