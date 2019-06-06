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
        self._handlers = defaultdict(list)
        self._general_handlers = []

    def _run(self):
        """
        Get event from queue and then process it.
        从队列中获取事件然后处理它。
        """
        while self._active:
            try:
                event = self._queue.get(block=True, timeout=1)
                self._process(event)
            except Empty:
                pass

    def _process(self, event: Event):
        """
        First ditribute event to those handlers registered listening
        to this type.
         第一次ditribute事件给那些处理者注册听
         这种类型。

        Then distrubute event to those general handlers which listens
        to all types.
        然后将事件分配给那些倾听的普通处理程序
         所有类型。
        """
        if event.type in self._handlers:
            [handler(event) for handler in self._handlers[event.type]]

        if self._general_handlers:
            [handler(event) for handler in self._general_handlers]

    def _run_timer(self):
        """
        Sleep by interval second(s) and then generate a timer event.
        按秒间隔睡眠，然后生成计时器事件。
        """
        while self._active:
            sleep(self._interval)
            event = Event(EVENT_TIMER)
            self.put(event)

    def start(self):
        """
        Start event engine to process events and generate timer events.
        启动事件引擎以处理事件并生成计时器事件。
        """
        self._active = True
        self._thread.start()
        self._timer.start()

    def stop(self):
        """
        Stop event engine.
        停止事件引擎。
        """
        self._active = False
        self._timer.join()
        self._thread.join()

    def put(self, event: Event):
        """
        Put an event object into event queue.
        将事件对象放入事件队列。
        """
        self._queue.put(event)

    def register(self, type: str, handler: HandlerType):
        """
        Register a new handler function for a specific event type. Every
        function can only be registered once for each event type.
        为特定事件类型注册新的处理函数。每个函数只能为每种事件类型注册一次。
        """
        handler_list = self._handlers[type]
        if handler not in handler_list:
            handler_list.append(handler)

    def unregister(self, type: str, handler: HandlerType):
        """
        Unregister an existing handler function from event engine.
        从事件引擎取消注册现有的处理函数。
        """
        handler_list = self._handlers[type]

        if handler in handler_list:
            handler_list.remove(handler)

        if not handler_list:
            self._handlers.pop(type)

    def register_general(self, handler: HandlerType):
        """
        Register a new handler function for all event types. Every 
        function can only be registered once for each event type.
        为所有事件类型注册新的处理函数。一切
         函数只能为每种事件类型注册一次。
        """
        if handler not in self._general_handlers:
            self._general_handlers.append(handler)

    def unregister_general(self, handler: HandlerType):
        """
        Unregister an existing general handler function.
        取消注册现有的通用处理函数。
        """
        if handler in self._general_handlers:
            self._general_handlers.remove(handler)
