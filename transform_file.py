import pathlib
import re
import csv
from datetime import datetime
import io
import os
import logging
import logging.handlers
from dotenv import load_dotenv

logger: logging.Logger

def newLogger(logName: str = "applog"):
    logger = logging.getLogger(logName)
    logger.setLevel(logging.DEBUG)
    logPath = pathlib.Path().joinpath("log")
    logPath.mkdir(parents=True, exist_ok=True)
    logPath = logPath.joinpath(logName).with_suffix(".log")
    fh = logging.handlers.TimedRotatingFileHandler(logPath, when='midnight', interval=1, backupCount=7, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

def getFilenameDictInfo(file: pathlib.Path | str):
    file = pathlib.Path(file)
    filename = file.name
    logger.debug("Nome del file ricevuto in input: '%s'", filename)

    namePattern = re.compile(
        r"^(?P<dispositivo>.+)_"
        r"(?P<tipo>LoadCurve|Avg|index)_"
        r"(?P<data>\d{4}-\d{2}-\d{2})_"
        r"(?P<ora>\d{2}-\d{2}-\d{2})",
        re.IGNORECASE
    )

    nameMatch = namePattern.match(filename)
    logger.debug("Risultato del match sulla regex: %s", True if nameMatch is True else None)

    if nameMatch: 
        infoDict = nameMatch.groupdict()
        logger.debug("Informazioni ottenute dal nome del file:\n%s", infoDict)
        return infoDict

    raise ValueError("Le informazioni richieste non sono state individuate")

def newFileName(old: dict, loadName: str, index: int = 0) -> str:
    dataora = old['data'] + " " + old['ora']
    dataora = datetime.strptime(dataora, "%Y-%m-%d %H-%M-%S")

    name = str()
    if loadName: name += loadName
    else: name += old['dispositivo']

    if index: name += "_" + str(index)
    
    return name + "_" + old['tipo'].upper() + "_" + dataora.strftime("%Y%m%d%H%M%S")

def splitLongFile(righe: list[list[str]], MAX: int):
    logger.debug("Separo il file in pezzi più piccoli")

    intestazione = righe[0:9] # 8 rows of metadata + 1 header row = 9 rows
    del righe[0:9]

    chunksList = list()
    # se non c'è più nulla (es. file senza dati), restituisce solo un chunk con intestazione
    if not righe:
        strBuffer = io.StringIO()
        writer = csv.writer(strBuffer, lineterminator='\n')
        writer.writerows(intestazione)
        chunksList.append(strBuffer)
        return chunksList

    blocks_n = (len(righe) - 1) // MAX + 1

    for i in range(0, blocks_n):
        strBuffer = io.StringIO()
        writer = csv.writer(strBuffer, lineterminator='\n')

        start = i * MAX
        end = i * MAX + MAX

        writer.writerows(intestazione)
        writer.writerows(righe[start:end])

        chunksList.append(strBuffer)

    return chunksList

def process_generic(selectedFile: pathlib.Path) -> tuple[list[list[str]], str]:
    logger.debug("Il file '%s' viene gestito con logica generica", selectedFile.name)

    with open(selectedFile, mode='r', encoding='utf-8-sig') as currentFile:
        reader = csv.reader(currentFile, delimiter=',', quotechar='"')
        righe = list(reader)

    # Identifica l'indice dell'intestazione (Measured value)
    measured_idx = -1
    for i, r in enumerate(righe):
        if r and r[0].strip().lower() == "measured value":
            measured_idx = i
            break
            
    if measured_idx != -1:
        measured = righe.pop(measured_idx)
        measured[0] = "data"
    else:
        # Fallback se non trovato
        measured = ["data"]

    # Identifica l'indice di inizio dei dati (data formattata come AAAA-MM-GG)
    date_regex = re.compile(r'^\d{4}-\d{2}-\d{2}')
    data_idx = len(righe) # di default in fondo
    for i, r in enumerate(righe):
        if r and date_regex.match(r[0]):
            data_idx = i
            break
            
    metadata = righe[:data_idx]
    data = righe[data_idx:]
    
    # Rimuove le righe inutili dai metadati come la riga "Date" e "Values" nei LoadCurve
    metadata = [m for m in metadata if not (m and m[0].strip().lower() == "date")]
    
    # Riempie o tronca i metadati in modo che siano esattamente 8 righe
    if len(metadata) > 8:
        metadata = metadata[:8]
    while len(metadata) < 8:
        metadata.append([])
        
    # Combina: 8 righe di metadati + 1 riga intestazione + righe dati
    righe_finali = metadata + [measured] + data
    
    # Estrae il loadName
    loadName = ""
    for r in righe_finali:
        if r and r[0].strip().lower() == "load name":
            if len(r) > 1:
                loadName = r[1]
            break
            
    return righe_finali, loadName

def writeFilesOnDisk(chunks: list, originalName: str, loadName: str, exportPath: pathlib.Path):
    logger.debug("Inizio scrittura di %d file", len(chunks))

    for idx, c in enumerate(chunks):
        # Manteniamo la struttura nomi del file originale
        # se c'è un solo chunk, possiamo passare index=0 per non aggiungere l'indice se desiderato,
        # ma lo script originale aggiunge sempre index se passato.
        newName = newFileName(getFilenameDictInfo(originalName), loadName, idx)
        newPath = exportPath.joinpath(newName).with_suffix(".csv")
        logger.debug("Il nuovo file sarà nominato '%s'", newPath.name)

        with open(newPath, mode='w', encoding='utf-8', newline='') as f:
            f.write(c.getvalue())

        logger.info("Scritto su disco il file '%s'", newPath.name)

if __name__ == "__main__":
    start = datetime.now()
    logger = newLogger("csv-converter")
    logger.info("Script avviato")

    try:
        load_dotenv()
        logger.debug("Trovato file '.env'")

        WEBVIEW_EXPORT_PATH = os.getenv("WEBVIEW_EXPORT_PATH", ".")
        WEBVIEW_EXPORT_PATH = pathlib.Path(WEBVIEW_EXPORT_PATH) 

        EXPORT_TEMP_DIR = os.getenv("EXPORT_TEMP_DIR", WEBVIEW_EXPORT_PATH / "export")
        EXPORT_TEMP_DIR = pathlib.Path(EXPORT_TEMP_DIR)
        EXPORT_TEMP_DIR.mkdir(parents=True, exist_ok=True)
            
        EXPORT_MAXROWS = int(os.getenv("EXPORT_MAXROWS", 300))

        logger.info("Variabili caricate correttamente")

        csvFileList = pathlib.Path(WEBVIEW_EXPORT_PATH).glob("*.csv")

        for f in csvFileList:
            if "export" in str(f): continue # salta file nella cartella di esportazione
            logger.debug("Considero il file '%s'", f.name)

            try:
                edited, loadName = process_generic(f)
                logger.debug("Prime 10 righe elaborate o File vuoto" if edited else "File vuoto")
            except Exception as e:
                logger.exception(e)
                continue

            if not edited: continue

            fileChunks = splitLongFile(edited, EXPORT_MAXROWS)
            logger.info("Il file '%s' è stato diviso in %d parti", f.name, len(fileChunks))

            writeFilesOnDisk(fileChunks, f.stem, loadName, EXPORT_TEMP_DIR)
    
    except Exception as ex:
        logger.exception(ex)

    logger.info("Script terminato in %s", datetime.now()-start)