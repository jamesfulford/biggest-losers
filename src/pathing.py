import os


def get_paths():
    app_dir = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..'))

    env_name = os.path.basename(app_dir)

    data_dir = os.path.abspath(os.path.join(app_dir, '..', env_name + '-data'))

    paths = {
        'name': env_name,
        'app': {
            'dir': app_dir,
        },
        'data': {
            'dir': data_dir,
        },
    }

    paths['data']["inputs"] = {
        'dir': os.path.join(paths['data']['dir'], 'inputs')}

    paths['data']["outputs"] = {
        'dir': os.path.join(paths['data']['dir'], 'outputs')}
    paths['data']["outputs"]["biggest_losers_csv"] = os.path.join(
        paths['data']['outputs']['dir'], 'biggest_losers.csv')
    paths['data']["outputs"]["filled_orders_csv"] = os.path.join(
        paths['data']['outputs']['dir'], 'filled_orders.csv')
    paths['data']["outputs"]["order_intentions_csv"] = os.path.join(
        paths['data']['outputs']['dir'], 'order_intentions_{today}.csv')

    paths['data']["logs"] = {'dir': os.path.join(paths['data']['dir'], 'logs')}

    paths['data']["cache"] = {
        'dir': os.path.join(paths['data']['dir'], 'cache')}

    return paths


def get_order_intentions_csv_path(today):
    return get_paths()['data']['outputs']['order_intentions_csv'].format(today=today)


if __name__ == '__main__':
    print(get_paths())
