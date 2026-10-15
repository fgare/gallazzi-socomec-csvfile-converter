import pathlib
import re
import csv
from datetime import datetime
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
- scrivere i nuovi file in una cartella temporanea (creata precedentemente)
'''

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
    ch.setLevel(logging.INFO)
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

    raise ValueError("Le infomazioni richieste non sono state individuate")


def selectFileGroup(inputFile: pathlib.Path):
    tipo = getFilenameDictInfo(inputFile)['tipo']
    tipo = str(tipo).lower()
    logger.debug("Tipo di file riconosciuto: %s", tipo)

    match tipo:
        case "loadcurve":
            return typeLoadCurve(inputFile)
        case "avg":
            return typeAvg(inputFile)
        case "index":
            return typeIndex(inputFile)


'''
Genera il nuovo nome per il file, inserendo l'indice se specificato.
Il nuovo nome viene formato secondo il seguente schema: <nome dispositivo>_<indice>_<dataora>
'''
def newFileName(old: dict, loadName: str, index: int = 0) -> str:
    dataora = old['data'] + " " + old['ora']
    dataora = datetime.strptime(dataora, "%Y-%m-%d %H-%M-%S")

    name = str()

    if loadName: name += loadName
    else: name += old['dispositivo']

    if index: name += "_" + str(index)
    
    return name + "_" + old['tipo'].upper() + "_" + dataora.strftime("%Y%m%d%H%M%S")


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
        writer = csv.writer(strBuffer, lineterminator='\n')

        start = i * MAX
        end = i * MAX + MAX

        writer.writerows(intestazione)
        writer.writerows(righe[start:end])

        chunksList.append(strBuffer)

    return chunksList


def findRowStart(righe: list[list[str]], searchString: str) -> tuple[int, list[str]]:
    for id, row in enumerate(righe):
        if row and row[0].strip().lower() == searchString.strip().lower():
            return id, row

    raise ValueError("Riga 'Load name' non trovata all'interno del file")


def typeLoadCurve(selectedFile: pathlib.Path) -> tuple[list[list[str]], str]:
    logger.debug("Il file viene gestito come tipo LOAD CURVE")

    # Usando utf-8-sig rimuove il BOM iniziale invisibile
    with open (selectedFile, mode='r', encoding='utf-8-sig') as currentFile:
        logger.debug("Apro il file '%s' in lettura", selectedFile.name)

        reader = csv.reader(currentFile, delimiter=',', quotechar='\"')
        righe = list(reader)

        # estrae la riga con le unità misurate
        measured = righe.pop(6)
        # rimuovo una riga inutile per allinearle il numero di righe inziali a quello degli altri file
        righe.pop(4) 
        # rinomina la prima colonna in 'data'
        measured[0] = "data"
        # inserisce la nuova riga di intestazione modificata
        righe.insert(8, measured)

        logger.debug("L'ordine delle righe di intestazione è stato modificato")

        (_, loadName) = findRowStart(righe, "load name")

        # in load name considero l'elemento 1 in quanto è il primo a contenere il nome del carico.
        # L'elemento 0 contiene la dicitura LoadName
        return righe, loadName[1]


def typeAvg(selectedFile: pathlib.Path) -> tuple[list[list[str]], str]:
    logger.debug("Il file viene gestito come tipo AVG")

    # Usando utf-8-sig rimuove il BOM iniziale invisibile
    with open (selectedFile, mode='r', encoding='utf-8-sig') as currentFile:
        logger.debug("Apro il file '%s' in lettura", selectedFile.name)

        reader = csv.reader(currentFile, delimiter=',', quotechar='\"')
        righe = list(reader)

        # estrae la riga con le unità misurate
        measured = righe.pop(4)
        # rinomina la prima colonna in 'data'
        measured[0] = "data"
        # inserisce la nuova riga di intestazione modificata
        righe.insert(8, measured)

        logger.debug("L'ordine delle righe di intestazione è stato modificato")

        (_, loadName) = findRowStart(righe, "load name")

        # in load name considero l'elemento 1 in quanto è il primo a contenere il nome del carico.
        # L'elemento 0 contiene la dicitura LoadName
        return righe, loadName[1]


def typeIndex(selectedFile: pathlib.Path) -> tuple[list[list[str]], str]:
    logger.debug("Il file viene gestito come tipo INDEX")
    
    # Usando utf-8-sig rimuove il BOM iniziale invisibile
    with open (selectedFile, mode='r', encoding='utf-8-sig') as currentFile:
        logger.debug("Apro il file '%s' in lettura", selectedFile.name)

        reader = csv.reader(currentFile, delimiter=',', quotechar='\"')
        righe = list(reader)

        # estrae la riga con le unità misurate
        measured = righe.pop(6)
        # rinomina la prima colonna in 'data'
        measured[0] = "data"
        # inserisce la nuova riga di intestazione modificata
        righe.insert(8, measured)

        logger.debug("L'ordine delle righe di intestazione è stato modificato")

        (_, loadName) = findRowStart(righe, "load name")

        # in load name considero l'elemento 1 in quanto è il primo a contenere il nome del carico.
        # L'elemento 0 contiene la dicitura LoadName
        return righe, loadName[1]


def writeFilesOnDisk(chunks: list, originalName: str, loadName: str, exportPath: pathlib.Path):
    logger.debug("Inizio scrittura di %d file", len(chunks))

    for idx, c in enumerate(chunks):
        newName = newFileName(getFilenameDictInfo(originalName), loadName, idx)
        newPath = exportPath.joinpath(newName).with_suffix(".csv")
        logger.debug("Il nuovo file sarà nominato '%s'", newPath.name)

        with open(newPath, mode='w', encoding='utf-8', newline='') as f:
            f.write(c.getvalue())

        logger.info("Scritto su disco il file '%s'", newPath.name)


if __name__ == "__main__":
    start = datetime.now()
    logger = newLogger("gallazzi-csv-converter")
    logger.info("Script avviato")
    try:
        load_dotenv()
        logger.debug("Trovato file '.env'")

        WEBVIEW_EXPORT_PATH = os.getenv("WEBVIEW_EXPORT_PATH")
        if not WEBVIEW_EXPORT_PATH:
            raise ValueError(f"La variabile {WEBVIEW_EXPORT_PATH} non e' impostata")
        
        WEBVIEW_EXPORT_PATH = pathlib.Path(WEBVIEW_EXPORT_PATH) 

        # legge la cartella di esportazione dei file.
        # se non è scritta nel file, considera la cartella di lettura e genera un sottocartella /export
        EXPORT_TEMP_DIR = os.getenv("EXPORT_TEMP_DIR", WEBVIEW_EXPORT_PATH / "export")
        EXPORT_TEMP_DIR = pathlib.Path(EXPORT_TEMP_DIR)
        EXPORT_TEMP_DIR.mkdir(parents=True, exist_ok=True)
            
        EXPORT_MAXROWS = int(os.getenv("EXPORT_MAXROWS", 300))

        # crea cartella in cui salvare temporaneamente i file
        #pathlib.Path.mkdir(EXPORT_TEMP_DIR / "export_temp", parents=True, exist_ok=True)
        logger.info("Variabili importate correttamente dal file '.env'")

        # lista dei file presenti nella cartella
        csvFileList = pathlib.Path(WEBVIEW_EXPORT_PATH).glob("*.csv", case_sensitive=False)
        # logger.info("Nella cartella '%s' sono presenti %d file", WEBVIEW_EXPORT_PATH.name, sum(1 for _ in csvFileList))

        for f in csvFileList:
            logger.debug("Considero il file '%s'", f.name)

            try:
                edited, loadName = workOnFile(f)
                logger.debug("%s", edited[:10] if edited else "File vuoto")
            except Exception as e:
                logger.exception(e)
                continue

            # il file può essere vuoto
            if not edited: continue

            fileChunks = splitLongFile(edited, EXPORT_MAXROWS)
            logger.info("Il file è stato diviso in %d parti", len(fileChunks))

            writeFilesOnDisk(fileChunks, f.stem, loadName, EXPORT_TEMP_DIR)
    
    except Exception as ex:
        logger.exception(ex)

    logger.info("Script terminato in %s", datetime.now()-start)