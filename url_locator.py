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
    # Split the URL
    parts = re.match(r"(?P<protocol>[a-zA-Z]+)://(?P<ip>[0-9.]+):(?P<port>[0-9]+)(?P<path>.*)", url)

    if parts:
        # Rebuild the URL
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

def _test_http_connection(url):
    global counter
    try:
        with requests.Session() as session:
            response = session.get(url, timeout=2, verify=False)
    except requests.exceptions.RequestException as e:
        with lock:
            counter += 1
        return f"Exception when trying to connect to {url}: {e}"
    
    with lock:
        counter += 1
    if response.status_code == 200:
        return f"Successful connection to {url}"
    else:
        print(f"Connection failure to {url}. Status code: {response.status_code}")
        #return f"Connection failure to {url}. Status code: {response.status_code}"

def _test_rtsp(url, result, finished_event):
    try:
        print(url)
        cap = cv2.VideoCapture(url)
        ret, frame = cap.read()
        cap.release()
        result.put(ret)  # Put the result in the queue
        finished_event.set()  # Indicate that the process has finished
    except:
        finished_event.set()

def _test_rtsp_connection(url, timeout=10):
    try:
        result = Queue()
        finished_event = Event()

        # Start the process that executes the RTSP test function
        process = Process(target=_test_rtsp, args=(url, result, finished_event))
        process.start()

        # Wait for the timeout or until the event is set, whichever comes first
        process.join(timeout)

        if process.is_alive():
            # If the process is still alive after the timeout, it should be terminated
            process.terminate()
            process.join()  # It's important to join after terminating to clean up process resources

        # Safely increment the counter using a lock
        #with lock:
        #    global counter, found
        #    counter += 1

        # Check if the event was set by the process, indicating it completed successfully
        if finished_event.is_set():
            ret = result.get()  # Get the result of the process

            if ret:
                found = True
                return f"Successful connection to {url}"
            else:
                return ''
        else:
            # If the event is not set, assume the process did not complete successfully
            print(f"RTSP test for {url} did not finish before the timeout")
            return ''
    except:
        return ''

found_camera = False 

def _test_connection(url):
    global found_camera
    result = None

    # Verifica si ya se encontró una cámara
    if found_camera or url is None:
        return ''

    if 'http' in url:
        result = _test_http_connection(url)
    elif 'rtsp' in url:
        result = _test_rtsp_connection(url)
    else:
        result = f"Unrecognized protocol in URL: {url}"

    # Si se encuentra una cámara, actualiza la variable global
    if result and "Successful connection" in result:
        found_camera = True

    return result

def _test_connections(urls):
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_url = {executor.submit(_test_connection, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            if found_camera:
                return future.result()  # Retorna el resultado de la cámara encontrada
            try:
                result = future.result()
                if found_camera:
                    return result
            except Exception as exc:
                continue
    return None

def open_camera(url):
    cap = cv2.VideoCapture(url)
    while(cap.isOpened()):
        ret, frame = cap.read()
        if ret:
            cv2.imshow('Camera', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        else:
            break
    cap.release()
    cv2.destroyAllWindows()

def scan_urls(ip, port, brand, df_models):
    global found_camera
    found_camera = False

    df = df_models

    if brand and not brand.isspace():
        df = df[df['Model'].str.contains(brand, case=False, na=False)]

    if port == 554:
        df = df[df['Protocol'].str.contains('rtsp', case=False, na=False)]
    else:
        df = df[df['Protocol'].str.contains('http', case=False, na=False)]

    df = df.copy()

    df.loc[:, 'Complete_URL'] = df.apply(lambda row: _fix_url(_build_url(row['Protocol'], ip, port, row['URL'])), axis=1)
    df.loc[:, 'Complete_URL'] = df['Complete_URL'].str.rstrip('/')

    df = df.drop_duplicates(subset='Complete_URL')

    urls = df['Complete_URL']

    results = _test_connections(urls)

    for result in results:
        if(not result is None):
            return result
