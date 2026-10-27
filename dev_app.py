import customtkinter as ctk

from database.database import Database
from views.main_window import MainWindow
from utils.theme import apply_theme


def main():
    apply_theme()

    db = Database()
    db.initialize()

    fake_user = {
        "id": 1,
        "username": "admin",
    }

    app = MainWindow(
        user=fake_user,
        db=db,
    )

    app.show_page("dashboard")

    app.mainloop()


if __name__ == "__main__":
    main()