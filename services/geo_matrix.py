"""
Geographical & Sector Matrix Hierarchy for Italian Commercial Lead Generation.
Structure: Region -> Province -> City -> Sector -> Keyword
"""

from typing import List, Dict, Generator, Tuple

SECTORS: Dict[str, List[str]] = {
    "Ristorazione": [
        "ristorante", "pizzeria", "trattoria", "osteria", 
        "pizzeria d'asporto", "pizzeria al taglio", "pub e birreria", 
        "bistrot", "sushi e poké", "tavola calda"
    ],
    "Studi Professionali": [
        "studio legale avvocato", "avvocato penalista", "avvocato civilista", 
        "dentista", "studio dentistico", "notaio", "studio commercialista"
    ],
    "Centri e Servizi": [
        "centro estetico", "parrucchiere", "salone barbiere", 
        "spa centro benessere", "galleria d'arte"
    ],
    "Hospitality": [
        "hotel", "bed and breakfast", "albergo", "affittacamere", "agriturismo"
    ],
    "Boutique e Retail": [
        "boutique", "negozio abbigliamento", "negozio scarpe e calzature", 
        "negozio streetwear", "boutique moda", "negozio accessori moda", 
        "negozio borse e pelletteria", "gioielleria", "ottica"
    ],
    "Automotive": [
        "officina meccanica", "gommista", "concessionaria auto", 
        "concessionario moto", "carrozzeria", "elettrauto", 
        "autolavaggio", "centro revisioni"
    ],
    "Fitness e Sport": [
        "palestra e centro fitness", "personal trainer", 
        "studio pilates e yoga", "box crossfit", "centro sportivo", 
        "scuola arti marziali", "padel club", "centro danza"
    ],
    "Veterinaria e Pet Care": [
        "clinica veterinaria", "ambulatorio veterinario", 
        "toelettatura animali", "pet shop negozio animali", 
        "ospedale veterinario", "pensione per cani e gatti"
    ]
}

ITALY_GEO_TREE: Dict[str, Dict[str, List[str]]] = {
    "Lombardia": {
        "Milano": ["Milano", "Milano Navigli", "Milano Brera", "Milano Isola", "Milano Porta Romana", "Milano Baggio", "Sesto San Giovanni", "Cinisello Balsamo", "Legnano", "Rho"],
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
        "Roma": ["Roma", "Roma Trastevere", "Roma Prati", "Roma EUR", "Roma Parioli", "Roma San Lorenzo", "Guidonia Montecelio", "Fiumicino", "Tivoli", "Pomezia"],
        "Latina": ["Latina", "Aprilia", "Terracina", "Formia"],
        "Frosinone": ["Frosinone", "Cassino", "Alatri"],
        "Viterbo": ["Viterbo", "Civitavecchia"],
        "Rieti": ["Rieti"]
    },
    "Veneto": {
        "Venezia": ["Venezia", "Mestre", "Chioggia", "San Donà di Piave"],
        "Verona": ["Verona", "Villafranca di Verona", "Legnago"],
        "Padova": ["Padova", "Vigonza", "Selvazzano Dentro"],
        "Vicenza": ["Vicenza", "Bassano del Grappa", "Schio"],
        "Treviso": ["Treviso", "Conegliano", "Castelfranco Veneto"],
        "Rovigo": ["Rovigo", "Adria"],
        "Belluno": ["Belluno", "Feltre"]
    },
    "Piemonte": {
        "Torino": ["Torino", "Torino Crocetta", "Torino San Salvario", "Torino Vanchiglia", "Moncalieri", "Collegno", "Rivoli", "Nichelino"],
        "Novara": ["Novara", "Trecate"],
        "Alessandria": ["Alessandria", "Casale Monferrato", "Novi Ligure"],
        "Cuneo": ["Cuneo", "Alba", "Bra"],
        "Asti": ["Asti"],
        "Biella": ["Biella"],
        "Vercelli": ["Vercelli"]
    },
    "Emilia-Romagna": {
        "Bologna": ["Bologna", "Bologna Saragozza", "Bologna Bolognina", "Imola", "Casalecchio di Reno", "San Lazzaro di Savena"],
        "Modena": ["Modena", "Carpi", "Sassuolo", "Formigine"],
        "Parma": ["Parma", "Fidenza"],
        "Reggio Emilia": ["Reggio Emilia", "Correggio", "Scandiano"],
        "Ravenna": ["Ravenna", "Faenza", "Lugo"],
        "Forlì-Cesena": ["Forlì", "Cesena"],
        "Rimini": ["Rimini", "Riccione"],
        "Ferrara": ["Ferrara", "Cento"],
        "Piacenza": ["Piacenza"]
    },
    "Toscana": {
        "Firenze": ["Firenze", "Scandicci", "Sesto Fiorentino", "Empoli"],
        "Prato": ["Prato"],
        "Livorno": ["Livorno", "Piombino"],
        "Arezzo": ["Arezzo"],
        "Pistoia": ["Pistoia", "Montecatini Terme"],
        "Pisa": ["Pisa", "Cascina"],
        "Lucca": ["Lucca", "Viareggio"],
        "Grosseto": ["Grosseto"],
        "Massa-Carrara": ["Massa", "Carrara"],
        "Siena": ["Siena"]
    },
    "Campania": {
        "Napoli": ["Napoli", "Giugliano in Campania", "Torre del Greco", "Pozzuoli", "Casoria"],
        "Salerno": ["Salerno", "Cava de' Tirreni", "Battipaglia"],
        "Caserta": ["Caserta", "Aversa", "Marcianise"],
        "Avellino": ["Avellino"],
        "Benevento": ["Benevento"]
    },
    "Sicilia": {
        "Palermo": ["Palermo", "Bagheria", "Monreale"],
        "Catania": ["Catania", "Acireale", "Misterbianco"],
        "Messina": ["Messina", "Barcellona Pozzo di Gotto"],
        "Agrigento": ["Agrigento", "Sciacca"],
        "Trapani": ["Trapani", "Marsala"],
        "Siracusa": ["Siracusa"],
        "Ragusa": ["Ragusa", "Modica"],
        "Caltanissetta": ["Caltanissetta"],
        "Enna": ["Enna"]
    },
    "Puglia": {
        "Bari": ["Bari", "Altamura", "Molfetta", "Bitonto"],
        "Taranto": ["Taranto", "Martina Franca"],
        "Foggia": ["Foggia", "Cerignola", "Manfredonia"],
        "Lecce": ["Lecce", "Nardò"],
        "Barletta-Andria-Trani": ["Andria", "Barletta", "Trani"],
        "Brindisi": ["Brindisi"]
    },
    "Liguria": {
        "Genova": ["Genova", "Rapallo", "Chiavari"],
        "La Spezia": ["La Spezia", "Sarzana"],
        "Savona": ["Savona", "Albenga"],
        "Imperia": ["Imperia", "Sanremo"]
    },
    "Marche": {
        "Ancona": ["Ancona", "Senigallia", "Jesi"],
        "Pesaro e Urbino": ["Pesaro", "Fano", "Urbino"],
        "Macerata": ["Macerata", "Civitanova Marche"],
        "Ascoli Piceno": ["Ascoli Piceno", "San Benedetto del Tronto"],
        "Fermo": ["Fermo"]
    },
    "Abruzzo": {
        "Pescara": ["Pescara", "Montesilvano"],
        "L'Aquila": ["L'Aquila", "Avezzano"],
        "Chieti": ["Chieti", "Vasto"],
        "Teramo": ["Teramo"]
    },
    "Friuli-Venezia Giulia": {
        "Trieste": ["Trieste"],
        "Udine": ["Udine"],
        "Pordenone": ["Pordenone"],
        "Gorizia": ["Gorizia", "Monfalcone"]
    },
    "Trentino-Alto Adige": {
        "Trento": ["Trento", "Rovereto"],
        "Bolzano": ["Bolzano", "Merano"]
    },
    "Umbria": {
        "Perugia": ["Perugia", "Foligno", "Città di Castello"],
        "Terni": ["Terni"]
    },
    "Sardegna": {
        "Cagliari": ["Cagliari", "Quartu Sant'Elena"],
        "Sassari": ["Sassari", "Alghero"],
        "Nuoro": ["Nuoro"],
        "Oristano": ["Oristano"]
    },
    "Calabria": {
        "Reggio Calabria": ["Reggio Calabria"],
        "Catanzaro": ["Catanzaro", "Lamezia Terme"],
        "Cosenza": ["Cosenza", "Corigliano-Rossano"]
    },
    "Basilicata": {
        "Potenza": ["Potenza"],
        "Matera": ["Matera"]
    },
    "Molise": {
        "Campobasso": ["Campobasso", "Termoli"],
        "Isernia": ["Isernia"]
    },
    "Valle d'Aosta": {
        "Aosta": ["Aosta"]
    }
}

