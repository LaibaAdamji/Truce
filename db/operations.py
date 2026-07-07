from db.client import supabase
from models.schemas import Project


#basic get methods

def save_project(name: str) -> dict:
    project = Project(name=name)
    data = project.model_dump(mode="json")
    response = supabase.table("projects").insert(data).execute()
    return response.data


def get_projects() -> list[dict]:
    response = supabase.table("projects").select("*").execute()
    return response.data