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
        logging.error(f'Could not parse date {datetime_str}')
        return None

'''
Process surveyed elevation points along profile

reads CSV file exported from Excel and reformats and exports as JSON file more 
suitable for use with D3 charts.

WARNING: code is tightly coupled to Excel spreadsheet format

output attribute names shortened to minimize file size:
    x: distance along profile in feet
    z: water level in feet

 e.g.
    [
        {
            "x": 15.7,
            "z": 10266.88
        },
        ...
    ]
'''
def write_elevations(data, output_filename):
    results = []
    for col in data.items():
        # col[0] is column name
        results.append({
            'x': col[0],
            'z': col[1]
        })
    with open(output_filename, "w") as file:
        json.dump(results, file, indent=2)


'''
given a series of the interpolated waterlevel measurements for a given profile and timestamp, calculate the 
area of surface water and unsaturated ground
'''
def calculate_areas(measurements, elevations):
    max_values = pd.concat([measurements,elevations], axis=1).max(axis=1)
    max_values.name = 'max'
    max_area = np.trapz(max_values, measurements.index)
    ground_area = np.trapz(elevations, measurements.index)
    waterlevel_area = np.trapz(measurements, measurements.index)
    surface_water_area = max_area - ground_area
    unsaturated_area = max_area - waterlevel_area

    return [round(surface_water_area), round(unsaturated_area)]


