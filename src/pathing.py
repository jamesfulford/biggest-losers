import os


def get_paths(target_environment_name=None):
    app_dir = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..'))

    current_environment_name = os.path.basename(app_dir)
    environment_root_dir = os.path.abspath(os.path.join(app_dir, '..'))
    data_dir = os.path.join(
        environment_root_dir, current_environment_name + '-data')

    if target_environment_name is not None:
        data_dir = os.path.join(
            data_dir, "remote-environments", target_environment_name)

    paths = {
        'name': target_environment_name or current_environment_name,
        'app': {
            'dir': app_dir,
        },
        'data': {
            'dir': data_dir,
        },
    }

    paths['data']["inputs"] = {
        'dir': os.path.join(paths['data']['dir'], 'inputs')}
    paths['data']["inputs"]["td-token_json"] = os.path.join(
        paths['data']['inputs']['dir'], "td-token", "output", 'token.json')

    paths['data']["outputs"] = {
        'dir': os.path.join(paths['data']['dir'], 'outputs')}
    paths['data']["outputs"]["biggest_losers_csv"] = os.path.join(
        paths['data']['outputs']['dir'], 'biggest_losers.csv')
    paths['data']["outputs"]["filled_orders_csv"] = os.path.join(
        paths['data']['outputs']['dir'], 'filled_orders.csv')
    paths['data']["outputs"]["order_intentions_csv"] = os.path.join(
        paths['data']['outputs']['dir'], 'order_intentions_{today}.csv')
    paths['data']["outputs"]["performance_csv"] = os.path.join(
        paths['data']['outputs']['dir'], 'performance-{environment}.csv')

    paths['data']["logs"] = {'dir': os.path.join(paths['data']['dir'], 'logs')}

    paths['data']["cache"] = {
        'dir': os.path.join(paths['data']['dir'], 'cache')}

    return paths


def get_order_intentions_csv_path(today):
    return get_paths()['data']['outputs']['order_intentions_csv'].format(today=today)


if __name__ == '__main__':
    # on James' local machine this code is checked out at ~/biggest-losers
    default_paths = get_paths()
    print(default_paths)
    assert default_paths['name'] == 'biggest-losers'
    assert default_paths['data']["dir"] == '/Users/jamesfulford/biggest-losers-data'

    paper_paths = get_paths('paper')
    print(paper_paths)
    assert paper_paths['name'] == 'paper', paper_paths['name']
    assert paper_paths['data']["dir"] == '/Users/jamesfulford/biggest-losers-data/remote-environments/paper'

    prod_paths = get_paths('prod')
    print(prod_paths)
    assert prod_paths['name'] == 'prod', prod_paths['name']
    assert prod_paths['data']["dir"] == '/Users/jamesfulford/biggest-losers-data/remote-environments/prod'
