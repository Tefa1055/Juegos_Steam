#Librerias
from typing import List, Optional
from datetime import datetime

# Importa FastAPI, HTTPException, status, Query, Body Y Path
from fastapi import FastAPI, HTTPException, status, Query, Body, Path
from pydantic import BaseModel, Field # Importa Field para añadir descripciones en los modelos

# Importa las funciones de operaciones y los modelos originales
import operations # Importamos el módulo completo
from models import Game, PlayerActivity # Importamos las clases modelo

class GameBase(BaseModel):
    title: str = Field(..., description="Título del videojuego")
    developer: str = Field(..., description="Nombre del desarrollador")
    publisher: str = Field(..., description="Nombre del publicador")
    genres: List[str] = Field([], description="Lista de géneros a los que pertenece el juego")
    release_date: str = Field(..., description="Fecha de lanzamiento (formato texto, ej. 'YYYY-MM-DD' o 'QxYYYY')")
    price: Optional[float] = Field(None, description="Precio actual del juego, si aplica")
    tags: List[str] = Field([], description="Lista de etiquetas asociadas al juego")

class GameCreate(GameBase):
    # Modelo usado para crear un juego (puede ser igual a GameBase si no hay campos extra)
    pass

class GameResponse(GameBase):
    # Modelo usado para representar un juego en las respuestas.
    id: int = Field(..., description="Identificador único del juego en la API")
    is_deleted: bool = Field(False, description="Indica si el juego ha sido eliminado lógicamente")

    class Config:
        from_attributes = True
        json_schema_extra = { # Ejemplo para la documentación
            "example": {
                "id": 1,
                "title": "Portal 2",
                "developer": "Valve",
                "publisher": "Valve",
                "genres": ["Adventure", "Puzzle"],
                "release_date": "2011-04-18",
                "price": 9.99,
                "tags": ["Puzzle", "Sci-fi", "Co-op"],
                "is_deleted": False
            }
        }


class PlayerActivityBase(BaseModel):
    game_id: int = Field(..., description="Identificador del juego al que pertenece el registro de actividad")
    current_players: int = Field(..., description="Número de jugadores concurrentes en el momento del registro")
    peak_players_24h: int = Field(..., description="Pico de jugadores en las últimas 24 horas antes del registro")

class PlayerActivityCreate(PlayerActivityBase):
    # Modelo usado para crear un registro de actividad
    pass 

class PlayerActivityResponse(PlayerActivityBase):
    # Modelo usado para representar un registro de actividad en las respuestas
    id: int = Field(..., description="Identificador único del registro de actividad")
    timestamp: datetime = Field(..., description="Fecha y hora del registro de actividad (formato ISO 8601)")
    is_deleted: bool = Field(False, description="Indica si el registro ha sido eliminado lógicamente")

    class Config:
        from_attributes = True
        json_schema_extra = { # Ejemplo
            "example": {
                "id": 101,
                "game_id": 620, # ID de Portal 2
                "timestamp": "2023-10-27T10:00:00",
                "current_players": 15000,
                "peak_players_24h": 25000,
                "is_deleted": False
            }
        }


#FastAPI

app = FastAPI(
    title="API de Videojuegos de Steam", # Título para la documentación
    description="Servicio para consultar y gestionar información de juegos y su actividad en Steam. Datos basados en Steam.", # Descripción para la documentación
    version="1.0.0",
)


#Endpoints para el Modelo Game

# GET - Obtener todos los juegos
@app.get(
    "/api/v1/juegos",  # <--- RUTA EN ESPAÑOL
    response_model=List[GameResponse],
    summary="Listado de todos los Juegos"
)
def read_all_games(
    include_deleted: bool = Query(False, description="Incluir juegos eliminados lógicamente en la respuesta")
):
    """
    Obtiene una lista de todos los videojuegos disponibles en la colección.
    Por defecto, solo se muestran los juegos activos (no marcados como eliminados lógicamente).
    """
    games = operations.get_all_games(include_deleted=include_deleted)
    return games # FastAPI/Pydantic serializarán automáticamente la lista de objetos Game a GameResponse


#Endpoints ESPECIFICOS que deben ir antes de los endpoints con parametros de ruta genericos 

