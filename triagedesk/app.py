from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

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
