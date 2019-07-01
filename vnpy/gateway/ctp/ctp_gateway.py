"""
"""

from datetime import datetime

from vnpy.api.ctp import (
    MdApi,
    TdApi,
    THOST_FTDC_OAS_Submitted,
    THOST_FTDC_OAS_Accepted,
    THOST_FTDC_OAS_Rejected,
    THOST_FTDC_OST_NoTradeQueueing,
    THOST_FTDC_OST_PartTradedQueueing,
    THOST_FTDC_OST_AllTraded,
    THOST_FTDC_OST_Canceled,
    THOST_FTDC_D_Buy, 
    THOST_FTDC_D_Sell,
    THOST_FTDC_PD_Long,
    THOST_FTDC_PD_Short,
    THOST_FTDC_OPT_LimitPrice,
    THOST_FTDC_OPT_AnyPrice,
    THOST_FTDC_OF_Open,
    THOST_FTDC_OFEN_Close,
    THOST_FTDC_OFEN_CloseYesterday,
    THOST_FTDC_OFEN_CloseToday,
    THOST_FTDC_PC_Futures,
    THOST_FTDC_PC_Options,
    THOST_FTDC_PC_Combination,
    THOST_FTDC_CP_CallOptions,
    THOST_FTDC_CP_PutOptions,
    THOST_FTDC_HF_Speculation,
    THOST_FTDC_CC_Immediately,
    THOST_FTDC_FCC_NotForceClose,
    THOST_FTDC_TC_GFD,
    THOST_FTDC_VC_AV,
    THOST_FTDC_TC_IOC,
    THOST_FTDC_VC_CV,
    THOST_FTDC_AF_Delete
)
from vnpy.trader.constant import (
    Direction,
    Offset,
    Exchange,
    OrderType,
    Product,
    Status,
    OptionType
)
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    TickData,
    OrderData,
    TradeData,
    PositionData,
    AccountData,
    ContractData,
    OrderRequest,
    CancelRequest,
    SubscribeRequest,
)
from vnpy.trader.utility import get_folder_path
from vnpy.trader.event import EVENT_TIMER


STATUS_CTP2VT = {
    THOST_FTDC_OAS_Submitted: Status.SUBMITTING,
    THOST_FTDC_OAS_Accepted: Status.SUBMITTING,
    THOST_FTDC_OAS_Rejected: Status.REJECTED,
    THOST_FTDC_OST_NoTradeQueueing: Status.NOTTRADED,
    THOST_FTDC_OST_PartTradedQueueing: Status.PARTTRADED,
    THOST_FTDC_OST_AllTraded: Status.ALLTRADED,
    THOST_FTDC_OST_Canceled: Status.CANCELLED
}

DIRECTION_VT2CTP = {
    Direction.LONG: THOST_FTDC_D_Buy, 
    Direction.SHORT: THOST_FTDC_D_Sell
}
DIRECTION_CTP2VT = {v: k for k, v in DIRECTION_VT2CTP.items()}
DIRECTION_CTP2VT[THOST_FTDC_PD_Long] = Direction.LONG
DIRECTION_CTP2VT[THOST_FTDC_PD_Short] = Direction.SHORT

ORDERTYPE_VT2CTP = {
    OrderType.LIMIT: THOST_FTDC_OPT_LimitPrice, 
    OrderType.MARKET: THOST_FTDC_OPT_AnyPrice
}
ORDERTYPE_CTP2VT = {v: k for k, v in ORDERTYPE_VT2CTP.items()}

OFFSET_VT2CTP = {
    Offset.OPEN: THOST_FTDC_OF_Open, 
    Offset.CLOSE: THOST_FTDC_OFEN_Close,
    Offset.CLOSETODAY: THOST_FTDC_OFEN_CloseToday,
    Offset.CLOSEYESTERDAY: THOST_FTDC_OFEN_CloseYesterday,
}
OFFSET_CTP2VT = {v: k for k, v in OFFSET_VT2CTP.items()}

EXCHANGE_CTP2VT = {
    "CFFEX": Exchange.CFFEX,
    "SHFE": Exchange.SHFE,
    "CZCE": Exchange.CZCE,
    "DCE": Exchange.DCE,
    "INE": Exchange.INE
}

PRODUCT_CTP2VT = {
    THOST_FTDC_PC_Futures: Product.FUTURES,
    THOST_FTDC_PC_Options: Product.OPTION,
    THOST_FTDC_PC_Combination: Product.SPREAD
}

