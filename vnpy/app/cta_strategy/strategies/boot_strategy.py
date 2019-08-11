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
    current_price=0     # 下单价格
    max_open=4          #每天最大开仓次数
    open_count=0        #今日开仓次数


    stop_long_price=0   #多单止损价格
    stop_short_price=0  #空单止损价格
    ma_value = 0        #5min avgrage
    vt_orderids = []        # 保存委托代码的列表
    # 参数列表，保存了参数的名称
    parameters = ["current_price", "max_open", "open_count","fixed_size"]


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
        self.load_bar(1)       #初始化加载数据

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
        # 当前无仓位
        if self.ma_value!=0:
            if self.pos == 0:
                if tick.last_price > self.ma_value :  # The current price is above the 5min moving average，Long positions
                    self.stop_long_price = tick.last_price - 20  # long stop  price
                    self.current_price = tick.last_price + 2
                    print("当前开仓次数：(%s)" % (self.open_count))
                    orderId = self.buy(tick.last_price + 2, self.fixed_size)
                elif tick.last_price < self.ma_value:  # The current price is above the 5min moving average，Short positions
                    self.stop_short_price = tick.last_price + 20  # short stop  price
                    self.current_price = tick.last_price + 2
                    orderId = self.short(tick.last_price - 2, self.fixed_size)
                    print("当前开仓次数：(%s)" % (self.open_count))
            elif self.pos > 0:
                if  self.stop_long_price!=0 :  # long stop loss,current price <= Stop-Loss Price，trigger stop price
                    if tick.last_price <= self.stop_long_price or tick.last_price>=self.ma_value:
                        self.sell(self.stop_long_price - 2, abs(self.pos))
            elif self.pos < 0:  # Hold short positions
                if   self.stop_short_price!=0:  # short stop loss,current price>=Stop-Loss Price，trigger stop price
                    if tick.last_price >= self.stop_short_price or tick.last_price>=self.ma_value:
                        self.cover(self.stop_short_price + 2, abs(self.pos))


        #从本地查询持仓情况
        #防止服务崩掉昨日持仓还在，看是否有昨日持仓，如果有看看是否满足平仓条件，

        # if self.position:
        #     if self.position['direction'] == "long":
        #         self.stop_long_price = self.position['price']-20
        #         if  tick.last_price <= self.position['price']:         #buy, the latest_price less than current_price,sell
        #             self.sell(tick.last_price - 2, abs(self.position['volume']))
        #         else:
        #             self.pos = self.position['volume']
        #             self.current_price = self.position['price']
        #     else:
        #         self.stop_short_price = self.position['price'] + 20
        #         if tick.last_price >= self.position['price']:    #short,  the latest_price more than the current_price,cover
        #             self.cover(tick.last_price + 2, abs(self.position['volume']))
        #         else:
        #             self.pos=-self.position['volume']
        #             self.current_price = self.position['price']
        #     self.clearData()






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
