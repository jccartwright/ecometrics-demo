import pandas as pd
import numpy as np
from collections import defaultdict
import h3
import warnings
from datetime import datetime
import logging
import os
import argparse
import json

'''
accommodate native date format from Excel. Ignores seconds and milliseconds 
'''
def convert_date(date_string):
    date_str,time_str = date_string.split(' ')
    hours = time_str.split(':')[0]
    datetime_str = f'{date_str}T{hours}:00:00'
    try:
        return datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S').isoformat(timespec='minutes')
    except:
        print(f'Could not parse date {datetime_str}')
        return None

'''
Process surveyed elevation points along profile

reads CSV file exported from Excel and reformats and exports as JSON file more 
suitable for use with D3 charts.

WARNING: code is tightly coupled to Excel spreadsheet format

output attribute names shortened to minimize file size:
    x: distance along profile
    z: water level in meters

 e.g.
    [
        {
            "x": 15.7,
            "z": 10266.88
        },
        ...
    ]
'''
def write_elevations(df, output_filename):
    # create a data file of surveyed points along profile
    elevations = []
    for station in df.items():
        elevations.append({"x":station[1]['Station'], "z":station[1]['ground elevation']})

    with open(output_filename, "w") as file:
        json.dump(elevations, file, indent=2)



'''
series represents measurements for all wells at given timestamp
wells is a dataframe of well attributes indexed by well ID
e.g. surface elevation, which are invariant across time
'''
def format_waterlevel(series, wells):
    values = []
    for well_id, waterlevel in series.items():
        values.append({
            "id": well_id,
            "x": wells.loc['Station', well_id],
            "z": waterlevel
        })
    return values

'''
Process water level data

reads CSV file exported from Excel and reformats and exports as JSON file more 
suitable for use with D3 charts.

WARNING: code is tightly coupled to Excel spreadsheet format

output attribute names shortened to minimize file size:
    id: well id
    x: distance along profile
    z: water level in meters

e.g.
    [
        {
            "label": "2023-09-24T14:00",
            "values": [
                {
                    "id": "1.1",
                    "x": 15.7,
                    "z": 10266.88
                },
                ...
            ]
        }
    ]
'''
def write_waterlevels(df, wells, output_filename):
    # because we're not using Pandas to_json methods, explicitly replace the NaN values with null
    # TODO why doesn't this work?
    # df_filled = df.fillna(value=None)
    df_filled = df.replace(np.nan, None)
    results = []
    # iterate over each timestamp
    for ts,row in df_filled.iterrows():
        results.append({ 'label': ts, 'values': format_waterlevel(row, wells) })

    with open(output_filename, "w") as file:
        json.dump(results, file, indent=2)

'''
    Create a wells data file using both the elevations and waterlevels CSV input data
     WARNING: code is tightly coupled to Excel spreadsheet format

    output attribute names shortened to minimize file size:
        id: well id
        x: distance along profile
        min_z: minimum water level (in meters) over all datetimes
        max_z: maximum water level (in meters) over all datetimes
        surface: elevation (in meters) of surface where well is located

    e.g.
    [
        {
            "id": "1.1",
            "x": 15.7,
            "min_z": 10270.88,
            "max_z": 10266.77,
            "surface": 10269.57,
            "sensor": 8404.24
        }
        ...
    ]
'''
def write_wells(waterlevels, wells, output_filename):
    # calculate max/min for each well
    min_values = waterlevels.min()
    max_values = waterlevels.max()
    # join all attributes into dataframe and create list of objects
    wells_data = []
    df = pd.concat([wells.loc['Station'],min_values, max_values, wells.loc['ground elevation'], wells.loc['sensor elev']], axis=1, keys=['x', 'min_z', 'max_z', 'surface','sensor'])
    for label, row in df.iterrows():
        wells_data.append({"id": label, "x": row.iloc[0], "min_z": row.iloc[1], "max_z": row.iloc[2], "surface": row.iloc[3], "sensor": row.iloc[4]})

    with open(output_filename, "w") as f:
        json.dump(wells_data, f, indent=2)


