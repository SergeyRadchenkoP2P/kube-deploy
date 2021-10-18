import requests
import json
import operator
import time
from flask import Flask, make_response

app = Flask(__name__)

@app.route("/metrics")
def metrics():
    validators = get_config('polka_nodes')['validators']
    accounts = get_accounts(validators = validators)

    try:
        out = "# HELP polkadot_accounts_controllers Changed or not\n"
        out += "# TYPE polkadot_accounts_controllers counter\n"

        for k,v in accounts.items():
            out += 'polkadot_accounts_controllers{validator="%s",account_addr="%s"} %s\n' % (validators[k]['node'],k,v['controller']['result'])

        out += "# HELP polkadot_accounts_payees Changed or not\n"
        out += "# TYPE polkadot_accounts_payees counter\n"

        for k,v in accounts.items():
            out += 'polkadot_accounts_payees{validator="%s",account_addr="%s"} %s\n' % (validators[k]['node'],k,v['payee']['result'])

        out += "# HELP polkadot_accounts_commission Changed or not\n"
        out += "# TYPE polkadot_accounts_commission counter\n"

        for k,v in accounts.items():
            out += 'polkadot_accounts_commission{validator="%s",account_addr="%s"} %s\n' % (validators[k]['node'],k,v['commission']['result'])

        out += "# HELP polkadot_accounts_balance Free tokens on an account\n"
        out += "# TYPE polkadot_accounts_balance gauge\n"

        for k,v in accounts.items():
            out += 'polkadot_accounts_balance{validator="%s",account_addr="%s",balance_of="controller"} %s\n' % (validators[k]['node'],v['controller']['address'],v['controller']['balance'])

        for k,v in accounts.items():
            out += 'polkadot_accounts_balance{validator="%s",account_addr="%s",balance_of="payee"} %s\n' % (validators[k]['node'],v['payee']['address'],v['payee']['balance'])

    except KeyError:
        pass

    response = make_response(out, 200)
    response.mimetype = "text/plain"
    
    return response

def get_config(part):
    with open('./config.json') as config_file:
        data = json.load(config_file)
   
    return data[part]

def api_server_request(endpoint,account_id = None):
    api_host = get_config('api_server')['host']
    api_port = get_config('api_server')['port']

    node_ws_host = get_config('polka_nodes')['host']
    node_ws_port = get_config('polka_nodes')['port']

    url = 'http://' + api_host + ':' + api_port

    node = '?websocket=ws://' + node_ws_host + ':' + node_ws_port
    
    if account_id:
        return requests.get(url + endpoint + node + '&account_id=' + account_id).json()
    else:
        return requests.get(url + endpoint + node).json()

def get_accounts(**kwargs):
    validators = kwargs['validators']
    result = {}

    for stash in validators.keys():
        result[stash] = {'controller':{},'payee':{},'commission':{}}
        result[stash]['controller']['address'] = api_server_request('/api/query/staking/bonded',stash)['result']
        payee = api_server_request('/api/query/staking/payee',stash)['result']
        result[stash]['commission']['commission'] = api_server_request('/api/query/staking/validators',stash)['result']['commission']

        if 'staked' in payee.keys():
            payee = stash
        elif 'controller' in payee.keys():
            payee = result[stash]['controller']['address']
        elif 'account' in payee.keys():
            payee = payee['account']
        else:
            payee = None

        result[stash]['payee']['address'] = payee

        result[stash]['controller']['balance'] = api_server_request('/api/query/system/account',result[stash]['controller']['address'])['result']['data']['free']
        result[stash]['payee']['balance'] = api_server_request('/api/query/system/account',payee)['result']['data']['free']

        if result[stash]['controller']['address'] == validators[stash]['controller']:
            result[stash]['controller']['result'] = 0
        else:
            result[stash]['controller']['result'] = 1

        if result[stash]['payee']['address'] == validators[stash]['payee']:
            result[stash]['payee']['result'] = 0
        else:
            result[stash]['payee']['result'] = 1

        if result[stash]['commission']['commission'] == validators[stash]['commission']:
            result[stash]['commission']['result'] = 0
        else:
            result[stash]['commission']['result'] = 1

    return result

if __name__ == '__main__':
    endpoint_listen = get_config('exporter')['listen']
    endpoint_port = get_config('exporter')['port']

    app.run(host=endpoint_listen, port=int(endpoint_port))