# GET - Filtrar juegos por género
@app.get(
    "/api/v1/juegos/filtrar",  # <--- RUTA EN ESPAÑOL. Esta ruta especifica debe ir PRIMERO en el grupo de /juegos/...
    response_model=List[GameResponse],
    summary="Filtrar juegos por Género"
)
#Usar Query para los parametros de consulta
def filter_games(
    genre: str = Query(..., description="Género por el que filtrar los juegos. Ej: Action, RPG."),
    include_deleted: bool = Query(False, description="Incluir juegos eliminados lógicamente en los resultados.")
):
    """
    Obtiene una lista de juegos filtrada por el género especificado.
    La búsqueda de género es insensible a mayúsculas/minúsculas.
    """
    filtered_games = operations.filter_games_by_genre(genre, include_deleted=include_deleted)
    return filtered_games


# GET Buscar juegos por título
@app.get(
    "/api/v1/juegos/buscar",  # <--- RUTA EN ESPAÑOL. Esta ruta especifica tambien debe ir antes que la del ID
    response_model=List[GameResponse],
    summary="Buscar juegos por Título"
)
# Usar Query para los parametros de consulta 
def search_games(
    q: str = Query(..., description="Palabra clave o frase para buscar en el título del juego. Ej: Grand Theft Auto."),
    include_deleted: bool = Query(False, description="Incluir juegos eliminados lógicamente en los resultados.")
):
    """
    Busca juegos cuyos títulos contengan la cadena de consulta especificada.
    La búsqueda es insensible a mayúsculas/minúsculas.
    """
    found_games = operations.search_games_by_title(q, include_deleted=include_deleted)
    return found_games

# --- Endpoint con parametro de ruta generico, debe ir DESPUÉS de los especificos ---

# GET - Obtener un juego por ID
@app.get(
    "/api/v1/juegos/{id_juego}",  # <--- RUTA EN ESPAÑOL CON PARÁMETRO. Esta ruta con {id_juego} debe ir DESPUÉS de /filtrar y /buscar
    response_model=GameResponse,
    summary="Detalle de Juego por ID"
)
# Usar Path para la documentación y validación del parámetro de ruta
def read_game_by_id(
    id_juego: int = Path(..., description="ID único del juego a obtener") # <--- Usar Path
):
    """
    Obtiene los detalles de un juego específico utilizando su ID.
    Retorna 404 Not Found si el juego no existe o está marcado como eliminado lógicamente.
    """
    game = operations.get_game_by_id(id_juego)
    if game is None:
        # Lanzar una excepción HTTP que FastAPI convierte en respuesta 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Juego no encontrado o eliminado.")
    return game

# --- Continuar con los demas endpoints de Game ---

# POST - Crear un nuevo juego
@app.post(
    "/api/v1/juegos",  # <--- RUTA EN ESPAÑOL (sin barra final, si prefieres)
    response_model=GameResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nuevo Juego"
)
def create_new_game(game: GameCreate = Body(..., description="Datos del juego a crear")): # Usar Body para documentacion del parametro de cuerpo
    """
    Crea un nuevo juego en la colección.
    Recibe los datos del juego en el cuerpo de la solicitud en formato JSON.
    """
    try:
        # Convierte el modelo Pydantic V2 a un diccionario
        new_game_data = game.model_dump() # Usa .dict() si usas Pydantic V1
        created_game = operations.create_game(new_game_data)
        return created_game # FastAPI/Pydantic serializa el objeto Game a GameResponse
    except ValueError as e:
        # Si operations.create_game lanza un ValueError (por ejemplo, por validación en operations),
        # lo convertimos en un error HTTP 400 Bad Request
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Captura cualquier otra excepción inesperada durante la creación
        print(f"Error interno al crear el juego: {e}") # Imprime en consola del servidor para depuración
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al crear el juego.")


# PUT - Actualizar un juego existente
@app.put(
    "/api/v1/juegos/{id_juego}",  # <--- RUTA EN ESPAÑOL CON PARÁMETRO
    response_model=GameResponse,
    summary="Actualizar Juego por ID"
)
# Usar Path para la documentacion del parametro de ruta y Body para el de cuerpo
def update_existing_game(
    id_juego: int = Path(..., description="ID único del juego a actualizar"), # <--- Usar Path
    update_data: GameCreate = Body(..., description="Datos para actualizar el juego") # Usar Body
):
    """
    Actualiza los datos de un juego existente por su ID.
    Recibe los datos actualizados en el cuerpo de la solicitud en formato JSON.
    Retorna 404 si el juego no existe o está eliminado lógicamente.
    Retorna 400 si los datos de actualización son inválidos.
    """
    try:
        # Convierte el modelo Pydantic V2 a un diccionario.
        # model_dump(exclude_unset=True) es útil si GameCreate tuviera campos Optional y solo quieres actualizar los enviados.
        # Si GameCreate requiere todos los campos, .model_dump() basta.
        updated_game = operations.update_game(id_juego, update_data.model_dump()) # Usa .dict() si usas Pydantic V1

        if updated_game is None:
            # Si operations.update_game retorna None, significa que el juego no fue encontrado o estaba eliminado
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Juego no encontrado o eliminado.")

        return updated_game # FastAPI/Pydantic serializa el objeto Game a GameResponse
    except ValueError as e:
         # Si operations.update_game lanza un ValueError (por ejemplo, por validación en operations),
        # lo convertimos en un error HTTP 400 Bad Request
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
         # Captura cualquier otra excepción inesperada durante la actualización
        print(f"Error interno al actualizar el juego: {e}") # Imprime en consola del servidor
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar el juego.")


