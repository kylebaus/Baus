import json

class Config:
    def __init__(self, path):
        self.path = path
        
        with open(path) as json_file:
            self.json = json.load(json_file)
       
    def get_json(self):
        return self.json
