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
series is a tuple representing measurements for all wells at given timestamp
wells is a dataframe of well attributes indexed by well ID
e.g. surface elevation, which are invariant across time
'''
def format_waterlevel(series, wells):
    values = []
    mydict = dict(series)
    # pull off only column which does not contain waterlevel values
    timestamp = mydict.pop('timestamp')
    # iterate over remaining columns, i.e. wells
    for k,v in mydict.items():
        values.append({
            "id": str(k),
            "x": wells.loc[str(k)]['Station'],
            "z": v
        })
    return { 'label': timestamp, 'values': values }


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
    for row in df.iterrows():
        # row is a tuple with the first element being integer index and the second a Series with
        # Station (i.e. distance along profile) and surface elevation in meters
        elevations.append({"x": float(row[1]['Station']),"z": float(row[1]['ground elevation'])})

    with open(output_filename, "w") as file:
        json.dump(elevations, file, indent=2)


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
    results = []
    for row in df.dropna().iterrows():
        results.append(format_waterlevel(row[1], wells))

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
            "surface": 10269.57
        }
        ...
    ]
'''
def write_wells(waterlevels, wells, output_filename):
    # calculate max/min for each well
    min_values = waterlevels.iloc[:,1:].min()
    # change index type to string to allow combining w/ wells dataframe
    min_values.index = min_values.index.astype(str)
    max_values = waterlevels.iloc[:,1:].max()
    max_values.index = max_values.index.astype(str)
    # join all attributes into dataframe and create list of objects
    wells_data = []
    df = pd.concat([wells['Station'],min_values, max_values, wells['ground elevation']], axis=1, keys=['x', 'min_z', 'max_z', 'surface'])
    for label, row in df.iterrows():
        wells_data.append({"id": label, "x": row.iloc[0], "min_z": row.iloc[1], "max_z": row.iloc[2], "surface": row.iloc[3]})

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
                'label': ' '.join(xl.sheet_names[0].split(' ')[0:-1])
            })
    with open(os.path.join(output_dir, 'input_files.json'), 'w') as file:
        prefixes = [ i['label'].replace(' ','_') for i in input_files]
        json.dump(prefixes, file)

    # for file in input_files[0:1]:
    for file in input_files:
        print(f'processing {file["filename"]}...')
        # skip first row with stations since we get them from the ground worksheet
        # add "parse_dates=['well id']" to convert to actual Timestamp but then can't truncate
        waterlevels = pd.read_excel(file['filename'], sheet_name=f'{file['label']} water', header=1, dtype={'well id':str}).dropna()
        waterlevels.rename(columns={'well id':'timestamp'},inplace=True)
        # strip off minutes, seconds, milliseconds, etc.
        waterlevels['timestamp'] = waterlevels['timestamp'].apply(lambda x: x[0:16])
        count_with_dupes = len(waterlevels)
        # TODO drop duplicates?
        waterlevels.drop_duplicates(subset=['timestamp'], inplace=True)
        count_without_dupes = len(waterlevels)
        if count_without_dupes == count_with_dupes:
            print(f'\t...{count_without_dupes} waterlevel records')
        else:
            print(f'\t...{count_without_dupes} waterlevel records, removed {count_with_dupes - count_without_dupes} duplicates')

        elevations = pd.read_excel(file['filename'], sheet_name=f'{file['label']} ground', dtype={'well location': str})
        elevations.rename(columns={'well location':'well id'},inplace=True)
        print(f'\t...{len(elevations)} survey stations along profile')

        # same format as elevations but limited to the rows corresponding to well locations
        wells = elevations.dropna().copy()
        wells.set_index('well id', inplace=True)
        print(f'\t...{len(wells)} well records')

        waterlevels_output_filename = os.path.join(output_dir, f'{file['label'].replace(' ','_')}_waterlevels.json')
        wells_output_filename = os.path.join(output_dir, f'{file['label'].replace(' ','_')}_wells.json')
        elevations_output_filename = os.path.join(output_dir, f'{file['label'].replace(' ','_')}_elevations.json')

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