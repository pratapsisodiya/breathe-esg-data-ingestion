# parsers package
from . import sap, utility, concur

PARSER_MAP = {
    "SAP_FUEL": sap.parse,
    "UTILITY": utility.parse,
    "CONCUR": concur.parse,
}
