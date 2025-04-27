# operations.py

from typing import List, Optional, Dict, Any
from datetime import datetime
import os # Puede ser útil para verificar archivos, aunque la persistencia lo hace

# Importar los modelos y datos en memoria
# Asegurate de que estos modelos existan en models.py
from models import Game, PlayerActivity, games_data, player_activity_data, next_game_id, next_activity_id, set_initial_ids

# Importar las funciones de persistencia
# Asegurate de que estas funciones existan en persistence.py y manejen los archivos CSV correctamente
from persistence import load_games_from_csv, save_games_to_csv, load_player_activity_from_csv, save_player_activity_to_csv

# Cargar los datos al iniciar el módulo operations
# Esto asegura que los datos estén disponibles en memoria cuando las operaciones sean llamadas.
# En una aplicación real, esto podría ir en el punto de entrada principal (main.py)
# para asegurar que se carguen UNA VEZ al iniciar la app.
print("Cargando datos iniciales...")
load_games_from_csv()
load_player_activity_from_csv()
set_initial_ids() # Asegurarse de que los contadores de ID se inicialicen después de cargar
print("Datos cargados y IDs inicializados.")


# --- Funciones Auxiliares ---
# Son útiles para encontrar elementos por ID, manejando Soft Delete
def find_game_by_id(game_id: int, include_deleted: bool = False) -> Optional[Game]:
    """Encuentra un juego por su ID en la lista en memoria."""
    for game in games_data:
        # Asegurarse de comparar int con int, aunque Pydantic valida
        if game.id == game_id:
            if not game.is_deleted or include_deleted:
                return game
            else:
                # Encontrado, pero marcado como eliminado lógicamente y include_deleted es False
                return None
    return None # No encontrado

def find_activity_by_id(activity_id: int, include_deleted: bool = False) -> Optional[PlayerActivity]:
    """Encuentra un registro de actividad por su ID en la lista en memoria."""
    for activity in player_activity_data:
         # Asegurarse de comparar int con int
        if activity.id == activity_id:
            if not activity.is_deleted or include_deleted:
                return activity
            else:
                 # Encontrado, pero marcado como eliminado lógicamente y include_deleted es False
                return None
    return None # No encontrado


# --- CRUD para el Modelo Game ---

def get_all_games(include_deleted: bool = False) -> List[Game]:
    """Obtiene todos los juegos (excluye eliminados lógicamente por defecto)."""
    print(f"Operations: get_all_games(include_deleted={include_deleted})")
    if include_deleted:
        return games_data
    else:
        # Filtrar para excluir juegos marcados como eliminados
        return [game for game in games_data if not game.is_deleted]

def get_game_by_id(game_id: int) -> Optional[Game]:
    """Obtiene un juego específico por su ID (excluye eliminados lógicamente)."""
    print(f"Operations: get_game_by_id(game_id={game_id})")
    # Reutilizamos la función auxiliar find_game_by_id
    # No incluir eliminados por defecto al obtener por ID en el endpoint publico
    return find_game_by_id(game_id, include_deleted=False)


def create_game(game_data: Dict[str, Any]) -> Game:
    """Crea un nuevo juego y lo añade a la lista."""
    global next_game_id # Indicar que vamos a modificar la variable global
    print(f"Operations: create_game({game_data})")

    # Crear la instancia del modelo Game
    # Pydantic ya valida los tipos si vienes de un BaseModel, pero la validacion manual sigue siendo util
    # Asegurarse de manejar los tipos de datos, especialmente las listas y opcionales

    # Convertir listas/strings si es necesario (aunque Pydantic BaseModel deberia manejarlo si se usa Body/Pydantic)
    genres = game_data.get('genres', [])
    tags = game_data.get('tags', [])
    price = game_data.get('price', None) # Pydantic BaseModel con Optional[float] deberia validar esto

    new_game = Game(
        id=next_game_id, # Asignar el proximo ID
        title=game_data['title'],
        developer=game_data['developer'],
        publisher=game_data['publisher'],
        genres=genres,
        release_date=game_data['release_date'],
        price=price,
        tags=tags,
        is_deleted=False # Siempre False al crear
    )

    # Añadir el nuevo juego a la lista en memoria
    games_data.append(new_game)

    # Incrementar el contador para el próximo juego *después* de usar el ID
    next_game_id += 1

    # Guardar los cambios en el archivo CSV
    save_games_to_csv()
    print(f"Operations: Creado juego con ID {new_game.id}. Total juegos: {len(games_data)}")

    return new_game

