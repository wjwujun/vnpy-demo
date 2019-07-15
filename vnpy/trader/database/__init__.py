import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnpy.trader.database.database import BaseDatabaseManager


"""
database这个module的时候，
    1、自动运行init.py文件，
    2、读取.vntrader/vt_setting.json中的数据库配置信息
    3、然后调用.initialize中的init方法。
"""

if "VNPY_TESTING" not in os.environ:
    from vnpy.trader.setting import get_settings
    from .initialize import init

    settings = get_settings("database.")
    database_manager: "BaseDatabaseManager" = init(settings=settings)
