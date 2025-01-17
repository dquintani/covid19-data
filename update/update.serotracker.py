#!/usr/bin/env python
# coding: utf-8

import re
import csv
import json
import requests
import unidecode

import numpy as np
import pandas as pd

import update_utils


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)',
    'x-time-zone': 'America/La_Paz'
}


def format_column(column_name):
    column_name = column_name.lower()
    column_name = column_name.replace(',', '')
    column_name = column_name.replace('(s)', '')
    column_name = column_name.replace('(jbi)', '')
    column_name = column_name.replace('(archive)', '')
    column_name = column_name.replace('(granular)', '')

    column_name = column_name.replace('(', '')
    column_name = column_name.replace(')', '')

    column_name = column_name.strip()
    column_name = '_'.join(column_name.split(' '))
    column_name = unidecode.unidecode(column_name)

    return column_name


FLOAT_COLUMNS = [
    'serum_positive_prevalence',
    'serum_pos_prevalence_95pct_ci_lower',
    'serum_pos_prevalence_95pct_ci_upper',
    'specificity',
    'sensitivity'
]
BASE_URL = 'https://airtable.com'
RESO_URL = BASE_URL + '/embed/shrtuN7F8x4bdkdDA'
def fetch_data():
    cdata = requests.get(RESO_URL, headers=HEADERS)
    cdata = cdata.text

    urlWithParams = next(_ for _ in cdata.split('\n') if _.startswith('urlWithParams'))
    urlWithParams = urlWithParams.split(':', 1)[1].strip()
    urlWithParams = urlWithParams.encode('utf-8').decode('unicode_escape')
    urlWithParams = urlWithParams[1:-2]

    reqHeaders = next(_ for _ in cdata.split('\n') if _.startswith('var headers'))
    reqHeaders = json.loads(reqHeaders.split('=', 1)[1].strip()[:-1])

    cdata = requests.get(
        BASE_URL + urlWithParams,
        headers=dict(**reqHeaders, **HEADERS)
    )
    json_data = cdata.json()

    data_columns = json_data['data']['table']['columns']
    store_data = []

    for data_row in json_data['data']['table']['rows']:
        data_row = data_row['cellValuesByColumnId']
        store_row = {}

        for column in data_columns:
            if column['id'] not in data_row:
                continue

            data = data_row[column['id']]

            if type(data) == dict and 'valuesByForeignRowId' in data:
                data = data['valuesByForeignRowId']
                data = list(data.values())[0]

            if column['type'] == 'select':
                data = [data]

            if column['type'] in ['select', 'multiSelect']:
                column_choices = column['typeOptions']['choices']
                data = [column_choices[_]['name'] for _ in data]

            if type(data) == list:
                data = '; '.join(data)

            store_row[column['name']] = data

        store_data.append(store_row)

    store_data = pd.DataFrame.from_dict(store_data)
    store_data.columns = [format_column(_) for _ in store_data.columns]

    store_data = store_data.drop(columns='last_modified_time', errors='ignore')

    store_data['publication_date'] = store_data['publication_date'].str.slice(0, 24)
    store_data_columns = [_ for _ in store_data.columns if 'date' in _]
    store_data[store_data_columns] = store_data[store_data_columns].apply(
        lambda _: pd.to_datetime(_).dt.tz_localize(None)
    )

    store_data['date_created'] = store_data['date_created'].astype('datetime64[D]')
    store_data['test_manufacturer'] = store_data['test_manufacturer'].fillna('NR')

    store_data[FLOAT_COLUMNS] = store_data[FLOAT_COLUMNS].round(3)

    string_columns = [_ for _ in store_data.columns if hasattr(store_data[_], 'str')]

    for column in string_columns:
        store_data[column] = store_data[column].str.strip()
        store_data[column] = store_data[column].str.replace(
            r'(\r\n)+', '; ', regex=True
        ).str.replace(
            r'[\n]+', '; ', regex=True
        )

    return store_data


