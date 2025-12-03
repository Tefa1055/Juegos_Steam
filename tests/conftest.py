# tests/conftest.py
import os
import sys
import pytest

# 🔥 Agregar la carpeta raíz del proyecto al PYTHONPATH
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

import database
import models

@pytest.fixture(scope="session", autouse=True)
def prepare_db():
    """
    Se ejecuta UNA VEZ antes de todos los tests.
    Crea todas las tablas necesarias en database.db.
    """
    database.create_db_and_tables()
