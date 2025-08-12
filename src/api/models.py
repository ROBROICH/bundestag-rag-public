from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from pydantic import BaseModel, Field


class Fundstelle(BaseModel):
    """Document reference information"""
    pdf_url: Optional[str] = None
    seite: Optional[str] = None
    anfangsseite: Optional[str] = None
    endseite: Optional[str] = None
    anfangsquadrant: Optional[str] = None
    endquadrant: Optional[str] = None
    id: Optional[str] = None
    dokumentnummer: Optional[str] = None
    datum: Optional[str] = None
    dokumentart: Optional[str] = None
    drucksachetyp: Optional[str] = None
    herausgeber: Optional[str] = None
    urheber: Optional[List[str]] = None
    
    class Config:
        extra = "allow"


class Urheber(BaseModel):
    """Document author/originator"""
    einbringer: Optional[Union[str, bool, List[str]]] = None
    rolle: Optional[str] = None
    bezeichnung: Optional[str] = None
    titel: Optional[str] = None
    
    class Config:
        extra = "allow"


class Ressort(BaseModel):
    """Ministry/Department information"""
    federfuehrend: Optional[Union[str, bool, List[str]]] = None
    beteiligt: Optional[List[str]] = None
    
    class Config:
        extra = "allow"


class Verkuendung(BaseModel):
    """Publication information"""
    fundstelle: Optional[str] = None
    verkuendungsblatt: Optional[str] = None
    
    class Config:
        extra = "allow"


class VorgangDeskriptor(BaseModel):
    """Procedure descriptor"""
    name: str
    notation: Optional[str] = None
    
    class Config:
        extra = "allow"


class Vorgang(BaseModel):
    """Parliamentary procedure"""
    id: str
    typ: str = "Vorgang"
    beratungsstand: Optional[str] = None
    vorgangstyp: str
    wahlperiode: int
    initiative: Optional[List[str]] = None
    datum: Optional[str] = None
    aktualisiert: str
    titel: str
    abstract: Optional[str] = None
    sachgebiet: Optional[List[str]] = None
    deskriptor: Optional[List[VorgangDeskriptor]] = None
    gesta: Optional[str] = None
    verkuendung: Optional[List[Verkuendung]] = None
    
    class Config:
        extra = "allow"


class VorgangsBezug(BaseModel):
    """Procedure reference"""
    id: str
    titel: str
    vorgangstyp: str
    
    class Config:
        extra = "allow"


class AutorAnzeige(BaseModel):
    """Author display information"""
    id: str
    titel: str
    autor_titel: str
    
    class Config:
        extra = "allow"


class Drucksache(BaseModel):
    """Parliamentary document"""
    id: str
    typ: str = "Dokument"
    dokumentart: str = "Drucksache"
    drucksachetyp: str
    dokumentnummer: str
    wahlperiode: int
    herausgeber: str
    datum: str
    aktualisiert: str
    titel: str
    fundstelle: Optional[Fundstelle] = None
    pdf_hash: Optional[str] = None
    urheber: Optional[List[Urheber]] = None
    ressort: Optional[List[Ressort]] = None
    autoren_anzahl: Optional[int] = None
    autoren_anzeige: Optional[List[AutorAnzeige]] = None
    vorgangsbezug_anzahl: Optional[int] = None
    vorgangsbezug: Optional[List[VorgangsBezug]] = None
    
    class Config:
        extra = "allow"  # Allow additional fields from API


class Plenarprotokoll(BaseModel):
    """Plenary protocol"""
    id: str
    typ: str = "Dokument"
    dokumentart: str = "Plenarprotokoll"
    dokumentnummer: str
    wahlperiode: int
    herausgeber: str
    datum: str
    aktualisiert: str
    titel: str
    fundstelle: Optional[Fundstelle] = None
    
    class Config:
        extra = "allow"


class Person(BaseModel):
    """Person master data"""
    id: str
    vorname: Optional[str] = None
    nachname: Optional[str] = None
    ortszusatz: Optional[str] = None
    adel: Optional[str] = None
    aktualisiert: str
    
    class Config:
        extra = "allow"


class Aktivitaet(BaseModel):
    """Activity"""
    id: str
    titel: Optional[str] = None
    datum: Optional[str] = None
    aktualisiert: str
    
    class Config:
        extra = "allow"


class ListResponse(BaseModel):
    """Base response for list endpoints"""
    numFound: int
    cursor: str
    documents: List[Dict[str, Any]]


class VorgangListResponse(ListResponse):
    documents: List[Vorgang]


class DrucksacheListResponse(ListResponse):
    documents: List[Drucksache]


class PlenarprotokollListResponse(ListResponse):
    documents: List[Plenarprotokoll]


class PersonListResponse(ListResponse):
    documents: List[Person]


class AktivitaetListResponse(ListResponse):
    documents: List[Aktivitaet]


class APIError(BaseModel):
    """API error response"""
    code: int
    message: str
