"""Optional standalone FastAPI service."""

from fastapi import FastAPI
from pydantic import BaseModel

from site_proforma.proforma import calculate
from site_proforma.schemas import FinancialModel, Massing, SiteData
from site_proforma.site import lookup

app = FastAPI(title="site-proforma", version="0.0.1")


@app.get("/site/{parcel_id}", response_model=SiteData)
def site_endpoint(parcel_id: str) -> SiteData:
    return lookup(parcel_id)


class ProformaRequest(BaseModel):
    massing: Massing
    site: SiteData


@app.post("/proforma", response_model=FinancialModel)
def proforma_endpoint(req: ProformaRequest) -> FinancialModel:
    return calculate(req.massing, req.site)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
