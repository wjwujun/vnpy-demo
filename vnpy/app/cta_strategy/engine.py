""""""

import importlib
import os
from collections import defaultdict
from pathlib import Path
from time import sleep, time
from typing import Any, Callable
from datetime import datetime, timedelta
from threading import Thread
from queue import Queue
from copy import copy

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.object import (OrderRequest,SubscribeRequest,HistoryRequest,LogData,TickData,BarData,ContractData)
from vnpy.trader.event import (EVENT_TICK, EVENT_ORDER, EVENT_TRADE,EVENT_POSITION,EVENT_ACCOUNT)
from vnpy.trader.constant import (Direction, OrderType, Interval, Exchange, Offset, Status)
from vnpy.trader.utility import load_json, save_json, extract_vt_symbol, round_to, BarGenerator
from vnpy.trader.database import database_manager
from vnpy.trader.rqdata import rqdata_client

from .base import (APP_NAME,EVENT_CTA_LOG,EVENT_CTA_STRATEGY,EVENT_CTA_STOPORDER,EngineType,StopOrder,StopOrderStatus,STOPORDER_PREFIX
)
from .template import CtaTemplate
from .converter import OffsetConverter


STOP_STATUS_MAP = {
    Status.SUBMITTING: StopOrderStatus.WAITING,
    Status.NOTTRADED: StopOrderStatus.WAITING,
    Status.PARTTRADED: StopOrderStatus.TRIGGERED,
    Status.ALLTRADED: StopOrderStatus.TRIGGERED,
    Status.CANCELLED: StopOrderStatus.CANCELLED,
    Status.REJECTED: StopOrderStatus.CANCELLED
}


