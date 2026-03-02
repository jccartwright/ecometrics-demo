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
    results = []
    for col in df.items():
        # col[0] is column name
        results.append({
            'x': col[1]['station'],
            'z': col[1]['ground elevation']
        })
    with open(output_filename, "w") as file:
        json.dump(results, file, indent=2)


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
def write_waterlevels(df, wells, beaverdams, output_filename):
    # because we're not using Pandas to_json methods, explicitly replace the NaN values with null
    # TODO why doesn't this work?
    # df_filled = df.fillna(value=None)
    df_filled = df.replace(np.nan, None)
    results = []
    for row in df_filled.iterrows():
        dt = row[0]
        record = {
            "label": dt,
            "values": []
        }
        # add beaverdams attributes if necessary
        if not pd.isnull(beaverdams.loc[dt]['mimicry']):
            record['mimicry'] = beaverdams.loc[dt]['mimicry']
        if not pd.isnull(beaverdams.loc[dt]['beavers']):
            record['beavers'] = beaverdams.loc[dt]['beavers']

        for col in row[1].items():
            station = col[0]
            waterlevel = col[1]
            # although waterlevel values usually only appear at wells, they may appear at any station
            if not pd.isnull(waterlevel):
                # flag "below sensor" readings
                if col[1] == "BS":
                    sensor = wells.loc['sensor elev'][station]
                    record['values'].append({ "x": station, "z": sensor, "bs": True})
                else:
                    record['values'].append({ "x": station, "z": waterlevel})
        # add record for this timestamp
        results.append(record)

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
def write_wells(df, output_filename):
    results = []
    for col in df.items():
        # col[0] is column name
        results.append({
            'x': col[1]['station'],
            'surface': col[1]['ground elevation'],
            'sensor': col[1]['sensor elev'],
            'id': col[1]['well id'],
            'min_z': col[1]['min'],
            'max_z': col[1]['max']
        })
    with open(output_filename, "w") as f:
        json.dump(results, f, indent=2)


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
        # workbook basename (w/o path or file extension == worksheet name == basename of output files
        input_files.append(
            {
                'filename': os.path.join(input_dir, excel_file),
                'label': excel_file.split('.')[0],
            })
    with open(os.path.join(output_dir, 'input_files.json'), 'w') as file:
        # TODO simplify now that basename of input file matches that of output file?
        prefixes = [ i['label'].replace(' ','_') for i in input_files]
        json.dump(prefixes, file)

    # for file in input_files[0:1]:
    for file in input_files:
        # Excel file expected to contain a single worksheet named to match file basename. Sheet is organized with one
        # column for each surveyed location (i.e. Station).
        # First five rows are metadata:
        #   beavers (activity and mimicry)
        #   station (distance along profile)
        #   ground elevation
        #   sensor elev (height of sensor w/in well)
        #   well id (string uniquely identifying well along profile)
        print(f'processing {file["filename"]}...')

        try:
            # read worksheet and drop any rows where all fields are null
            df = pd.read_excel(file['filename'], sheet_name=file['label'], header=None, index_col=0).dropna(how='all')
            # remove rows with no timestamp value. Not caught on import due to spurious values in beaverdams columns
            df = df[df.index.notna()]

            # create new "beaverdams" dataframe with two columns, "mimicry", "beavers", indexed by timestamp
            beaverdams = df.iloc[5:, [-2, -1]].copy()
            beaverdams.name = 'beaver dams'
            beaverdams.columns = ['mimicry', 'beavers']
            try:
                beaverdams.index = beaverdams.index.map(lambda x: x.strftime('%Y-%m-%d %H:%M'))
            except:
                print(beaverdams.index)
            # having made a copy, remove the two beaverdams columns from original dataframe
            df.drop(columns=df.columns[[-2,-1]], inplace=True)

            # series of station values to use as column labels
            stations = df.iloc[1].copy(deep=True)

            # create dataframe with two rows (station, ground elevation) and column for each location
            elevations = df.iloc[1:3].copy(deep=True)

            # create dataframe with four rows (Station, ground elevation, sensor elevation, well_id) and column for each well
            wells = df.iloc[1:5].copy(deep=True)
            # drop all columns except for those with wells
            wells.dropna(axis=1, subset=['well id'], inplace=True)
            well_ids = wells.loc['well id']
            # label columns by station rather than well id to match elevations, waterlevels
            wells.columns = wells.loc['station'].tolist()

            # create waterlevel dataframe
            # drop "header" rows
            waterlevels = df.drop(['beaver dams','station','ground elevation','sensor elev','well id'], axis=0)
            # convert timestamp to string with hour precision
            waterlevels.index = waterlevels.index.map(lambda x: x.strftime('%Y-%m-%d %H:%M'))
            waterlevels.columns = stations.tolist()

            # calc min/max for each well and add to dataframe. exclude rows marked as "below sensor"
            well_values = waterlevels[wells.loc['station'].tolist()]
            min_values = well_values[waterlevels != 'BS'].min(skipna=True)
            min_values.name = 'min'
            max_values = well_values[waterlevels != 'BS'].max(skipna=True)
            max_values.name = 'max'
            wells.loc['min'] = min_values
            wells.loc['max'] = max_values

            # drop columns which contain no waterlevel measurements. Some columns w/o wells may contain values
            waterlevels.dropna(axis=1, how='all', inplace=True)

            # TODO check for duplicate timestamps
            # if waterlevels.index.has_duplicates:
            #     msg = f'file {file["filename"]} contains duplicate timestamps'
            #     logging.error(msg)
            #     raise Exception(msg)
            print(f'\t...{len(waterlevels)} waterlevel records')
            print(f'\t...{len(elevations.loc['station'])} survey stations along profile')
            print(f'\t...{len(wells.loc['well id'])} well records')

        except Exception as e:
            logging.error(e)
            logging.error(f'file {file["filename"]} is not formatted correctly. skipping...')
            continue

        waterlevels_output_filename = os.path.join(output_dir, f'{file['label']}_waterlevels.json')
        wells_output_filename = os.path.join(output_dir, f'{file['label']}_wells.json')
        elevations_output_filename = os.path.join(output_dir, f'{file['label']}_elevations.json')

        write_waterlevels(df=waterlevels, wells=wells, beaverdams=beaverdams, output_filename=waterlevels_output_filename)
        write_wells(df=wells, output_filename=wells_output_filename)
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