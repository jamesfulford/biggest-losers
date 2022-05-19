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