def get_all_cities() -> List[Tuple[str, str, str]]:
    """Returns flat list of all (Region, Province, City) tuples across Italy."""
    cities = []
    for region, provinces in ITALY_GEO_TREE.items():
        for province, city_list in provinces.items():
            for city in city_list:
                cities.append((region, province, city))
    return cities

def get_all_search_targets() -> List[Tuple[str, str, str, str, str]]:
    """
    Generates structured targets for total counting and index tracking:
    For each city, alternates across all 8 sectors (CYCLES_PER_CITY times).
    """
    from config import settings
    cities = get_all_cities()
    sector_names = list(SECTORS.keys())
    cycles = max(1, getattr(settings, "CYCLES_PER_CITY", 1))

    targets = []
    for region, province, city in cities:
        for _ in range(cycles):
            for sector in sector_names:
                targets.append((region, province, city, sector, SECTORS[sector][0]))
    return targets

def generate_search_targets(offset: int = 0) -> Generator[Tuple[str, str, str, str, str], None, None]:
    """
    Generates an alternating stream of search tasks starting from given offset.
    Sequence:
    For a given city:
      Sector 1 (random keyword) -> Sector 2 (random keyword) -> ... -> Sector 8 (random keyword)
    Then advances to the next city.
    Once all Italian cities are covered, loops back to the start (Milano) picking fresh random keywords!
    """
    import random
    from config import settings

    cities = get_all_cities()
    sector_names = list(SECTORS.keys())
    total_cities = len(cities)
    total_sectors = len(sector_names)
    cycles = max(1, getattr(settings, "CYCLES_PER_CITY", 1))

    total_steps = total_cities * total_sectors * cycles
    if total_steps == 0:
        return

    start = offset % total_steps
    for i in range(total_steps):
        current_step = (start + i) % total_steps
        
        # Step layout: each city gets (total_sectors * cycles) consecutive steps
        steps_per_city = total_sectors * cycles
        city_idx = (current_step // steps_per_city) % total_cities
        sector_idx = current_step % total_sectors
        
        region, province, city = cities[city_idx]
        sector = sector_names[sector_idx]
        
        # Pick a random keyword from this sector to ensure diverse search discovery
        available_keywords = SECTORS.get(sector, ["attività"])
        keyword = random.choice(available_keywords)
        
        yield (region, province, city, sector, keyword)
