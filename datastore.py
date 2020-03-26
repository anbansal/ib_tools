from functools import partial
from typing import List, Union
from abc import ABC, abstractmethod
import pickle

import pandas as pd
from ib_insync.contract import Future, ContFuture, Contract
from arctic import Arctic
from arctic.exceptions import NoDataFoundException
from arctic.store.versioned_item import VersionedItem
from arctic.date import DateRange
from logbook import Logger

from config import default_path

log = Logger(__name__)


class AbstractBaseStore(ABC):

    @abstractmethod
    def write(self, symbol: Union[str, Contract]):
        pass

    @abstractmethod
    def read(self, symbol: Union[str, Contract]):
        pass

    @abstractmethod
    def keys(self) -> List[str]:
        pass

    def _symbol(self, obj: Union[Contract, str]) -> str:
        if isinstance(obj, Contract):
            return f'{obj.localSymbol}_{obj.secType}'
        else:
            return obj

    def _metadata(self, obj: Union[Contract, str]):
        if isinstance(obj, Contract):
            return {**obj.nonDefaults(),
                    **{'repr': repr(obj),
                       'secType': obj.secType,
                       'object': obj}}
        else:
            return {}

    @staticmethod
    def _clean(df):
        df = df.sort_index(ascending=True)
        df.drop(index=df[df.index.duplicated()].index, inplace=True)
        return df

    def check_earliest(self, symbol):
        try:
            return self.read(symbol).index.min()
        except (KeyError, AttributeError):
            return None

    def check_latest(self, symbol):
        try:
            return self.read(symbol).index.max()
        except (KeyError, AttributeError):
            return None


class ArcticStore(AbstractBaseStore):

    def __init__(self, lib: str, host: str = 'localhost') -> None:
        """
        Library name is whatToShow + barSize, eg.
        TRADES_1_min
        BID_ASK_1_hour
        MIDPOINT_30_secs
        """
        lib = lib.replace(' ', '_')
        self.db = Arctic(host)
        self.db.initialize_library(lib)
        self.store = self.db[lib]

    def write(self, symbol: Union[str, Contract],
              data: pd.DataFrame, meta: dict = {}) -> VersionedItem:
        metadata = self._metadata(symbol)
        metadata.update(meta)
        return self.store.write(
            self._symbol(symbol),
            self._clean(data),
            metadata=metadata)

    def read(self, symbol: Union[str, Contract]):
        try:
            return self.store.read(self._symbol(symbol)).data
        except (NoDataFoundException, AttributeError):
            return None

    def read_object(self, symbol: Union[str, Contract]):
        try:
            return self.store.read(self._symbol(symbol))
        except NoDataFoundException:
            return None

    def keys(self) -> List[str]:
        return self.store.list_symbols()

    def _metadata(self, obj: Union[Contract, str]):
        if isinstance(obj, Contract):
            meta = super()._metadata(obj)
            #meta.update({'object': pickle.dumps(obj)})
            meta.update({'object': None})
        return meta


class PyTablesStore(AbstractBaseStore):

    def __init__(self, lib: str, path: str = default_path) -> None:
        lib = lib.replace(' ', '_')
        path = f'{path}/{lib}.h5'
        self.store = partial(pd.HDFStore, path)

    def write(self, symbol: Union[str, Contract],
              data: pd.DataFrame, meta: dict = {}) -> None:
        with self.store() as store:
            store.append(self._symbol(symbol),
                         self._clean(data))

    def read(self, symbol: Union[str, Contract]):
        with self.store() as store:
            data = store.select(self._symbol(symbol))
        return data

    def keys(self) -> List[str]:
        with self.store() as store:
            keys = store.keys()
        return keys


class PickleStore(AbstractBaseStore):

    def __init__(self, lib: str, path: str = default_path) -> None:
        lib = lib.replace(' ', '_')
        pass


# ==================================================================
# DEPRECATED
# ==================================================================


class Store:

    def __init__(self, path=default_path, what='cont_fut_only'):
        path = f'{default_path}/{what}.h5'
        self.store = partial(pd.HDFStore, path)

    def write(self, symbol, data, freq='min'):
        with self.store() as store:
            store.append(self._symbol(symbol, freq), data)

    def date_string(self, start_date=None, end_date=None):
        dates = []
        if start_date:
            if isinstance(start_date, pd.Timestamp):
                start_date = start_date.strftime('%Y%m%d')
            dates.append(f'index >= {start_date}')
        if end_date:
            if isinstance(end_date, pd.Timestamp):
                end_date = end_date.strftime('%Y%m%d')
            dates.append(f'index <= {end_date}')
        if len(dates) == 2:
            return ' & '.join(dates)
        else:
            return dates[0]

    def read(self, symbol, freq='min', start_date=None, end_date=None):
        date_string = None
        if start_date or end_date:
            date_string = self.date_string(start_date, end_date)
        symbol = self._symbol(symbol, freq)
        with self.store() as store:
            if date_string:
                data = store.select(symbol, date_string)
            else:
                data = store.select(symbol)
        return data

    def remove(self, symbol, freq='min', *args, **kwargs):
        symbol = self._symbol(symbol, freq)
        with self.store() as store:
            store.remove(symbol)

    def check_earliest(self, symbol, freq='min'):
        try:
            return self.read(symbol, freq=freq).index.min()
        except KeyError:
            return None

    def check_latest(self, symbol, freq='min'):
        try:
            return self.read(symbol, freq=freq).index.max()
        except KeyError:
            return None

    def _symbol(self, s, freq):
        if isinstance(s, ContFuture):
            string = (f'cont/{freq}/{s.symbol}_'
                      f'{s.lastTradeDateOrContractMonth}_{s.exchange}'
                      f'_{s.currency}')
            return string
        elif isinstance(s, Future):
            string = (f'{freq}/{s.symbol}_{s.lastTradeDateOrContractMonth}'
                      f'_{s.exchange}_{s.currency}')
            return string

        else:
            return s

    def clean_store(self):
        with self.store() as store:
            for key in store.keys():
                df = store.select(key).sort_index(ascending=False)
                df.drop(index=df[df.index.duplicated()].index, inplace=True)
                store.remove(key)
                store.append(key, df)

    def keys(self):
        with self.store() as store:
            keys = store.keys()
        return keys

        """
        TODO:
        implement pickle store
        df = pd.read_pickle('notebooks/data/minute_NQ_cont_non_active_included.pickle'
                            ).loc['20180201':].sort_index(ascending=False)
        """