# DELETE - Eliminar lógicamente un juego
@app.delete(
    "/api/v1/juegos/{id_juego}",  # <--- RUTA EN ESPAÑOL CON PARÁMETRO
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar Juego (Lógico) por ID"
)
# Usar Path para la documentación del parámetro de ruta
def delete_existing_game(
    id_juego: int = Path(..., description="ID único del juego a eliminar lógicamente") # <--- Usar Path
):
    """
    Marca un juego existente como eliminado lógicamente por su ID (Soft Delete).
    No elimina el registro físicamente de la persistencia (solo actualiza el estado).
    Retorna 404 si el juego no existe o ya estaba marcado como eliminado.
    Retorna 204 No Content si la eliminación lógica fue exitosa.
    """
    try:
        # Llama a la función delete_game de operations.py
        deleted = operations.delete_game(id_juego)

        if not deleted:
            # Si operations.delete_game retorna False, significa que el juego no fue encontrado o ya estaba eliminado
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Juego no encontrado o ya eliminado.")

        # Si retorna True, la operación fue exitosa. El código de estado 204 No Content
        # es apropiado para eliminaciones exitosas que no retornan un cuerpo de respuesta.
        return # FastAPI manejará el retorno 204 porque la función no retorna nada explícitamente

    except Exception as e:
         # Captura cualquier otra excepción inesperada durante la eliminación
        print(f"Error interno al eliminar el juego: {e}") # Imprime en consola del servidor
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al eliminar el juego.")


# --- Endpoints para el Modelo PlayerActivity ---

# GET - Obtener todos los registros de actividad
@app.get(
    "/api/v1/actividad_jugadores",  # <--- RUTA EN ESPAÑOL (plural)
    response_model=List[PlayerActivityResponse],
    summary="Listado de Actividad de Jugadores"
)
# Usar Query para el parametro de consulta
def read_all_player_activity(
    include_deleted: bool = Query(False, description="Incluir registros de actividad eliminados lógicamente en la respuesta.")
):
     """
    Obtiene la lista completa de registros de actividad de jugadores disponibles.
    """
     activity_records = operations.get_all_player_activity(include_deleted=include_deleted)
     return activity_records


# GET - Obtener un registro de actividad por ID
@app.get(
    "/api/v1/actividad_jugadores/{id_actividad}",  # <--- RUTA EN ESPAÑOL (plural) CON PARÁMETRO
    response_model=PlayerActivityResponse,
    summary="Detalle de Actividad por ID"
)
# Usar Path para la documentación y validación del parámetro de ruta
def read_player_activity_by_id(
    id_actividad: int = Path(..., description="ID único del registro de actividad a obtener") # <--- Usar Path
):
    """
    Obtiene los detalles de un registro de actividad específico utilizando su ID.
    Retorna 404 Not Found si el registro no existe o está marcado como eliminado lógicamente.
    """
    activity = operations.get_player_activity_by_id(id_actividad)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro de actividad no encontrado o eliminado.")
    return activity


