import csv
import argparse
import os
import json
import datetime

DELAYS = [
    # Delay details
    'CARRIER_DELAY', 'WEATHER_DELAY', 'NAS_DELAY', 'SECURITY_DELAY', 'LATE_AIRCRAFT_DELAY']

HEADERS = [
              # Time
              'YEAR', 'MONTH', 'DAY_OF_MONTH',

              # Origin airport details
              'ORIGIN_STATE_ABR', 'ORIGIN_STATE_NM',

              # Destination airport details
              'DEST_STATE_ABR', 'DEST_STATE_NM',

              # Departure details
              'CRS_DEP_TIME', 'DEP_TIME', 'DEP_DELAY_NEW', 'TAXI_OUT', 'WHEELS_OFF',

              # Arrival details
              'CRS_ARR_TIME', 'ARR_TIME', 'ARR_DELAY_NEW', 'TAXI_IN', 'WHEELS_ON',

              # FLight details
              'CRS_ELAPSED_TIME', 'ACTUAL_ELAPSED_TIME', 'AIR_TIME', 'DISTANCE',

          ] + DELAYS

DERIVED_HEADERS = [
    'AIRLINE_NAME',  # From OP_UNIQUE_CARRIER using L_unique carriers
    'ORIGIN_AIRPORT_NAME',  # From ORIGIN using L_airport
    'DEST_AIRPORT_NAME',  # From DEST using L_airport
]

months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

AIRPORT_MAPPING = dict()
AIRLINES_MAPPING = dict()


def load_mapping(filepath):
    mapping = dict()
    with open(filepath, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            mapping[row['Code']] = row['Description']
    return mapping


def load_airports(path):
    AIRPORT_MAPPING.update(load_mapping(path + '/L_AIRPORT.csv'))
    # print(f"Loaded {len(AIRPORT_MAPPING)} Airports")


def load_airlines(path):
    AIRLINES_MAPPING.update(load_mapping(path + '/L_UNIQUE_CARRIERS.csv'))
    # print(f"Loaded {len(AIRLINES_MAPPING)} Airlines")


dataset = []

airlines_to_filter = dict()
origins_to_filter = dict()
dest_to_filter = dict()


def check_delay(row):
    for delay in DELAYS:
        if row[delay] and int(float(row[delay])) > 0:
            return True
    return False


def is_weekday(row):
    date = datetime.date(int(row['YEAR']), int(row['MONTH']), int(row['DAY_OF_MONTH']))
    return date.weekday() < 5


def add_derived_data(extracted_row, row):
    extracted_row['AIRLINE_NAME'] = AIRLINES_MAPPING[row['OP_UNIQUE_CARRIER']]
    extracted_row['ORIGIN_AIRPORT_NAME'] = AIRPORT_MAPPING[row['ORIGIN']]
    extracted_row['DEST_AIRPORT_NAME'] = AIRPORT_MAPPING[row['DEST']]


def clean_data(extracted_row):
    for idx, delay in enumerate(DELAYS):
        extracted_row[delay] = int(float(extracted_row[delay]))


### Combine and select raw data

def preprocess(path):
    print(f"Pre process running !!")

    complete_data = 0
    total_size_approx = 0

    week_delay_map = []

    updated_headers = HEADERS[:]
    updated_headers.insert(4, DERIVED_HEADERS[0])
    updated_headers.insert(5, DERIVED_HEADERS[1])
    updated_headers.insert(8, DERIVED_HEADERS[2])
    write_header = True

    files = ['2023/'+m+'_23' for m in months] + ['2024/'+m+'_24' for m in months]
    for month, file in enumerate(files):
        total = 0
        parsed = 0
        file_name = '/' + file + '.csv'

        if not os.path.exists(path + file_name):
            print(f"File {file_name} does not exist!")
            continue

        print(f"\n{file}:")

        file_stats = os.stat(path + file_name)
        f_size = file_stats.st_size / (1000 * 1000)

        print(f"File size = {f_size:.2f} MB")

        week_delays = {
            'weekday': {
                'delays': [0, 0, 0, 0, 0],
                'no_delays': [0, 0, 0, 0, 0]
            },
            'weekend': {
                'delays': [0, 0, 0, 0, 0],
                'no_delays': [0, 0, 0, 0, 0]
            },
        }
        weekdays_count = 0
        with open(path + file_name, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if check_delay(row):
                    extracted_rows = {k: row[k] for k in HEADERS}

                    add_derived_data(extracted_rows, row)

                    clean_data(extracted_rows)

                    dataset.append(extracted_rows)

                k = 'weekday' if is_weekday(row) else 'weekend'
                if is_weekday(row): weekdays_count += 1
                for idx, delay in enumerate(DELAYS):
                    d = 'delays' if row[delay] and float(row[delay]) > 0 else 'no_delays'
                    week_delays[k][d][idx] += 1
                    parsed += 1
                total += 1

        complete_data += parsed
        print(f"Total={total} \t Parsed={parsed}")

        for week, values in week_delays.items():
            norm = weekdays_count if week == 'weekday' else total - weekdays_count
            for k in week_delays[week].keys():
                for i in range(5):
                    week_delays[week][k][i] = round(week_delays[week][k][i] * 100 / norm, 3)

        print(f"{file.split('/')[0]+'-'+str(month % 12 + 1)}, Delays: {week_delays}")
        week_delay_map.append({(file.split('/')[0]+'-'+str(month % 12 + 1)): week_delays})

        compressed = parsed / total
        print(f"Compressed = {compressed:.3f} %")
        total_size_approx += compressed * f_size

        with open(path + '/airlines_delay_data_v3.csv', 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, delimiter=',', fieldnames=updated_headers, extrasaction='ignore')
            if write_header:
                writer.writeheader()
                write_header = False
            for data in dataset:
                writer.writerow(data)

        dataset.clear()

    with open(path + '/all_week.json', 'w') as outfile:
        json.dump(week_delay_map, outfile)

    print(f"\nTotal data size = {complete_data}")
    print(f"Total size approx = {total_size_approx:.2f} MB")
    print(f"Pre process completed!!")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--Path', help='Data files path', required=True)
    args = parser.parse_args()
    datapath = args.Path

    load_airports(datapath)
    load_airlines(datapath)

    preprocess(datapath)
