import argparse
import csv
import re
import unicodedata
from pathlib import Path

import requests


URL_CKAN = (
    "https://opendata.vlci.valencia.es/"
    "api/3/action/datastore_search"
)

RECURSOS = {
    "2016_2021": "4be7248b-9597-4017-89af-82a9b6e2382f",
    "2021_2022": None,
}

CARPETA_SALIDA = Path("data") / "raw" / "historico_aire"

LIMITE = 10000


def normalizar_nombre(nombre):
    nombre = unicodedata.normalize("NFD", nombre)
    nombre = "".join(
        caracter
        for caracter in nombre
        if unicodedata.category(caracter) != "Mn"
    )

    nombre = nombre.lower().strip()

    # Caso específico indicado en el enunciado
    nombre = nombre.replace("pm2.5", "pm2_5")

    nombre = re.sub(r"\s+", "_", nombre)
    nombre = re.sub(r"[^a-z0-9_]", "", nombre)

    return nombre

def descargar_recurso(resource_id):
    registros = []
    offset = 0

    while True:
        parametros = {
            "resource_id": resource_id,
            "limit": LIMITE,
            "offset": offset,
        }

        respuesta = requests.get(
            URL_CKAN,
            params=parametros,
            timeout=60,
        )

        respuesta.raise_for_status()

        resultado = respuesta.json()

        if not resultado.get("success"):
            raise RuntimeError(
                "CKAN ha devuelto una respuesta no válida."
            )

        datos = resultado["result"]
        lote = datos["records"]

        if not lote:
            break

        registros.extend(lote)

        print(
            f"Registros descargados: {len(registros)}"
            f" de {datos['total']}"
        )

        offset += len(lote)

        if offset >= datos["total"]:
            break

    return registros


def guardar_csv(registros, nombre_archivo):
    if not registros:
        print(f"No hay registros para guardar: {nombre_archivo}")
        return

    CARPETA_SALIDA.mkdir(
        parents=True,
        exist_ok=True,
    )

    ruta = CARPETA_SALIDA / nombre_archivo

    nombres_originales = list(registros[0].keys())
    nombres_columnas = [
        normalizar_nombre(nombre)
        for nombre in nombres_originales
    ]

    with ruta.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as archivo:
        escritor = csv.DictWriter(
            archivo,
            fieldnames=nombres_columnas,
        )

        escritor.writeheader()

        for registro in registros:
            fila = {}

            for nombre_original, nombre_normalizado in zip(
                nombres_originales,
                nombres_columnas,
            ):
                valor = registro.get(nombre_original)

                if valor is None:
                    valor = ""
                elif not isinstance(valor, str):
                    valor = str(valor)

                fila[nombre_normalizado] = valor

            escritor.writerow(fila)

    print(f"Archivo guardado: {ruta}")

def archivo_completo(ruta, total_esperado):
    if not ruta.exists():
        return False

    with ruta.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as archivo:
        lector = csv.reader(archivo)
        next(lector, None)
        numero_registros = sum(1 for _ in lector)

    return numero_registros == total_esperado


def procesar_recurso(nombre, resource_id, forzar):
    nombre_archivo = f"historico_aire_{nombre}.csv"
    ruta = CARPETA_SALIDA / nombre_archivo

    if ruta.exists() and not forzar:
        print(
            f"El archivo ya existe, se omite la descarga: {ruta}"
        )
        return

    if not resource_id:
        print(
            f"Recurso {nombre}: falta el identificador CKAN. "
            "Se omite."
        )
        return

    print(f"Descargando histórico {nombre}...")

    registros = descargar_recurso(resource_id)

    print(f"Total de registros recibidos: {len(registros)}")

    guardar_csv(registros, nombre_archivo)

    if archivo_completo(ruta, len(registros)):
        print("Comprobación del archivo: correcta.")
    else:
        print("Advertencia: el número de registros no coincide.")

def main():
    parser = argparse.ArgumentParser(
        description="Descarga del histórico de calidad del aire"
    )

    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Volver a descargar los archivos existentes",
    )

    args = parser.parse_args()

    for nombre, resource_id in RECURSOS.items():
        try:
            procesar_recurso(
                nombre,
                resource_id,
                args.forzar,
            )

        except Exception as error:
            print(
                f"Error al procesar el histórico {nombre}: {error}"
            )


if __name__ == "__main__":
    main()