def main(args):
    if not os.path.exists(args.manifest):
        logging.error(f'file {args.manifest} does not exist')
        return

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    if not args.input_dir:
        input_dir = os.path.dirname(args.manifest)
    else:
        input_dir = args.input_dir

    with open(args.manifest, 'r') as file:
        files_manifest = [i.strip() for i in  file.readlines()]

    input_files = []
    for excel_file in files_manifest:
        xl = pd.ExcelFile(os.path.join(input_dir, excel_file))
        # print(f'{excel_file}: {xl.sheet_names}')
        input_files.append(
            {
                'filename': os.path.join(input_dir, excel_file),
                'label': excel_file.split('.')[0],
            })
    with open(os.path.join(output_dir, 'input_files.json'), 'w') as file:
        prefixes = [ i['label'].replace(' ','_') for i in input_files]
        json.dump(prefixes, file)

    # for file in input_files[0:1]:
    for file in input_files:
        # Excel file expected to contain a single worksheet named to match file basename. Sheet is organized with one
        # column for each surveyed location (i.e. Station).
        # First four rows are metadata:
        #   Station (distance along profile)
        #   ground elevation
        #   sensor elev (height of sensor w/in well)
        #   well id (string uniquely identifying well along profile)
        print(f'processing {file["filename"]}...')

        try:
            # read worksheet and drop any rows where all fields are null
            waterlevels = pd.read_excel(file['filename'], sheet_name=file['label'], header=None, index_col=0, na_values=['BS']).dropna(how='all')

            # create dataframe with two rows (Station, ground elevation) and column for each location
            elevations = waterlevels.iloc[0:2].copy(deep=True)
            # drop all columns except for those with wells
            waterlevels.dropna(axis=1, subset=['well id'], inplace=True)

            # use for column labels on wells, waterlevels
            well_ids = waterlevels.loc['well id']

            # create dataframe with three rows (Station, ground elevation, sensor elevation) and column for each well
            wells = waterlevels.iloc[0:3].copy(deep=True)
            wells.columns = well_ids.tolist()

            # trim unneeded rows of original dataframe to just waterlevel data: one column per well, one row per timestamp
            waterlevels.drop(['Station','ground elevation','sensor elev','well id'], axis=0, inplace=True)
            waterlevels.index.name = 'timestamp'
            waterlevels.columns = well_ids.tolist()
            # convert timestamp to string with hour precision
            waterlevels.index = waterlevels.index.map(lambda x: x.strftime('%Y-%m-%d %H:%M'))

            if waterlevels.index.has_duplicates:
                msg = f'file {file["filename"]} contains duplicate timestamps'
                logging.error(msg)
                raise Exception(msg)
            print(f'\t...{len(waterlevels)} waterlevel records')
            print(f'\t...{len(elevations.loc['Station'])} survey stations along profile')
            print(f'\t...{len(wells.columns)} well records')
        except Exception as e:
            logging.error(f'file {file["filename"]} is not formatted correctly. skipping...')
            continue

        waterlevels_output_filename = os.path.join(output_dir, f'{file['label']}_waterlevels.json')
        wells_output_filename = os.path.join(output_dir, f'{file['label']}_wells.json')
        elevations_output_filename = os.path.join(output_dir, f'{file['label']}_elevations.json')

        write_waterlevels(df=waterlevels, wells=wells, output_filename=waterlevels_output_filename)
        write_wells(waterlevels=waterlevels, wells=wells, output_filename=wells_output_filename)
        write_elevations(df=elevations, output_filename=elevations_output_filename)

if __name__ == "__main__":
    levels = {
        'error': logging.ERROR,
        'warning': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG
    }

    # setup command line arguments
    arg_parser = argparse.ArgumentParser(
        description="""create files to support Ecometrics Demo"""
    )
    arg_parser.add_argument("--manifest", required=True, help="path to manifest of Excel filenames")
    # arg_parser.add_argument("--elevations", required=True, help="path to CSV file of surveyed stations")
    # arg_parser.add_argument("--waterlevels", required=True, help="path to CSV file of waterlevel data")
    # arg_parser.add_argument("--output_prefix", required=True, help="prefix used with all output JSON files")
    arg_parser.add_argument("--output_dir", default=".", help="directory to hold output files, default is current directory")
    arg_parser.add_argument("--input_dir", help="directory containing the Excel files. Default is the directory containing the manifest")
    arg_parser.add_argument("--loglevel", default="warning", required=False,
                            choices=['debug', 'info', 'warning', 'error'],
                            help="set verbosity of logging, default is 'warning'")
    args = arg_parser.parse_args()
    logging.basicConfig(level=levels.get(args.loglevel))
    logging.getLogger('chardet').level = logging.ERROR

    main(args)