from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional

import sqlalchemy as sa
import streamlit as st
from sqlalchemy import Boolean, Column, Date, Integer, MetaData, String, Table
from streamlit.connections import SQLConnection

st.set_page_config(
    page_title="Todo App",
    page_icon="📃",
    initial_sidebar_state="collapsed",
)

# === Переводы ===

translations = {
    "English": {
        "title": "📌 To-Do List",
        "new_todo": "New todo",
        "add_todo": "Add",
        "description": "Description",
        "due_date": "Due date",
        "title_label": "Title",
        "save": "Save",
        "cancel": "Cancel",
        "done": "Done",
        "redo": "Redo",
        "edit": "Edit",
        "delete": "Delete",
        "no_description": "*No description*",
        "due_prefix": "Due",
        "table_warning": "Create table from admin sidebar",
        "admin": "Admin",
        "create_table": "Create table",
        "table_created": "Todo table created successfully!",
        "session_state_debug": "Session State Debug",
        "new_task_subheader": "📌 New todo",
        "settings": "Settings",
        "language_label": "Language",
    },
    "Русский": {
        "title": "📌 Список дел",
        "new_todo": "Новая задача",
        "add_todo": "Добавить",
        "description": "Описание",
        "due_date": "Срок",
        "title_label": "Заголовок",
        "save": "Сохранить",
        "cancel": "Отмена",
        "done": "Выполнено",
        "redo": "Вернуть",
        "edit": "Редактировать",
        "delete": "Удалить",
        "no_description": "*Нет описания*",
        "due_prefix": "Срок",
        "table_warning": "Создайте таблицу через админ-панель",
        "admin": "Админ",
        "create_table": "Создать таблицу",
        "table_created": "Таблица успешно создана!",
        "session_state_debug": "Отладка состояния сессии",
        "new_task_subheader": "📌 Новая задача",
        "settings": "Настройки",
        "language_label": "Язык",
    }
}

def t(key: str) -> str:
    lang = st.session_state.get("lang_selector", "English")
    return translations.get(lang, translations["English"]).get(key, key)

# === Модель и БД ===

TABLE_NAME = "todo"
SESSION_STATE_KEY_TODOS = "todos_data"

@dataclass
class Todo:
    id: Optional[int] = None
    title: str = ""
    description: Optional[str] = None
    created_at: Optional[date] = None
    due_at: Optional[date] = None
    done: bool = False

    @classmethod
    def from_row(cls, row):
        return cls(**row._mapping) if row else None

@st.cache_resource
def connect_table():
    metadata_obj = MetaData()
    todo_table = Table(
        TABLE_NAME, metadata_obj,
        Column("id", Integer, primary_key=True),
        Column("title", String(30)),
        Column("description", String, nullable=True),
        Column("created_at", Date),
        Column("due_at", Date, nullable=True),
        Column("done", Boolean, nullable=True),
    )
    return metadata_obj, todo_table

# === Работа с БД ===

def check_table_exists(connection: SQLConnection, table_name: str) -> bool:
    inspector = sa.inspect(connection.engine)
    return inspector.has_table(table_name)

def load_all_todos(connection: SQLConnection, table: Table) -> Dict[int, Todo]:
    stmt = sa.select(table).order_by(table.c.id)
    with connection.session as session:
        return {todo.id: todo for todo in [Todo.from_row(r) for r in session.execute(stmt).all()] if todo}

def load_todo(connection: SQLConnection, table: Table, todo_id: int) -> Optional[Todo]:
    stmt = sa.select(table).where(table.c.id == todo_id)
    with connection.session as session:
        return Todo.from_row(session.execute(stmt).first())

# === Коллбэки ===

def create_todo_callback(connection: SQLConnection, table: Table):
    if not st.session_state.new_todo_form__title:
        st.toast("Title empty, not adding todo")
        return
    new_todo = {
        "title": st.session_state.new_todo_form__title,
        "description": st.session_state.new_todo_form__description,
        "created_at": date.today(),
        "due_at": st.session_state.new_todo_form__due_date,
        "done": False,
    }
    stmt = table.insert().values(**new_todo)
    with connection.session as session:
        session.execute(stmt)
        session.commit()
    st.session_state[SESSION_STATE_KEY_TODOS] = load_all_todos(connection, table)

def update_todo_callback(connection: SQLConnection, table: Table, todo_id: int):
    values = {
        "title": st.session_state[f"edit_todo_form_{todo_id}__title"],
        "description": st.session_state[f"edit_todo_form_{todo_id}__description"],
        "due_at": st.session_state[f"edit_todo_form_{todo_id}__due_date"],
    }
    if not values["title"]:
        st.toast("Title cannot be empty", icon="⚠️")
        st.session_state[f"currently_editing__{todo_id}"] = True
        return
    stmt = table.update().where(table.c.id == todo_id).values(**values)
    with connection.session as session:
        session.execute(stmt)
        session.commit()
    st.session_state[SESSION_STATE_KEY_TODOS][todo_id] = load_todo(connection, table, todo_id)
    st.session_state[f"currently_editing__{todo_id}"] = False