'''
Process water level data

reads CSV file exported from Excel and reformats and exports as JSON file more 
suitable for use with D3 charts.

WARNING: code is tightly coupled to Excel spreadsheet format

output attribute names shortened to minimize file size:
    id: well id
    x: distance along profile in feet
    z: water level in feet

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
def write_waterlevels(df, df2, wells, elevations, beaverdams, output_filename):
    results = []
    for row in df.iterrows():
        # elements: timestamp (index), waterlevels (value)
        dt = row[0]
        record = {
            "label": dt,
            "measured": [],
            "interpolated": []
        }
        # add beaverdams attributes if necessary
        if pd.notna(beaverdams.at[dt,'mimicry']):
            record['mimicry'] = beaverdams.at[dt,'mimicry']
        if pd.notna(beaverdams.at[dt,'beavers']):
            record['beavers'] = beaverdams.at[dt,'beavers']

        s = row[1]
        # only write out non-null waterlevels
        for col in s[s.notna()].items():
            station = col[0]
            waterlevel = col[1]
            # flag "below sensor" readings
            if waterlevel == 'BS':
                sensor = wells.loc['sensor elev'][station]
                record['measured'].append({ "x": station, "z": sensor,"bs": True})
            else:
                record['measured'].append({ "x": station, "z": waterlevel})

        # interpolated values have waterlevel value at all stations
        s = df2.loc[dt]

        # calculate areas and add to record
        surface_water_area, unsaturated_area = calculate_areas(s, elevations)
        record['surface_water_area'] = surface_water_area
        record['unsaturated_area'] = unsaturated_area

        for col in s.items():
            record['interpolated'].append({ "x": col[0], "z": round(col[1], 3)})

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

# expects incoming dataframe to have 4 "header" rows: station, ground elevation, sensor elevation, well id
def calculate_wells(df):
    wells = df.iloc[0:4].copy(deep=True)
    # drop all columns except for those with wells
    wells.dropna(axis=1, subset=['well id'], inplace=True)
    well_ids = wells.loc['well id']
    # label columns by station rather than well id to match elevations, waterlevels
    # TODO way to avoid duplicate station values? one in column label, one in first row of dataframe
    wells.columns = wells.loc['station']
    # slightly different behavior
    # wells.columns = wells.loc['station'].tolist()
    # wells.index.name = 'station'
    # temporary dataframe with just the waterlevel values
    tmp_df = df[4:].copy(deep=True)
    tmp_df.columns = df.loc['station']
    # just the waterlevel columns with wells
    well_values = tmp_df[wells.loc['station']]

    # TODO "below sensor" flag will be changing from 'BS' to -9999
    min_values = well_values[tmp_df != 'BS'].min(skipna=True)
    min_values.name = 'min'
    max_values = well_values[tmp_df != 'BS'].max(skipna=True)
    max_values.name = 'max'

    # append to wells dataframe
    wells.loc['min'] = min_values
    wells.loc['max'] = max_values
    # return wells.drop(['station'], axis=0)
    return wells


def calculate_interpolated_waterlevels(waterlevels, wells):
    df = waterlevels.copy(deep=True)
    # replace BS flags with corresponding sensor elevation
    for row in df.iterrows():
        dt = row[0]
        for col in row[1].items():
            station = col[0]
            if col[1] == 'BS':
                df.at[dt,station] = wells.at['sensor elev',station]
    df = df.astype(float)
    df.interpolate(axis=1,limit_direction='both',method='index', inplace=True)
    return df

def main(args):
    if not os.path.exists(args.manifest):
        logging.error(f'file {args.manifest} does not exist')
        return

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # default to directory containing the manifest file
    if not args.input_dir:
        input_dir = os.path.dirname(args.manifest)
    else:
        input_dir = args.input_dir

    with open(args.manifest, 'r') as file:
        files_manifest = [i.strip() for i in  file.readlines()]

    input_files = []
    for excel_file in files_manifest:
        xl = pd.ExcelFile(os.path.join(input_dir, excel_file))
        # workbook basename (w/o path or file extension == worksheet name == basename of output files
        input_files.append(
            {
                'filename': os.path.join(input_dir, excel_file),
                'label': excel_file.split('.')[0],
            })

    # Webapp needs a JSON file listing file basenames
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
        logging.info(f'processing {file["filename"]}...')

        waterlevels_output_filename = os.path.join(output_dir, f'{file['label']}_waterlevels.json')
        wells_output_filename = os.path.join(output_dir, f'{file['label']}_wells.json')
        elevations_output_filename = os.path.join(output_dir, f'{file['label']}_elevations.json')

        try:
            # read worksheet and drop any rows where all fields are null
            df = pd.read_excel(file['filename'], sheet_name=file['label'], header=None, index_col=0).dropna(how='all')
            # remove rows with no timestamp value. Not caught on import due to spurious values in beaverdams columns
            df = df[df.index.notna()]
            # create new "beaverdams" dataframe with two columns, "mimicry", "beavers", indexed by timestamp
            beaverdams = df.iloc[5:, -2:].copy()
            beaverdams.name = 'beaver dams'
            beaverdams.index.name = 'datetime'
            beaverdams.columns = ['mimicry', 'beavers']
            try:
                beaverdams.index = beaverdams.index.map(lambda x: x.strftime('%Y-%m-%d %H:%M'))
            except:
                logging.error(f'failed to convert index to datetime: {beaverdams.index}')
            # having made a copy, remove the two beaverdams columns from original dataframe
            df.drop(columns=df.columns[[-2,-1]], inplace=True)
            df.drop(['beaver dams'], axis=0, inplace=True)

            # series of station values to use as column labels
            stations = df.loc['station'].copy()
            # TODO why are some 'float' and others 'float64'?
            stations = stations.astype(float)

            # create series of ground level measurements indexed by stations
            elevations = df.loc['ground elevation'].copy()
            elevations.index = stations

            # create a dataframe with just the wells
            wells = calculate_wells(df)

            # create waterlevel dataframe
            # drop "header" rows
            waterlevels = df.drop(['station','ground elevation','sensor elev','well id'], axis=0).copy(deep=True)
            # convert timestamp to string with hour precision
            waterlevels.index = waterlevels.index.map(lambda x: x.strftime('%Y-%m-%d %H:%M'))
            waterlevels.columns = stations
            # waterlevels.index.name = 'datetime'

            interpolated_waterlevels = calculate_interpolated_waterlevels(waterlevels, wells)

            # drop columns from measured values dataframe which contain no waterlevel measurements.
            # Note that some columns w/o wells may contain values
            waterlevels.dropna(axis=1, how='all', inplace=True)

            # TODO check for duplicate timestamps
            # if waterlevels.index.has_duplicates:
            #     msg = f'file {file["filename"]} contains duplicate timestamps'
            #     logging.error(msg)
            #     raise Exception(msg)
            logging.info(f'\t...{len(waterlevels)} waterlevel records')
            logging.info(f'\t...{len(elevations)} survey stations along profile')
            logging.info(f'\t...{len(wells.loc['well id'])} well records')

            write_waterlevels(df=waterlevels, df2=interpolated_waterlevels, elevations=elevations, wells=wells, beaverdams=beaverdams, output_filename=waterlevels_output_filename)
            write_wells(df=wells, output_filename=wells_output_filename)
            write_elevations(data=elevations, output_filename=elevations_output_filename)

        except Exception as e:
            logging.error(e)
            logging.error(f'file {file["filename"]} is not formatted correctly. skipping...')
            continue


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