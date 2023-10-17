import importlib.util

class StrategyManager:
    def __init__(self, config, dispatcher):
        self.config = config
        self.dispatcher = dispatcher
        self.strategy_id = 0
        self.strategy_map = {}

        for strategy in config["strategies"]:
            spec = importlib.util.spec_from_file_location(strategy["filename"], 
                                                          strategy["path"])
            modulevar = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulevar)
            
            # TODO: add AbstractStrategy assertion
            self.strategy_map[self.strategy_id] =\
                getattr(modulevar, strategy["name"])(self.strategy_id,
                                                     dispatcher,
                                                     dispatcher.register_strategy(self.strategy_id),
                                                     strategy)

            print("StrategyManager: registered", strategy["name"], self.strategy_id)

        self.strategy_id += 1

    def run(self):
        print("StrategyManager: starting strategy loop")
        while True:
            for strategy in self.strategy_map.values():
                strategy.update()
