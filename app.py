import streamlit as st
from db.operations import save_project, get_projects

st.title("Initial Scaffolding Test")

name = st.text_input("Project name")

if st.button("Save Project"):
    if name.strip():
        save_project(name)
        st.success(f"Saved: {name}")
    else:
        st.warning("Enter a name first")

st.subheader("All Projects")
projects = get_projects()
st.table(projects)