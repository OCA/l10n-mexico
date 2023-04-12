import csv
import glob
import os


def load_csv_fixtures(env, fixtures_dir_path):
    # list csv files in fixtures_dir_path
    csv_files = glob.glob(os.path.join(fixtures_dir_path, "*.csv"))
    for csv_file in csv_files:
        _load_csv_fixture_file(csv_file, env)


def _load_csv_fixture_file(csv_file, env):
    model_name = os.path.basename(csv_file)[0:-4]
    model = env[model_name]
    with open(csv_file, "r") as csv_file:
        # open using csv.DictReader
        csv_reader = csv.DictReader(csv_file)
        # create a list of dictionaries
        for entry in csv_reader:
            entry["name"] = ""
            model.create(entry)
