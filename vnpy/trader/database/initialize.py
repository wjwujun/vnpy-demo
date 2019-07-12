""""""
from .database import BaseDatabaseManager, Driver


##根据根据不同的类型driver类型,调用init_sql或者init_nosql
def init(settings: dict) -> BaseDatabaseManager:
    driver = Driver(settings["driver"])
    if driver is Driver.MONGODB:
        return init_nosql(driver=driver, settings=settings)
    else:
        return init_sql(driver=driver, settings=settings)


def init_sql(driver: Driver, settings: dict):
    from .database_sql import init
    keys = {'database', "host", "port", "user", "password"}
    settings = {k: v for k, v in settings.items() if k in keys}

    ##调用database_sql.py中调用真正的init函数
    _database_manager = init(driver, settings)
    return _database_manager


def init_nosql(driver: Driver, settings: dict):
    from .database_mongo import init
    _database_manager = init(driver, settings=settings)
    return _database_manager
