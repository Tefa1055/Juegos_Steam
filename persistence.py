# persistence.py

import csv
import os
from typing import List, Optional
from datetime import datetime # Importar si se usa en set_initial_ids o from_csv_row

# Importar los modelos y las listas de datos, y los contadores de ID desde models.py
# Asegurate de que estos esten correctamente definidos en models.py
from models import Game, PlayerActivity, games_data, player_activity_data, next_game_id, next_activity_id

# Definir los nombres de los archivos CSV y el directorio
DATA_DIR = 'data'
GAMES_CSV_FILE = os.path.join(DATA_DIR, 'games.csv')
PLAYER_ACTIVITY_CSV_FILE = os.path.join(DATA_DIR, 'player_activity.csv')

# Encabezados para los archivos CSV - deben coincidir con el orden en to_csv_row y from_csv_row
GAMES_CSV_HEADERS = ['id', 'title', 'developer', 'publisher', 'genres', 'release_date', 'price', 'tags', 'is_deleted']
PLAYER_ACTIVITY_CSV_HEADERS = ['id', 'game_id', 'timestamp', 'current_players', 'peak_players_24h', 'is_deleted']


def load_games_from_csv():
    """Carga los datos de los juegos desde el archivo games.csv."""
    print(f"Intentando cargar datos desde {GAMES_CSV_FILE}...")
    games_data.clear() # Limpiar la lista en memoria antes de cargar
    if not os.path.exists(GAMES_CSV_FILE):
        print(f"Archivo no encontrado: {GAMES_CSV_FILE}. Se creará uno nuevo al guardar.")
        # Asegurarse de que el directorio exista si no existe el archivo
        os.makedirs(DATA_DIR, exist_ok=True)
        # Opcional: crear un archivo vacío con encabezado si no existe
        # with open(GAMES_CSV_FILE, mode='w', newline='', encoding='utf-8') as outfile:
        #     writer = csv.writer(outfile)
        #     writer.writerow(GAMES_CSV_HEADERS)
        return

    with open(GAMES_CSV_FILE, mode='r', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        try:
            header = next(reader) # Leer la fila de encabezados
            if header != GAMES_CSV_HEADERS:
                 print(f"Advertencia: El encabezado de {GAMES_CSV_FILE} no coincide con el esperado. Encabezado leido: {header}")
                 # Dependiendo de la rigurosidad, podrías saltar el archivo o intentar adivinar
                 # Por ahora, asumimos que el primer registro despues del encabezado es data
        except StopIteration:
            # El archivo esta vacio (excepto quizas por el encabezado si se creo antes)
            print(f"Archivo {GAMES_CSV_FILE} esta vacio.")
            return # No hay datos para cargar

        for row in reader:
            # Omitir filas vacías si las hay
            if not row or len(row) < len(GAMES_CSV_HEADERS): # Tambien omitir filas incompletas
                continue
            try:
                # Crear un objeto Game desde la fila usando el método estático definido en models.py
                game = Game.from_csv_row(row)
                games_data.append(game)
            except ValueError as e:
                print(f"Error al procesar la fila en {GAMES_CSV_FILE}: {row} - Error: {e}")
                # Continuar con la siguiente fila para no detener la carga completa

    print(f"Cargados {len(games_data)} juegos desde {GAMES_CSV_FILE}.")


def load_player_activity_from_csv():
    """Carga los datos de actividad de jugadores desde el archivo player_activity.csv."""
    print(f"Intentando cargar datos desde {PLAYER_ACTIVITY_CSV_FILE}...")
    player_activity_data.clear() # Limpiar la lista en memoria antes de cargar
    if not os.path.exists(PLAYER_ACTIVITY_CSV_FILE):
        print(f"Archivo no encontrado: {PLAYER_ACTIVITY_CSV_FILE}. Se creará uno nuevo al guardar.")
         # Asegurarse de que el directorio exista si no existe el archivo
        os.makedirs(DATA_DIR, exist_ok=True)
        # Opcional: crear un archivo vacío con encabezado si no existe
        # with open(PLAYER_ACTIVITY_CSV_FILE, mode='w', newline='', encoding='utf-8') as outfile:
        #     writer = csv.writer(outfile)
        #     writer.writerow(PLAYER_ACTIVITY_CSV_HEADERS)
        return

    with open(PLAYER_ACTIVITY_CSV_FILE, mode='r', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        try:
            header = next(reader) # Leer la fila de encabezados
            if header != PLAYER_ACTIVITY_CSV_HEADERS:
                 print(f"Advertencia: El encabezado de {PLAYER_ACTIVITY_CSV_FILE} no coincide con el esperado. Encabezado leido: {header}")
                 # Dependiendo de la rigurosidad, podrías saltar el archivo o intentar adivinar
        except StopIteration:
             # El archivo esta vacio
            print(f"Archivo {PLAYER_ACTIVITY_CSV_FILE} esta vacio.")
            return # No hay datos para cargar


        for row in reader:
            if not row or len(row) < len(PLAYER_ACTIVITY_CSV_HEADERS): # Omitir filas vacias o incompletas
                continue
            try:
                 # Crear un objeto PlayerActivity desde la fila usando el metodo estatico en models.py
                activity = PlayerActivity.from_csv_row(row)
                player_activity_data.append(activity)
            except ValueError as e:
                print(f"Error al procesar la fila en {PLAYER_ACTIVITY_CSV_FILE}: {row} - Error: {e}")
                # Continuar con la siguiente fila

    print(f"Cargados {len(player_activity_data)} registros de actividad desde {PLAYER_ACTIVITY_CSV_FILE}.")

# --- Implementación de la función para inicializar los contadores de ID ---
# ESTA FUNCION ESTABA FALTANDO Y CAUSABA EL PROBLEMA DE LOS ID
def set_initial_ids():
    """
    Establece los contadores next_game_id y next_activity_id
    basándose en los IDs máximos encontrados en los datos cargados en memoria.
    """
    # Debes declarar estas variables como globales para poder modificarlas
    global next_game_id
    global next_activity_id

    print("Inicializando contadores de ID...")

    max_game_id = 0
    if games_data: # Si la lista de juegos no esta vacia, buscar el ID maximo
        try:
            # Encontrar el ID maximo en la lista de juegos
            # Usar una comprension de lista para solo considerar IDs enteros
            valid_game_ids = [game.id for game in games_data if isinstance(game.id, int)]
            if valid_game_ids: # Asegurarse de que hay IDs enteros validos antes de calcular el maximo
                 max_game_id = max(valid_game_ids)
        except ValueError:
            # Esto ya lo deberia manejar el from_csv_row, pero es una capa extra de seguridad
            print("Advertencia: Error al encontrar maximo ID de juego. Posibles IDs no numericos.")
            pass # Continuar con 0 si hay errores

    # Establecer el proximo ID de juego al maximo encontrado + 1
    next_game_id = max_game_id + 1
    print(f"Inicializando next_game_id a: {next_game_id} (Max ID encontrado: {max_game_id})")


    max_activity_id = 0
    if player_activity_data: # Si la lista de actividad no esta vacia
         try:
            # Encontrar el ID maximo en la lista de actividad
            # Usar una comprension de lista para solo considerar IDs enteros
            valid_activity_ids = [activity.id for activity in player_activity_data if isinstance(activity.id, int)]
            if valid_activity_ids: # Asegurarse de que hay IDs enteros validos antes de calcular el maximo
                 max_activity_id = max(valid_activity_ids)
         except ValueError:
            # Capa extra de seguridad
            print("Advertencia: Error al encontrar maximo ID de actividad. Posibles IDs no numericos.")
            pass # Continuar con 0 si hay errores


    # Establecer el proximo ID de actividad al maximo encontrado + 1
    next_activity_id = max_activity_id + 1
    print(f"Inicializando next_activity_id a: {next_activity_id} (Max ID encontrado: {max_activity_id})")

# Asegurate de que next_game_id y next_activity_id tambien esten inicializadas con un valor por defecto (ej. 1)
# en tu archivo models.py o cerca de las declaraciones globales en persistence.py,
# antes de que load_... y set_initial_ids() sean llamadas.
# Ejemplo en models.py:
# next_game_id = 1
# next_activity_id = 1


def save_games_to_csv():
    """Guarda los datos actuales de los juegos a games.csv."""
    os.makedirs(DATA_DIR, exist_ok=True) # Asegurarse de que el directorio exista

    with open(GAMES_CSV_FILE, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)

        # Escribir el encabezado primero
        writer.writerow(GAMES_CSV_HEADERS)

        # Escribir cada objeto Game como una fila
        for game in games_data:
            writer.writerow(game.to_csv_row())

    print(f"Guardados {len(games_data)} juegos en {GAMES_CSV_FILE}.")

def save_player_activity_to_csv():
    """Guarda los datos actuales de actividad de jugadores a player_activity.csv."""
    os.makedirs(DATA_DIR, exist_ok=True) # Asegurarse de que el directorio exista

    with open(PLAYER_ACTIVITY_CSV_FILE, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)

        # Escribir el encabezado primero
        writer.writerow(PLAYER_ACTIVITY_CSV_HEADERS)

        # Escribir cada objeto PlayerActivity como una fila
        for activity in player_activity_data:
            writer.writerow(activity.to_csv_row())

    print(f"Guardados {len(player_activity_data)} registros de actividad en {PLAYER_ACTIVITY_CSV_FILE}.")