OPTIONTYPE_CTP2VT = {
    THOST_FTDC_CP_CallOptions: OptionType.CALL,
    THOST_FTDC_CP_PutOptions: OptionType.PUT
}


symbol_exchange_map = {}
symbol_name_map = {}
symbol_size_map = {}


class CtpGateway(BaseGateway):
    """
    VN Trader Gateway for CTP .
     default_setting = {
        "用户名": "107462",
        "密码": "110120",
        "经纪商代码": "9999",
        "交易服务器": "tcp://180.168.146.187:10001",
        "行情服务器": "tcp://180.168.146.187:10011",
        "产品名称": "simnow_client_test",
        "授权编码": "0000000000000000"
    }
    """



    def __init__(self, event_engine):
        """Constructor"""
        super(CtpGateway, self).__init__(event_engine, "CTP")

        self.td_api = CtpTdApi(self)
        self.md_api = CtpMdApi(self)
        self.activeContracts = []
        #期货合约下载
        self.activeContracts = []

    def connect(self, setting: dict):
        """"""
        userid = setting["用户名"]
        password = setting["密码"]
        brokerid = setting["经纪商代码"]
        td_address = setting["交易服务器"]
        md_address = setting["行情服务器"]
        product_info = setting["产品名称"]
        auth_code = setting["授权编码"]
        
        if not td_address.startswith("tcp://"):
            td_address = "tcp://" + td_address
        if not md_address.startswith("tcp://"):
            md_address = "tcp://" + md_address
        
        self.td_api.connect(td_address, userid, password, brokerid, auth_code, product_info)
        self.md_api.connect(md_address, userid, password, brokerid)
        
        self.init_query()

    def subscribe(self, req: SubscribeRequest):
        """"""
        self.md_api.subscribe(req)

    def send_order(self, req: OrderRequest):
        """"""
        return self.td_api.send_order(req)

    def cancel_order(self, req: CancelRequest):
        """"""
        self.td_api.cancel_order(req)

    def query_account(self):
        """"""
        self.td_api.query_account()

    def query_position(self):
        """"""
        self.td_api.query_position()

    def close(self):
        """"""
        self.td_api.close()
        self.md_api.close()

    def write_error(self, msg: str, error: dict):
        """"""
        error_id = error["ErrorID"]
        error_msg = error["ErrorMsg"]
        msg = f"{msg}，代码：{error_id}，信息：{error_msg}"
        self.write_log(msg)        
    
    def process_timer_event(self, event):
        """"""
        self.count += 1
        if self.count < 2:
            return
        self.count = 0
        
        func = self.query_functions.pop(0)
        func()
        self.query_functions.append(func)
        
    def init_query(self):
        """
            查询账户信息
        """
        self.count = 0
        self.query_functions = [self.query_account, self.query_position]
        self.event_engine.register(EVENT_TIMER, self.process_timer_event)


