import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import coronatracker as ct


def make_plots(data: [pd.DataFrame]):
    """
    Generates the plots displayed in tweets posted by this bot.
    :param data: A list of DataFrames. The first frame should contain all the JHU data for the U.S, and the second
    frame should contain time series information.
    """
    print('Attempting to build plots!')
    ct.logger.info('Making plots...')

    us_frame = data[0]
    ts_data = data[1]
    # Threshold number of cases needed to be displayed
    case_limit = 20
    has_many_cases = us_frame.cases > case_limit
    us_frame = us_frame[has_many_cases]

    # General Plot Setup. Plots are "shown" then immediately closed to refresh the figure
    plt.style.use('fivethirtyeight')

    for jhu_tick in plt.xticks()[1]:
        jhu_tick.set_rotation(45)

    plt.suptitle('COVID-19 Details for the United States')
    # Plot setup for CDC figure
    # cdc_ax.bar(x=cdc_frame['measure'], height=cdc_frame['counts'])
    # cdc_ax.set_xlabel('Test Result')
    # cdc_ax.set_ylabel('Count')
    # cdc_ax.set_title('U.S COVID-19 Cases and Transmission Route')

    # Plot setup for JHU figure
    state_frame = ct.make_state_frame(us_frame)
    pos = np.arange(len(state_frame['state']))
    width = 0.7
    # Interval is [Start, Stop) so we need to go one more
    plt.gcf().set_size_inches(14, 14)
    plt.yticks(np.arange(start=0, stop=state_frame['cases'].max() + 1, step=20))
    case_bar = plt.bar(pos, state_frame['cases'], width, label='Cases')
    death_bar = plt.bar(pos, state_frame['deaths'], width, label='Deaths')
    recov_bar = plt.bar(pos, state_frame['recoveries'], width,
                        bottom=state_frame['deaths'], label='Recoveries')

    plt.xlabel('State')
    plt.ylabel('Count')
    plt.title(f'Confirmed COVID-19 Case Statistics in U.S States with at least {case_limit} Cases')
    plt.xticks(pos, state_frame['state'].tolist(), fontsize=10)
    plt.legend((case_bar[0], death_bar[0], recov_bar[0]), ('Cases', 'Deaths', 'Recoveries'), loc='upper right')
    plt.savefig(ct.plot_path + 'state_sum.png')
    plt.show(block=False)
    plt.close()

    # Time Series Plot
    freqs = get_country_cumulative(ts_data)
    make_time_series_plot(freqs)

    ct.logger.info('Created plots!')


def make_time_series_plot(freqs: list):
    """
    Creates a simple line plot of the number of cases for each day of the outbreak
    :param freqs: The number of cases for each day of the outbreak
    """

    days = len(freqs)
    fig, (reg_ax, log_ax) = plt.subplots(1, 2)

    fig.set_size_inches(12, 10)

    fig.suptitle('Cumulative Cases per Day in the United States (Standard Scale and Natural Log)')

    reg_ax.plot(np.arange(start=1, stop=days + 1), freqs, color='red')
    reg_ax.set_xlabel('Days Since 01/21/2020')
    reg_ax.set_ylabel('Number of cases')

    log_freqs = [math.log(freq) for freq in freqs]

    log_ax.plot(np.arange(start=1, stop=days + 1), log_freqs, color='red')
    log_ax.set_xlabel('Days Since 01/21/2020')
    log_ax.set_ylabel('Number of cases (Natural Log Scale)')

    plt.savefig(ct.plot_path + 'rate_plot.png')
    plt.show(block=False)
    plt.close()


def get_country_cumulative(data: pd.DataFrame) -> list:
    """
    Calculates the cumulative of new cases for the U.S each day
    :param data: A DataFrame containing time series data for cases
    :return: A list of the number of cases for each day
    """

    rates = [data[column].tolist() for column in data.columns if column != 'state' and column != 'city']
    daily_rates = [np.sum(day_rate) for day_rate in rates]

    return daily_rates

