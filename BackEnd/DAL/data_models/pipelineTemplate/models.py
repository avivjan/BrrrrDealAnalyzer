from sqlalchemy import Column, String, DateTime, JSON, func

from db import Base


class PipelineTemplate(Base):
    """Persisted bought-deal pipeline template, one row per deal type.

    `stages` is a JSON array shaped like:
        [
          {"id": "purchase", "name": "Purchase",
           "subStages": [{"id": "purchase_agreement", "label": "Purchase Agreement"}, ...]},
          ...
        ]

    IDs are stable string identifiers. Labels/names are display-only and may
    change freely without impacting existing deals (whose `bought_stage` and
    `completed_substages` keys reference IDs, not labels).
    """

    __tablename__ = "pipeline_templates"

    deal_type = Column(String, primary_key=True)  # "BRRRR" | "FLIP"
    stages = Column(JSON, nullable=False, default=list)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
