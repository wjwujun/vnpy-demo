"""
Event-driven framework of vn.py framework.
"""

from collections import defaultdict
from queue import Empty, Queue
from threading import Thread
from time import sleep
from typing import Any, Callable

EVENT_TIMER = "eTimer"


class Event:
    """
    Event object consists of a type string which is used 
    by event engine for distributing event, and a data 
    object which contains the real data. 
    """

    def __init__(self, type: str, data: Any = None):
        """"""
        self.type = type
        self.data = data


# Defines handler function to be used in event engine.
HandlerType = Callable[[Event], None]


class EventEngine:
    """
    事件引擎根据其类型分发事件对象
         对那些注册的处理者。

     它还会每隔一秒钟生成一次计时器事件，
     可用于计时目的。
    """

    def __init__(self, interval: int = 1):
        """
         如果是，则默认情况下每1秒生成一次定时器事件
             间隔未指定。
        """
        self._interval = interval
        self._queue = Queue()
        self._active = False
        self._thread = Thread(target=self._run)
        self._timer = Thread(target=self._run_timer)

        # 其中每个键对应的值是一个列表，列表中保存了对该事件进行监听的函数功能
        self._handlers = defaultdict(list)

        # __generalHandlers是一个列表，用来保存通用回调函数（所有事件均调用）
        self._general_handlers = []

    # 引擎运行
    def _run(self):
        while self._active:
            try:
                event = self._queue.get(block=True, timeout=1)
                self._process(event)
            except Empty:
                pass

    # 处理事件
    def _process(self, event: Event):
        # 检查是否存在对该事件进行监听的处理函数
        if event.type in self._handlers:        # 若存在，则按顺序将事件传递给处理函数执行
             for handler in self._handlers[event.type]:
                 handler(event)

        # 调用通用处理函数进行处理
        if self._general_handlers:
            for handler in self._general_handlers:
                handler(event)

    # 运行在计时器线程中的循环函数
    def _run_timer(self):
        while self._active:
            sleep(self._interval)            # 等待
            event = Event(EVENT_TIMER)        # 创建计时器事件
            self.put(event)             # 向队列中存入计时器事件

    # 引擎启动, timer：是否要启动计时器
    def start(self):
        self._active = True      # 将引擎设为启动
        self._thread.start()         # 启动事件处理线程
        self._timer.start()         # 启动计时器，计时器事件间隔默认设定为1秒

    # 停止引擎
    def stop(self):
        self._active = False
        self._timer.join()
        self._thread.join()          # 等待事件处理线程退出

    def put(self, event: Event):
        self._queue.put(event)

    # 注册事件处理函数监听
    def register(self, type: str, handler: HandlerType):
        # 尝试获取该事件类型对应的处理函数列表，若无defaultDict会自动创建新的list
        handler_list = self._handlers[type]

        # 若要注册的处理器不在该事件的处理器列表中，则注册该事件
        if handler not in handler_list:
            handler_list.append(handler)

    # 注销事件处理函数监听
    def unregister(self, type: str, handler: HandlerType):

        handler_list = self._handlers[type]     # 尝试获取该事件类型对应的处理函数列表，若无则忽略该次注销请求

        if handler in handler_list:     # 如果该函数存在于列表中，则移除
            handler_list.remove(handler)

        if not handler_list:
            self._handlers.pop(type)

    # 注册通用事件处理函数监听
    def register_general(self, handler: HandlerType):
        if handler not in self._general_handlers:
            self._general_handlers.append(handler)
    #注销通用事件处理函数监听
    def unregister_general(self, handler: HandlerType):

        if handler in self._general_handlers:
            self._general_handlers.remove(handler)
