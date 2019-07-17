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
一个ATR-RSI指标结合的交易策略，适合用在股指的1分钟和5分钟线上。
2. 将IF0000_1min.csv用ctaHistoryData.py导入MongoDB后，直接运行本文件即可回测策略

"""
class AtrRsiStrategy(CtaTemplate):
    """"""

    author = "用Python的交易员"

    # 策略参数
    atr_length = 22       # 计算ATR指标的窗口数
    atr_ma_length = 10    # 计算ATR均线的窗口数
    rsi_length = 5        # 计算RSI的窗口数
    rsi_entry = 16        # RSI的开仓信号
    trailing_percent = 0.8  # 百分比移动止损
    fixed_size = 1          # 每次交易的数量

    # 策略变量
    atr_value = 0       # 最新的ATR指标数值
    atr_ma = 0          # ATR移动平均的数值
    rsi_value = 0       # RSI指标的数值
    rsi_buy = 0         # RSI买开阈值
    rsi_sell = 0        # RSI卖开阈值
    intra_trade_high = 0    # 移动止损用的持仓期内最高价
    intra_trade_low = 0     # 移动止损用的持仓期内最低价

    # 参数列表，保存了参数的名称
    parameters = ["atr_length", "atr_ma_length", "rsi_length",
                  "rsi_entry", "trailing_percent", "fixed_size"]

    # 变量列表，保存了变量的名称
    variables = ["atr_value", "atr_ma", "rsi_value", "rsi_buy", "rsi_sell"]

    # ----------------------------------------------------------------------
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(AtrRsiStrategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        # 创建K线合成器对象
        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager()
        # 注意策略类中的可变对象属性（通常是list和dict等），在策略初始化时需要重新创建，
        # 否则会出现多个策略实例之间数据共享的情况，有可能导致潜在的策略逻辑错误风险，
        # 策略类中的这些可变对象属性可以选择不写，全都放在__init__下面，写主要是为了阅读
        # 策略时方便（更多是个编程习惯的选择）

    # ----------------------------------------------------------------------
    def on_init(self):
        """
        Callback when strategy is inited.
        初始化策略（必须由用户继承实现）
        """
        self.write_log("策略初始化")
        # 初始化RSI入场阈值
        self.rsi_buy = 50 + self.rsi_entry
        self.rsi_sell = 50 - self.rsi_entry

        # 载入历史数据，并采用回放计算的方式初始化策略数值
        self.load_bar(10)        # 初始化数据所用的天数10

    def on_start(self):
        """
        Callback when strategy is started.
         策略启动的回调
        """
        self.write_log("策略启动")

    def on_stop(self):
        """
        Callback when strategy is stopped.
        停止策略的回调
        """
        self.write_log("策略停止")

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        收到行情TICK的回调
        """
        print("-------------------------策略接收到消息的时候")
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        收到Bar推送的回调
        """
        self.cancel_all()

        # 保存K线数据
        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        # 计算指标数值
        atr_array = am.atr(self.atr_length, array=True)
        self.atr_value = atr_array[-1]
        self.atr_ma = atr_array[-self.atr_ma_length:].mean()
        self.rsi_value = am.rsi(self.rsi_length)
        # 判断是否要进行交易

        # 当前无仓位
        if self.pos == 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price

            # ATR数值上穿其移动平均线，说明行情短期内波动加大
            # 即处于趋势的概率较大，适合CTA开仓
            if self.atr_value > self.atr_ma:
                # 使用RSI指标的趋势行情时，会在超买超卖区钝化特征，作为开仓信号
                if self.rsi_value > self.rsi_buy:
                    # 这里为了保证成交，选择超价5个整指数点下单
                    print("=========策略中开仓，buy")
                    print(bar.close_price + 5)
                    print(self.fixed_size)
                    self.buy(bar.close_price + 5, self.fixed_size)
                elif self.rsi_value < self.rsi_sell:
                    print("=========策略中开仓，short")
                    print(bar.close_price-5)
                    print(self.fixed_size)
                    self.short(bar.close_price - 5, self.fixed_size)
        # 持有多头仓位
        elif self.pos > 0:
            # 计算多头持有期内的最高价，以及重置最低价
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = bar.low_price
            # 计算多头移动止损
            long_stop = self.intra_trade_high * \
                (1 - self.trailing_percent / 100)
            # 发出本地止损委托
            self.sell(long_stop, abs(self.pos), stop=True)
        # 持有空头仓位
        elif self.pos < 0:
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
            self.intra_trade_high = bar.high_price

            short_stop = self.intra_trade_low * \
                (1 + self.trailing_percent / 100)
            self.cover(short_stop, abs(self.pos), stop=True)
        # 发出状态更新事件
        self.put_event()

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        收到委托变化推送 回调
        """
        pass

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        发出状态更新事件
        """
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        停止单推送
        """
        pass
