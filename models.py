from typing import List, Optional
from datetime import datetime

class Game:
    def __init__(self, id: int, title: str, developer: str, publisher: str, genres: List[str], release_date: str, price: Optional[float] = None, tags: Optional[List[str]] = None, is_deleted: bool = False):
        self.id = id
        self.title = title
        self.developer = developer
        self.publisher = publisher
        self.genres = genres # Lista de strings
        self.release_date = release_date # Podrías usar datetime.date si prefieres, pero str es más simple para CSV
        self.price = price # Opcional, algunos juegos son gratuitos
        self.tags = tags # Opcional, lista de strings
        self.is_deleted = is_deleted # Campo para Soft Delete

    def __repr__(self):
        # Representación útil para debugging
        return f"Game(id={self.id}, title='{self.title}', is_deleted={self.is_deleted})"

    # Método para convertir el objeto a un formato que se pueda guardar en CSV
    def to_csv_row(self):
        # Convertir listas a strings separadas por un caracter (ej: ';') para guardar en CSV
        genres_str = ";".join(self.genres) if self.genres else ""
        tags_str = ";".join(self.tags) if self.tags else ""
        # Asegurarse de que los campos opcionales se guarden como string vacío si son None
        price_str = str(self.price) if self.price is not None else ""
        is_deleted_str = "True" if self.is_deleted else "False"

        return [
            str(self.id),
            self.title,
            self.developer,
            self.publisher,
            genres_str,
            self.release_date,
            price_str,
            tags_str,
            is_deleted_str
        ]

    @staticmethod
    def from_csv_row(row: List[str]):
        # Método para crear un objeto Game desde una fila de CSV
        # Asegurarse de manejar los tipos de datos y los campos opcionales/listas
        game_id = int(row[0])
        title = row[1]
        developer = row[2]
        publisher = row[3]
        genres = row[4].split(";") if row[4] else []
        release_date = row[5]
        price = float(row[6]) if row[6] else None # Convertir string a float
        tags = row[7].split(";") if row[7] else []
        is_deleted = row[8].lower() == 'true' # Convertir string a booleano

        return Game(game_id, title, developer, publisher, genres, release_date, price, tags, is_deleted)


class PlayerActivity:
    def __init__(self, id: int, game_id: int, timestamp: datetime, current_players: int, peak_players_24h: int, is_deleted: bool = False):
        self.id = id # Podría ser un ID único para este registro de actividad
        self.game_id = game_id # El ID del juego al que se refiere
        self.timestamp = timestamp # Cuando se registró la actividad
        self.current_players = current_players
        self.peak_players_24h = peak_players_24h
        self.is_deleted = is_deleted # Campo para Soft Delete

    def __repr__(self):
         # Representación útil para debugging
        return f"PlayerActivity(id={self.id}, game_id={self.game_id}, timestamp={self.timestamp.isoformat()}, current={self.current_players}, is_deleted={self.is_deleted})"

    # Método para convertir el objeto a un formato que se pueda guardar en CSV
    def to_csv_row(self):
        # Convertir datetime a string ISO para guardar en CSV
        timestamp_str = self.timestamp.isoformat()
        is_deleted_str = "True" if self.is_deleted else "False"

        return [
            str(self.id),
            str(self.game_id),
            timestamp_str,
            str(self.current_players),
            str(self.peak_players_24h),
            is_deleted_str
        ]

    @staticmethod
    def from_csv_row(row: List[str]):
        # Método para crear un objeto PlayerActivity desde una fila de CSV
        activity_id = int(row[0])
        game_id = int(row[1])
        # Convertir string ISO a objeto datetime
        timestamp = datetime.fromisoformat(row[2])
        current_players = int(row[3])
        peak_players_24h = int(row[4])
        is_deleted = row[5].lower() == 'true'

        return PlayerActivity(activity_id, game_id, timestamp, current_players, peak_players_24h, is_deleted)

# Variable global o de módulo para mantener los datos cargados en memoria
# Esto simplifica el ejemplo, en una app real grande usarías una base de datos
games_data: List[Game] = []
player_activity_data: List[PlayerActivity] = []

# Contador simple para asignar IDs únicos (si no vienen de la fuente externa)
next_game_id = 1
next_activity_id = 1

def set_initial_ids():
    """
    Función para establecer los contadores de ID basados en los datos cargados,
    útil al iniciar la aplicación.
    """
    global next_game_id, next_activity_id
    if games_data:
        # Asegurarse de que el próximo ID sea mayor que el ID más alto existente
        next_game_id = max([game.id for game in games_data]) + 1
    if player_activity_data:
         # Asegurarse de que el próximo ID sea mayor que el ID más alto existente
        next_activity_id = max([activity.id for activity in player_activity_data]) + 1
