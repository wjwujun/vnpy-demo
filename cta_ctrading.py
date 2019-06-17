import multiprocessing
from time import sleep
from datetime import datetime, time
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine, LogEngine
from vnpy.gateway.ctp import CtpGateway
from vnpy.app.cta_strategy import CtaStrategyApp
from vnpy.app.risk_manager import RiskManagerApp
#----------------------------------------------------------------------
def run_child_process():
    """子进程运行函数"""
    print('-'*73)
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    # 创建日志引擎
    log_engine = LogEngine(main_engine,event_engine)

    log_engine.info('启动行情记录运行子进程')
    log_engine.info('事件引擎创建成功')
    main_engine.add_gateway(CtpGateway)
    log_engine.info('主引擎创建成功')
    main_engine.connect('CTP')
    log_engine.info('CTP接口连接成功')
    sleep(3)
    main_engine.add_app(RiskManagerApp)
    cta = main_engine.add_app(CtaStrategyApp)    
    cta.init_engine()       #初始化CTA引擎
    cta.init_all_strategies()
    log_engine.info('CTA策略初始化成功')
    sleep(3)
    cta.start_all_strategies()
    log_engine.info('CTA策略启动成功')
    #保存合约数据到硬盘
    main_engine.save_contracts() 
    while True:
        #每5分钟保存一次手续费数据,保证金率数据
        main_engine.save_commission_margin_ratio()  
        sleep(300)
#----------------------------------------------------------------------
def run_parent_process():
    """父进程运行函数,限制交易时间"""
    # 创建日志引擎
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    # 创建日志引擎
    log_engine = LogEngine(main_engine,event_engine)
    log_engine.info('启动行情记录守护父进程')
    day_start = time(8, 57)         # 日盘启动和停止时间
    day_end = time(15, 3)
    night_start = time(20, 57)      # 夜盘启动和停止时间
    night_end = time(2, 33)   
    process = None        # 子进程句柄
    while True:
        current_time = datetime.now().time()        
        recording = False
        # 判断当前处于的时间段
        if ((current_time >= day_start and current_time <= day_end) or current_time >= night_start or current_time <= night_end):
            recording = True
        if (datetime.today().weekday() == 5  and current_time > night_end) or datetime.today().weekday() == 6 or (datetime.today().weekday() == 0  and current_time < day_start):
            recording = False
        # 记录时间则需要启动子进程
        if recording and process is None:
            log_engine.info('启动子进程')
            process = multiprocessing.Process(target=run_child_process)
            process.start()
            log_engine.info('子进程启动成功')
        # 非记录时间则退出子进程
        if not recording and process is not None:
            log_engine.info('关闭子进程')
            process.terminate()
            process.join()
            process = None
            log_engine.info('子进程关闭成功')
        sleep(3)
if __name__ == '__main__':
    #run_child_process()  #全天记录行情数据
    run_parent_process()  #过滤非交易时间记录行情数据



