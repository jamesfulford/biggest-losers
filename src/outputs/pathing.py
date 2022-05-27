import os
from typing import Optional


def get_chronicle_folder_paths(chronicle_name: str, target_environment_name: Optional[str] = None):
    paths = get_paths(target_environment_name=target_environment_name)
    dir_path = os.path.join(
        paths['data']['chronicles']['dir'], chronicle_name)

    return {
        'dir': dir_path,
        'metadata.json': os.path.join(dir_path, 'metadata.json'),
        'snapshots.jsonl': os.path.join(dir_path, 'snapshots.jsonl'),
    }


def get_results_folder_paths(results_folder_name: str, target_environment_name: Optional[str] = None):
    paths = get_paths(target_environment_name=target_environment_name)
    dir_path = os.path.join(
        paths['data']['results']['dir'], results_folder_name)

    return {
        "dir": dir_path,
        "plain-filled-orders.jsonl": os.path.join(dir_path, "plain-filled-orders.jsonl"),
        "intentions.jsonl": os.path.join(dir_path, "intentions.jsonl"),
        "intentioned-filled-orders.jsonl": os.path.join(dir_path, "intentioned-filled-orders.jsonl"),
        "summary.json": os.path.join(dir_path, "summary.json"),
        "metadata.json": os.path.join(dir_path, "metadata.json"),
    }


def get_paths(target_environment_name: Optional[str] = None):
    app_dir = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', '..'))

    if app_dir == "/app":
        current_environment_name = "docker"
        data_dir = "/data"
    else:
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

    results_dir = os.path.join(data_dir, 'results')
    paths['data']['results'] = {'dir': results_dir}

    chronicles_dir = os.path.join(data_dir, 'chronicles')
    paths['data']['chronicles'] = {'dir': chronicles_dir}

    paths['data']["inputs"] = {
        'dir': os.path.join(data_dir, 'inputs')}
    paths['data']["inputs"]["td-token_json"] = os.path.join(
        paths['data']['inputs']['dir'], "td-token", "output", 'token.json')

    outputs_dir = os.path.join(data_dir, 'outputs')
    output_paths = {'dir': outputs_dir}
    paths['data']["outputs"] = output_paths
    output_paths["losers_csv"] = os.path.join(outputs_dir, 'losers.csv')
    output_paths["winners_csv"] = os.path.join(outputs_dir, 'winners.csv')
    output_paths["supernovas_csv"] = os.path.join(
        outputs_dir, 'supernovas.csv')
    output_paths["rollercoasters_csv"] = os.path.join(
        outputs_dir, 'rollercoasters.csv')
    output_paths["gappers_csv"] = os.path.join(outputs_dir, 'gappers.csv')
    output_paths["volume_movers_csv"] = os.path.join(
        outputs_dir, 'volume_movers.csv')
    output_paths["daily_rsi_oversold_csv"] = os.path.join(
        outputs_dir, 'daily_rsi_oversold.csv')

    output_paths["filled_orders_csv"] = os.path.join(
        outputs_dir, 'filled_orders.csv')
    output_paths["order_intentions_jsonl"] = os.path.join(
        outputs_dir, 'order_intentions_{algo_name}.jsonl')
    output_paths["performance_csv"] = os.path.join(
        outputs_dir, 'performance-{environment}.csv')

    paths['data']["logs"] = {'dir': os.path.join(data_dir, 'logs')}

    paths['data']["cache"] = {
        'dir': os.path.join(data_dir, 'cache')}

    return paths


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
