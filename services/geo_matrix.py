"""
Geographical & Sector Matrix Hierarchy for Italian Commercial Lead Generation.
Structure: Region -> Province -> City -> Sector -> Keyword
"""

from typing import List, Dict, Generator, Tuple

SECTORS: Dict[str, List[str]] = {
    "Ristorazione": ["ristorante", "pizzeria", "trattoria"],
    "Studi Professionali": ["studio legale avvocato", "dentista", "notaio"],
    "Centri e Servizi": ["centro estetico", "parrucchiere", "galleria d'arte"],
    "Hospitality": ["hotel", "bed and breakfast", "albergo"]
}

ITALY_GEO_TREE: Dict[str, Dict[str, List[str]]] = {
    "Lombardia": {
        "Milano": ["Milano", "Sesto San Giovanni", "Cinisello Balsamo", "Legnano", "Rho"],
        "Monza e Brianza": ["Monza", "Seregno", "Lissone", "Desio"],
        "Bergamo": ["Bergamo", "Treviglio", "Seriate"],
        "Brescia": ["Brescia", "Desenzano del Garda", "Montichiari"],
        "Como": ["Como", "Cantù", "Erba"],
        "Varese": ["Varese", "Busto Arsizio", "Gallarate"],
        "Pavia": ["Pavia", "Vigevano", "Voghera"],
        "Cremona": ["Cremona", "Crema"],
        "Lecco": ["Lecco", "Merate"],
        "Lodi": ["Lodi", "Codogno"],
        "Mantova": ["Mantova", "Castiglione delle Stiviere"],
        "Sondrio": ["Sondrio", "Morbegno"]
    },
    "Lazio": {
        "Roma": ["Roma", "Guidonia Montecelio", "Fiumicino", "Tivoli"],
        "Latina": ["Latina", "Aprilia", "Terracina"],
        "Frosinone": ["Frosinone", "Cassino"]
    },
    "Veneto": {
        "Venezia": ["Venezia", "Mestre", "Chioggia"],
        "Verona": ["Verona", "Villafranca di Verona"],
        "Padova": ["Padova", "Vigonza"]
    },
    "Piemonte": {
        "Torino": ["Torino", "Moncalieri", "Collegno"],
        "Novara": ["Novara", "Trecate"],
        "Alessandria": ["Alessandria", "Casale Monferrato"]
    },
    "Emilia-Romagna": {
        "Bologna": ["Bologna", "Imola", "Casalecchio di Reno"],
        "Modena": ["Modena", "Carpi", "Sassuolo"],
        "Parma": ["Parma", "Fidenza"]
    }
}

def get_all_search_targets() -> List[Tuple[str, str, str, str, str]]:
    """Generates full flat list of target tuples."""
    targets = []
    for region, provinces in ITALY_GEO_TREE.items():
        for province, cities in provinces.items():
            for city in cities:
                for sector, keywords in SECTORS.items():
                    for keyword in keywords:
                        targets.append((region, province, city, sector, keyword))
    return targets

def generate_search_targets(offset: int = 0) -> Generator[Tuple[str, str, str, str, str], None, None]:
    """
    Generates an ordered stream of search tasks starting from given offset.
    Yields tuple: (Region, Province, City, Sector, Keyword)
    """
    targets = get_all_search_targets()
    total = len(targets)
    if total == 0:
        return
    start = offset % total
    for i in range(total):
        yield targets[(start + i) % total]