def update_game(game_id: int, update_data: Dict[str, Any]) -> Optional[Game]:
    """Actualiza los datos de un juego existente."""
    print(f"Operations: update_game(game_id={game_id}, update_data={update_data})")
    # Usar find_game_by_id con include_deleted=False para no actualizar si ya esta logicamente eliminado
    game_to_update = find_game_by_id(game_id, include_deleted=False)

    if not game_to_update:
        print(f"Operations: Juego con ID {game_id} no encontrado o eliminado para actualizar.")
        return None # Juego no encontrado o eliminado lógicamente

    # Actualizar atributos si están presentes en update_data
    # Pydantic BaseModel deberia validar update_data antes de llegar aqui
    for key, value in update_data.items():
        # Evitar actualizar el ID o el estado de eliminado accidentalmente desde update_data
        if key != 'id' and key != 'is_deleted' and hasattr(game_to_update, key):
             # Para listas como genres/tags, reemplazar la lista existente
             if key in ['genres', 'tags'] and isinstance(value, list):
                  setattr(game_to_update, key, value)
             # Para price, asegurarse de que None o numero son validos
             elif key == 'price' and (value is None or isinstance(value, (int, float))):
                  setattr(game_to_update, key, value)
             # Para otros campos, simplemente asignar
             else:
                  setattr(game_to_update, key, value)

    # Guardar los cambios en el archivo CSV
    save_games_to_csv()
    print(f"Operations: Actualizado juego con ID {game_id}.")

    return game_to_update


def delete_game(game_id: int) -> bool:
    """Marca un juego como eliminado lógicamente (Soft Delete)."""
    print(f"Operations: delete_game(game_id={game_id})")
    # Usar find_game_by_id con include_deleted=False para no intentar eliminar si ya esta logicamente eliminado
    game_to_delete = find_game_by_id(game_id, include_deleted=False)

    if not game_to_delete:
        print(f"Operations: Juego con ID {game_id} no encontrado o ya eliminado para eliminar.")
        return False # Juego no encontrado o ya eliminado lógicamente

    # Marcar como eliminado lógicamente
    game_to_delete.is_deleted = True
    # Opcional: podrías añadir un campo deleted_at = datetime.now() en el modelo Game

    # Guardar los cambios en el archivo CSV
    save_games_to_csv()
    print(f"Operations: Marcado como eliminado logicamente juego con ID {game_id}.")

    return True # Eliminado lógicamente con éxito


# --- CRUD para el Modelo PlayerActivity ---
# Implementacion de las funciones CRUD para PlayerActivity

# Implementacion de get_all_player_activity - ESTA ES LA QUE FALTABA Y CAUSABA EL ERROR 500
def get_all_player_activity(include_deleted: bool = False) -> List[PlayerActivity]:
    """Obtiene todos los registros de actividad de jugador (excluye eliminados lógicamente por defecto)."""
    # ELIMINAR LA LÍNEA 'global player_activity_data' AQUÍ
    print(f"Operations: get_all_player_activity(include_deleted={include_deleted})")

    if include_deleted:
        return player_activity_data
    else:
        # Filtrar para excluir registros marcados como eliminados lógicamente
        return [activity for activity in player_activity_data if not activity.is_deleted]

# Implementacion de get_player_activity_by_id (usando la funcion auxiliar find_activity_by_id)
def get_player_activity_by_id(activity_id: int) -> Optional[PlayerActivity]:
    """Obtiene un registro de actividad específico por su ID (excluye eliminados lógicamente)."""
    print(f"Operations: get_player_activity_by_id(activity_id={activity_id})")
    # Reutilizamos la función auxiliar find_activity_by_id
    # No incluir eliminados por defecto al obtener por ID en el endpoint publico
    return find_activity_by_id(activity_id, include_deleted=False)

# Implementacion de create_player_activity (ya la tenias implementada, la incluyo para completar)
def create_player_activity(activity_data: Dict[str, Any]) -> PlayerActivity:
    """Crea un nuevo registro de actividad."""
    global next_activity_id
    print(f"Operations: create_player_activity({activity_data})")

    # Validar que los campos numéricos sean enteros válidos (aunque Pydantic en main.py ya lo hace)
    # Esto es una capa de validacion defensiva en Operations
    try:
        game_id = int(activity_data['game_id'])
        current_players = int(activity_data['current_players'])
        peak_players_24h = int(activity_data['peak_players_24h'])
    except ValueError:
        raise ValueError("Los campos game_id, current_players y peak_players_24h deben ser números enteros válidos.")

    # Validar que el game_id exista (opcional pero recomendado)
    # Buscamos el juego sin incluir eliminados logicamente
    game = find_game_by_id(game_id, include_deleted=False)
    if not game:
         raise ValueError(f"No existe un juego con ID {game_id} para asociar esta actividad.")


    new_activity_id = next_activity_id
    next_activity_id += 1

    # Usar la hora actual para el timestamp
    timestamp = datetime.now()

    new_activity = PlayerActivity(
        id=new_activity_id,
        game_id=game_id, # Usar el entero ya validado
        timestamp=timestamp,
        current_players=current_players, # Usar el entero ya validado
        peak_players_24h=peak_players_24h, # Usar el entero ya validado
        is_deleted=False
    )

    player_activity_data.append(new_activity)
    save_player_activity_to_csv()
    print(f"Operations: Creado registro de actividad con ID {new_activity.id}. Total registros: {len(player_activity_data)}")

    return new_activity

