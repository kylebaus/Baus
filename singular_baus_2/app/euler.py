import sys
import asyncio
import threading
import logging
import datetime as dt

# Singular
import singular
import singular.config

# Euler
import euler.system
import euler.strategy

def main(path):
    logging.basicConfig(filename="euler.log", level=logging.INFO)

    config = singular.config.Config(path)
        
    dispatcher = euler.system.Dispatcher(None, config.get_json())
    dispatcher.run()

    strategy_manager = euler.strategy.StrategyManager(config.get_json(), dispatcher)

    counter = 0
    while True:
        # drains gateway queues and puts events on strategy queues
        pre_consume_all_exch_ts = dt.datetime.now()
        for gateway in dispatcher.gateway_management_system.gateway_map.values():
            # pre_consume_ts = dt.datetime.now()
            gateway.consume_all()
            # diff = (dt.datetime.now() - pre_consume_ts).total_seconds() * 1000
            # if diff > 25:
            #     logging.info(f" | {dt.datetime.now()} | Queue Check - {gateway.config['account']['exchange']} {round(diff, 3)} ms elapsed")
        post_consume_all_exch_ts = dt.datetime.now()
        
        for strategy in strategy_manager.strategy_map.values():
            strategy.update()    
        
        post_strategy_update_ts = dt.datetime.now()
        queue_drain_diff = (post_consume_all_exch_ts - pre_consume_all_exch_ts).total_seconds() * 1000
        strat_update_diff = (post_strategy_update_ts - post_consume_all_exch_ts).total_seconds() * 1000
        if queue_drain_diff > 1000:
            logging.info(f" | {dt.datetime.now()} | TOTAL EXCHANGE Queue Check {round(queue_drain_diff)} ms elapsed")
        if strat_update_diff > 1000:
            logging.info(f" | {dt.datetime.now()} | STRATEGY UPDATE {round(strat_update_diff)} ms elapsed")

        counter += 1

if __name__ == "__main__":
    args = sys.argv[1:]
    path = args[0]
    main(path)