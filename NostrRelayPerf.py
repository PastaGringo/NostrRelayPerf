#!/usr/bin/env python3

import argparse
import subprocess
import os
from nostr_sdk import Keys, Client, NostrSigner, EventBuilder, Filter, Metadata, Nip46Signer, init_logger, LogLevel, \
    NostrConnectUri
from datetime import timedelta
import datetime
import time
import sqlite3
import re
import asciichartpy
import sys

app_name = "NostrRelayPerf"

# Vérifier si le WebSocket est ouvert
def is_websocket_open(client):
    if client.is_connected():
        return True
    else:
        return False

def fetch_column_data(conn, site_name, column_name):
    try:
        c = conn.cursor()
        c.execute(f"SELECT {column_name} FROM {site_name}")
        rows = c.fetchall()
        return [row[0] for row in rows]
    except sqlite3.Error as e:
        print(e)

# Fonction pour afficher les données d'une table
def print_table_data(conn, table_name):
    try:
        c = conn.cursor()
        c.execute(f"SELECT * FROM {table_name}")
        rows = c.fetchall()
        if rows:
            # Obtenir les noms des colonnes
            columns = [description[0] for description in c.description]
            print(f"Columns of table '{table_name}':")
            print(f"Data from table '{table_name}':")
            print(columns)
            for row in rows:
                print(row)
        else:
            print(f"No data found in table '{table_name}'")
    except sqlite3.Error as e:
        print(e)

def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except sqlite3.Error as e:
        print(e)
    return conn

# Fonction pour créer une table pour un site
def create_site_table(conn, site_name):
    try:
        c = conn.cursor()
        c.execute(f'''CREATE TABLE IF NOT EXISTS {site_name}
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, read_ms INTEGER, write_ms INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    except sqlite3.Error as e:
        print(e)

# Fonction pour insérer une mesure pour un site
def insert_measure(conn, site_name, read_ms, write_ms):
    try:
        c = conn.cursor()
        c.execute(f"INSERT INTO {site_name} (read_ms, write_ms) VALUES (?, ?)", (read_ms, write_ms))
        conn.commit()
    except sqlite3.Error as e:
        print(e)

# Fonction pour effacer toutes les valeurs de la table
def clear_table_data(conn, table_name):
    try:
        c = conn.cursor()
        c.execute(f"DELETE FROM {table_name}")
        conn.commit()
        print(f"All data deleted from table '{table_name}'")
    except sqlite3.Error as e:
        print(e)

def GetWriteReadPerf(content, nostr_relay, db_filename):
    keys = Keys.parse("nsec1zksskfkqz7ycy0lm8dd3thfyekaq3hjeyvw3alx2zeftfq9qq7lq29cmv7")
    sk = keys.secret_key()
    pk = keys.public_key()
    signer = NostrSigner.keys(keys)
    client = Client(signer)
    nostr_relay_ws = f"wss://{nostr_relay}"
    client.add_relays([nostr_relay_ws])
    client.connect()
    start_time = time.time()
    start_time_human = datetime.datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')
    event = EventBuilder.text_note(content, []).to_event(keys)
    event_id = client.send_event(event)
    end_time = time.time()
    end_time_human = datetime.datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')
    write_elapsed_time_ms = round((end_time - start_time) * 1000)
    f = Filter().id(event_id)
    start_time = time.time()
    client.get_events_of([f], timedelta(seconds=10))
    end_time = time.time()
    read_elapsed_time_ms = round((end_time - start_time) * 1000)
    conn = create_connection(db_filename)
    site_name = nostr_relay
    site_name = re.sub(r'\W+', '_', site_name)
    create_site_table(conn, site_name)
    insert_measure(conn, site_name, read_elapsed_time_ms, write_elapsed_time_ms)
    conn.close()

def Welcome(nostr_relay):
    clear_console()
    nostr_relay_ws = f"wss://{nostr_relay}"
    site_name = nostr_relay
    site_name = re.sub(r'\W+', '_', site_name)
    print("")
    print("--- Welcome to", app_name, "---")
    print("")
    print("Verify if", app_name, "deps are available...")
    print("")
    print("Prepare local sqlite db...")
    #####################################################
    #GetWriteReadPerf("Testing write speed...", nostr_relay)
    print("")
    #####################################################
    print("Getting performances data from sqlite table...")
    db_filename = f"{nostr_relay}.db"
    conn = create_connection(db_filename)
    print_table_data(conn, site_name)
    print()
    #####################################################
    print("Displaying data...")
    action_count = 0
    while True:
        GetWriteReadPerf("Testing write speed...", nostr_relay, db_filename)
        action_count += 1
        if action_count == 60:
            clear_table_data(conn, site_name)
            action_count = 0

        # Récupérer les données de la table pour les temps d'écriture
        # Récupérer les données de la colonne pour les temps d'écriture
        write_values = fetch_column_data(conn, site_name, 'write_ms')

        # Récupérer les données de la colonne pour les temps de lecture
        read_values = fetch_column_data(conn, site_name, 'read_ms')

        # Créer un graphique ASCII pour les temps d'écriture
        write_chart = asciichartpy.plot(write_values, {'height': 15, 'colors': [asciichartpy.red]})

        # Créer un graphique ASCII pour les temps de lecture
        read_chart = asciichartpy.plot(read_values, {'height': 15, 'colors': [asciichartpy.green]})

        # Effacer l'écran
        clear_console()

        # Afficher les graphiques ASCII
        print(f"WRITE time in milliseconds from Nostr relay {nostr_relay_ws}:")
        print(write_chart)
        print()
        print(f"READ time in milliseconds from Nostr relay {nostr_relay_ws}:")
        print(read_chart)

        # Attendre avant de rafraîchir les données
        time.sleep(1)  # Rafraîchissement toutes les 5 secondes

def clear_console():
    subprocess.call('cls' if os.name == 'nt' else 'clear', shell=True)

def main():
    parser = argparse.ArgumentParser(description="Nostr Relay Performance Monitor")
    parser.add_argument("-r", "--relay", help="Nostr relay hostname", required=False)
    args = parser.parse_args()
    nostr_relay = args.relay

    if not nostr_relay:
        print("usage: nostrelayperf.py [-h] -r RELAY | --relay RELAY", file=sys.stderr)
        print("nostrelayperf.py: ERROR: a Nostr relay without WSS:// is required.", file=sys.stderr)
        print("For instance: nostrelayperf.py -r nostr.fractalized.net")
        print("The script won't check if Nostr relay websocket is healthy. Please verify your Nostr relay URL and state otherwise script will display wrong data.")
        return

    Welcome(nostr_relay)

if __name__ == "__main__":
    main()
