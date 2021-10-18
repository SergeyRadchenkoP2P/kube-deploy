import requests
import json
import operator
import time
from flask import Flask, make_response

app = Flask(__name__)

@app.route("/metrics")
def metrics():
    validators = get_config('polka_nodes')['validators']

    rewards = get_era_rewards(
        validators = validators,
        session_validators = api_server_request(endpoint = '/api/derive/staking/validators'),
        era = api_server_request(endpoint = '/api/query/staking/activeEra'),
        raw_data = api_server_request(endpoint = '/api/query/staking/erasRewardPoints')
        )

    unappliedSlashes = get_unnaplied_slashes(
        validators = validators,
        raw_data = api_server_request(endpoint = '/api/query/staking/unappliedSlashes')
        )

    try:
        out = '# HELP polkadot_era_common Some basic era metrics\n'
        out += '# TYPE polkadot_era_common counter\n'

        for k,v in rewards['common'].items():
            out += 'polkadot_era_common{metric="%s"} %s\n' % (k,v)

        out += "# HELP polkadot_era_rewards_validator Validator points\n"
        out += "# TYPE polkadot_era_rewards_validator counter\n"

        for k,v in rewards['our_points'].items():
            out += 'polkadot_era_rewards_validator{validator="%s",account_addr="%s"} %s\n' % (validators[k]['node'],k,v)
      
        out += "# HELP polkadot_era_position_validator Validator position\n"
        out += "# TYPE polkadot_era_position_validator counter\n"

        for k,v in rewards['position'].items():
            out += 'polkadot_era_position_validator{validator="%s",account_addr="%s"} %s\n' % (validators[k]['node'],k,v)

        out += "# HELP polkadot_era_rewards_zug ZUG points\n"
        out += "# TYPE polkadot_era_rewards_zug counter\n"

        for k,v in rewards['zug_points'].items():
            out += 'polkadot_era_rewards_zug{account_addr="%s"} %s\n' % (k,v)

        out += "# HELP polkadot_era_unapplied_slashes Validator slashed in current era\n"
        out += "# TYPE polkadot_era_unapplied_slashes counter\n"

        for k,v in unappliedSlashes.items():
            out += 'polkadot_era_unapplied_slashes{validator="%s",account_addr="%s"} %s\n' % (validators[k]['node'],k,v)

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

def get_unnaplied_slashes(**kwargs):
    raw_data = kwargs['raw_data']
    validators = kwargs['validators'].keys()

    result = {k:0 for k in validators}
    
    for i in raw_data['result']:
        if i['validator'] in result.keys():
           result[i['validator']] = i['payout']

    return result

def get_era_rewards(**kwargs):
    raw_data = kwargs['raw_data']
    validators = kwargs['validators'].keys()
    session_validators = kwargs['session_validators']
    result = {'common':{}}
   
    result['our_points'] = {k:v for k,v in raw_data['result']['individual'].items() if k in validators}
    result['zug_points'] = {k:v for k,v in raw_data['result']['individual'].items() if k.startswith(('1zug','Czug'))}
    result['position'] = {k:list(dict(sorted(raw_data['result']['individual'].items(), key=operator.itemgetter(1),reverse=True)).keys()).index(k) for k in raw_data['result']['individual'].keys() if k in validators}
    result['common']['era'] = kwargs['era']['result']['index']
    result['common']['total_points'] = raw_data['result']['total']
    result['common']['total_validators'] = len(session_validators['result']['validators'])
   
    for i in session_validators['result']['validators']:
        if i in validators and i not in result['our_points'].keys():
            result['our_points'][i] = 0
        elif i.startswith(('1zug','Czug')) and i not in result['zug_points'].keys():
            result['zug_points'][i] = 0

    return result

if __name__ == '__main__':
    endpoint_listen = get_config('exporter')['listen']
    endpoint_port = get_config('exporter')['port']

    app.run(host=endpoint_listen, port=int(endpoint_port))