# Implementacion de update_player_activity (usando la funcion auxiliar find_activity_by_id)
def update_player_activity(activity_id: int, update_data: Dict[str, Any]) -> Optional[PlayerActivity]:
    """Actualiza los datos de un registro de actividad existente."""
    print(f"Operations: update_player_activity(activity_id={activity_id}, update_data={update_data})")
    # Usar find_activity_by_id con include_deleted=False para no actualizar si ya esta logicamente eliminado
    activity_to_update = find_activity_by_id(activity_id, include_deleted=False)

    if not activity_to_update:
        print(f"Operations: Registro de actividad con ID {activity_id} no encontrado o eliminado para actualizar.")
        return None # Registro no encontrado o eliminado lógicamente

    # Actualizar atributos si están presentes en update_data
    # Pydantic BaseModel en main.py deberia validar update_data antes de llegar aqui,
    # pero añadimos validacion defensiva para game_id, current_players, peak_players_24h
    for key, value in update_data.items():
        # Evitar actualizar el ID, timestamp o estado de eliminado accidentalmente
        if key != 'id' and key != 'timestamp' and key != 'is_deleted' and hasattr(activity_to_update, key):
            # Asegurarse de que game_id, current_players, peak_players_24h son enteros si se actualizan
            if key in ['game_id', 'current_players', 'peak_players_24h']:
                 try:
                      setattr(activity_to_update, key, int(value))
                 except ValueError:
                      # Aunque Pydantic validaria, buena practica defensiva
                      raise ValueError(f"El campo '{key}' debe ser un número entero válido.")
            else: # Para otros campos (aunque solo tenemos los 3 numericos en PlayerActivityBase)
                setattr(activity_to_update, key, value)

    # Guardar los cambios en el archivo CSV
    save_player_activity_to_csv()
    print(f"Operations: Actualizado registro de actividad con ID {activity_id}.")

    return activity_to_update

# Implementacion de delete_player_activity (Soft Delete) (usando la funcion auxiliar find_activity_by_id)
def delete_player_activity(activity_id: int) -> bool:
    """Marca un registro de actividad como eliminado lógicamente (Soft Delete)."""
    print(f"Operations: delete_player_activity(activity_id={activity_id})")
    # Usar find_activity_by_id con include_deleted=False para no intentar eliminar si ya esta logicamente eliminado
    activity_to_delete = find_activity_by_id(activity_id, include_deleted=False)

    if not activity_to_delete:
        print(f"Operations: Registro de actividad con ID {activity_id} no encontrado o ya eliminado para eliminar.")
        return False # Registro no encontrado o ya eliminado lógicamente

    # Marcar como eliminado lógicamente
    activity_to_delete.is_deleted = True
    # Opcional: añadir deleted_at = datetime.now() en el modelo PlayerActivity

    # Guardar los cambios en el archivo CSV
    save_player_activity_to_csv()
    print(f"Operations: Marcado como eliminado logicamente registro de actividad con ID {activity_id}.")

    return True # Eliminado lógicamente con éxito


# --- Funciones de Filtrado y Búsqueda (ya las tenias implementadas, las incluyo para completar) ---

def filter_games_by_genre(genre: str, include_deleted: bool = False) -> List[Game]:
    """
    Filtra juegos por género.
    Por defecto, excluye los juegos marcados como eliminados lógicamente.
    La comparación del género es insensible a mayúsculas/minúsculas.
    """
    print(f"Operations: filter_games_by_genre(genre='{genre}', include_deleted={include_deleted})")
    genre_lower = genre.strip().lower() # Convertir el género buscado a minúsculas y quitar espacios

    # Usar una comprensión de lista para filtrar los juegos
    # Incluye el juego si NO está eliminado LÓGICAMENTE (o si include_deleted es True)
    # Y si el género buscado (en minúsculas) está en la lista de géneros del juego (también comparando en minúsculas)
    filtered_list = [
        game for game in games_data
        if (not game.is_deleted or include_deleted) and
           genre_lower in [g.strip().lower() for g in game.genres] # Convertir cada género del juego a minúsculas para la comparación
    ]
    print(f"Operations: Encontrados {len(filtered_list)} juegos para género '{genre}'.")
    return filtered_list

def search_games_by_title(query: str, include_deleted: bool = False) -> List[Game]:
    """
    Busca juegos por palabras clave en el título.
    La búsqueda es insensible a mayúsculas/minúsculas.
    Por defecto, excluye los juegos marcados como eliminados lógicamente.
    """
    print(f"Operations: search_games_by_title(query='{query}', include_deleted={include_deleted})")
    query_lower = query.strip().lower() # Convertir la consulta a minúsculas y quitar espacios

    if not query_lower:
        print("Operations: Consulta de busqueda vacia.")
        return [] # Si la consulta está vacía, retornar una lista vacía

    # Usar una comprensión de lista para buscar juegos
    # Incluye el juego si NO está eliminado LÓGICAMENTE (o si include_deleted es True)
    # Y si la consulta (en minúsculas) está contenida en el título del juego (en minúsculas)
    found_list = [
        game for game in games_data
        if (not game.is_deleted or include_deleted) and
           query_lower in game.title.strip().lower() # Comprobar si la consulta está en el título (insensible a mayúsculas/minúsculas)
    ]
    print(f"Operations: Encontrados {len(found_list)} juegos para consulta '{query}'.")
    return found_list