from dispatcher import Dispatcher
import json

class YourExecutorClass:
    pass  # implement

if __name__ == "__main__":
    # Load Config
    with open("config.json", "r") as f:
        config = json.load(f)
    
    # Initialize Dispatcher
    executor = YourExecutorClass()
    dispatcher = Dispatcher(executor, config)

    # main code