class CtaEngine(BaseEngine):
    """"""

    engine_type = EngineType.LIVE  # live trading engine

    setting_filename = "cta_strategy_setting.json"
    data_filename = "cta_strategy_data.json"
    position_filename="posotion_data.json"
    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        """"""
        super(CtaEngine, self).__init__(
            main_engine, event_engine, APP_NAME)

        self.strategy_setting = {}  # strategy_name: dict
        self.strategy_data = {}     # strategy_name: dict
        self.position_data = {"pnl":0}     # strategy_name: dict

        self.classes = {}           # class_name: stategy_class
        self.strategies = {}        # strategy_name: strategy

        self.symbol_strategy_map = defaultdict(list)                   # vt_symbol: strategy list
        self.orderid_strategy_map = {}  # vt_orderid: strategy
        self.strategy_orderid_map = defaultdict(set)                    # strategy_name: orderid list

        self.stop_order_count = 0   # for generating stop_orderid
        self.stop_orders = {}       # stop_orderid: stop_order

        self.init_thread = None
        self.init_queue = Queue()

        self.rq_client = None
        self.rq_symbols = set()
        self.tick={}
        self.vt_tradeids = set()    # for filtering duplicate trade

        self.offset_converter = OffsetConverter(self.main_engine)
        self.bg = BarGenerator(self.on_bar)
        self.balance_now=0.0

    def init_engine(self):
        """
            初始化策略引擎
        """
        self.init_rqdata()
        self.load_strategy_class()
        self.load_strategy_setting()
        self.load_strategy_data()
        self.register_event()
        self.write_log("CTA策略引擎初始化成功")



    def get_setting(self):
        """"""
        setting = {}

        if self.class_name:
            setting["class_name"] = self.class_name

        for name, tp in self.edits.items():
            edit, type_ = tp
            value_text = edit.text()

            if type_ == bool:
                if value_text == "True":
                    value = True
                else:
                    value = False
            else:
                value = type_(value_text)

            setting[name] = value

        return setting

    def close(self):
        """
            关闭CTA策略全部启动
        """
        self.stop_all_strategies()
    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        database_manager.save_bar_data([bar])

    def register_event(self):
        """
        注册相关的时间处理函数
        """
        #tick数据处理方法
        self.event_engine.register(EVENT_TICK, self.process_tick_event)

        #挂单的处理方法
        self.event_engine.register(EVENT_ORDER, self.process_order_event)
        #交易的处理方法
        self.event_engine.register(EVENT_TRADE, self.process_trade_event)
        #持仓数据处理方法
        self.event_engine.register(EVENT_POSITION, self.process_position_event)
        #处理账户情况
        self.event_engine.register(EVENT_ACCOUNT, self.process_account_event)

    def init_rqdata(self):
        """
            初始化 RQData client.
        """
        result = rqdata_client.init()
        if result:
            self.write_log("RQData数据接口初始化成功")

    #从RQData查询k线数据
    def query_bar_from_rq(self, symbol: str, exchange: Exchange, interval: Interval, start: datetime, end: datetime):
        req = HistoryRequest(
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            start=start,
            end=end
        )
        data = rqdata_client.query_history(req)
        return data

    #接收到tick数据后的处理方法,
    def process_tick_event(self, event: Event):
        tick = event.data
        #print("-----------------------------------保存-----收到tick的")
        #print(tick)
        if tick.datetime.strftime("%H:%M:%S") <= "15:10:00":
            database_manager.save_tick_data([tick])
        self.bg.update_tick(tick)
        self.tick=tick
        strategies = self.symbol_strategy_map[tick.vt_symbol]
        if not strategies:
            return

        self.check_stop_order(tick)
        for strategy in strategies:
            #收到tick的时候，查询当前的持有情况
            #holding=self.offset_converter.get_position_holding(tick.vt_symbol)
            if strategy.inited:
                self.call_strategy_func(strategy, strategy.on_tick, tick)

    #挂单的处理方法
    def process_order_event(self, event: Event):
        order = event.data
        
        self.offset_converter.update_order(order)

        strategy = self.orderid_strategy_map.get(order.vt_orderid, None)
        if not strategy:
            return

        # 如果订单不再有效，请删除vt_orderid。
        vt_orderids = self.strategy_orderid_map[strategy.strategy_name]
        if order.vt_orderid in vt_orderids and not order.is_active():
            vt_orderids.remove(order.vt_orderid)

        # 对于服务器停止顺序，调用策略on_stop_order函数
        if order.type == OrderType.STOP:
            so = StopOrder(
                vt_symbol=order.vt_symbol,
                direction=order.direction,
                offset=order.offset,
                price=order.price,
                volume=order.volume,
                stop_orderid=order.vt_orderid,
                strategy_name=strategy.strategy_name,
                status=STOP_STATUS_MAP[order.status],
                vt_orderids=[order.vt_orderid],
            )
            self.call_strategy_func(strategy, strategy.on_stop_order, so)  

        # 调用策略on_order函数
        self.call_strategy_func(strategy, strategy.on_order, order)

    #交易的处理方法
    def process_trade_event(self, event: Event):
        trade = event.data

        # Filter duplicate trade push
        if trade.vt_tradeid in self.vt_tradeids:
            return
        self.vt_tradeids.add(trade.vt_tradeid)

        self.offset_converter.update_trade(trade)

        strategy = self.orderid_strategy_map.get(trade.vt_orderid, None)
        if not strategy:
            return

        # Update strategy pos before calling on_trade method
        # 在调用on_trade方法之前更新策略pos
        if trade.direction == Direction.LONG:
            strategy.pos += trade.volume
        else:
            strategy.pos -= trade.volume

        self.call_strategy_func(strategy, strategy.on_trade, trade)
        # 保存相关策略参数到本地
        self.sync_strategy_data(strategy)
        # Update GUI
        self.put_strategy_event(strategy)

    # 持仓数据处理方法
    def process_position_event(self, event: Event):
        position = event.data

        #update holding position data
        self.offset_converter.update_position(position)
        # print("1111111111111111111111111")
        strategy = self.strategies["DoubleMa22Strategy"]
        strategy.pnl = position.pnl
        if position.volume!=0 or position.yd_volume!=0:
            #保存到mysql
            database_manager.save_position_data([position])
            # self.position_data['symbol']=position.symbol
            # if position.direction==Direction.LONG:
            #     self.position_data['direction']="long"
            # else:
            #     self.position_data['direction']="short"
            # self.position_data['volume']=position.volume
            # self.position_data['price']=position.price
            # self.position_data['yd_volume']=position.yd_volume
            # self.position_data['pnl']=position.pnl
            # self.position_data['frozen']=position.frozen
            # #将持仓数据保存到本地。
            # save_json(self.position_filename,self.position_data)

    #账户信息查看
    def process_account_event(self,event:Event):
        account=event.data
        #print("账户信息查看=================================")
        #print(account)
        #账户数据插入mysql

        if account.balance != self.balance_now:
            self.balance_now=account.balance
            database_manager.save_account_data([account])



    def check_stop_order(self, tick: TickData):

        for stop_order in list(self.stop_orders.values()):
            if stop_order.vt_symbol != tick.vt_symbol:
                continue

            long_triggered = (
                stop_order.direction == Direction.LONG and tick.last_price >= stop_order.price
            )
            short_triggered = (
                stop_order.direction == Direction.SHORT and tick.last_price <= stop_order.price
            )

            if long_triggered or short_triggered:
                strategy = self.strategies[stop_order.strategy_name]

                # 在停止订单后立即执行
                # 触发，使用限价（如果可用），否则
                # 使用ask_price_5或bid_price_5erwise
                if stop_order.direction == Direction.LONG:
                    if tick.limit_up:
                        price = tick.limit_up
                    else:
                        price = tick.ask_price_5
                else:
                    if tick.limit_down:
                        price = tick.limit_down
                    else:
                        price = tick.bid_price_5
                
                contract = self.main_engine.get_contract(stop_order.vt_symbol)

                vt_orderids = self.send_limit_order(
                    strategy, 
                    contract,
                    stop_order.direction, 
                    stop_order.offset, 
                    price, 
                    stop_order.volume,
                    stop_order.lock
                )

                # 如果成功放置，停止订单状态
                if vt_orderids:
                    #从关系图中删除
                    self.stop_orders.pop(stop_order.stop_orderid)

                    strategy_vt_orderids = self.strategy_orderid_map[strategy.strategy_name]
                    if stop_order.stop_orderid in strategy_vt_orderids:
                        strategy_vt_orderids.remove(stop_order.stop_orderid)

                    # 将停止订单状态更改为已取消并更新为策略。
                    stop_order.status = StopOrderStatus.TRIGGERED
                    stop_order.vt_orderids = vt_orderids

                    self.call_strategy_func(
                        strategy, strategy.on_stop_order, stop_order
                    )
                    self.put_stop_order_event(stop_order)
    #向服务器发送新订单。
    def send_server_order(
        self,strategy: CtaTemplate,contract: ContractData,direction: Direction,
        offset: Offset,price: float,volume: float,type: OrderType,lock: bool):
        """
        Send a new order to server.
        """
        # Create request and send order.
        original_req = OrderRequest(
            symbol=contract.symbol,
            exchange=contract.exchange,
            direction=direction,
            offset=offset,
            type=type,
            price=price,
            volume=volume,
        )

        # Convert with offset converter
        req_list = self.offset_converter.convert_order_request(original_req, lock)
        print("==================向CTP服务器发送请求的时候")
        print(req_list)
        # Send Orders
        vt_orderids = []

        for req in req_list:
            ##发送订单，返回订单号
            vt_orderid = self.main_engine.send_order(req, contract.gateway_name)
            vt_orderids.append(vt_orderid)

            self.offset_converter.update_order_request(req, vt_orderid)
            
            # 保存orderid和策略之间的关系。
            self.orderid_strategy_map[vt_orderid] = strategy
            self.strategy_orderid_map[strategy.strategy_name].add(vt_orderid)

        return vt_orderids
    #向服务器发送限价订单。
    def send_limit_order(
        self,strategy: CtaTemplate,contract: ContractData,direction: Direction,
        offset: Offset,price: float,volume: float,lock: bool):

        #print("------------------------------限价单-send_limit_order")
        return self.send_server_order(
            strategy,
            contract,
            direction,
            offset,
            price,
            volume,
            OrderType.LIMIT,
            lock
        )

    #向交易所服务器发送停止单
    def send_server_stop_order(
        self,strategy: CtaTemplate,contract: ContractData,direction: Direction,
        offset: Offset,price: float,volume: float,lock: bool):
        """
        Send a stop order to server.    #向服务器发送停止单
        
        Should only be used if stop order supported # 仅在支持停止订单时使用     在交易服务器上。
        on the trading server.
        """
        return self.send_server_order(strategy,contract,direction,offset,price,volume,OrderType.STOP,lock)
    #在本地保存一个停止单
    def send_local_stop_order(
        self,strategy: CtaTemplate,direction: Direction,offset: Offset,price: float,volume: float,lock: bool):
        """
        Create a new local stop order.
        """
        self.stop_order_count += 1
        stop_orderid = f"{STOPORDER_PREFIX}.{self.stop_order_count}"

        stop_order = StopOrder(
            vt_symbol=strategy.vt_symbol,
            direction=direction,
            offset=offset,
            price=price,
            volume=volume,
            stop_orderid=stop_orderid,
            strategy_name=strategy.strategy_name,
            lock=lock
        )

        self.stop_orders[stop_orderid] = stop_order

        vt_orderids = self.strategy_orderid_map[strategy.strategy_name]
        vt_orderids.add(stop_orderid)

        self.call_strategy_func(strategy, strategy.on_stop_order, stop_order)
        self.put_stop_order_event(stop_order)

        return stop_orderid

    def cancel_server_order(self, strategy: CtaTemplate, vt_orderid: str):
        """
        Cancel existing order by vt_orderid.
        """
        order = self.main_engine.get_order(vt_orderid)
        if not order:
            self.write_log(f"撤单失败，找不到委托{vt_orderid}", strategy)
            return

        req = order.create_cancel_request()
        self.main_engine.cancel_order(req, order.gateway_name)

    def cancel_local_stop_order(self, strategy: CtaTemplate, stop_orderid: str):
        """
        Cancel a local stop order.
        """
        stop_order = self.stop_orders.get(stop_orderid, None)
        if not stop_order:
            return
        strategy = self.strategies[stop_order.strategy_name]

        # Remove from relation map.
        self.stop_orders.pop(stop_orderid)

        vt_orderids = self.strategy_orderid_map[strategy.strategy_name]
        if stop_orderid in vt_orderids:
            vt_orderids.remove(stop_orderid)

        # Change stop order status to cancelled and update to strategy.
        stop_order.status = StopOrderStatus.CANCELLED

        self.call_strategy_func(strategy, strategy.on_stop_order, stop_order)
        self.put_stop_order_event(stop_order)

    #下订单
    def send_order(self,strategy: CtaTemplate,direction: Direction,offset: Offset,price: float,volume: float,stop: bool,lock: bool):

        contract = self.main_engine.get_contract(strategy.vt_symbol)
        if not contract:
            self.write_log(f"委托失败，找不到合约：{strategy.vt_symbol}", strategy)
            return ""
        #print("11111111111111111111111111")
        #print(self.strategy_orderid_map[strategy.strategy_name])
        # Round order price and volume to nearest incremental value
        price = round_to(price, contract.pricetick)
        volume = round_to(volume, contract.min_volume)
        
        if stop:            #stop为true为停止单
            if contract.stop_supported:
                return self.send_server_stop_order(strategy, contract, direction, offset, price, volume, lock)
            else:
                return self.send_local_stop_order(strategy, direction, offset, price, volume, lock)
        else:               #否则为市价单
            return self.send_limit_order(strategy, contract, direction, offset, price, volume, lock)

    def cancel_order(self, strategy: CtaTemplate, vt_orderid: str):
        """
        """
        if vt_orderid.startswith(STOPORDER_PREFIX):
            self.cancel_local_stop_order(strategy, vt_orderid)
        else:
            self.cancel_server_order(strategy, vt_orderid)

    def cancel_all(self, strategy: CtaTemplate):
        """
        Cancel all active orders of a strategy.
        """
        vt_orderids = self.strategy_orderid_map[strategy.strategy_name]
        if not vt_orderids:
            return

        for vt_orderid in copy(vt_orderids):
            self.cancel_order(strategy, vt_orderid)

    def get_engine_type(self):
        """"""
        return self.engine_type

    #策略初始化的时候加载历史数据，用于初始化
    def load_bar(self, vt_symbol: str, days: int, interval: Interval,callback: Callable[[BarData], None]):
        symbol, exchange = extract_vt_symbol(vt_symbol)
        end = datetime.now()
        start = end - timedelta(days)
        print("--指标计算开始加载时间:", start,end)
        # 从RQData 加载默认数据,如果找不到，从数据库加载数据
        bars = self.query_bar_from_rq(symbol, exchange, interval, start, end)
        if not bars:
            bars = database_manager.load_bar_data(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                start=start,
                end=end,
            )

        for bar in bars:
            callback(bar)

    def load_tick(self, vt_symbol: str,days: int,callback: Callable[[TickData], None]):
        """"""
        symbol, exchange = extract_vt_symbol(vt_symbol)
        end = datetime.now()
        start = end - timedelta(days)

        ticks = database_manager.load_tick_data(
            symbol=symbol,
            exchange=exchange,
            start=start,
            end=end,
        )

        for tick in ticks:
            callback(tick)

    def call_strategy_func(self, strategy: CtaTemplate, func: Callable, params: Any = None):
        """
            调用策略的函数并捕获引发的任何异常。
        """
        try:
            if params:
                func(params)
            else:
                func()
        except Exception:
            strategy.trading = False
            strategy.inited = False

            msg = f"触发异常已停止\n{traceback.format_exc()}"
            self.write_log(msg, strategy)

    def add_strategy(self, class_name: str, strategy_name: str, vt_symbol: str, setting: dict):
        """
            从本地初始化一个cta策略，或者添加一个新的
        """

        self.write_log(f"-------------------从本地初始化一个cta策略，或者添加一个新的")

        if strategy_name in self.strategies:
            self.write_log(f"创建策略失败，存在重名{strategy_name}")
            return

        strategy_class = self.classes.get(class_name, None)
        # print(strategy_class)
        # print(strategy_name)
        # print(vt_symbol)
        # print(setting)
        if not strategy_class:
            self.write_log(f"创建策略失败，找不到策略类{class_name}")
            return

        strategy = strategy_class(self, strategy_name, vt_symbol, setting)
        self.strategies[strategy_name] = strategy

        # 添加一个合约到配置文件里面
        strategies = self.symbol_strategy_map[vt_symbol]
        strategies.append(strategy)

        # 修改一个配置文件
        self.update_strategy_setting(strategy_name, setting)
        self.put_strategy_event(strategy)

    def init_strategy(self, strategy_name: str):
        """
            初始化某一个初始化策略
        """ 
        self.init_queue.put(strategy_name)

        if not self.init_thread:
            self.init_thread = Thread(target=self._init_strategy)
            self.init_thread.start()

    def _init_strategy(self):
        """
                在队列里面初始化一个策略
        """
        while not self.init_queue.empty():
            strategy_name = self.init_queue.get()
            strategy = self.strategies[strategy_name]
            if strategy.inited:
                self.write_log(f"{strategy_name}已经完成初始化，禁止重复操作")
                continue

            self.write_log(f"{strategy_name}开始执行初始化")

            # Call on_init function of strategy
            self.call_strategy_func(strategy, strategy.on_init)

            # Restore strategy data(variables)
            data = self.strategy_data.get(strategy_name, None)
            if data:
                for name in strategy.variables:
                    value = data.get(name, None)
                    if value:
                        setattr(strategy, name, value)

            # 订阅行情
            contract = self.main_engine.get_contract(strategy.vt_symbol)
            print("初始化的时候策略的时候，订阅相关合约+++++++++++++++")
            print(contract)

            if contract:
                req = SubscribeRequest(
                    symbol=contract.symbol, exchange=contract.exchange)
                self.main_engine.subscribe(req, contract.gateway_name)
            else:
                self.write_log(f"行情订阅失败，找不到合约{strategy.vt_symbol}", strategy)

            # Put event to update init completed status.
            strategy.inited = True
            # ==========================================交易状态更新回调
            self.put_strategy_event(strategy)
            self.write_log(f"{strategy_name}初始化完成")
        
        self.init_thread = None

    def start_strategy(self, strategy_name: str):
        """
            启动一个cta策略
        """
        strategy = self.strategies[strategy_name]
        if not strategy.inited:
            self.write_log(f"策略{strategy.strategy_name}启动失败，请先初始化")
            return

        if strategy.trading:
            self.write_log(f"{strategy_name}已经启动，请勿重复操作")
            return

        self.call_strategy_func(strategy, strategy.on_start)
        strategy.trading = True
        self.put_strategy_event(strategy)

    def stop_strategy(self, strategy_name: str):
        """
            停止一个cta策略
        """
        strategy = self.strategies[strategy_name]
        if not strategy.trading:
            return

        # Call on_stop function of the strategy
        self.call_strategy_func(strategy, strategy.on_stop)

        # Change trading status of strategy to False
        strategy.trading = False

        # Cancel all orders of the strategy
        self.cancel_all(strategy)

        # Sync strategy variables to data file
        self.sync_strategy_data(strategy)
        # print("停止一个cta策略+++++++++++++++++++++++++")
        # Update GUI
        self.put_strategy_event(strategy)

    def edit_strategy(self, strategy_name: str, setting: dict):
        """
            修改一个策略里面的参数
        """
        strategy = self.strategies[strategy_name]
        strategy.update_setting(setting)

        self.update_strategy_setting(strategy_name, setting)
        # print("修改一个策略里面的参数+++++++++++++++++++++++++")
        self.put_strategy_event(strategy)

    def remove_strategy(self, strategy_name: str):
        """
            移除一个策略
        """
        strategy = self.strategies[strategy_name]
        if strategy.trading:
            self.write_log(f"策略{strategy.strategy_name}移除失败，请先停止")
            return

        # Remove setting
        self.remove_strategy_setting(strategy_name)

        # Remove from symbol strategy map
        strategies = self.symbol_strategy_map[strategy.vt_symbol]
        strategies.remove(strategy)

        # Remove from active orderid map
        if strategy_name in self.strategy_orderid_map:
            vt_orderids = self.strategy_orderid_map.pop(strategy_name)

            # Remove vt_orderid strategy map
            for vt_orderid in vt_orderids:
                if vt_orderid in self.orderid_strategy_map:
                    self.orderid_strategy_map.pop(vt_orderid)

        # Remove from strategies
        self.strategies.pop(strategy_name)

        return True

    #从源码加载策略类
    def load_strategy_class(self):
        path1 = Path(__file__).parent.joinpath("strategies")

        self.load_strategy_class_from_folder(
            path1, "vnpy.app.cta_strategy.strategies")

        path2 = Path.cwd().joinpath("strategies")


        self.load_strategy_class_from_folder(path2, "strategies")

    #从某个文件夹加载策略类
    def load_strategy_class_from_folder(self, path: Path, module_name: str = ""):
        for dirpath, dirnames, filenames in os.walk(str(path)):
            for filename in filenames:
                if filename.endswith(".py"):
                    strategy_module_name = ".".join(
                        [module_name, filename.replace(".py", "")])
                    self.load_strategy_class_from_module(strategy_module_name)

    #获取本地所有cta策略文件，并且存入self.classes
    def load_strategy_class_from_module(self, module_name: str):

        try:
            module = importlib.import_module(module_name)

            for name in dir(module):
                value = getattr(module, name)
                if (isinstance(value, type) and issubclass(value, CtaTemplate) and value is not CtaTemplate):
                    self.classes[value.__name__] = value
            #print("***********************************")
            #print(self.classes)
        except:  # noqa
            msg = f"策略文件{module_name}加载失败，触发异常：\n{traceback.format_exc()}"
            self.write_log(msg)

    #从cta_strategy_data.json文件加载策略数据
    def load_strategy_data(self):
        self.strategy_data = load_json(self.data_filename)

    #将策略数据同步到cta_strategy_data.json文件中,在停止cta策略的时候将数据保存到文件中
    def sync_strategy_data(self, strategy: CtaTemplate):
        data = strategy.get_variables()
        data.pop("inited")      # 状态（inited，trading）不应同步。
        data.pop("trading")

        self.strategy_data[strategy.strategy_name] = data
        save_json(self.data_filename, self.strategy_data)

    #获取所有cta策略的名字
    def get_all_strategy_class_names(self):
        #print("获取所有cta策略的名字----------------------++++++++++")
        #print(self.classes.keys())

        return list(self.classes.keys())
    #获取cta策略的参数
    def get_strategy_class_parameters(self, class_name: str):
        strategy_class = self.classes[class_name]

        parameters = {}
        for name in strategy_class.parameters:
            parameters[name] = getattr(strategy_class, name)

        return parameters

    def get_strategy_parameters(self, strategy_name):
        """
            Get parameters of a strategy.
        """
        strategy = self.strategies[strategy_name]
        return strategy.get_parameters()

    def init_all_strategies(self):
        """
            CTA策略全部初始化
        """
        for strategy_name in self.strategies.keys():
            self.init_strategy(strategy_name)

    def start_all_strategies(self):
        """
            启动CTA策略全部启动
        """
        for strategy_name in self.strategies.keys():
            self.start_strategy(strategy_name)

    def stop_all_strategies(self):
        """
        """
        for strategy_name in self.strategies.keys():
            self.stop_strategy(strategy_name)

    def load_strategy_setting(self):
        """
            从本地策略json文件，加载相应名字的策略
        """
        self.strategy_setting = load_json(self.setting_filename)
        #print("从本地json文件,加载相应名字的策略==================================")
        #print(self.strategy_setting)

        #获取所有策略的名字
        #self.get_all_strategy_class_names()
        #print(self.classes)
        #获取策略相应的参数
        #print(self.get_strategy_class_parameters("AtrRsiStrategy"))
        #strategy_class = self.classes["AtrRsiStrategy"]
        #print("获取策略相关setting***************************************")
        #print(strategy_class.parameters)


        # if not self.strategy_setting:
        #     print("本地没有策略的时候,初始化策略······································")
        #     # 添加策略
        #     self.add_strategy("AtrRsiStrategy", "AtrRsiStrategy", "SR911",self.get_strategy_class_parameters("AtrRsiStrategy"))
        # else:
        for strategy_name, strategy_config in self.strategy_setting.items():
            self.add_strategy(
                strategy_config["class_name"],
                strategy_name,
                strategy_config["vt_symbol"],
                strategy_config["setting"]
            )
    def update_strategy_setting(self, strategy_name: str, setting: dict):
        """
            更新配置文件
        """
        strategy = self.strategies[strategy_name]

        self.strategy_setting[strategy_name] = {
            "class_name": strategy.__class__.__name__,
            "vt_symbol": strategy.vt_symbol,
            "setting": setting,
        }
        save_json(self.setting_filename, self.strategy_setting)

    def remove_strategy_setting(self, strategy_name: str):
        """
                删除配置文件
        """
        if strategy_name not in self.strategy_setting:
            return

        self.strategy_setting.pop(strategy_name)
        save_json(self.setting_filename, self.strategy_setting)

    def put_stop_order_event(self, stop_order: StopOrder):
        """
        Put an event to update stop order status.
        """
        event = Event(EVENT_CTA_STOPORDER, stop_order)
        self.event_engine.put(event)

    def put_strategy_event(self, strategy: CtaTemplate):
        """
        Put an event to update strategy status.
            推送一个cta事件
        """
        #print("推送cta事件的时候获取，cta参数*************")
        data = strategy.get_data()
        #print(strategy.get_data())
        #print(strategy.get_parameters())

        event = Event(EVENT_CTA_STRATEGY, data)
        self.event_engine.put(event)

    def write_log(self, msg: str, strategy: CtaTemplate = None):
        """
        Create cta engine log event.
        """
        if strategy:
            msg = f"{strategy.strategy_name}: {msg}"

        log = LogData(msg=msg, gateway_name="CtaStrategy")
        event = Event(type=EVENT_CTA_LOG, data=log)
        self.event_engine.put(event)

    def send_email(self, msg: str, strategy: CtaTemplate = None):
        """
        Send email to default receiver.
        """
        if strategy:
            subject = f"{strategy.strategy_name}"
        else:
            subject = "CTA策略引擎"

        self.main_engine.send_email(subject, msg)
