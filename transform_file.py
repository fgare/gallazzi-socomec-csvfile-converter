import pathlib
import re
import csv
from datetime import datetime, timedelta
import io
from dotenv import load_dotenv
import os
import logging, logging.handlers


'''
Operazioni:
- lista dei file nella cartella
- per ciascun file determinare il tipo di dati contenuti
- modificare ordine righe
- spaccare in file di MAX numero di righe
- scrivere i nuovi file su un buffer
- inviare via FTP
'''

logger: logging.Logger


def newLogger():
    logger = logging.getLogger("convertitore-file-webview")
    logger.setLevel(logging.DEBUG)
    fh = logging.handlers.TimedRotatingFileHandler("gallazzi.log", when='midnight', interval=1, backupCount=7, encoding='utf-8')
    fh.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def workOnFile(filepath: pathlib.Path):
    return selectFileGroup(filepath)


def getFilenameDictInfo(file: pathlib.Path | str):
    file = pathlib.Path(file) # nel caso l'argomento fosse str
    filename = file.name

    namePattern = re.compile(
        r"^(?P<dispositivo>.+?)_"
        r"(?P<tipo>LoadCurve|avg|index)_"
        r"(?P<data>\d{4}-\d{2}-\d{2})_"
        r"(?P<ora>\d{2}-\d{2}-\d{2})"
        r"\.csv$",
        re.IGNORECASE
    )

    nameMatch = namePattern.match(filename)

    if nameMatch: 
        infoDict = nameMatch.groupdict()
        logger.debug("Informazioni ottenute dal nome del file:\n%s", infoDict)
        return infoDict

    raise ValueError("Le infomazioni richieste non sono state individuate")


def selectFileGroup(inputFile: pathlib.Path):
    tipo = getFilenameDictInfo(inputFile)['tipo']
    tipo = str(tipo).lower
    logger.debug("Tipo di file riconosciuto: %s", tipo)

    match tipo:
        case "loadcurve":
            pass
        case "avg":
            return typeAvg(inputFile)
        case "index":
            pass


'''
Genera il nuovo nome per il file, inserendo l'indice se specificato.
Il nuovo nome viene formato secondo il seguente schema: <nome dispositivo>_<indice>_<dataora>
'''
def newFileName(old: dict, index: int = 0):
    dataora = old['data'] + " " + old['ora']
    dataora = datetime.strptime(dataora, "%Y-%m-%d %H-%M-%S")

    if index:
        return old['dispositivo'] + "_" + index + "_" + dataora.strftime("%Y%m%d%H%M%S")

    return old['dispositivo'] + "_" + dataora.strftime("%Y%m%d%H%M%S")


'''
Riceve in input un file csv espresso come lista di righe.
Estrae l'intestazione e genera file da massimo DIM righe.
I file sono temporaneamente memorizzati in buffer di testo.
'''
def splitLongFile(righe: list[list[str]], MAX: int):
    logger.debug("Separo il file in pezzi più piccoli")

    intestazione = righe[0:8]
    del righe[0:8]

    chunksList = list()
    blocks_n = len(righe) // MAX + 1

    for i in range(0,blocks_n):
        strBuffer = io.StringIO()
        writer = csv.writer(strBuffer)

        start = i * MAX
        end = i * MAX + MAX

        writer.writerows(intestazione)
        writer.writerows(righe[start:end])

        chunksList.append(strBuffer)

    return chunksList
        

def typeLoadCurve():
    pass


def typeAvg(selectedFile: pathlib.Path):
    logger.debug("Il file viene gestito come tipo AVG")

    with open (selectedFile, 'r') as currentFile:
        reader = csv.reader(currentFile, delimiter=',',quotechar='\"')
        righe = list(reader)

        # estrae la riga con le unità misurate
        measured = righe.pop(4)
        # rinomina la prima colonna in 'data'
        measured[0] = "data"
        # inserisce la nuova riga di intestazione modificata
        righe.insert(8, measured)

        logger.debug("L'ordine delle righe di intestazione è stato modificato")
        return righe


def typeIndex():
    pass


def writeFilesOnDisk(chunks: list, originalName: str, exportPath: pathlib.Path):
    for idx, c in enumerate(chunks):
        newName = newFileName(getFilenameDictInfo(originalName), idx)
        newPath = exportPath.joinpath(newName).with_suffix(".csv")

        with open(newPath, mode='w', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=';')
            writer.writerows(c)


if __name__ == "__main__":
    start = datetime.now()
    logger = newLogger()

    load_dotenv()
    logger.debug("Trovato file '.env'")

    WEBVIEW_EXPORT_PATH = os.getenv("WEBVIEW_EXPORT_PATH")
    if not WEBVIEW_EXPORT_PATH:
        raise ValueError(f"La variabile {WEBVIEW_EXPORT_PATH} non e' impostata")
    
    WEBVIEW_EXPORT_PATH = pathlib.Path(WEBVIEW_EXPORT_PATH)

    EXPORT_TEMP_DIR = os.getenv("EXPORT_TEMP_DIR", pathlib.Path.cwd())
    EXPORT_TEMP_DIR = pathlib.Path(EXPORT_TEMP_DIR)
        
    EXPORT_MAXROWS = int(os.getenv("EXPORT_MAXROWS", 300))

    # crea cartella in cui salvare temporaneamente i file
    pathlib.Path.mkdir(EXPORT_TEMP_DIR / "export_temp", parents=True, exist_ok=True)
    logger.debug("Variabili importate correttamente da '.env'")

    # lista dei file presenti nella cartella
    csvFileList = pathlib.Path(WEBVIEW_EXPORT_PATH).glob("*.csv", case_sensitive=False)
    # logger.info("Nella cartella '%s' sono presenti %d file", WEBVIEW_EXPORT_PATH.name, sum(1 for _ in csvFileList))

    for f in csvFileList:
        logger.debug("File '%s'", f.name)

        try:
            edited = workOnFile(f)
        except Exception:
            continue

        # il file può essere vuoto
        if not edited: continue

        fileChunks = splitLongFile(edited, EXPORT_MAXROWS)
        logger.info("Il file è stato diviso in %d parti", len(fileChunks))

        writeFilesOnDisk(fileChunks, f.stem, EXPORT_TEMP_DIR)

    logger.info("Script terminato in %s", datetime.now()-start)