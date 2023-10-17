
class Balance:
    def __init__(self, account, currency):
        self.account = account
        self.currency = currency

    ### Interface ###
    
    def get_account(self):
        return self.account

    def get_currency(self):
        return self.currency