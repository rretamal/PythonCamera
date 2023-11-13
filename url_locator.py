import requests
from bs4 import BeautifulSoup
import csv
import pandas as pd
import os
import cv2
import concurrent.futures
import threading
#import vlc
import time
import re

from multiprocessing import Process, Queue, Event

def _fix_url(url):
    # Split the url
    parts = re.match(r"(?P<protocol>[a-zA-Z]+)://(?P<ip>[0-9.]+):(?P<port>[0-9]+)(?P<path>.*)", url)

    if parts:
        # Rebuild
        protocol = parts.group('protocol')
        ip = parts.group('ip')
        port = parts.group('port')
        path = parts.group('path')

        
        if not path.startswith('/'):
            path = '/' + path

        fixed_url = f"{protocol}://{ip}:{port}{path}"

        return fixed_url
    else:
        print(f"URL not recognized: {url}")
        return None

def _build_url(protocol, ip, port, path):
    
    # Check protocol '://'
    if protocol.endswith('://'):
        return f"{protocol}{ip}:{port}{path}"
    else:
        return f"{protocol}://{ip}:{port}{path}"

def probar_conexion_http(url):
    global contador
    try:
        with requests.Session() as sesion:
            respuesta = sesion.get(url, timeout=2, verify=False)
    except requests.exceptions.RequestException as e:
        with lock:
            contador += 1
        return f"Excepción al tratar de conectar a {url}: {e}"
    
    with lock:
        contador += 1
    if respuesta.status_code == 200:
        return f"Conexión exitosa a {url}"
    else:
        print(f"Fallo en la conexión a {url}. Código de estado: {respuesta.status_code}")
        #return f"Fallo en la conexión a {url}. Código de estado: {respuesta.status_code}"

def prueba_rtsp(url, resultado, evento_terminado):
    try:
        print(url)
        cap = cv2.VideoCapture(url)
        ret, frame = cap.read()
        cap.release()
        resultado.put(ret)  # Poner el resultado en la cola
        evento_terminado.set()  # Indicar que el proceso ha terminado
    except:
        evento_terminado.set()

def probar_conexion_rtsp(url, timeout=30):
    try:
        resultado = Queue()
        evento_terminado = Event()

        # Iniciar el proceso que ejecuta la función de prueba RTSP
        proceso = Process(target=prueba_rtsp, args=(url, resultado, evento_terminado))
        proceso.start()

        # Esperar por el timeout o hasta que el evento esté establecido, lo que ocurra primero
        proceso.join(timeout)

        if proceso.is_alive():
            # Si el proceso sigue vivo después del timeout, se debe terminar
            proceso.terminate()
            proceso.join()  # Es importante unirse después de terminar para limpiar los recursos del proceso

        # Incrementar el contador con seguridad usando un bloqueo
        with lock:
            global contador, encontrado
            contador += 1

        # Verificar si el evento fue establecido por el proceso, lo que indica que se completó correctamente
        if evento_terminado.is_set():
            ret = resultado.get()  # Obtener el resultado del proceso

            if ret:
                encontrado = True
                return f"Conexión exitosa a {url}"
            else:
                return ''
        else:
            # Si el evento no está establecido, se asume que el proceso no terminó correctamente
            print(f"La prueba RTSP para {url} no terminó antes del timeout")
            return ''
    except:
        return ''

def probar_conexion(url):
    global contador
    resultado = None

    if(url is None):
        return ''

    if 'http' in url:
        resultado = probar_conexion_http(url)
    elif 'rtsp' in url:
        resultado = probar_conexion_rtsp(url)
    else:
        resultado = f"Protocolo no reconocido en la URL: {url}"
    
    if contador > 1:
        # Imprimir el contador y el total de URLs
        print(f'Progreso: {contador}/{len(urls)}')
    
    return resultado

def probar_conexiones(urls):
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        resultados = list(executor.map(probar_conexion, urls))
    return resultados

def abrir_camara(url):
    cap = cv2.VideoCapture(url)
    while(cap.isOpened()):
        ret, frame = cap.read()
        if ret:
            cv2.imshow('Cámara', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        else:
            break
    cap.release()
    cv2.destroyAllWindows()
    
def ScanUrls(ip, opened_ports, brand, df_models):

    for port in opened_ports:

        df = df_models

        if brand and not brand.isspace():
            df = df[df['Model'].str.contains(brand, case=False, na=False)]

            if port == '554':
                df = df[df['Protocol'].str.contains('rtsp', case=False, na=False)]
            else:
                df = df[df['Protocol'].str.contains('http', case=False, na=False)]

            df['URL_complete'] = df.apply(lambda row: _fix_url(_build_url(row['Protocolo'], ip, port, row['URL'])), axis=1)
            df['URL_complete'] = df['URL_complete'].str.rstrip('/')
            df = df.drop_duplicates(subset='URL_complete')

            lock = threading.Lock()
            contador = 0
            encontrado = False
