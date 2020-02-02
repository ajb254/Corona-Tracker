import os
import time
import logging
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials
import gspread

jhu_path = os.getcwd() + '/jhu_data/'
cdc_path = os.getcwd() + '/cdc_data/'
plot_path = os.getcwd() + '/plots/'

now = datetime.now()
now_file_ext = now.strftime('%m_%d_%H_%M_%S.csv')

log_path = os.getcwd() + '/logs/coronatracker_log.log'
log_format = '%(levelname)s | %(asctime)s | %(message)s'

state_map = {'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'CA': 'California', 'CO': 'Colorado',
             'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii',
             'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky',
             'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan',
             'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska',
             'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
             'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon',
             'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota',
             'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington',
             'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming'}

if os.path.exists(os.getcwd() + '/logs/') is not True:
    try:
        os.mkdir(os.getcwd() + '/logs/')
    except OSError as error:
        print(f'Could not create log directory because {error.strerror}!')

logging.basicConfig(filename=log_path, format=log_format, filemode='w', level=logging.INFO)

logger = logging.getLogger()


def get_jhu_data() -> pd.DataFrame:
    """
    Connects to Google Sheets API and gets data for the United States from JHU's tracker
    :return A pandas dataframe with columns state, city, cases, deaths, recoveries
    """
    logger.info('Attempting to connect to JHU sheet')

    jhu_sheet_id = '1yZv9w9zRKwrGTaR-YzmAqMefw4wMlaXocejdxZaTs6w'
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(jhu_sheet_id)
    newest_sheet = sheet.worksheets()[0]

    us_cities = []
    us_states = []
    us_cases = []
    us_deaths = []
    us_recoveries = []

    for row in newest_sheet.get_all_values():
        region = row[0]
        country = row[1]
        cases = row[3]
        deaths = row[4]
        recoveries = row[5]

        if country == 'US':
            # Regions don't get entered unless they have cases, so we know we can always convert this
            cases = int(cases)

            # Deaths and recoveries are usually entered as a blank value if there are no values
            # so we have to be careful
            try:
                deaths = int(deaths)
                recoveries = int(recoveries)
            except ValueError:
                deaths = 0
                recoveries = 0

            city, state = region.split(',')

            us_states.append(state_map[state.replace(' ', '')])
            us_cities.append(city)
            us_cases.append(cases)
            us_deaths.append(deaths)
            us_recoveries.append(recoveries)

    data = {'state': us_states, 'city': us_cities, 'cases': us_cases, 'deaths': us_deaths, 'recoveries': us_recoveries}
    frame = pd.DataFrame(data)

    if frame.empty is not True:
        logger.info('Successfully downloaded JHU data! Saving as jhu_{}'.format(now_file_ext))

    frame.to_csv(jhu_path + 'jhu_' + now_file_ext)

    return frame


def get_data_for(name: str, var: str, data: pd.DataFrame, region='state') -> pd.Series:
    """
    Allows for selection of data by variable at the state or city level
    :param data: The dataframe to select from
    :param var: The variable to select. Valid inputs are cases, deaths, and recoveries
    :param name: The name of the location (i.e Berkeley or California)
    :param region: Whether to select based on state level data or city level data. Default is state. Valid inputs are
    city and state
    :return: A Series containing the requested data
    """

    if region == 'state':
        target_frame = data[data.state.str.contains(name)]

        return target_frame[var]
    elif region == 'city':
        target_frame = data[data.city.str.contains(name)]

        return target_frame[var]
    else:
        logger.warning('Received invalid region {}'.format(region))
        raise ValueError('Unknown region {}! Region must be either state or city!'.format(region))


def make_state_frame(data: pd.DataFrame) -> pd.DataFrame:
    """
    Creates a dataframe containing data at the state level
    :param data: The dataframe to ready values from
    :return: A data frame containing the same data from the JHU frame but organized at the state level
    """
    state_deaths = []
    state_cases = []
    state_recoveries = []
    states = []

    for state in data['state']:
        deaths = get_data_for(state, 'deaths', data)
        cases = get_data_for(state, 'cases', data)
        recoveries = get_data_for(state, 'recoveries', data)

        if state not in states:
            states.append(state)
            state_deaths.append(deaths.sum())
            state_cases.append(cases.sum())
            state_recoveries.append(recoveries.sum())

    ret_data = {'state': states, 'cases': state_cases, 'deaths': state_deaths, 'recoveries': state_recoveries}

    return pd.DataFrame(ret_data)