# POST - Crear un nuevo registro de actividad
@app.post(
    "/api/v1/actividad_jugadores",  # <--- RUTA EN ESPAÑOL (plural, con barra final)
    response_model=PlayerActivityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nuevo Registro de Actividad"
)
# Usar Body para documentacion del parametro de cuerpo
def create_new_player_activity(activity: PlayerActivityCreate = Body(..., description="Datos del registro de actividad a crear")): # Recibe datos validados por Pydantic
    """
    Crea un nuevo registro de actividad de jugadores.
    Recibe los datos de actividad (game_id, current_players, peak_players_24h) en el cuerpo de la solicitud.
    """
    try:
        # Convierte el modelo Pydantic V2 a un diccionario
        created_activity = operations.create_player_activity(activity.model_dump()) # Usa .dict() si usas Pydantic V1
        return created_activity # FastAPI/Pydantic serializa el objeto PlayerActivity a PlayerActivityResponse
    except ValueError as e:
        # Si operations.create_player_activity lanza un ValueError, lo convertimos en un error HTTP 400
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Captura cualquier otra excepción inesperada durante la creación
        print(f"Error interno al crear el registro de actividad: {e}") # Imprime en consola del servidor
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al crear el registro de actividad.")


# PUT - Actualizar un registro de actividad existente
@app.put(
    "/api/v1/actividad_jugadores/{id_actividad}",  # <--- RUTA EN ESPAÑOL (plural) CON PARÁMETRO
    response_model=PlayerActivityResponse,
    summary="Actualizar Registro de Actividad por ID"
)
# Usar Path para la documentacion del parametro de ruta y Body para el de cuerpo
def update_existing_player_activity(
    id_actividad: int = Path(..., description="ID único del registro de actividad a actualizar"), # <--- Usar Path
    update_data: PlayerActivityCreate = Body(..., description="Datos para actualizar el registro de actividad") # Usar Body
):
    """
    Actualiza los datos de un registro de actividad existente por su ID.
    Recibe los datos actualizados en el cuerpo de la solicitud en formato JSON.
    Retorna 404 si el registro no existe o está marcado como eliminado lógicamente.
    Retorna 400 si los datos de actualización son inválidos.
    """
    try:
        # Convierte el modelo Pydantic V2 a un diccionario
        updated_activity = operations.update_player_activity(id_actividad, update_data.model_dump()) # Usa .dict() si usas Pydantic V1

        if updated_activity is None:
            # Si operations.update_player_activity retorna None, significa que el registro no fue encontrado
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro de actividad no encontrado o eliminado.")

        return updated_activity # FastAPI/Pydantic serializa el objeto PlayerActivity a PlayerActivityResponse
    except ValueError as e:
         # Si operations.update_player_activity lanza un ValueError, lo convertimos en un error HTTP 400
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
         # Captura cualquier otra excepción inesperada durante la actualización
        print(f"Error interno al actualizar el registro de actividad: {e}") # Imprime en consola del servidor
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar el registro de actividad.")


# DELETE - Eliminar lógicamente un registro de actividad
@app.delete(
    "/api/v1/actividad_jugadores/{id_actividad}",  # <--- RUTA EN ESPAÑOL (plural) CON PARÁMETRO
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar Registro de Actividad (Lógico) por ID"
)
# Usar Path para la documentación del parámetro de ruta
def delete_existing_player_activity(
    id_actividad: int = Path(..., description="ID único del registro de actividad a eliminar lógicamente") # <--- Usar Path
):
    """
    Marca un registro de actividad existente como eliminado lógicamente por su ID (Soft Delete).
    No elimina el registro físicamente.
    Retorna 404 si el registro no existe o ya estaba marcado como eliminado lógicamente.
    Retorna 204 No Content si la eliminación lógica fue exitosa.
    """
    try:
        # Llama a la función delete_player_activity de operations.py
        deleted = operations.delete_player_activity(id_actividad)

        if not deleted:
            # Si operations.delete_player_activity retorna False, significa que el registro no fue encontrado o ya estaba eliminado
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro de actividad no encontrado o ya eliminado.")

        # Si retorna True, la operación fue exitosa. Retornamos 204 No Content.
        return # FastAPI manejará el retorno 204 porque la función no retorna nada explícitamente

    except Exception as e:
         # Captura cualquier otra excepción inesperada durante la eliminación
        print(f"Error interno al eliminar el registro de actividad: {e}") # Imprime en consola del servidor
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al eliminar el registro de actividad.")


# --- Cómo Ejecutar la API ---
# Para ejecutar la API, guarda este archivo como main.py
# Asegúrate de tener uvicorn y fastapi instalados (`pip install fastapi uvicorn pydantic`)
# Abre tu terminal en el directorio del proyecto y ejecuta:
# uvicorn main:app --reload
# Esto iniciará un servidor local en http://127.0.0.1:8000.
# '--reload' reinicia el servidor automáticamente al guardar cambios en los archivos.

# Verás la documentación interactiva (Swagger UI) en:
# http://127.0.0.