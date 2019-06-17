""""""

from threading import Thread
from queue import Queue, Empty
from copy import copy

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.object import (
    SubscribeRequest,
    TickData,
    BarData,
    ContractData
)
from vnpy.trader.event import EVENT_TICK, EVENT_CONTRACT
from vnpy.trader.utility import load_json, save_json, BarGenerator
from vnpy.trader.database import database_manager


APP_NAME = "DataRecorder"

EVENT_RECORDER_LOG = "eRecorderLog"
EVENT_RECORDER_UPDATE = "eRecorderUpdate"

#行情记录引擎
class RecorderEngine(BaseEngine):
    """"""
    setting_filename = "data_recorder_setting.json"

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        """"""
        super().__init__(main_engine, event_engine, APP_NAME)

        self.queue = Queue()
        self.thread = Thread(target=self.run)
        self.active = False

        self.tick_recordings = {}
        self.bar_recordings = {}
        self.bar_generators = {}

        self.load_setting()
        self.register_event()
        self.start()
        self.put_event()

    #将订阅信息保存到json文件
    def load_setting(self):
        """
         该json文件用于存放行情记录的任务，当每次启动行情模块后，会调用load_setting()函数来得到tick_recordings和bar_recordings字典，进而开始记录的任务。
        """
        setting = load_json(self.setting_filename)
        self.tick_recordings = setting.get("tick", {})
        self.bar_recordings = setting.get("bar", {})

    def save_setting(self):
        """
            主要把tick_recordings或者bar_recordings通过save_json()函数保存到C:/Users/Administrator/.vntrader文件夹data_recorder_setting.json上。
        """
        setting = {
            "tick": self.tick_recordings,
            "bar": self.bar_recordings
        }
        save_json(self.setting_filename, setting)

    #执行记录行情任务
    def run(self):
        """
            在while循环中，从queue队列读取任务，调用save_tick_data()或者save_bar_data()函数来记录数据，并且载入到数据库中。
        """
        print("1111111111111111111")
        while self.active:
            try:
                task = self.queue.get(timeout=1)
                task_type, data = task

                if task_type == "tick":
                    database_manager.save_tick_data([data])
                elif task_type == "bar":
                    database_manager.save_bar_data([data])

            except Empty:
                continue
    #停止记录
    def close(self):
        """
            停止记录操作：只需手动关闭行情记录模块窗口就停止记录行情。
            记录行情状态改为False, 停止while循环；
            调用join()函数关掉线程。
        """
        self.active = False

        if self.thread.is_alive():
            self.thread.join()


    #此时行情记录模块的启动状态为True，会启动while循环，可以添加任务实现实时行情记录。
    def start(self):
        """"""
        self.active = True
        self.thread.start()

    def add_bar_recording(self, vt_symbol: str):
        """"""
        if vt_symbol in self.bar_recordings:
            self.write_log(f"已在K线记录列表中：{vt_symbol}")
            return

        contract = self.main_engine.get_contract(vt_symbol)
        if not contract:
            self.write_log(f"找不到合约：{vt_symbol}")
            return

        self.bar_recordings[vt_symbol] = {
            "symbol": contract.symbol,
            "exchange": contract.exchange.value,
            "gateway_name": contract.gateway_name
        }

        self.subscribe(contract)
        self.save_setting()
        self.put_event()

        self.write_log(f"添加K线记录成功：{vt_symbol}")

    #行情记录
    def add_tick_recording(self, vt_symbol: str):
        """
            行情收录的具体原理：若无合约记录的历史，用户需要先添加行情记录任务，如连接CTP接口后记录rb1905.SHFE的tick数据，然后调用add_tick_recording()函数执行下面工作：
                1、先创建tick_recordings字典；
                2、调用接口的suscribe()函数订阅行情； 3 )保存该tick_recordings字典到json文件上；
                3、推送行情记录事件。
        """
        if vt_symbol in self.tick_recordings:
            self.write_log(f"已在Tick记录列表中：{vt_symbol}")
            return

        contract = self.main_engine.get_contract(vt_symbol)
        if not contract:
            self.write_log(f"找不到合约：{vt_symbol}")
            return

        self.tick_recordings[vt_symbol] = {
            "symbol": contract.symbol,
            "exchange": contract.exchange.value,
            "gateway_name": contract.gateway_name
        }

        self.subscribe(contract)
        self.save_setting()
        self.put_event()

        self.write_log(f"添加Tick记录成功：{vt_symbol}")

    def remove_bar_recording(self, vt_symbol: str):
        """"""
        if vt_symbol not in self.bar_recordings:
            self.write_log(f"不在K线记录列表中：{vt_symbol}")
            return

        self.bar_recordings.pop(vt_symbol)
        self.save_setting()
        self.put_event()

        self.write_log(f"移除K线记录成功：{vt_symbol}")

    #移除记录
    def remove_tick_recording(self, vt_symbol: str):
        """
        移除记录操作：输入需要移除合约品种的本地代码，如rb1905.SHFE。该本地代码必须在“Tick记录列表” 或者“K线记录列表”中。若要移除Tick记录，只需在”Tick记录“那一栏上点击”移除“按钮即可。

        下面展示代码运作原理：
            1、从tick_recordings字典移除vt_symbol
            2、调用save_setting()函数保存json配置文件
            3、推送最新的tick_recordings字典来继续记录行情，原来移除合约品种不再记录。

        """
        if vt_symbol not in self.tick_recordings:
            self.write_log(f"不在Tick记录列表中：{vt_symbol}")
            return

        self.tick_recordings.pop(vt_symbol)
        self.save_setting()
        self.put_event()

        self.write_log(f"移除Tick记录成功：{vt_symbol}")

    #注册行情记录事件
    def register_event(self):
        """
        register_event()函数分别注册2种事件：EVENT_CONTRACT、EVENT_TICK
            1、EVENT_CONTRACT事件，调用的是process_contract_event()函数: 从tick_recordings和bar_recordings字典获取需要订阅的合约品种；然后使用subscribe()函数进行订阅行情。
            2、EVENT_TICK事件，调用的是process_tick_event()函数：从tick_recordings和bar_recordings字典获取需要订阅的合约品种；然后使用record_tick()和record_bar()函数，把行情记录任务推送到queue队列中等待执行。
        """
        self.event_engine.register(EVENT_TICK, self.process_tick_event)
        self.event_engine.register(EVENT_CONTRACT, self.process_contract_event)


    def process_tick_event(self, event: Event):
        """"""
        tick = event.data

        if tick.vt_symbol in self.tick_recordings:
            self.record_tick(tick)

        if tick.vt_symbol in self.bar_recordings:
            bg = self.get_bar_generator(tick.vt_symbol)
            bg.update_tick(tick)

    def process_contract_event(self, event: Event):
        """"""
        contract = event.data
        vt_symbol = contract.vt_symbol

        if (vt_symbol in self.tick_recordings or vt_symbol in self.bar_recordings):
            self.subscribe(contract)

    def write_log(self, msg: str):
        """"""
        event = Event(
            EVENT_RECORDER_LOG,
            msg
        )
        self.event_engine.put(event)

    #推送行情记录事件
    def put_event(self):
        """
            1、创建行情记录列表tick_symbols和bar_symbols，并且缓存在data字典里；
            2、创建evnte对象，其类型是EVENT_RECORDER_UPDATE, 内容是data字典；
            3、调用event_engine的put()函数推送event事件。
        """
        tick_symbols = list(self.tick_recordings.keys())
        tick_symbols.sort()

        bar_symbols = list(self.bar_recordings.keys())
        bar_symbols.sort()

        data = {
            "tick": tick_symbols,
            "bar": bar_symbols
        }

        event = Event(
            EVENT_RECORDER_UPDATE,
            data
        )
        self.event_engine.put(event)

    def record_tick(self, tick: TickData):
        """"""
        task = ("tick", copy(tick))
        self.queue.put(task)

    def record_bar(self, bar: BarData):
        """"""
        task = ("bar", copy(bar))
        self.queue.put(task)

    def get_bar_generator(self, vt_symbol: str):
        """"""
        bg = self.bar_generators.get(vt_symbol, None)

        if not bg:
            bg = BarGenerator(self.record_bar)
            self.bar_generators[vt_symbol] = bg

        return bg

    #订阅行情
    def subscribe(self, contract: ContractData):
        """
            调用main_engine的suscribe()函数来订阅行情，需要填入的信息为symbol、exchange、gateway_name
        """
        req = SubscribeRequest(
            symbol=contract.symbol,
            exchange=contract.exchange
        )
        self.main_engine.subscribe(req, contract.gateway_name)
