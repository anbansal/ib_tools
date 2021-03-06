from ib_insync import IB, util
from ib_insync.ibcontroller import IBC, Watchdog

from handlers import Handlers
from saver import ArcticSaver
from blotter import MongoBlotter
from trader import Manager
from trader import Trader
from strategy import strategy_kwargs
from logger import logger, rotating_logger_with_shell
from logbook import INFO

log = rotating_logger_with_shell(__file__[:-3], INFO, INFO)


class Start(Handlers):

    def __init__(self, ib, manager):
        util.patchAsyncio()
        self.manager = manager
        ibc = IBC(twsVersion=979,
                  gateway=False,
                  tradingMode='paper',
                  )
        watchdog = Watchdog(ibc, ib,
                            port='4002',
                            clientId=0,
                            )
        log.debug('attaching handlers...')
        super().__init__(ib, watchdog)
        # this is the main entry point into strategy
        watchdog.startedEvent += manager.onStarted
        log.debug('initializing watchdog...')
        watchdog.start()
        log.debug('watchdog initialized')
        ib.run()


ib = IB()
# util.logToConsole(DEBUG)
blotter = MongoBlotter()
saver = ArcticSaver()
trader = Trader(ib, blotter)
manager = Manager(ib, trader=trader, saver=saver, **strategy_kwargs)
start = Start(ib, manager)
