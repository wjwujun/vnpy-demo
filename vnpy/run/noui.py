import multiprocessing
from time import sleep
from datetime import datetime, time
from logging import INFO

from vnpy.app.cta_backtester import CtaBacktesterApp
from vnpy.app.data_recorder import DataRecorderApp
from vnpy.event import EventEngine
from vnpy.trader.setting import SETTINGS
from vnpy.trader.engine import MainEngine

from vnpy.gateway.ctp import CtpGateway
from vnpy.app.cta_strategy import CtaStrategyApp
from vnpy.app.cta_strategy.base import EVENT_CTA_LOG


SETTINGS["log.active"] = True
SETTINGS["log.level"] = INFO
SETTINGS["log.console"] = True


ctp_setting = {
    "用户名": "107462",
    "密码": "110120",
    "经纪商代码": "9999",
    #"交易服务器": "tcp://180.168.146.187:10101",
    "交易服务器": "tcp://180.168.146.187:10130",        #非交易时段
    #"行情服务器": "tcp://180.168.146.187:10111",
    "行情服务器": "tcp://180.168.146.187:10131",        #非交易时段
    "产品名称": "simnow_client_test",
    "授权编码": "0000000000000000",
    "产品信息": ""
}


def run_child():
    """
    Running in the child process.
        home update test
    """
    SETTINGS["log.file"] = True

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(CtpGateway)
    cta_engine = main_engine.add_app(CtaStrategyApp)
    main_engine.write_log("主引擎创建成功")

    #"创建数据记录引擎"
    #data_engine=main_engine.add_app(DataRecorderApp)

    #创建回测引擎11
    #ctaback_engine=main_engine.add_app(CtaBacktesterApp)
    #ctaback_engine.init_engine

    log_engine = main_engine.get_engine("log")
    event_engine.register(EVENT_CTA_LOG, log_engine.process_log_event)
    main_engine.write_log("注册日志事件监听")

    main_engine.connect(ctp_setting, "CTP")
    main_engine.write_log("连接CTP接口")

    sleep(10)       #必须得等所有合约，保存完了以后才开始策略的初始化，否则，策略初始化比ctp合约保存更快执行，最后导致取出来的合约信息是空，无法订阅行情

    cta_engine.init_engine()
    main_engine.write_log("CTA策略初始化完成")

    cta_engine.init_all_strategies()
    sleep(60)   # 留出足够的时间来完成策略初始化
    main_engine.write_log("CTA策略全部初始化")

    cta_engine.start_all_strategies()
    main_engine.write_log("CTA策略全部启动")

    while True:
        sleep(1)


def run_parent():
    """
    Running in the parent process.
    """
    print("启动CTA策略守护父进程")

    # Chinese futures market trading period (day/night)
    DAY_START = time(8, 45)
    DAY_END = time(15, 30)

    NIGHT_START = time(20, 45)
    NIGHT_END = time(2, 45)

    child_process = None

    while True:
        current_time = datetime.now().time()
        trading = True

        # 判断当前处于的时间段
        """
        if (
            (current_time >= DAY_START and current_time <= DAY_END)
            or (current_time >= NIGHT_START)
            or (current_time <= NIGHT_END)
        ):
            trading = True

        if (datetime.today().weekday() == 5  and current_time > NIGHT_END) or datetime.today().weekday() == 6:
            trading = False
        """

        # 记录时间则需要启动子进程
        if trading and child_process is None:
            print("启动子进程")
            child_process = multiprocessing.Process(target=run_child)
            child_process.start()
            print("子进程启动成功")

        # 非记录时间则退出子进程
        if not trading and child_process is not None:
            print("关闭子进程")
            child_process.terminate()
            child_process.join()
            child_process = None
            print("子进程关闭成功")

        sleep(5)

if __name__ == "__main__":
    run_parent()