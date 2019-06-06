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

#cta策略示例
class BollChannelStrategy(CtaTemplate):
    """"""

    author = "用Python的交易员"

    boll_window = 18
    boll_dev = 3.4
    cci_window = 10
    atr_window = 30
    sl_multiplier = 5.2
    fixed_size = 1

    boll_up = 0
    boll_down = 0
    cci_value = 0
    atr_value = 0

    intra_trade_high = 0
    intra_trade_low = 0
    long_stop = 0
    short_stop = 0

    parameters = ["boll_window", "boll_dev", "cci_window",
                  "atr_window", "sl_multiplier", "fixed_size"]
    variables = ["boll_up", "boll_down", "cci_value", "atr_value",
                 "intra_trade_high", "intra_trade_low", "long_stop", "short_stop"]

    #传入CTA引擎、策略名称、vt_symbol、参数设置。
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(BollChannelStrategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        #调用K线生成模块:通过时间切片来把Tick数据合成1分钟K线数据，然后更大的时间周期数据，如15分钟K线。
        self.bg = BarGenerator(self.on_bar, 15, self.on_15min_bar)

        #调用K线时间序列管理模块：基于K线数据，如1分钟、15分钟，来生成相应的技术指标。
        self.am = ArrayManager()

    def on_init(self):
        """
        Callback when strategy is inited.
        """
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

    #Tick数据回报¶
    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        策略订阅某品种合约行情，交易所会推送Tick数据到该策略上。由于BollChannelStrategy是基于15分钟K线来生成交易信号的，故收到Tick数据后，需要用到K线生成模块里面的update_tick函数，通过时间切片的方法，聚合成1分钟K线数据，并且推送到on_bar函数。
        """
        self.bg.update_tick(tick)

    #K线数据回报
    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        收到推送过来的1分钟K线数据后，通过K线生成模块里面的update_bar函数，以分钟切片的方法，合成15分钟K线数据，并且推送到on_15min_bar函数。
        """
        self.bg.update_bar(bar)


    #15分钟K线数据回报
    def on_15min_bar(self, bar: BarData):
        """
            负责CTA信号的生成，由3部分组成：
                1.清空未成交委托：为了防止之前下的单子在上一个15分钟没有成交，但是下一个15分钟可能已经调整了价格，就用cancel_all()方法立刻撤销之前未成交的所有委托，保证策略在当前这15分钟开始时的整个状态是清晰和唯一的。
                2.调用K线时间序列管理模块：基于最新的15分钟K线数据来计算相应计算指标，如布林带通道上下轨、CCI指标、ATR指标
                3.信号计算：通过持仓的判断以及结合CCI指标、布林带通道、ATR指标在通道突破点挂出停止单委托（buy/sell)，同时设置离场点(short/cover)。
                注意：CTA策略具有低胜率和高盈亏比的特定：在难以提升胜率的情况下，研究提高策略盈亏比有利于策略盈利水平的上升
        """
        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        self.boll_up, self.boll_down = am.boll(self.boll_window, self.boll_dev)
        self.cci_value = am.cci(self.cci_window)
        self.atr_value = am.atr(self.atr_window)

        if self.pos == 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price

            if self.cci_value > 0:
                self.buy(self.boll_up, self.fixed_size, True)
            elif self.cci_value < 0:
                self.short(self.boll_down, self.fixed_size, True)

        elif self.pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = bar.low_price

            self.long_stop = self.intra_trade_high - self.atr_value * self.sl_multiplier
            self.sell(self.long_stop, abs(self.pos), True)

        elif self.pos < 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)

            self.short_stop = self.intra_trade_low + self.atr_value * self.sl_multiplier
            self.cover(self.short_stop, abs(self.pos), True)

        self.put_event()

    #委托回报
    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        在策略中可以直接pass，其具体逻辑应用交给回测/实盘引擎负责。
        """
        pass

    #停止单回报
    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        在策略中可以直接pass，其具体逻辑应用交给回测/实盘引擎负责。
        """
        self.put_event()

    #停止单回报
    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        在策略中可以直接pass，其具体逻辑应用交给回测/实盘引擎负责。
        """
        pass