level0_patch = {
    'Congo': 'Democratic Republic of the Congo',
    'Czechia': 'Czech Republic',
    'Iran (Islamic Republic of)': 'Iran',
    'occupied Palestinian territory (including east Jerusalem)': 'Palestinian Territory',
    'occupied Palestinian territory, including east Jerusalem': 'Palestinian Territory',
    'occupied Palestinian territory - including east Jerusalem': 'Palestinian Territory',
    'occupied Palestinian territory': 'Palestinian Territory',
    'Republic of Korea': 'South Korea',
    'Russian Federation':  'Russia',
    'The United Kingdom': 'United Kingdom',
    'United Kingdom of Great Britain and Northern Ireland': 'United Kingdom',
    'United States of America': 'United States',
    'Viet Nam': 'Vietnam',
    'Lao People\'s Democratic Republic': 'Laos',
    'Venezuela (Bolivarian Republic of)': 'Venezuela',
    'Syrian Arab Republic': 'Syria',
}


level1_patch = {
    'brussels-capital': 'Brussels',
    'sao paolo': 'Sao Paulo',
    'greater sao paulo': 'Sao Paulo',
    'british colombia': 'British Columbia',
    'shanghai municipality': 'Shanghai',
    'wuhan': 'Hubei',
    'capital district cundinamarca': 'Bogota',
    'central bohemian': 'Central Bohemia',
    'brno / south moravian': 'South Moravian',
    'olomouc / olomouc': 'Olomoucky',
    'south-kivu': 'South Kivu',
    'kinhasa': 'Kinshasa',
    'copenhagen': 'Copenhague',
    'capital  and  zealand': 'Capital Region',
    'diredawa': 'Dire Dawa',
    'somme': 'Hauts-de-France',
    'paris': 'Ile-de-France',
    'ile de france': 'Ile-de-France',
    'grand-est': 'Grand Est',
    'île-de-france and grand est': 'Ile-de-France',
    'mecklenburg-westpomerania': 'Mecklenburg-Vorpommern',
    'heinsberg': 'North Rhine-Westphalia',
    'nct delhi': 'Delhi',
    'karnatka': 'Karnataka',
    'srinagar': 'Jammu and Kashmir',
    'haryan': 'Haryana',
    'madya pradesh': 'Madhya Pradesh',
    'national capital territory of delhi': 'Delhi',
    'andhra': 'Andhra Pradesh',
    'guilan': 'Gilan',
    'sistan and balouchestan': 'Sistan and Baluchestan',
    'udine': 'Friuli Venezia Giulia',
    'prato': 'Tuscany',    
    'trento': 'Trentino-Alto Adige',
    'avellino in the campania': 'Campania',
    'naples': 'Campania',
    'turin': 'Piedmont',
    'le marche': 'The Marches',
    'emilia romagna': 'Emilia-Romagna',
    'province of modena': 'Emilia-Romagna',
    'modena': 'Emilia-Romagna',
    'verona': 'Veneto',
    'padova': 'Veneto',
    'province of padova': 'Veneto',
    'brescia': 'Lombardy',
    'province of brescia': 'Lombardy',
    'foggia': 'Apulia',
    'province of foggia': 'Apulia',
    'tokyo prefecture': 'Tokyo',
    'nairobi': 'Nairobi Area',
    'southern  malawi': 'Southern Region',
    'midhordland': 'Hordaland',
    'karachi': 'Sindh',
    'lima and callao': 'Lima Region',
    'mazowieckie': 'Mazovia',
    'silesian voivodeship': 'Silesia',
    'silesian': 'Silesia',
    'opole': 'Opole Voivodeship',
    'north gyeongsang': 'Gyeongsangbuk-do',
    'chungbuk': 'North Chungcheong',
    'tyumen': 'Tyumenskaya',
    'republic of tartarstan': 'Tatarstan',
    'mecca': 'Makkah',
    'kwazulu natal': 'KwaZulu-Natal',
    'alacant': 'Valencia',
    'zaragoza': 'Aragon',
    'alicante': 'Valencia',
    'salamanca': 'Castille and Leon',
    'na & zaragoza': 'Aragon',
    'barcelona': 'Catalonia',
    'uppland': 'Stockholm',
    'sodermanland and uppland': 'Stockholm',
    'sodermanland, uppland': 'Stockholm',
    'norbotten': 'Norrbotten',
    'south east england': 'England',
    'east of england': 'England',
    'greater london': 'England',
    'east midlands': 'England',
    'england and wales': 'England',
    'london': 'England',
    'west midlands': 'England',
    'emirate of abu dhabi': 'Abu Dhabi',
    'washington d.c': 'District of Columbia',
    'atlanta': 'Georgia',
    'minesota': 'Minnesota',
    'indiada': 'Indiana',
    'antwerp province': 'Flemish Region',
    'department of vaupes': 'Vaupes',
    'copenhagen': 'Capital Region',
    'karaganda': 'Qaraghandy',
    'gaza': 'Gaza Strip',
    'skopje': 'Grad Skopje'
}


