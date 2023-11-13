import socket
import concurrent.futures
import os
import requests
from bs4 import BeautifulSoup
import csv

# Define the range of IP addresses to scan (e.g., '192.168.1.1' to '192.168.1.255')
start_ip = '192.168.100.1'
end_ip = '192.168.100.255'
cameraUrl = 'https://www.ispyconnect.com'

# Define the list of ports to check
ports_to_check = [554]  # Add your ports here

def scrape_cameras(url):
    global cameraUrl
    
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the table
    table = soup.find('table')
    
    if table is None:
        print("No se encontró la tabla")
        return
    
    rows = table.find_all('tr')
    
    with open('cameras.csv', mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Marca', 'Modelo', 'Tipo', 'Protocolo', 'URL'])  # Head of the csv
        
        for row in rows:
            cols = row.find_all('td')
            for col in cols:
                links = col.find_all('a')
                for link in links:
                    marca_modelo = link.text
                    detalle_url = cameraUrl + link['href']
                   
                    detalles_camaras = get_details_camera(detalle_url)
                    
                    if detalles_camaras is not None and len(detalles_camaras) > 0:

                        for camera in detalles_camaras:
                            model, tipo, protocolo, url_camara = camera
                            writer.writerow([marca_modelo, model, tipo, protocolo, url_camara])  # Head of the csv
                            print(model)
                        else:
                            model, tipo, protocolo, url_camara = None, None, None, None  # default data

                    print(detalle_url)
    
    print("Finishing cameras download")

def get_details_camera(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table', {'class': 'table table-striped table-bordered'})
        
        if table is None:
            print("No se encontró la tabla")
            return None
        
        rows = table.find_all('tr')[1:]  # Jump first row
        
        detalles_camaras = []  # Create the list to store the values
        
        for row in rows:
            cols = row.find_all('td')
            modelos = cols[0].text.split(', ')  # Split the list
            tipo = cols[1].text
            protocolo = cols[2].text
            path = cols[3].text

            # Add the detail
            for modelo in modelos:
                detalles_camaras.append((modelo, tipo, protocolo, path))
               
        return detalles_camaras

    except requests.exceptions.RequestException as e:
        print(f"Error de solicitud: {e}")
        return None
    except AttributeError as e:
        print(f"Error al parsear la página: {e}")
        return None

# URL de la página que contiene la información de las cámaras
url = 'https://www.ispyconnect.com/cameras'  # Asumiendo que esta es la URL, puede que no lo sea

# Function to convert IP address to a tuple of integers
def ip_to_tuple(ip):
    return tuple(int(part) for part in ip.split('.'))

# Function to convert a tuple of integers to an IP address string
def tuple_to_ip(tup):
    return '.'.join(str(part) for part in tup)

# Function to increment an IP address
def increment_ip(ip):
    tup = ip_to_tuple(ip)
    tup = tup[:3] + (tup[3] + 1,)
    return tuple_to_ip(tup)

# Function to check a single port on an IP
def check_port(ip, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)  # Timeout for the socket connection
        try:
            s.connect((ip, port))
            return (ip, port, True)
        except:
            return (ip, port, False)

# Function to scan a single IP
def scan_ip(ip):
    print("Testing: " + ip)
    results = []
    for port in ports_to_check:
        result = check_port(ip, port)
        if result[2]:  # If port is open
            results.append(result)
    return results

# Main scanning function
def scan_ips(start_ip, end_ip):
    current_ip = start_ip
    end_tuple = ip_to_tuple(end_ip)
    open_ports = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_ip = {executor.submit(scan_ip, ip): ip for ip in generate_ips(start_ip, end_ip)}
        for future in concurrent.futures.as_completed(future_to_ip):
            ip = future_to_ip[future]
            try:
                open_ports.extend(future.result())
            except Exception as exc:
                print(f'{ip} generated an exception: {exc}')
    
    return open_ports

# Function to generate all IPs in the range
def generate_ips(start_ip, end_ip):
    current_ip = start_ip
    while ip_to_tuple(current_ip) <= ip_to_tuple(end_ip):
        yield current_ip
        current_ip = increment_ip(current_ip)

if(not os.path.isfile('cameras.csv')):
    scrape_cameras(url)

# Run the scan
found_ports = scan_ips(start_ip, end_ip)
print("Found open ports:", found_ports)
