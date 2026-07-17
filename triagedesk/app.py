import uuid

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from triagedesk.console_queries import get_run_detail, list_runs
from triagedesk.db import get_db
from triagedesk.models import Ticket

app = FastAPI(title="TriageDesk")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)) -> dict:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "body": ticket.body,
        "queue": ticket.queue,
        "language": ticket.language,
        "source": ticket.source,
    }


@app.get("/api/runs")
def api_list_runs(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)) -> dict:
    return list_runs(db, limit=limit, offset=offset)


@app.get("/api/runs/{run_id}")
def api_get_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    detail = get_run_detail(db, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="run not found")
    return detail
