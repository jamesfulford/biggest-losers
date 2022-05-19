import os
import shutil
import src.outputs.pathing as pathing


def delete_result(result_name: str):
    paths = pathing.get_results_folder_paths(result_name)
    path = paths['dir']

    shutil.rmtree(path)


def create_result(result_name: str):
    paths = pathing.get_results_folder_paths(result_name)
    path = paths['dir']

    os.mkdir(path)


def list_results():
    paths = pathing.get_paths()
    path = paths['data']['results']['dir']

    return [
        p for p in os.listdir(path) if not p.startswith(".")
    ]


def main():
    import argparse
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest='command')
    list_parser = subparsers.add_parser('list')

    create_parser = subparsers.add_parser('create')
    create_parser.add_argument('result_name')

    delete_parser = subparsers.add_parser('delete')
    delete_parser.add_argument('result_name')

    args = parser.parse_args()

    if args.command == 'create':
        assert args.result_name
        try:
            create_result(args.result_name)
        except FileExistsError:
            print(
                f"Result '{args.result_name}' already exists, no action taken.")

    elif args.command == 'delete':
        assert args.result_name
        try:
            delete_result(args.result_name)
        except FileNotFoundError:
            print(f"No result named '{args.result_name}', no action taken.")

    elif args.command == 'list':
        for result_name in list_results():
            print(result_name)
