from importlib import import_module


def get_scanner(scanner: str):
    assert scanner.replace("_", "").isalpha()
    module = import_module("src.scan." + scanner)

    return module.get_all_candidates_on_day
