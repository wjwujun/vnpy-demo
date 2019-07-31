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
    min bar 止损
"""

class DoubleMa44Strategy(CtaTemplate):
    author = "wj"
    position_filename = "posotion_data.json"

    # 策略变量
    fixed_size = 1      # 开仓数量
    current_price=0     # 下单价格
    max_open=5          #每天最大开仓次数
    open_count=0        #今日开仓次数
    today=0             #当天时间


    stop_long_price=0   #多单止损价格
    stop_short_price=0  #空单止损价格
    ma_value = 0        #5min avgrage
    vt_orderids = []        # 保存委托代码的列表
    # 参数列表，保存了参数的名称
    parameters = ["current_price", "max_open", "open_count",
                  "today", "fixed_size"]


    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(DoubleMa44Strategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.bg = BarGenerator(self.on_bar,5,self.on_5min_bar)
        self.am = ArrayManager()
        self.today=time.strftime("%Y-%m-%d", time.localtime())
        self.position = load_json(self.position_filename)
        print("------------boot")
        print(self.position)
        # print(self.position['volume'])


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


    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)

        # 从本地查询持仓情况
        print("boot_strategy ------ receive data")
        print(bar)
        print("------------------当前仓位")
        print(self.pos)
        print(self.position)
        print(self.ma_value)
        # 防止服务崩掉昨日持仓还在，看是否有昨日持仓，如果有看看是否满足平仓条件，

        if self.position:
            if self.position['direction'] == "long":
                self.stop_long_price = self.position['price'] - 20
                if bar.close_price <= self.position['price']:  # buy, the latest_price less than current_price,sell
                    self.sell(bar.close_price - 2, abs(self.position['volume']))
                    print("--------------position___sell")
                else:
                    self.pos = self.position['volume']
                    self.current_price = self.position['price']
            else:
                self.stop_short_price = self.position['price'] + 20
                if bar.close_price >= self.position[
                    'price']:  # short,  the latest_price more than the current_price,cover
                    self.cover(bar.close_price + 2, abs(self.position['volume']))
                    print("--------------position_cover")
                else:
                    self.pos = -self.position['volume']
                    self.current_price = self.position['price']
            self.clearData()

        if self.pos > 0:
            if bar.close_price <= self.stop_long_price:  # long stop loss,current price <= Stop-Loss Price，trigger stop price
                print("==========long 平仓 11")
                print(self.stop_long_price - 2)
                self.sell(self.stop_long_price - 2, abs(self.pos))
            elif self.ma_value != 0 and bar.close_price <= self.ma_value:
                print("==========long 平仓 22")
                print(self.ma_value)
                self.sell(bar.close_price - 2, abs(self.pos))
        elif self.pos < 0:  # Hold short positions
            if bar.close_price >= self.stop_short_price:  # short stop loss,current price>=Stop-Loss Price，trigger stop price
                print("==========short 平仓11")
                print(self.stop_short_price + 2)
                self.cover(self.stop_short_price + 2, abs(self.pos))
            elif self.ma_value != 0 and bar.close_price >= self.ma_value:
                print("==========short 平仓22")
                print(self.ma_value)
                self.cover(bar.close_price + 2, abs(self.pos))




    def on_5min_bar(self, bar: BarData):
        """5分钟K线"""

        # 撤销之前发出的尚未成交的委托（包括限价单和停止单）
        self.cancel_all()
        self.vt_orderids.clear()
        # 保存K线数据
        self.am.update_bar(bar)
        print("---------------当前均线更新")
        print(self.am.count)
        print(self.am.size)
        print(self.am.inited)
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
        print("----------当前均线价格")
        print(self.ma_value)
        # 当前无仓位
        if self.pos == 0:
            if bar.close_price > self.ma_value:  # The current price is above the 5min moving average，Long positions
                print("-----------------open position buy")
                print(bar.close_price + 2)
                self.stop_long_price = bar.close_price - 20  # long stop  price
                self.current_price = bar.close_price + 2
                open_count+=1
                self.buy(bar.close_price + 2, self.fixed_size)

            elif bar.close_price < self.ma_value:  # The current price is above the 5min moving average，Short positions
                print("-----------------open position short")
                print(bar.close_price - 2)
                self.stop_short_price = bar.close_price + 20  # short stop  price
                self.current_price = bar.close_price + 2
                open_count += 1
                self.short(bar.close_price - 2, self.fixed_size)


        # 发出状态更新事件
        self.put_event()



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
