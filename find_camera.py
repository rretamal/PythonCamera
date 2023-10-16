import requests
from bs4 import BeautifulSoup
import csv
import pandas as pd
import os
import cv2
import concurrent.futures
import threading
import re
import multiprocessing

cameraUrl = 'https://www.ispyconnect.com'

def obtener_detalles_camara(url):
    # Esta función debería ser implementada para seguir el enlace a la página de la cámara
    # y extraer los detalles relevantes como el tipo, protocolo y URL.
    # Por ahora, simplemente retornará valores ficticios:
    return "Tipo", "Protocolo", "URL"

def scrape_cameras(url):
    global cameraUrl
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Buscar la tabla por alguna característica distintiva, en este caso supondré que es la única tabla en la página
    table = soup.find('table')
    
    if table is None:
        print("No se encontró la tabla")
        return
    
    rows = table.find_all('tr')
    
    with open('cameras.csv', mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Marca', 'Modelo', 'Tipo', 'Protocolo', 'URL'])  # Cabecera del CSV
        
        for row in rows:
            cols = row.find_all('td')
            for col in cols:
                links = col.find_all('a')
                for link in links:
                    marca_modelo = link.text
                    detalle_url = cameraUrl + link['href']
                   
                    detalles_camaras = obtener_detalles_camara(detalle_url)
                    
                    if detalles_camaras is not None and len(detalles_camaras) > 0:

                        for camera in detalles_camaras:
                            model, tipo, protocolo, url_camara = camera
                            writer.writerow([marca_modelo, model, tipo, protocolo, url_camara])  # Cabecera del CSV
                            print(model)
                        else:
                            model, tipo, protocolo, url_camara = None, None, None, None  # o cualquier valor predeterminado que desees

                    print(detalle_url)

def obtener_detalles_camara(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table', {'class': 'table table-striped table-bordered'})
        
        if table is None:
            print("No se encontró la tabla")
            return None
        
        rows = table.find_all('tr')[1:]  # Saltar la fila de encabezado
        
        detalles_camaras = []  # Lista para almacenar los detalles de todas las cámaras
        
        for row in rows:
            cols = row.find_all('td')
            modelos = cols[0].text.split(', ')  # Dividir la lista de modelos por coma y espacio
            tipo = cols[1].text
            protocolo = cols[2].text
            path = cols[3].text

            # Agregar los detalles de cada modelo a la lista
            for modelo in modelos:
                detalles_camaras.append((modelo, tipo, protocolo, path))
               
        return detalles_camaras

    except requests.exceptions.RequestException as e:
        print(f"Error de solicitud: {e}")
        return None
    except AttributeError as e:
        print(f"Error al parsear la página: {e}")
        return None

def guardar_detalles_csv(detalles_camaras):
    with open('camaras.csv', mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Modelo', 'Tipo', 'Protocolo', 'Ruta'])  # Cabecera del CSV
        writer.writerows(detalles_camaras)  # Escribir todas las filas a la vez
                   
def corregir_url(url):
    # Dividir la URL en partes usando expresiones regulares
    partes = re.match(r"(?P<protocolo>[a-zA-Z]+)://(?P<ip>[0-9.]+):(?P<puerto>[0-9]+)(?P<path>.*)", url)

    if partes:
        # Reconstruir la URL
        protocolo = partes.group('protocolo')
        ip = partes.group('ip')
        puerto = partes.group('puerto')
        path = partes.group('path')

        # Asegurar que el path comienza con '/'
        if not path.startswith('/'):
            path = '/' + path

        url_corregida = f"{protocolo}://{ip}:{puerto}{path}"
        return url_corregida
    else:
        print(f"URL no reconocida: {url}")
        return None
    
# URL de la página que contiene la información de las cámaras
url = 'https://www.ispyconnect.com/cameras'  # Asumiendo que esta es la URL, puede que no lo sea

if(not os.path.isfile('cameras.csv')):
    scrape_cameras(url)

df = pd.read_csv('cameras.csv')

marca = ''  # reemplazar con la marca proporcionada o None si no se proporciona
ip = '192.168.100.32'  # reemplazar con la IP proporcionada
puerto = '554'  # reemplazar con el puerto proporcionado

if marca and not marca.isspace():
    df = df[df['Modelo'].str.contains(marca, case=False, na=False)]

# Filtrar por protocolo basado en el puerto
if puerto == '554':
    df = df[df['Protocolo'].str.contains('rtsp', case=False, na=False)]
else:
    df = df[df['Protocolo'].str.contains('http', case=False, na=False)]

# Función para construir la URL
def construir_url(protocolo, ip, puerto, ruta):
    # Verificar si el protocolo ya incluye '://'
    if protocolo.endswith('://'):
        return f"{protocolo}{ip}:{puerto}{ruta}"
    else:
        return f"{protocolo}://{ip}:{puerto}{ruta}"

# Crear una nueva columna con las URLs completas
df['URL_completa'] = df.apply(lambda row: corregir_url(construir_url(row['Protocolo'], ip, puerto, row['URL'])), axis=1)

# Eliminar filas duplicadas basadas en la columna 'URL_completa'
df['URL_completa'] = df['URL_completa'].str.rstrip('/')
df = df.drop_duplicates(subset='URL_completa')

# Inicializar un bloqueo y una variable contador
lock = threading.Lock()
contador = 0
encontrado = False

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
    print(url)
    cap = cv2.VideoCapture(url)
    ret, frame = cap.read()
    cap.release()
    resultado.put(ret)  # Poner el resultado en la cola
    evento_terminado.set()  # Indicar que el proceso ha terminado

def probar_conexion_rtsp(url, timeout=5):
    global contador, encontrado

    resultado = multiprocessing.Queue()  # Cola para almacenar el resultado
    evento_terminado = multiprocessing.Event()  # Evento para indicar la terminación del proceso
    proceso = multiprocessing.Process(target=prueba_rtsp, args=(url, resultado, evento_terminado))
    proceso.start()
    proceso.join(timeout)  # Esperar por el timeout

    with lock:
        contador += 1  # Incrementar el contador

    if evento_terminado.is_set():
        # Si el evento está establecido, el proceso terminó normalmente
        ret = resultado.get()
        if ret:
            encontrado = True
            return f"Conexión exitosa a {url}"
        else:
            print(f"Fallo en la conexión a {url}")
            return ''
    else:
        # Si el evento no está establecido, el proceso no terminó, por lo que se debe terminar
        proceso.terminate()
        return ''

    

def probar_conexion(url):
    resultado = None

    if(url is None):
        return ''

    if 'http' in url:
        resultado = probar_conexion_http(url)
    elif 'rtsp' in url:
        resultado = probar_conexion_rtsp(url)
    else:
        resultado = f"Protocolo no reconocido en la URL: {url}"
    
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

urls = df['URL_completa']

# Probar las conexiones
resultados = probar_conexiones(urls)

# Imprimir los resultados
for resultado in resultados:
    if(not resultado is None):
        print(resultado)