def resolve_iso3166(store_data):
    iso_level_0, iso_geo_names, geo_names = update_utils.fetch_geocodes(
        trim_admin_level=False
    )
    specific_geography = store_data['specific_geography'].str.split(
        ';', expand=True
    )

    specific_geography[1] = specific_geography[1].fillna('').str.strip()
    specific_geography[2] = specific_geography[2].str.cat(
        specific_geography.loc[:, 3:], sep=', ', na_rep='--'
    )
    specific_geography[2] = specific_geography[2].str.replace(
        ', --', ''
    ).str.strip().replace('--', '')

    specific_geography = specific_geography.T.dropna()
    specific_geography = specific_geography.T.replace('', np.nan)

    specific_geography[0] = specific_geography[0].str.replace('"', '')
    specific_geography[0] = specific_geography[0].replace(level0_patch)
    specific_geography[0] = specific_geography[0].replace(r'(.*),.*', r'\1', regex=True)

    iso_level_0 = iso_level_0.stack().droplevel(1)
    iso_level_0 = iso_level_0.reset_index().drop_duplicates().set_index(0)
    specific_geography[0] = iso_level_0.loc[specific_geography[0]].values

    for key, group_geography in specific_geography.groupby(0):
        if key is np.nan:
            continue

        data_adm1 = group_geography[1].replace('NR', np.nan).dropna()

        if len(data_adm1) < 1:
            continue

        data_adm1 = data_adm1.apply(unidecode.unidecode).str.lower()
        country_geo_names = geo_names[geo_names['geocode'].str.startswith(key)]

        missing = data_adm1[~data_adm1.isin(country_geo_names.index)]
        missing = missing.str.replace(
            update_utils.RE_PREFIX, ''
        ).str.replace(
            update_utils.RE_ARTICLE, ''
        ).str.strip()
        missing = missing.replace(level1_patch).str.lower()

        data_adm1.loc[missing.index] = missing
        data_adm1 = data_adm1.map(country_geo_names['geocode'].to_dict())

        specific_geography.loc[data_adm1.index, 1] = data_adm1

    specific_geography[1] = specific_geography[1].replace('NR', np.nan)

    store_data['adm0_isocode'] = specific_geography[0]
    store_data['adm1_isocode'] = specific_geography[1]

    return store_data


STORAGE_FILE = './raw/serotracker.csv'
if __name__ == '__main__':
    store_data = fetch_data()
    store_data = resolve_iso3166(store_data)

    store_data = store_data.set_index([
        'date_created', 'prevalence_estimate_name'
    ])
    store_data = store_data.sort_index()

    store_data.to_csv(STORAGE_FILE, quoting=csv.QUOTE_NONNUMERIC)
