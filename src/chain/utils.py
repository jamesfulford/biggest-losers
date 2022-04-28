
from src.data.polygon.option_chain import PolygonOptionChainContract


def _option_chain_contract_is_normal(chain: PolygonOptionChainContract) -> bool:
    return chain['spec']['contract_type'] in ('call', 'put') and chain['exercise_style'] == 'american' and chain['shares_per_contract'] == 100


def filter_option_chain_for_normality(chain: list[PolygonOptionChainContract]):
    return [contract for contract in chain if _option_chain_contract_is_normal(contract)]


def filter_option_chain_for_expiration(chain: list[PolygonOptionChainContract], min_days_to_expiration: int = 2, max_days_to_expiration: int = 14):
    assert min_days_to_expiration <= max_days_to_expiration
    return [contract for contract in chain if contract['days_to_expiration'] >= min_days_to_expiration and contract['days_to_expiration'] <= max_days_to_expiration]


def filter_option_chain_for_calls(chain: list[PolygonOptionChainContract]):
    return [contract for contract in chain if contract['spec']['contract_type'] == 'call']


def filter_option_chain_for_puts(chain: list[PolygonOptionChainContract]):
    return [contract for contract in chain if contract['spec']['contract_type'] == 'put']


def _is_in_the_money(contract: PolygonOptionChainContract, current_price: float) -> bool:
    return contract['spec']['strike_price'] <= current_price if contract['spec']['contract_type'] == 'call' else contract['spec']['strike_price'] >= current_price


def _is_out_of_the_money(contract: PolygonOptionChainContract, current_price: float) -> bool:
    return not _is_in_the_money(contract, current_price)


def filter_option_chain_for_out_of_the_money(chain: list[PolygonOptionChainContract], current_price: float):
    return [contract for contract in chain if _is_out_of_the_money(contract, current_price)]


def filter_option_chain_for_in_the_money(chain: list[PolygonOptionChainContract], current_price: float):
    return [contract for contract in chain if _is_in_the_money(contract, current_price)]


def filter_option_chain_for_near_the_money(chain: list[PolygonOptionChainContract], current_price: float, buffer: float = 10):
    return [contract for contract in chain if abs(contract['spec']['strike_price'] - current_price) < buffer]