def is_new_data(recent_data: pd.DataFrame, source='jhu') -> bool:
    """
    Checks to see if the data that was recently fetched is the same as existing data
    :param recent_data: The most recently fetched data
    :param source: The type of data to load for comparison. Defaults to data from JHU
    :return: True or false depending on whether or not the recent_data dataframe is newer than the previous one
    """
    prev_data = pd.read_csv(source + now_file_ext)
    columns = ['state', 'cases', 'deaths', 'recoveries']
    is_new = False

    for column in columns:
        if recent_data[column] != prev_data[column]:
            is_new = True
            break

    return is_new


def get_cdc_data() -> pd.DataFrame:
    """
    Scans the web page at the URL listed below for a table containing test result status for the United States
    :return: A dataframe with the columns measure and counts
    """

    cdc_url = 'https://www.cdc.gov/coronavirus/2019-ncov/cases-in-us.html'
    cdc_page = requests.get(cdc_url)
    cdc_soup = BeautifulSoup(cdc_page.content, features='html.parser')

    measures = []
    values = []

    table = cdc_soup.find('table')
    rows = table.find_all('tr')

    for entry in rows:
        measure_name = str(entry.find('th').get_text()).replace('§', '').replace(':', '')
        measure_val = int(entry.find('td').get_text())

        if measure_name != 'Total':
            measures.append(measure_name)
            values.append(measure_val)

    data = {'measure': measures, 'counts': values}
    frame = pd.DataFrame(data)

    if frame.empty is not True:
        logger.info('Successfully downloaded CDC data! Saving as CDC_{}'.format(now_file_ext))

    frame.to_csv(cdc_path + 'cdc_' + now_file_ext)

    return frame


def load_all_data(data_type: str) -> []:
    """
    Loads all of the data from a directory of a given type. (Ex. All the data from the CDC directory
    :param data_type: What type of data to download. Valid types are jhu or cdc
    :return: A list of all files in the directory
    """
    data = []

    if data_type.lower() == 'cdc':
        data = [file for file in os.listdir(cdc_path)]
    if data_type.lower() == 'jhu':
        data = [file for file in os.listdir(jhu_path)]

    return data


def main(first_run=True):
    if first_run:
        if os.path.exists(cdc_path) is not True:
            try:
                os.mkdir(cdc_path)
            except OSError as error:
                logger.critical(f'Could not create CDC data directory because {error.strerror}!')
        if os.path.exists(jhu_path) is not True:
            try:
                os.mkdir(jhu_path)
            except OSError as error:
                logger.critical(f'Could not create JHU data directory because {error.strerror}!')
        if os.path.exists(plot_path) is not True:
            try:
                os.mkdir(plot_path)
            except OSError as error:
                logger.critical(f'Could not create plots directory because {error.strerror}!')

    logger.info('Starting tracker loop')

    spacer = ' ' * 10

    if first_run:
        print('=' * 50,
              '\n',
              spacer + '2019-nCoV Tracker (U.S)\n',
              '=' * 50)
        print('To break this program out of its loop, press Ctrl+C')

    us_frame = get_jhu_data()
    cdc_frame = get_cdc_data()

    print('Displaying plot!')
    # General Plot Setup
    fig, (jhu_ax, cdc_ax) = plt.subplots(1, 2, figsize=(20, 20))
    fig.suptitle('2019-nCoV Details for the United States')
    # Plot setup for CDC figure
    cdc_ax.bar(x=cdc_frame['measure'], height=cdc_frame['counts'])
    cdc_ax.set_xlabel('Test Result')
    cdc_ax.set_ylabel('Count')
    cdc_ax.set_title('Positive, Negative, and Pending 2019-nCoV Cases in the United States')
    # Plot setup for JHU figure
    state_frame = make_state_frame(us_frame)
    # Interval is [Start, Stop) so we need to go one more
    jhu_ax.set_yticks(np.arange(start=0, stop=state_frame['cases'].max() + 1))
    jhu_ax.bar(x=state_frame['state'], height=state_frame['cases'])
    jhu_ax.set_xlabel('State')
    jhu_ax.set_ylabel('Confirmed Cases')
    jhu_ax.set_title('Confirmed 2019-nCoV Cases in the United States by State')
    plt.savefig(plot_path + 'state_sum.png')
    plt.show()
    plt.close()
    # Plot setup for city data
    plt.title('2019-nCoV Cases by city')
    plt.gcf().set_size_inches(10, 10)
    plt.yticks(np.arange(start=0, stop=us_frame['cases'].max() + 1))
    plt.bar(x=us_frame['city'], height=us_frame['cases'])
    plt.xlabel('City')
    plt.ylabel('Confirmed Cases')
    plt.savefig(plot_path + 'city_sum.png')
    plt.show()
    plt.close()


    try:
        while True:
            print('Sleeping now for one minute! Will check for new data afterwards...')
            time.sleep(60)
            main(first_run=False)
            break
    except KeyboardInterrupt:
        print('Exiting...')


if __name__ == '__main__':
    main()