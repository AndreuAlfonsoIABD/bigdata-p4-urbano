import requests
import json
import csv
import argparse
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

URL_TRAFICO = (
    "https://geoportal.valencia.es/server/rest/services/"
    "OPENDATA/Trafico/MapServer/208/query"
)

URL_AIRE = (
    "https://geoportal.valencia.es/server/rest/services/"
    "OPENDATA/MedioAmbiente/MapServer/156/query"
)

def consultar_arcgis(url):
    registros = []
    offset = 0
    limite = 1000

    while True:
        parametros = {
            "where": "1=1",
            "outFields": "*",
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": limite
        }

        respuesta = requests.get(
            url, 
            params=parametros, 
            timeout=30
        )

        respuesta.raise_for_status()

        datos = respuesta.json()
        features = datos["features"]

        if not features:
            break

        registros.extend(features)

        print(
            f"Registros descargados: {len(registros)}"
        )

        offset += len(features)

        if not datos.get("exceededTransferLimit", False):
            break
    
    return {
        "type": "FeatureCollection",
        "features": registros,
    }

def guardar_parquet(datos, fuente):
    captura_utc = datetime.now(timezone.utc)

    fecha = captura_utc.strftime("%Y-%m-%d")
    timestamp = captura_utc.strftime("%Y%m%dT%H%M%SZ")

    ruta = (
        Path("data")
        / "raw"
        / fuente
        / f"fecha={fecha}"
    )

    ruta.mkdir(parents=True, exist_ok=True)

    registros = []

    for feature in datos["features"]:
        registro = feature["properties"].copy()

        registro["geometry"] = json.dumps(
            feature.get("geometry"),
            ensure_ascii=False,
        )

        registro["captura_utc"] = captura_utc.isoformat()

        registros.append(registro)

    tabla = pa.Table.from_pylist(registros)

    archivo = ruta / f"{fuente}_{timestamp}.parquet"

    pq.write_table(tabla, archivo)

    print(f"Archivo Parquet guardado: {archivo}")

def registrar_ejecucion(fuente, estado, registros, error=None):
    ruta = Path("data/raw/_registro/ejecuciones.csv")

    ruta.parent.mkdir(parents=True, exist_ok=True)

    columnas = [
        "captura_utc",
        "fuente",
        "estado",
        "registros",
        "error",
    ]

    existe = ruta.exists()

    with ruta.open(
        "a",
        newline="",
        encoding="utf-8",
    ) as archivo:
        escritor = csv.DictWriter(
            archivo,
            fieldnames=columnas,
        )

        if not existe:
            escritor.writeheader()

        escritor.writerow({
            "captura_utc": datetime.now(timezone.utc).isoformat(),
            "fuente": fuente,
            "estado": estado,
            "registros": registros,
            "error": error or "",
        })

    print(f"Registro actualizado: {ruta}")

def main():
    parser = argparse.ArgumentParser(
        description="Recolector de datos urbanos de Valencia"
    )

    parser.add_argument(
        "--fuente",
        choices=["todas", "trafico", "aire"],
        default="todas",
        help="Fuente de datos que se desea consultar",
    )

    args = parser.parse_args()

    fuentes = {
        "trafico": URL_TRAFICO,
        "aire": URL_AIRE,
    }

    if args.fuente == "todas":
        fuentes_seleccionadas = fuentes.items()
    else:
        fuentes_seleccionadas = [
            (args.fuente, fuentes[args.fuente])
        ]

    for nombre, url in fuentes_seleccionadas:
        print(f"Consultando {nombre}...")

        try:
            datos = consultar_arcgis(url)

            numero_registros = len(datos["features"])

            print(
                f"Registros de {nombre} recibidos:",
                numero_registros,
            )

            guardar_parquet(datos, nombre)

            registrar_ejecucion(
                fuente=nombre,
                estado="ok",
                registros=numero_registros,
            )

        except Exception as error:
            print(
                f"Error al consultar o guardar {nombre}:",
                error,
            )

            registrar_ejecucion(
                fuente=nombre,
                estado="error",
                registros=0,
                error=str(error),
            )


if __name__ == "__main__":
    main()