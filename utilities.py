from typing import Optional, Union, List
from pathlib import Path
from os import makedirs, path


from ib_insync import IB, ContFuture, MarketOrder
from logbook import Logger

from datastore import AbstractBaseStore


log = Logger(__name__)


def update_details(ib: IB, store: AbstractBaseStore,
                   keys: Optional[Union[str, List[str]]] = None) -> None:
    """
    Pull contract details from ib and update metadata in store.

    Args:
    ib: connected IB instance
    store: datastore instance, for which data will be updated
    keys (Optional): keys in datastore, for which data is to be updated,
                     if not given, update all keys
    """
    if keys is None:
        keys = store.keys()
    elif isinstance(keys, str):
        keys = [keys]

    contracts = {}
    for key in keys:
        try:
            contract = eval(store.read_metadata(key)['repr'])
        except TypeError:
            log.error(f'Metadata missing for {key}')
            continue
        contract.update(includeExpired=True)
        contracts[key] = contract
    ib.qualifyContracts(*contracts.values())
    details = {k: ib.reqContractDetails(v)[0] for k, v in contracts.items()}

    # get commission levels
    order = MarketOrder('BUY', 1)
    commissions = {k: ib.whatIfOrder(v, order).commission
                   for k, v in contracts.items()}

    for c, d in details.items():
        _d = {'name': d.longName,
              'min_tick': d.minTick,
              'commission': commissions[c]
              }
        store.write_metadata(c, _d)


def default_path(*dirnames: str) -> str:
    """
    Return path created by joining  ~/ib_data/ and recursively all dirnames
    If the path doesn't exist create it.
    Should also work in Windows but not tested.
    """
    home = Path.home()
    dirnames_str = ' / '.join(dirnames)
    if not Path.exists(home / 'ib_data' / dirnames_str):
        makedirs(home.joinpath('ib_data', *dirnames))
    return path.join(str(home), 'ib_data', *dirnames)