def delete_todo_callback(connection: SQLConnection, table: Table, todo_id: int):
    stmt = table.delete().where(table.c.id == todo_id)
    with connection.session as session:
        session.execute(stmt)
        session.commit()
    st.session_state[SESSION_STATE_KEY_TODOS] = load_all_todos(connection, table)
    st.session_state[f"currently_editing__{todo_id}"] = False

def mark_done_callback(connection: SQLConnection, table: Table, todo_id: int):
    current = st.session_state[SESSION_STATE_KEY_TODOS][todo_id].done
    stmt = table.update().where(table.c.id == todo_id).values(done=not current)
    with connection.session as session:
        session.execute(stmt)
        session.commit()
    st.session_state[SESSION_STATE_KEY_TODOS][todo_id] = load_todo(connection, table, todo_id)

# === Интерфейсные компоненты ===

def todo_card(connection: SQLConnection, table: Table, todo: Todo):
    todo_id = todo.id
    with st.container(border=True):
        title = f"~~{todo.title}~~" if todo.done else todo.title
        desc = f"~~{todo.description or t('no_description')}~~" if todo.done else todo.description or t('no_description')
        due = f"~~{t('due_prefix')} {todo.due_at.strftime('%Y-%m-%d')}~~" if todo.done else f"{t('due_prefix')} {todo.due_at.strftime('%Y-%m-%d')}"
        st.subheader(title)
        st.markdown(desc)
        st.markdown(f":grey[{due}]")
        done_col, edit_col, del_col = st.columns(3)
        done_col.button(
            t("done") if not todo.done else t("redo"),
            icon=":material/check_circle:",
            key=f"display_todo_{todo_id}__done",
            on_click=mark_done_callback,
            args=(connection, table, todo_id),
            use_container_width=True,
        )
        edit_col.button(
            t("edit"),
            icon=":material/edit:",
            key=f"display_todo_{todo_id}__edit",
            on_click=lambda: st.session_state.update({f"currently_editing__{todo_id}": True}),
            disabled=todo.done,
            use_container_width=True,
        )
        if del_col.button(t("delete"), icon=":material/delete:", key=f"display_todo_{todo_id}__delete", use_container_width=True):
            delete_todo_callback(connection, table, todo_id)
            st.rerun(scope="app")

def todo_edit_widget(connection: SQLConnection, table: Table, todo: Todo):
    todo_id = todo.id
    with st.form(f"edit_todo_form_{todo_id}"):
        st.text_input(t("title_label"), value=todo.title, key=f"edit_todo_form_{todo_id}__title")
        st.text_area(t("description"), value=todo.description, key=f"edit_todo_form_{todo_id}__description")
        st.date_input(t("due_date"), value=todo.due_at, key=f"edit_todo_form_{todo_id}__due_date")
        col1, col2 = st.columns(2)
        col1.form_submit_button(t("save"), on_click=update_todo_callback, args=(connection, table, todo_id), use_container_width=True)
        col2.form_submit_button(t("cancel"), on_click=lambda: st.session_state.update({f"currently_editing__{todo_id}": False}), use_container_width=True)

@st.fragment
def todo_component(connection: SQLConnection, table: Table, todo_id: int):
    todo = st.session_state[SESSION_STATE_KEY_TODOS][todo_id]
    if not st.session_state.get(f"currently_editing__{todo_id}", False):
        todo_card(connection, table, todo)
    else:
        todo_edit_widget(connection, table, todo)

# === UI ===

with st.sidebar:
    st.header(t("settings"))
    lang = st.radio(t("language_label"), ["English", "Русский"], key="lang_selector", horizontal=True)
    st.divider()
    st.subheader(t("admin"))
    conn = st.connection("todo_db", ttl=5 * 60)
    metadata_obj, todo_table = connect_table()
    if st.button(t("create_table"), type="secondary"):
        metadata_obj.create_all(conn.engine)
        st.toast(t("table_created"), icon="✅")
    st.divider()
    st.subheader(t("session_state_debug"))
    st.json(st.session_state)

st.title(t("title"))

if not check_table_exists(conn, TABLE_NAME):
    st.warning(t("table_warning"), icon="⚠")
    st.stop()

if SESSION_STATE_KEY_TODOS not in st.session_state:
    with st.spinner("Loading Todos..."):
        st.session_state[SESSION_STATE_KEY_TODOS] = load_all_todos(conn, todo_table)

for todo_id in st.session_state[SESSION_STATE_KEY_TODOS]:
    if f"currently_editing__{todo_id}" not in st.session_state:
        st.session_state[f"currently_editing__{todo_id}"] = False
    todo_component(conn, todo_table, todo_id)

with st.form("new_todo_form", clear_on_submit=True):
    st.subheader(t("new_todo"))
    st.text_input(t("title_label"), key="new_todo_form__title")
    st.text_area(t("description"), key="new_todo_form__description")
    date_col, submit_col = st.columns((1, 2))
    date_col.date_input(t("due_date"), key="new_todo_form__due_date")
    submit_col.form_submit_button(t("add_todo"), on_click=create_todo_callback, args=(conn, todo_table), use_container_width=True)
