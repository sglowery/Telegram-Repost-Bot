import itertools
import os
import sys

import yaml

try:
    import ujson as json
except ImportError:
    import json


if __name__ == '__main__':
    print("\nMigrating group data files to 0.5.0")
    print("\nFinding main config file...")
    group_data_folder_name = None
    passed_argument = sys.argv[1] if len(sys.argv) > 1 else None
    config_paths = itertools.product(
        [file for file in [passed_argument, 'config.yaml', 'defaultconfig.yaml'] if file is not None],
        ['config', '../config', os.path.curdir, os.path.pardir]
    )
    for config_file_name, config_path in config_paths:
        try:
            path = os.path.abspath(config_path)
            joined = os.path.join(path, config_file_name)
            with open(joined) as f:
                group_data_folder_name = yaml.safe_load(f)['repost_data_path']
        except FileNotFoundError:
            pass
        else:
            print(f"Using config file located at {joined}")
            break
    if group_data_folder_name is None:
        raise RuntimeError("Couldn't find group data folder name from config files")
    else:
        print("\n\nFinding group data")
    try:
        path = os.path.abspath(group_data_folder_name)
        files = os.listdir(path)
    except FileNotFoundError:
        path = os.path.abspath(f'../{group_data_folder_name}')
        files = os.listdir(path)
    num_files = len(files)
    if num_files == 0:
        raise RuntimeError("Directory either doesn't have any files")
    elif not any(file[-5:] == '.json' for file in files):
        raise RuntimeError("Directory doesn't have any .json files")
    print(f"Using group data in {path}")
    files_done = 0
    files_migrated = 0
    error_files = 0
    for file in files:
        file_path = os.path.join(path, file)
        try:
            with open(file_path) as f:
                group_data = json.load(f)
            group_data["toggles"] = {**group_data["track"]}
            group_data["toggles"]["auto_callout"] = True
            group_data["toggles"]["auto_delete"] = False
            group_data["deleted"] = []
            del group_data["track"]
            with open(file_path, 'w') as f:
                json.dump(group_data, f)
            print(f"{file} successfully migrated")
            files_migrated += 1
            files_done += 1
        except KeyError:
            print(f"{file} already migrated; skipping...")
            files_done += 1
        except Exception as e:
            print(f"Error with file {file}: {e}")
            error_files += 1

    print(f"\n\nDone migrating {files_migrated} / {num_files} files")
    print(f"\n{files_done - files_migrated} files already migrated")
    print(f"\n{error_files} files had errors")
