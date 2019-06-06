from vnpy.app.data_recorder import DataRecorderApp
from vnpy.event import EventEngine
from time import sleep
from vnpy.trader.engine import MainEngine
from vnpy.gateway.ctp import CtpGateway
from vnpy.trader.utility import load_json,save_json
from vnpy.app.cta_strategy import CtaStrategyApp
from vnpy.app.cta_strategy.base import EVENT_CTA_LOG
from vnpy.trader.setting import get_settings

def main():
    vt_setting=get_settings()
    save_json("vt_setting.json",vt_setting)
    settings=load_json("connect_ctp.json")

    event_engine = EventEngine()

    ##主引擎，负责对API的调度
    main_engine = MainEngine(event_engine)
    main_engine.write_log("--------------------------------主引擎创建成功")

    main_engine.event_engine.register(EVENT_CTA_LOG,main_engine.engines["log"].process_log_event)
    main_engine.add_gateway(CtpGateway)
    main_engine.write_log("网关创建成功--------------------------------")
    main_engine.write_log("连接CTP接口--------------------------------")
    main_engine.connect(settings,"CTP")

    main_engine.add_app(DataRecorderApp)
    main_engine.write_log("添加行情记录App-----")

    sleep(10)
    cta=main_engine.add_app(CtaStrategyApp)
    main_engine.write_log("-------------创建CTA策略引擎成功")

    cta.init_engine()
    main_engine.write_log("-------------初始化CTA策略引擎成功")

    cta.init_all_strategies()
    main_engine.write_log("-------------初始化CTA策略成功")

    sleep(10)
    cta.start_all_strategies()

    while True:
        sleep(1)
if __name__ == "__main__":
    main()