class CtpMdApi(MdApi):
    """"""

    def __init__(self, gateway):
        """Constructor"""
        super(CtpMdApi, self).__init__()
        
        self.gateway = gateway
        self.gateway_name = gateway.gateway_name
        
        self.reqid = 0       # 操作请求编号
        
        self.connect_status = False    # 连接状态
        self.login_status = False   # 登录状态
        self.subscribed = set()
        
        self.userid = ""       # 账号
        self.password = ""     # 密码
        self.brokerid = 0      # 经纪商代码

    # 服务器连接成功的回调函数
    def onFrontConnected(self):
        """
        Callback when front server is connected.
        """
        self.connect_status = True
        self.gateway.write_log("行情服务器连接成功")
        self.login()

    # 服务器断开
    def onFrontDisconnected(self, reason: int):
        """
        Callback when front server is disconnected.
        """
        self.connect_status = False
        self.login_status = False
        self.gateway.write_log(f"行情连接断开，原因{reason}")


    # 登陆回报
    def onRspUserLogin(self, data: dict, error: dict, reqid: int, last: bool):
        """
        Callback when user is logged in.
        """
        if not error["ErrorID"]:
            self.login_status = True
            self.gateway.write_log("行情服务器登录成功")
            
            for symbol in self.subscribed:
                self.subscribeMarketData(symbol)
        else:
            self.gateway.write_error("行情登录失败", error)
    
    def onRspError(self, error: dict, reqid: int, last: bool):
        """
        Callback when error occured.
        """
        self.gateway.write_error("行情接口报错", error)

    # 订阅合约回报
    def onRspSubMarketData(self, data: dict, error: dict, reqid: int, last: bool):
        """"""
        if not error or not error["ErrorID"]:
            return
        
        self.gateway.write_error("行情订阅失败", error)

    # 行情推送
    def onRtnDepthMarketData(self, data: dict):
        """
        Callback of tick data update.
        """
        symbol = data["InstrumentID"]     #合约代码

        exchange = symbol_exchange_map.get(symbol, "")
        if not exchange:
            return
        
        timestamp = f"{data['ActionDay']} {data['UpdateTime']}.{int(data['UpdateMillisec']/100)}"

        # 创建对象
        tick = TickData(
            symbol=symbol,                  #合约代码
            exchange=exchange,              #交易所代码   #exchangeMapReverse.get(data['ExchangeID'], u'未知')
            datetime=datetime.strptime(timestamp, "%Y%m%d %H:%M:%S.%f"),     #交易日期
            name=symbol_name_map[symbol],
            volume=data["Volume"],                  #数量
            last_price=data["LastPrice"],           #最新价
            limit_up=data["UpperLimitPrice"],       #涨停板价
            limit_down=data["LowerLimitPrice"],     #跌停板价
            open_price=data["OpenPrice"],           #开仓价
            high_price=data["HighestPrice"],        #最高价
            low_price=data["LowestPrice"],          #最低价
            pre_close=data["PreClosePrice"],        #昨收盘价
            bid_price_1=data["BidPrice1"],          #申买价一
            ask_price_1=data["AskPrice1"],          #申卖价一
            bid_volume_1=data["BidVolume1"],        #申买量一
            ask_volume_1=data["AskVolume1"],        #申卖量一
            gateway_name=self.gateway_name
        )
        self.gateway.on_tick(tick)

    #连接服务器
    def connect(self, address: str, userid: str, password: str, brokerid: int):
        """
        Start connection to server.
        """
        self.userid = userid
        self.password = password
        self.brokerid = brokerid
        
        # If not connected, then start connection first.
        if not self.connect_status:
            path = get_folder_path(self.gateway_name.lower())
            self.createFtdcMdApi(str(path) + "\\Md")
            
            self.registerFront(address)
            self.init()
        # If already connected, then login immediately.
        elif not self.login_status:
            self.login()

    #登录
    def login(self):
        """
        Login onto server.
        """
        req = {
            "UserID": self.userid,
            "Password": self.password,
            "BrokerID": self.brokerid
        }
        
        self.reqid += 1
        self.reqUserLogin(req, self.reqid)

    # 订阅合约
    def subscribe(self, req: SubscribeRequest):
        """
        Subscribe to tick data update.
        """
        if self.login_status:
            self.subscribeMarketData(req.symbol)
        self.subscribed.add(req.symbol)
    
    def close(self):
        """
        Close the connection.
        """
        if self.connect_status:
            self.exit()

###########################################################

# 交易CTP_API实现
class CtpTdApi(TdApi):
    """"""

    def __init__(self, gateway):
        """Constructor"""
        super(CtpTdApi, self).__init__()
        
        self.gateway = gateway
        self.gateway_name = gateway.gateway_name
        
        self.reqid = 0      # 操作请求编号
        self.order_ref = 0
        
        self.connect_status = False    # 连接状态
        self.login_status = False      # 登录状态
        self.auth_staus = False
        self.login_failed = False
        
        self.userid = ""            # 账号
        self.password = ""          # 密码
        self.brokerid = 0           # 经纪商代码
        self.auth_code = ""         #授权编码
        self.product_info = ""      #产品名称
        
        self.frontid = 0
        self.sessionid = 0
        
        self.order_data = []   #订单数据
        self.trade_data = []   #交易数据
        self.positions = {}    #持仓数据
        self.sysid_orderid_map = {}

    # 服务器连接
    def onFrontConnected(self):
        """"""
        self.connect_status = True
        self.gateway.write_log("交易连接成功")
        
        if self.auth_code:
            self.authenticate()
        else:
            self.login()

    # 服务器断开
    def onFrontDisconnected(self, reason: int):
        """"""
        self.connect_status = False
        self.login_status = False
        self.gateway.write_log(f"交易连接断开，原因{reason}")

    #交易授权
    def onRspAuthenticate(self, data: dict, error: dict, reqid: int, last: bool):
        """"""
        if not error['ErrorID']:
            self.authStatus = True
            self.gateway.write_log("交易授权验证成功")
            self.login()
        else:
            self.gateway.write_error("交易授权验证失败", error)
    # 登陆回报
    def onRspUserLogin(self, data: dict, error: dict, reqid: int, last: bool):
        """"""
        if not error["ErrorID"]:
            self.frontid = data["FrontID"]
            self.sessionid = data["SessionID"]
            self.login_status = True
            self.gateway.write_log("交易登录成功")
            
            # Confirm settlement
            req = {
                "BrokerID": self.brokerid,
                "InvestorID": self.userid
            }
            self.reqid += 1
            self.reqSettlementInfoConfirm(req, self.reqid)
        else:
            self.login_failed = True
            
            self.gateway.write_error("交易登录失败", error)

    # 发单错误
    def onRspOrderInsert(self, data: dict, error: dict, reqid: int, last: bool):
        """"""
        order_ref = data["OrderRef"]
        orderid = f"{self.frontid}_{self.sessionid}_{order_ref}"
        
        symbol = data["InstrumentID"]
        exchange = symbol_exchange_map[symbol]
        
        order = OrderData(
            symbol=symbol,
            exchange=exchange,
            orderid=orderid,
            direction=DIRECTION_CTP2VT[data["Direction"]],
            offset=OFFSET_CTP2VT[data["CombOffsetFlag"]],
            price=data["LimitPrice"],
            volume=data["VolumeTotalOriginal"],
            status=Status.REJECTED,
            gateway_name=self.gateway_name
        )
        self.gateway.on_order(order)
        
        self.gateway.write_error("交易委托失败", error)

    # 撤单错误
    def onRspOrderAction(self, data: dict, error: dict, reqid: int, last: bool):
        """"""
        self.gateway.write_error("交易撤单失败", error)
    
    def onRspQueryMaxOrderVolume(self, data: dict, error: dict, reqid: int, last: bool):
        """"""
        pass

    # 确认结算信息回报
    def onRspSettlementInfoConfirm(self, data: dict, error: dict, reqid: int, last: bool):
        """
        Callback of settlment info confimation.
        """
        self.gateway.write_log("结算信息确认成功")
        
        self.reqid += 1
        self.reqQryInstrument({}, self.reqid)

    # 持仓查询回报
    def onRspQryInvestorPosition(self, data: dict, error: dict, reqid: int, last: bool):
        """"""
        if not data:
            return
        
        # Get buffered position object
        key = f"{data['InstrumentID'], data['PosiDirection']}"
        position = self.positions.get(key, None)
        if not position:
            position = PositionData(
                symbol=data["InstrumentID"],
                exchange=symbol_exchange_map[data["InstrumentID"]],
                direction=DIRECTION_CTP2VT[data["PosiDirection"]],
                gateway_name=self.gateway_name
            )
            self.positions[key] = position
        
        # For SHFE position data update
        if position.exchange == Exchange.SHFE:
            if data["YdPosition"] and not data["TodayPosition"]:
                position.yd_volume = data["Position"]
        # For other exchange position data update
        else:
            position.yd_volume = data["Position"] - data["TodayPosition"]
        
        # Get contract size (spread contract has no size value)
        size = symbol_size_map.get(position.symbol, 0)
        
        # Calculate previous position cost
        cost = position.price * position.volume * size
        
        # Update new position volume
        position.volume += data["Position"]
        position.pnl += data["PositionProfit"]
        
        # Calculate average position price
        if position.volume and size:
            cost += data["PositionCost"]
            position.price = cost / (position.volume * size)
        
        # Get frozen volume
        if position.direction == Direction.LONG:
            position.frozen += data["ShortFrozen"]
        else:
            position.frozen += data["LongFrozen"]
        
        if last:
            for position in self.positions.values():
                self.gateway.on_position(position)
                
            self.positions.clear()

    # 账户查询回报
    def onRspQryTradingAccount(self, data: dict, error: dict, reqid: int, last: bool):
        """"""
        account = AccountData(
            accountid=data["AccountID"],
            balance=data["Balance"],
            frozen=data["FrozenMargin"] + data["FrozenCash"] + data["FrozenCommission"],
            gateway_name=self.gateway_name
        )
        account.available = data["Available"]
        
        self.gateway.on_account(account)

    # 合约查询回报,由于该回报的推送速度极快，因此不适合全部存入队列中处理,选择先储存在一个本地字典中，全部收集完毕后再推送到队列中（由于耗时过长目前使用其他进程读取）
    def onRspQryInstrument(self, data: dict, error: dict, reqid: int, last: bool):
        """
        Callback of instrument query.
        """

        print("===================================")
        print(data["ProductClass"])
        product = PRODUCT_CTP2VT.get(data["ProductClass"], None)
        if product:            
            contract = ContractData(
                symbol=data["InstrumentID"],
                exchange=EXCHANGE_CTP2VT[data["ExchangeID"]],
                name=data["InstrumentName"],
                product=product,
                size=data["VolumeMultiple"],
                pricetick=data["PriceTick"],
                gateway_name=self.gateway_name
            )

            # 订阅行情信息，此处加过滤条件，筛选出自己想要的合约，进行订阅
            """
                req = SubscribeRequest(
                    symbol=data["InstrumentID"], exchange=EXCHANGE_CTP2VT[data["ExchangeID"]]
                )
                CtpGateway.subscribe(req)
            """




            # For option only
            if contract.product == Product.OPTION:
                contract.option_underlying = data["UnderlyingInstrID"],
                contract.option_type = OPTIONTYPE_CTP2VT.get(data["OptionsType"], None),
                contract.option_strike = data["StrikePrice"],
                contract.option_expiry = datetime.strptime(data["ExpireDate"], "%Y%m%d"),
            
            self.gateway.on_contract(contract)
            
            symbol_exchange_map[contract.symbol] = contract.exchange
            symbol_name_map[contract.symbol] = contract.name
            symbol_size_map[contract.symbol] = contract.size
        
        if last:
            self.gateway.write_log("合约信息查询成功")
            print("-----------------------------------合约信息")
            print(symbol_exchange_map)
            print("-----------------------------------名字")
            print(symbol_name_map)
            print("-----------------------------------大小")
            print(symbol_size_map)

            for data in self.order_data:
                self.onRtnOrder(data)
            self.order_data.clear()
            
            for data in self.trade_data:
                self.onRtnTrade(data)
            self.trade_data.clear()

    # 报单回报
    def onRtnOrder(self, data: dict):
        """
        Callback of order status update.
        """
        symbol = data["InstrumentID"]
        exchange = symbol_exchange_map.get(symbol, "")
        if not exchange:
            self.order_data.append(data)
            return
        
        frontid = data["FrontID"]
        sessionid = data["SessionID"]
        order_ref = data["OrderRef"]
        orderid = f"{frontid}_{sessionid}_{order_ref}"
        
        order = OrderData(
            symbol=symbol,
            exchange=exchange,
            orderid=orderid,
            type=ORDERTYPE_CTP2VT[data["OrderPriceType"]],
            direction=DIRECTION_CTP2VT[data["Direction"]],
            offset=OFFSET_CTP2VT[data["CombOffsetFlag"]],
            price=data["LimitPrice"],
            volume=data["VolumeTotalOriginal"],
            traded=data["VolumeTraded"],
            status=STATUS_CTP2VT[data["OrderStatus"]],
            time=data["InsertTime"],
            gateway_name=self.gateway_name
        )
        self.gateway.on_order(order)
        
        self.sysid_orderid_map[data["OrderSysID"]] = orderid

    # 成交回报
    def onRtnTrade(self, data: dict):
        """
        Callback of trade status update.
        """
        symbol = data["InstrumentID"]
        exchange = symbol_exchange_map.get(symbol, "")
        if not exchange:
            self.trade_data.append(data)
            return

        orderid = self.sysid_orderid_map[data["OrderSysID"]]
        
        trade = TradeData(
            symbol=symbol,
            exchange=exchange,
            orderid=orderid,
            tradeid=data["TradeID"],
            direction=DIRECTION_CTP2VT[data["Direction"]],
            offset=OFFSET_CTP2VT[data["OffsetFlag"]],
            price=data["Price"],
            volume=data["Volume"],
            time=data["TradeTime"],
            gateway_name=self.gateway_name
        )
        self.gateway.on_trade(trade)        

    #连接
    def connect(self, address: str, userid: str, password: str, brokerid: int, auth_code: str, product_info: str):
        """
        Start connection to server.
        """
        self.userid = userid
        self.password = password
        self.brokerid = brokerid
        self.auth_code = auth_code
        self.product_info = product_info
        
        if not self.connect_status:
            path = get_folder_path(self.gateway_name.lower())
            self.createFtdcTraderApi(str(path) + "\\Td")
            
            self.subscribePrivateTopic(0)
            self.subscribePublicTopic(0)
            
            self.registerFront(address)
            self.init()            
        else:
            self.authenticate()

    #身份验证
    def authenticate(self):
        """
        Authenticate with auth_code and product_info.
        使用auth_code和product_info进行身份验证。
        """
        req = {
            "UserID": self.userid,
            "BrokerID": self.brokerid,
            "AuthCode": self.auth_code,
            "UserProductInfo": self.product_info
        }
        
        self.reqid += 1
        self.reqAuthenticate(req, self.reqid)

    # 登录
    def login(self):
        """
        Login onto server.
        """
        if self.login_failed:
            return

        req = {
            "UserID": self.userid,
            "Password": self.password,
            "BrokerID": self.brokerid,
            "UserProductInfo": self.product_info
        }
        
        self.reqid += 1
        self.reqUserLogin(req, self.reqid)
        
    def send_order(self, req: OrderRequest):
        """
        Send new order.
        """
        self.order_ref += 1
        
        ctp_req = {
            "InstrumentID": req.symbol,
            "LimitPrice": req.price,
            "VolumeTotalOriginal": int(req.volume),
            "OrderPriceType": ORDERTYPE_VT2CTP.get(req.type, ""),
            "Direction": DIRECTION_VT2CTP.get(req.direction, ""),
            "CombOffsetFlag": OFFSET_VT2CTP.get(req.offset, ""),
            "OrderRef": str(self.order_ref),
            "InvestorID": self.userid,
            "UserID": self.userid,
            "BrokerID": self.brokerid,
            "CombHedgeFlag": THOST_FTDC_HF_Speculation,
            "ContingentCondition": THOST_FTDC_CC_Immediately,
            "ForceCloseReason": THOST_FTDC_FCC_NotForceClose,
            "IsAutoSuspend": 0,
            "TimeCondition": THOST_FTDC_TC_GFD,
            "VolumeCondition": THOST_FTDC_VC_AV,
            "MinVolume": 1
        }
        
        if req.type == OrderType.FAK:
            ctp_req["OrderPriceType"] = THOST_FTDC_OPT_LimitPrice
            ctp_req["TimeCondition"] = THOST_FTDC_TC_IOC
            ctp_req["VolumeCondition"] = THOST_FTDC_VC_AV
        elif req.type == OrderType.FOK:
            ctp_req["OrderPriceType"] = THOST_FTDC_OPT_LimitPrice
            ctp_req["TimeCondition"] = THOST_FTDC_TC_IOC
            ctp_req["VolumeCondition"] = THOST_FTDC_VC_CV            
        
        self.reqid += 1
        self.reqOrderInsert(ctp_req, self.reqid)
        
        orderid = f"{self.frontid}_{self.sessionid}_{self.order_ref}"
        order = req.create_order_data(orderid, self.gateway_name)
        self.gateway.on_order(order)
        
        return order.vt_orderid
    
    def cancel_order(self, req: CancelRequest):
        """
        Cancel existing order.
        """
        frontid, sessionid, order_ref = req.orderid.split("_")
        
        ctp_req = {
            "InstrumentID": req.symbol,
            "Exchange": req.exchange,
            "OrderRef": order_ref,
            "FrontID": int(frontid),
            "SessionID": int(sessionid),
            "ActionFlag": THOST_FTDC_AF_Delete,
            "BrokerID": self.brokerid,
            "InvestorID": self.userid
        }
        
        self.reqid += 1
        self.reqOrderAction(ctp_req, self.reqid)
    
    def query_account(self):
        """
        Query account balance data.
        """
        self.reqid += 1
        self.reqQryTradingAccount({}, self.reqid)
    
    def query_position(self):
        """
        Query position holding data.
        查询位置保持数据。
        """
        if not symbol_exchange_map:
            return
        
        req = {
            "BrokerID": self.brokerid,
            "InvestorID": self.userid
        }
        
        self.reqid += 1 
        self.reqQryInvestorPosition(req, self.reqid)
    
    def close(self):
        """"""
        if self.connect_status:
            self.exit()
